"""How fragile is the verdict? Exploratory (logged under PREREGISTRATION.md "Deviations").

  python3 -I sensitivity.py  -> out/sensitivity.json

Re-applies the pre-registered decision rule ("recommend the cheapest arm unless a more
complex arm beats it by >= G publishable points with the paired CI above 0, AND wins >= 60%
of human pairs, AND costs <= R x per publishable post") while varying:
  G      5, 10, 15 (pre-registered), 20, 25 points
  R      2, 3 (pre-registered), 4, 5 x
  price  0.5, 1 (list), 1.5, 2 x on every model price
  outcome  gate publishable (pre-registered) / editor would-publish (one coder) /
           human fine-as-is (panel), the latter two when their files exist
  baseline  all arms (A1 cron is the cheapest) / LLM arms only (A2 is the cheapest)
  model   both models pooled / llama-4-scout only / deepseek-v4-flash only

The human-pairs condition uses out/panel-summary.json when present; until then it is
reported as "not checked" and the verdict shown is what the other two conditions give.
Note the rule's cost condition can never be met against A1: A1 costs $0, so any LLM arm
is infinitely more expensive per publishable post.
"""

from __future__ import annotations

import json
import sys
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # -I drops the script dir from sys.path
from analyze import OUT, build_rows, paired_diff_boot  # noqa: E402

ORDER = ["A1-cron", "A2-cron-llm", "A3-langgraph", "A4-hermes"]  # cheapest / simplest first
GS = (0.05, 0.10, 0.15, 0.20, 0.25)
RS = (2, 3, 4, 5)
PRICE = (0.5, 1.0, 1.5, 2.0)
PREREG = (0.15, 3, 1.0)
CI_CACHE: dict = {}


def load_outcomes(rows: list[dict]) -> dict[str, dict]:
	out = {"gate_publishable": {r["run_id"]: r["publishable"] for r in rows}}
	p = OUT / "error-codes.jsonl"
	if p.exists():
		ed = {}
		for line in p.read_text().splitlines():
			if line.strip():
				e = json.loads(line)
				ed[e["run_id"]] = int(bool(e.get("would_publish")))
		out["editor_would_publish"] = ed
	p = OUT / "panel-asis.json"
	if p.exists():
		out["human_fine_as_is"] = {k: v["yes"] / v["of"] for k, v in json.loads(p.read_text()).items() if v["of"]}
	return out


def human_win_share() -> dict | None:
	p = OUT / "panel-summary.json"
	if not p.exists():
		return None
	s = json.loads(p.read_text())
	if not s.get("human_result_usable"):
		return {}
	shares = {}
	for pairing, v in s["head_to_head"].items():
		x, y = pairing.split(" vs ")
		tot = sum(v["wins"].values()) + v["neither"]
		for a, b in ((x, y), (y, x)):
			shares[(a, b)] = v["wins"].get(a, 0) / tot if tot else 0.0
	return shares


def verdict(rows, y, arms, g, r_max, price, shares) -> dict:
	"""Walk from the cheapest arm; switch to a costlier arm only if it clears every condition."""

	def stat(rs):
		v = [x[y] for x in rs if x[y] is not None]
		return sum(v) / len(v) if v else None

	def usd_per_pub(rs):
		pub = sum(x[y] for x in rs if x[y] is not None)
		return sum(x["usd"] for x in rs) * price / pub if pub else None

	by = {a: [x for x in rows if x["arm"] == a and x[y] is not None] for a in arms}
	pick, why = arms[0], []
	for cand in arms[1:]:
		base, other = by[pick], by[cand]
		if not base or not other:
			continue
		diff = stat(other) - stat(base)
		# The CI depends only on the two arms' runs, not on G, R or price: compute once.
		# Keyed on the runs and their outcome values, not id(rows): CPython reuses ids of freed lists.
		ck = (frozenset((x["run_id"], x[y]) for x in rows), pick, cand)
		if ck not in CI_CACHE:
			CI_CACHE[ck] = paired_diff_boot(base, other, stat)[0]
		lo = CI_CACHE[ck]
		cb, cc = usd_per_pub(base), usd_per_pub(other)
		# None: the candidate never publishes (fails). 0.0: the baseline never publishes, so its
		# cost per publishable post is unbounded and any publishing arm is cheaper (passes).
		# inf: the baseline is free (A1) and publishes, so no paid arm can be within R x (fails).
		if cc is None:
			ratio = None
		elif cb is None:
			ratio = 0.0
		else:
			ratio = cc / cb if cb else float("inf")
		share = None if shares is None else shares.get((cand, pick))
		ok_gap = diff >= g and lo is not None and lo > 0
		ok_cost = ratio is not None and ratio <= r_max
		ok_human = True if shares is None else (share is not None and share >= 0.6)
		why.append({"candidate": cand, "vs": pick, "diff": round(diff, 4), "ci_low": lo, "cost_ratio": None if ratio in (None, float("inf")) else round(ratio, 2), "cost_ratio_infinite": ratio == float("inf"), "human_share": share, "gap_ok": ok_gap, "cost_ok": ok_cost, "human_ok": ok_human if shares is not None else "not checked"})
		if ok_gap and ok_cost and ok_human:
			pick = cand
	return {"pick": pick, "steps": why}


def main() -> None:
	base_rows = [r for r in build_rows() if r["fault"] == "none" and r["run_id"].startswith("r")]
	outcomes = load_outcomes(base_rows)
	shares = human_win_share()
	# shares == {}: the panel ran but is not usable (alpha < 0.4 or one rater), so no candidate can
	# meet the human condition and every verdict stays on the cheapest arm.
	cond = "not checked (panel pending)" if shares is None else ("checked" if shares else "fails: panel not usable")
	res = {"human_pairs_condition": cond, "grid": [], "prereg": {}}
	for name, vals in outcomes.items():
		rows_all = [{**r, "y": vals.get(r["run_id"])} for r in base_rows]
		for base, model in product(("all arms", "LLM arms only"), ("pooled", "llama-4-scout", "deepseek-v4-flash")):
			arms = ORDER if base == "all arms" else ORDER[1:]
			rows = [r for r in rows_all if r["arm"] in arms and (model == "pooled" or r["arm"] == "A1-cron" or model in r["model"])]
			picks = {}
			for g, rr, pr in product(GS, RS, PRICE):
				v = verdict(rows, "y", arms, g, rr, pr, shares)
				picks[f"G={int(g * 100)} R={rr} price={pr}"] = v["pick"]
				if (g, rr, pr) == PREREG:
					res["prereg"][f"{name} | {base} | {model}"] = v
			counts = {}
			for p in picks.values():
				counts[p] = counts.get(p, 0) + 1
			res["grid"].append({"outcome": name, "baseline": base, "model": model, "settings": len(picks), "pick_counts": counts, "picks": picks})
	(OUT / "sensitivity.json").write_text(json.dumps(res, indent=1))
	for g in res["grid"]:
		print(f"{g['outcome']:22} {g['baseline']:14} {g['model']:18} {g['pick_counts']}")


if __name__ == "__main__":
	main()
