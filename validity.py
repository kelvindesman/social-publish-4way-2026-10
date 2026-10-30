"""Do the gates measure what matters? Exploratory (logged under PREREGISTRATION.md "Deviations").

  python3 -I validity.py  -> out/validity.json

For each reference judgment that exists:
  human    panel "fine to post as-is", majority of raters who saw the output (out/panel-asis.json)
  editor   one coder's would-publish call from error-analysis.md (out/error-codes.jsonl)
reports, per arm:
  - how often the gates agree with it (2x2: gate publishable vs reference yes)
  - gate precision (of gate-passed outputs, share the reference would publish) and recall
  - the LLM text judge's Spearman against it
  - $ per reference-publishable post = mean $ per clean run / reference-publishable rate,
    with a 95% CI resampling source posts. This is the headline the article leads with.
Rates use only outputs the reference judged; "of" says how many.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # -I drops the script dir from sys.path
from analyze import OUT, build_rows, cluster_boot  # noqa: E402
from panel import spearman  # noqa: E402


def references() -> dict[str, dict[str, int]]:
	refs = {}
	p = OUT / "panel-asis.json"
	if p.exists():
		refs["human"] = {k: int(v["yes"] * 2 > v["of"]) for k, v in json.loads(p.read_text()).items() if v["of"]}
	p = OUT / "error-codes.jsonl"
	if p.exists():
		ed = {}
		for line in p.read_text().splitlines():
			if line.strip():
				e = json.loads(line)
				ed[e["run_id"]] = int(bool(e.get("would_publish")))
		refs["editor"] = ed
	return refs


def block(rows: list[dict], all_rows: list[dict]) -> dict:
	n = len(rows)
	tp = sum(r["publishable"] and r["ref"] for r in rows)
	fp = sum(r["publishable"] and not r["ref"] for r in rows)
	fn = sum((not r["publishable"]) and r["ref"] for r in rows)
	tn = n - tp - fp - fn
	ref_rate = (tp + fn) / n if n else None
	usd_run = sum(r["usd"] for r in all_rows) / len(all_rows) if all_rows else None
	judged = [r for r in rows if r["text_quality"] is not None]

	def usd_per_ref(rs):
		k = sum(r["ref"] for r in rs)
		return (sum(r["usd"] for r in rs) / len(rs)) / (k / len(rs)) if k else None

	return {
		"of": n,
		"reference_publishable_rate": round(ref_rate, 4) if ref_rate is not None else None,
		"reference_publishable_ci": cluster_boot(rows, lambda rs: sum(r["ref"] for r in rs) / len(rs) if rs else None),
		"gate_vs_reference": {"both_yes": tp, "gate_only": fp, "reference_only": fn, "both_no": tn},
		"gate_agreement": round((tp + tn) / n, 4) if n else None,
		"gate_precision": round(tp / (tp + fp), 4) if tp + fp else None,
		"gate_recall": round(tp / (tp + fn), 4) if tp + fn else None,
		"judge_spearman": spearman([r["text_quality"] for r in judged], [float(r["ref"]) for r in judged]),
		"usd_per_reference_publishable_post": round(usd_run / ref_rate, 6) if usd_run is not None and ref_rate else None,
		"usd_per_reference_publishable_ci": cluster_boot(rows, usd_per_ref),
	}


def main() -> None:
	clean = [r for r in build_rows() if r["fault"] == "none" and r["run_id"].startswith("r")]
	out = {}
	for name, ref in references().items():
		rows = [{**r, "ref": ref[r["run_id"]]} for r in clean if r["run_id"] in ref]
		res = {"all": block(rows, clean)}
		for arm in sorted({r["arm"] for r in clean}):
			res[arm] = block([r for r in rows if r["arm"] == arm], [r for r in clean if r["arm"] == arm])
			for m in sorted({r["model"] for r in clean if r["arm"] == arm}):
				sel = lambda r: r["arm"] == arm and r["model"] == m
				res[f"{arm}|{m.rsplit('/', 1)[-1]}"] = block([r for r in rows if sel(r)], [r for r in clean if sel(r)])
		out[name] = res
	(OUT / "validity.json").write_text(json.dumps(out, indent=1))
	for name, res in out.items():
		for k, v in res.items():
			print(f"{name:7} {k:45} of={v['of']:3} ref={v['reference_publishable_rate']} prec={v['gate_precision']} rec={v['gate_recall']} $/ref-pub={v['usd_per_reference_publishable_post']}")
	if not out:
		print("no reference judgments yet (run the error analysis or the panel first)")


if __name__ == "__main__":
	main()
