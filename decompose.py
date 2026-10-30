"""Model vs architecture: how much of each outcome's variance is the model, the arm, their
interaction and the source post? Exploratory (logged under PREREGISTRATION.md "Deviations").

  python3 -I decompose.py  -> out/decompose.json

The pre-registered H5 used main effects only (analyze.eta_squared). That misses the
interaction, which is where A4 lives: 0% publishable on llama-4-scout, 93% on deepseek.
Here: LLM arms only (A1 has no model), clean counted runs. The design is balanced (6 reps x
5 sources per arm x model cell), so sequential sums of squares equal the orthogonal split:
  source, arm, model, arm x model, residual   (shares of the total sum of squares)
95% CIs resample source posts (10,000 draws), as analyze.py does.

Outcomes:
  publishable     gate verdict (0/1), every run
  text_quality    LLM judge mean (1-10); runs with no output have no score, so A4 on
                  llama-4-scout drops out and the interaction is understated
  would_publish   one coder's editor call from error-analysis.md (0/1), when present
  human_as_is     panel "fine to post as-is" share per output, when the panel has run
"""

from __future__ import annotations

import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # -I drops the script dir from sys.path
from analyze import OUT, build_rows, pct, rng  # noqa: E402

B = 10_000
TERMS = ("source", "arm", "model", "arm x model", "residual")


def ss_split(rows: list[dict], y: str) -> dict | None:
	rs = [r for r in rows if r.get(y) is not None]
	if len(rs) < 8:
		return None
	ys = [float(r[y]) for r in rs]
	grand = st.mean(ys)
	sst = sum((v - grand) ** 2 for v in ys)
	if not sst:
		return None

	def ss_of(key):
		g = defaultdict(list)
		for r in rs:
			g[key(r)].append(float(r[y]))
		return sum(len(v) * (st.mean(v) - grand) ** 2 for v in g.values())

	s_src = ss_of(lambda r: r["source"])
	s_arm = ss_of(lambda r: r["arm"])
	s_mod = ss_of(lambda r: r["model"])
	s_cell = ss_of(lambda r: (r["arm"], r["model"]))
	s_int = max(s_cell - s_arm - s_mod, 0.0)
	s_res = max(sst - s_src - s_cell, 0.0)
	return {
		"n": len(rs),
		"source": s_src / sst,
		"arm": s_arm / sst,
		"model": s_mod / sst,
		"arm x model": s_int / sst,
		"residual": s_res / sst,
	}


def boot(rows: list[dict], y: str) -> dict:
	by = defaultdict(list)
	for r in rows:
		by[r["source"]].append(r)
	ks = sorted(by)
	draws = defaultdict(list)
	for _ in range(B):
		sample = []
		for n, k in enumerate(rng.choices(ks, k=len(ks))):
			# Relabel each draw so a source drawn twice counts as two sources.
			sample += [{**r, "source": f"{k}#{n}"} for r in by[k]]
		s = ss_split(sample, y)
		if s:
			for t in TERMS:
				draws[t].append(s[t])
	return {t: (round(pct(v, 0.025), 4), round(pct(v, 0.975), 4)) for t, v in draws.items()}


def cell_means(rows: list[dict], y: str) -> dict:
	g = defaultdict(list)
	for r in rows:
		if r.get(y) is not None:
			g[f"{r['arm']}|{r['model'].rsplit('/', 1)[-1]}"].append(float(r[y]))
	return {k: {"n": len(v), "mean": round(st.mean(v), 4)} for k, v in sorted(g.items())}


def load_optional() -> tuple[dict, dict]:
	editor, human = {}, {}
	p = OUT / "error-codes.jsonl"
	if p.exists():
		for line in p.read_text().splitlines():
			if line.strip():
				e = json.loads(line)
				editor[e["run_id"]] = int(bool(e.get("would_publish")))
	p = OUT / "panel-asis.json"  # run_id -> {"yes": n, "of": n}, from panel_votes.py
	if p.exists():
		for rid, v in json.loads(p.read_text()).items():
			if v["of"]:
				human[rid] = v["yes"] / v["of"]
	return editor, human


def main() -> None:
	editor, human = load_optional()
	rows = [
		{**r, "would_publish": editor.get(r["run_id"]), "human_as_is": human.get(r["run_id"])}
		for r in build_rows()
		if r["fault"] == "none" and r["run_id"].startswith("r") and r["arm"] != "A1-cron"
	]
	out = {"design": "LLM arms (A2, A3, A4) x 2 models x 5 sources x 6 reps, clean counted runs", "outcomes": {}}
	for y in ("publishable", "text_quality", "would_publish", "human_as_is"):
		s = ss_split(rows, y)
		if not s:
			out["outcomes"][y] = {"status": "no data yet"}
			continue
		ci = boot(rows, y)
		out["outcomes"][y] = {
			"n": s["n"],
			"share": {t: round(s[t], 4) for t in TERMS},
			"share_ci": ci,
			"cell_means": cell_means(rows, y),
		}
	(OUT / "decompose.json").write_text(json.dumps(out, indent=1))
	print(json.dumps({y: v.get("share", v) for y, v in out["outcomes"].items()}, indent=1))


if __name__ == "__main__":
	main()
