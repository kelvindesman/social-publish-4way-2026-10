"""Export every number the public research page shows, plus its claims ledger.

  python3 -I export_article.py
  -> src/lib/research/social-publish-4way-2026-10.ts   (data module the page imports)
     scripts/research/social-publish-4way-2026-10/claims.json   (ledger for pnpm verify-claims /
                                                                  check:research-provenance)

Inputs: out/summary.json (analyze.py), out/validity.json, out/decompose.json,
out/sensitivity.json, out/error-codes.jsonl, out/probe-hermes-llama.jsonl, and when they
exist out/panel-summary.json, out/enforced-gates.jsonl and out/enforced-codes.jsonl. Nothing here is typed by hand:
re-run the scripts, then this, and the page follows.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # -I drops the script dir from sys.path
from analyze import CSV, OUT, build_rows  # noqa: E402

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
TS = ROOT / "src" / "lib" / "research" / "social-publish-4way-2026-10.ts"
LEDGER = HERE / "claims.json"
ARMS = ["A1-cron", "A2-cron-llm", "A3-langgraph", "A4-hermes"]
MODEL_SHORT = {"llama-4-scout-17b-16e-instruct": "llama-4-scout", "deepseek-v4-flash-0731": "deepseek-v4-flash"}


def jload(name: str):
	p = OUT / name
	return json.loads(p.read_text()) if p.exists() else None


def jl(name: str) -> list[dict]:
	p = OUT / name
	return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def pct(x: float | None, d: int = 0) -> float | None:
	return None if x is None else round(100 * x, d)


def main() -> None:
	summary, validity, decomp, sens = jload("summary.json"), jload("validity.json"), jload("decompose.json"), jload("sensitivity.json")
	panel, codes, codes_enf = jload("panel-summary.json"), jl("error-codes.jsonl"), jl("enforced-codes.jsonl")
	rows = [r for r in build_rows() if r["run_id"].startswith("r")]
	clean = [r for r in rows if r["fault"] == "none"]
	ed = validity["editor"]
	claims: list[dict] = []
	sha = hashlib.sha256(CSV.read_bytes()).hexdigest()

	def claim(cid: str, count: int, n: int, metric: str, pool: str, desc: str) -> str:
		v = f"{round(100 * count / n, 1)}%" if n else "n/a"  # 1 decimal: claims-ledger.ts rule 2
		claims.append({"claim_id": cid, "value": v, "description": desc, "numerator": {"metric": metric, "count": count, "n": n, "pool": pool}, "derived_by": "scripts/research/social-publish-4way-2026-10/export_article.py#main", "dataset_sha256": sha, "computed_at": date.today().isoformat()})
		return v

	# Facts-gate false positives ("$293k" read as a new number): pass rate with only those forgiven.
	gates = {g["run_id"]: g for g in jl("gates.jsonl")}
	k_fp = {c["run_id"] for c in codes if "facts_gate_k_abbrev_false_positive" in (c.get("flags") or [])}

	def corrected(r: dict) -> bool:
		g = gates.get(r["run_id"]) or {}
		return bool(r["publishable"]) or (r["run_id"] in k_fp and all(g.get(k) for k in ("schema", "lengths", "link", "slop")))

	arms = []
	for a in ARMS:
		rs = [r for r in clean if r["arm"] == a]
		n = len(rs)
		gate_yes = sum(r["publishable"] for r in rs)
		ed_yes = sum(1 for r in rs if r["editor_would_publish"] == 1)
		s, v = summary["clean"][a], ed[a]
		claim(f"{a}-gate-publishable", gate_yes, n, "gate_publishable", a, f"{a}: share of clean runs that pass every automated gate")
		claim(f"{a}-gate-corrected", sum(corrected(r) for r in rs), n, "gate_publishable_k_abbrev_forgiven", a, f"{a}: share of clean runs passing every gate once facts-gate false positives on k-abbreviations are forgiven")
		claim(f"{a}-editor-publishable", ed_yes, n, "editor_would_publish", a, f"{a}: share of clean runs an editor would publish as-is (one coder)")
		arms.append({
			"arm": a,
			"runs": n,
			"gatePublishable": {"count": gate_yes, "pct": pct(gate_yes / n), "ciPct": [pct(x) for x in s["publishable_rate_ci"]]},
			"gateCorrected": {"count": sum(corrected(r) for r in rs), "pct": pct(sum(corrected(r) for r in rs) / n)},
			"editorPublishable": {"count": ed_yes, "pct": pct(ed_yes / n), "ciPct": [pct(x) for x in v["reference_publishable_ci"]]},
			"usdPerGatePublishable": s["usd_per_publishable_post"],
			"usdPerEditorPublishable": v["usd_per_reference_publishable_post"],
			"usdPerEditorPublishableCi": v["usd_per_reference_publishable_ci"],
			"usdPerRun": s["usd_per_run_mean"],
			"tokensP50": s["total_tokens"]["p50"],
			"tokensP95": s["total_tokens"]["p95"],
			"secondsP50": s["wall_seconds"]["p50"],
			"llmCallsP50": s["llm_calls"]["p50"],
			"gateVsEditor": v["gate_vs_reference"],
			"ourLoc": summary["build"][a]["our_loc"],
			"thirdPartyPackages": summary["build"][a]["third_party_packages"],
		})

	cells = []
	for a in ARMS[1:]:
		for m in ("llama-4-scout-17b-16e-instruct", "deepseek-v4-flash-0731"):
			rs = [r for r in clean if r["arm"] == a and r["model"].endswith(m)]
			n = len(rs)
			g = sum(r["publishable"] for r in rs)
			e = sum(1 for r in rs if r["editor_would_publish"] == 1)
			short = MODEL_SHORT[m]
			claim(f"{a}-{short}-editor-publishable", e, n, "editor_would_publish", f"{a}|{short}", f"{a} on {short}: editor would publish")
			claim(f"{a}-{short}-gate-publishable", g, n, "gate_publishable", f"{a}|{short}", f"{a} on {short}: passes every gate")
			cells.append({"arm": a, "model": short, "runs": n, "gatePct": pct(g / n), "editorPct": pct(e / n), "editorCount": e, "usdPerEditorPublishable": ed[f"{a}|{m}"]["usd_per_reference_publishable_post"]})

	# Gate validity, clean runs with an editor call.
	both = [r for r in clean if r["editor_would_publish"] != ""]
	gate_yes = [r for r in both if r["publishable"]]
	prec_n = sum(r["editor_would_publish"] for r in gate_yes)
	claim("gate-precision", prec_n, len(gate_yes), "editor_yes_among_gate_yes", "clean runs", "Of clean runs that pass every gate, share an editor would publish")
	chrome = [c for c in codes if "page_chrome_leak" in (c.get("codes") or [])]
	chrome_gate = sum(1 for c in chrome if c.get("gate_publishable"))
	claim("chrome-leak-gate-passed", chrome_gate, len(chrome), "gate_publishable", "runs leaking page counters or ads", "Of outputs that use page counters or sidebar ads as content, share the gates passed")
	facts_fail = [c for c in codes if "facts_gate_k_abbrev_false_positive" in (c.get("flags") or [])]

	modes = {}
	for a in ARMS:
		cnt = Counter(m for c in codes if c["arm"] == a and c.get("clean") for m in (c.get("codes") or []))
		modes[a] = [{"mode": m, "count": k} for m, k in cnt.most_common(4)]

	def shares(y):
		o = decomp["outcomes"].get(y) or {}
		if "share" not in o:
			return None
		return {t: {"pct": pct(o["share"][t]), "ciPct": [pct(x) for x in o["share_ci"].get(t, (None, None))]} for t in ("model", "arm", "arm x model", "source", "residual")}

	# Decision-rule steps on the gate outcome, per model subset: the gap and cost ratio each candidate faced.
	rule_steps = []
	for k, v in sens["prereg"].items():
		outcome, baseline, model = (x.strip() for x in k.split("|"))
		if outcome != "gate_publishable":
			continue
		for st in v["steps"]:
			rule_steps.append({"baseline": baseline, "model": model, "candidate": st["candidate"], "vs": st["vs"], "diffPts": pct(st["diff"]), "ciLowPts": pct(st["ci_low"]), "costRatio": st["cost_ratio"], "costRatioInfinite": st["cost_ratio_infinite"], "gapOk": st["gap_ok"], "costOk": st["cost_ok"]})

	sens_rows = [{"outcome": g["outcome"], "baseline": g["baseline"], "model": g["model"], "settings": g["settings"], "picks": g["pick_counts"]} for g in sens["grid"]]

	probe = defaultdict(lambda: {"calls": 0, "properToolCalls": 0, "change": "", "stream": False})
	for p in jl("probe-hermes-llama.jsonl"):
		c = probe[p["cell"]]
		c["calls"] += 1
		c["properToolCalls"] += p.get("kind") == "tool_calls"
		c["change"], c["stream"] = p["change"], p["stream"]

	faults = {}
	for k, v in summary["faults"].items():
		a, f = k.split("|")
		faults.setdefault(a, {})[f] = v["outcomes"]

	# Exploratory A4-enf cells (deviation 15), one entry per cell: streamed / not streamed.
	enforced = []
	eg = jl("enforced-gates.jsonl")
	for arm in sorted({g["arm"] for g in eg}):
		gs = [g for g in eg if g["arm"] == arm]
		eyes = sum(1 for c in codes_enf if c["arm"] == arm and c.get("would_publish"))
		enforced.append({"arm": arm, "streamed": not arm.endswith("nostream"), "runs": len(gs), "withOutput": sum(1 for g in gs if g.get("schema")), "gatePublishable": sum(g["publishable"] for g in gs), "editorPublishable": eyes})

	# Coder vs the human rater, on the pairs where the coder would publish exactly one side.
	agree = None
	votes, key = jload("panel-votes.json"), jload("panel-key.json")
	if votes and key:
		ed_pub = {c["run_id"]: bool(c.get("would_publish")) for c in codes}
		agree = {"sameSide": 0, "otherSide": 0, "neither": 0}
		for rater in votes.values():
			for q, ch in rater["choices"].items():
				ea, eb = ed_pub.get(key[q]["a"]["run_id"]), ed_pub.get(key[q]["b"]["run_id"])
				if ea is None or eb is None or ea == eb:
					continue
				coder = "a" if ea else "b"
				agree["neither" if ch == "neither" else ("sameSide" if ch == coder else "otherSide")] += 1
	asis = jload("panel-asis.json") or {}
	rh = jload("repeat-hook.json")
	repeat = None if not rh else {"byArm": [{"arm": a, "outputs": v["outputs"], "repeat": v["any_repeat"]} for a, v in rh["by_arm"].items()], "sourcesRepeating": sum(1 for x in rh["sources"] if x["repeated_in_description"]), "sourcesWithTitleNumbers": sum(1 for x in rh["sources"] if x["title_numbers"])}
	et = jload("enforced-turns.json") or {}
	if rh:
		for a, v in rh["by_arm"].items():
			claim(f"{a}-repeat-figure", v["any_repeat"], v["outputs"], "repeat_hook_any", a, f"{a}: clean outputs whose hook and next paragraph, or tweet 1 and 2, repeat a figure")

	data = {
		"snapshotDate": "2026-10-16",
		"updated": date.today().isoformat(),
		"design": {"sources": len({r["source"] for r in clean}), "repsPerModel": 6, "models": ["llama-4-scout", "deepseek-v4-flash"], "cleanRuns": len(clean), "faultRuns": len(rows) - len(clean)},
		"experimentUsd": summary["experiment_usd_total"],
		"arms": arms,
		"cells": cells,
		"gate": {"precisionPct": pct(prec_n / len(gate_yes)), "gateYes": len(gate_yes), "gateYesEditorYes": prec_n, "chromeLeakRuns": len(chrome), "chromeLeakGatePassed": chrome_gate, "factsGateFailuresAllFalsePositive": len(facts_fail)},
		"topModes": modes,
		"decomposition": {"gatePublishable": shares("publishable"), "editorPublishable": shares("would_publish"), "judgeTextQuality": shares("text_quality"), "humanFineAsIs": shares("human_as_is")},
		"sensitivity": sens_rows,
		"ruleSteps": rule_steps,
		"hermesProbe": [{"cell": k, **v} for k, v in probe.items()],
		"faults": faults,
		"panel": None if not panel else {"raters": len(panel["raters"]), "answers": panel["answers"], "alpha": panel["krippendorff_alpha_nominal"], "usable": panel["human_result_usable"], "bradleyTerry": panel["bradley_terry_log_strength"], "headToHead": [{"pairing": k, "wins": v["wins"], "neither": v["neither"]} for k, v in panel["head_to_head"].items()], "judgeSpearman": panel["llm_judge_spearman_vs_human"], "judgeN": panel["llm_judge_n_outputs"], "fineAsIs": {"yes": sum(v["yes"] for v in asis.values()), "of": sum(v["of"] for v in asis.values())}, "coderVsRater": agree},
		"repeatHook": repeat,
		"enforcedOutcomes": et.get("per_cell_outcome"),
		"enforcedTurns": et.get("per_cell_turns"),
		"enforcedHermesLlama": enforced,  # [] until run_enforced.py has run
	}
	body = json.dumps(data, indent="\t")
	TS.write_text(
		"// Generated by scripts/research/social-publish-4way-2026-10/export_article.py — do not edit by hand.\n"
		"// Every number on /research/cron-vs-llm-vs-langgraph-vs-agent-2026 comes from here.\n"
		f"export const SOCIAL_4WAY_2026_10 = {body} as const;\n"
	)
	# Repo style (Biome) so the generated module passes `pnpm check` unchanged.
	subprocess.run([str(ROOT / "node_modules" / ".bin" / "biome"), "format", "--write", str(TS)], cwd=ROOT, check=True, capture_output=True)
	LEDGER.write_text(json.dumps({"research_dir": "scripts/research/social-publish-4way-2026-10", "dataset_file": "../../../public/data/social-publish-4way-2026-10.csv", "claims": claims}, indent=2) + "\n")
	print(f"wrote {TS.relative_to(ROOT)} and {LEDGER.relative_to(ROOT)} ({len(claims)} claims)")


if __name__ == "__main__":
	main()
