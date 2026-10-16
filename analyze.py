"""Join runs + proxy usage + gates + judges into the pre-registered metrics (PREREGISTRATION.md).

Outputs:
  out/summary.json                                        every number the README and article cite
  ../../../public/data/social-publish-4way-2026-10.csv    one row per counted run (public)

Prices: Workers AI list prices from src/lib/ai/workers-ai-catalog.ts.
Cadence for $/month: 12 runs/day (the production social-generate schedule, every 2 hours).
CIs: 95% percentile bootstrap, 10,000 resamples, clustered by source post (resample the
5 sources with replacement, keep every run of a drawn source). Pairwise arm differences
resample the same sources for both arms (paired by source).

Stdlib only: python3 -I analyze.py
"""

from __future__ import annotations

import csv
import json
import random
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "out"
CSV = HERE.parents[2] / "public" / "data" / "social-publish-4way-2026-10.csv"
PRICES = {  # $ per 1M input, output tokens
	"@cf/meta/llama-4-scout-17b-16e-instruct": (0.27, 0.85),
	"@cf/deepseek-ai/deepseek-v4-flash-0731": (0.44, 1.32),
}
MODELS = {"m1": "@cf/meta/llama-4-scout-17b-16e-instruct", "m2": "@cf/deepseek-ai/deepseek-v4-flash-0731"}
RUNS_PER_MONTH = 12 * 30
B = 10_000
GATES = ("schema", "lengths", "link", "facts", "slop")
rng = random.Random(42)


def jl(name: str) -> list[dict]:
	p = OUT / name
	return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def pct(xs: list[float], q: float) -> float | None:
	xs = sorted(x for x in xs if x is not None)
	if not xs:
		return None
	k = (len(xs) - 1) * q
	lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
	return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def cluster_boot(rows: list[dict], stat, key: str = "source") -> tuple[float | None, float | None]:
	by = defaultdict(list)
	for r in rows:
		by[r[key]].append(r)
	ks = list(by)
	if not ks:
		return None, None
	vals = []
	for _ in range(B):
		sample = [r for k in rng.choices(ks, k=len(ks)) for r in by[k]]
		v = stat(sample)
		if v is not None:
			vals.append(v)
	return (round(pct(vals, 0.025), 4), round(pct(vals, 0.975), 4)) if vals else (None, None)


def paired_diff_boot(a: list[dict], b: list[dict], stat) -> tuple[float | None, float | None]:
	"""CI of stat(b) - stat(a), resampling the same source draw for both arms."""
	ba, bb = defaultdict(list), defaultdict(list)
	for r in a:
		ba[r["source"]].append(r)
	for r in b:
		bb[r["source"]].append(r)
	ks = sorted(set(ba) & set(bb))
	vals = []
	for _ in range(B):
		draw = rng.choices(ks, k=len(ks))
		sa = [r for k in draw for r in ba[k]]
		sb = [r for k in draw for r in bb[k]]
		x, y = stat(sa), stat(sb)
		if x is not None and y is not None:
			vals.append(y - x)
	return (round(pct(vals, 0.025), 4), round(pct(vals, 0.975), 4)) if vals else (None, None)


def rate(field: str):
	return lambda rs: (sum(r[field] for r in rs) / len(rs)) if rs else None


def quant(field: str, q: float):
	return lambda rs: pct([r[field] for r in rs], q)


def dist(rows: list[dict], field: str) -> dict:
	xs = [r[field] for r in rows if r[field] is not None]
	if not xs:
		return {}
	return {
		"p50": round(pct(xs, 0.5), 4),
		"p50_ci": cluster_boot(rows, quant(field, 0.5)),
		"p95": round(pct(xs, 0.95), 4),
		"p95_ci": cluster_boot(rows, quant(field, 0.95)),
		"max": max(xs),
	}


def loc(*files: str) -> int:
	n = 0
	for f in files:
		for line in (HERE / f).read_text().splitlines():
			s = line.strip()
			if s and not s.startswith("#") and not s.startswith('"""'):
				n += 1
	return n


def eta_squared(rows: list[dict], y: str, factors: tuple[str, ...]) -> dict:
	"""Main-effect sum of squares share per factor (balanced design, no interaction term)."""
	ys = [r[y] for r in rows if r[y] is not None]
	if len(ys) < 3:
		return {}
	grand = st.mean(ys)
	sst = sum((v - grand) ** 2 for v in ys)
	out = {}
	for f in factors:
		groups = defaultdict(list)
		for r in rows:
			if r[y] is not None:
				groups[r[f]].append(r[y])
		ssf = sum(len(g) * (st.mean(g) - grand) ** 2 for g in groups.values())
		out[f] = round(ssf / sst, 4) if sst else None
	return out


def build_rows() -> list[dict]:
	usage = defaultdict(lambda: {"calls": 0, "failed": 0, "in": 0, "out": 0, "usd": 0.0})
	for u in jl("usage.jsonl"):
		r = usage[u["run_id"]]
		r["calls"] += 1
		r["failed"] += u["status"] != 200
		pin, pout = u.get("prompt_tokens") or 0, u.get("completion_tokens") or 0
		r["in"] += pin
		r["out"] += pout
		ip, op = PRICES.get(u.get("model") or "", (0.0, 0.0))
		r["usd"] += pin * ip / 1e6 + pout * op / 1e6
	gates = {g["run_id"]: g for g in jl("gates.jsonl")}
	text = {j["run_id"]: j for j in jl("judge-text.jsonl") if "mean" in j}
	vis = {j["run_id"]: j for j in jl("judge-visual.jsonl") if "overall" in j}
	vchk = {v["run_id"]: v for v in jl("visual-checks.jsonl")}
	rows = []
	for r in jl("runs.jsonl"):
		u = usage[r["run_id"]]
		g = gates.get(r["run_id"], {})
		rows.append(
			{
				"run_id": r["run_id"],
				"arm": r["arm"],
				"model": MODELS.get(r["model"], "none"),
				"fault": r["fault"],
				"source": r["source"].rsplit("/", 1)[1],
				"rep": r["rep"],
				"completed": int(r["exit"] == 0 and r["has_output"]),
				"wall_seconds": r["wall_s"],
				"llm_calls": u["calls"],
				"failed_llm_calls": u["failed"],
				"input_tokens": u["in"],
				"output_tokens": u["out"],
				"total_tokens": u["in"] + u["out"],
				"usd": round(u["usd"], 6),
				**{f"gate_{k}": int(bool(g.get(k))) for k in GATES},
				"publishable": int(bool(g.get("publishable"))),
				"followed_brief": int(bool(g.get("brief"))),
				"invented_numbers": len(g.get("invented_numbers") or []),
				"slop_score": g.get("slop_score"),
				"fault_outcome": g.get("outcome") or "",
				"text_quality": text.get(r["run_id"], {}).get("mean"),
				"carousel_fits": int(bool(vchk.get(r["run_id"], {}).get("fits"))),
				"visual_quality": vis.get(r["run_id"], {}).get("overall"),
			}
		)
	return rows


def arm_block(a: list[dict]) -> dict:
	n = len(a)
	usd_total = sum(r["usd"] for r in a)
	pub = sum(r["publishable"] for r in a)
	q = [r["text_quality"] for r in a if r["text_quality"] is not None]
	return {
		"runs": n,
		"publishable_rate": round(pub / n, 4),
		"publishable_rate_ci": cluster_boot(a, rate("publishable")),
		"usd_per_publishable_post": round(usd_total / pub, 6) if pub else None,
		"usd_per_publishable_ci": cluster_boot(
			a, lambda rs: (sum(r["usd"] for r in rs) / s) if (s := sum(r["publishable"] for r in rs)) else None
		),
		"usd_per_run_mean": round(usd_total / n, 6),
		"usd_per_month_at_12_runs_per_day": round(usd_total / n * RUNS_PER_MONTH, 4),
		"completed_rate": round(sum(r["completed"] for r in a) / n, 4),
		"followed_brief_rate": round(sum(r["followed_brief"] for r in a) / n, 4),
		"runs_with_invented_numbers": sum(r["invented_numbers"] > 0 for r in a),
		"gate_fail_counts": {k: sum(1 - r[f"gate_{k}"] for r in a) for k in GATES},
		"llm_calls": dist(a, "llm_calls"),
		"total_tokens": dist(a, "total_tokens"),
		"wall_seconds": dist(a, "wall_seconds"),
		"failed_llm_calls_total": sum(r["failed_llm_calls"] for r in a),
		"mean_text_quality_1_10": round(st.mean(q), 3) if q else None,
		"mean_slop_score": round(st.mean(s), 2) if (s := [r["slop_score"] for r in a if r["slop_score"] is not None]) else None,
		"carousel_fits_rate": round(sum(r["carousel_fits"] for r in a) / n, 4),
	}


def main() -> None:
	rows = build_rows()
	CSV.parent.mkdir(parents=True, exist_ok=True)
	with CSV.open("w", newline="") as f:
		w = csv.DictWriter(f, fieldnames=list(rows[0]))
		w.writeheader()
		w.writerows(rows)

	clean = [r for r in rows if r["fault"] == "none"]
	faults = [r for r in rows if r["fault"] != "none"]
	arms = sorted({r["arm"] for r in clean})
	summary: dict = {"clean": {}, "clean_by_model": {}, "pairwise": {}, "faults": {}}
	for arm in arms:
		summary["clean"][arm] = arm_block([r for r in clean if r["arm"] == arm])
		for m in sorted({r["model"] for r in clean if r["arm"] == arm}):
			summary["clean_by_model"][f"{arm}|{m}"] = arm_block([r for r in clean if r["arm"] == arm and r["model"] == m])

	# Pairwise publishable-rate differences (later arm minus earlier arm), paired by source.
	for i, x in enumerate(arms):
		for y in arms[i + 1 :]:
			a = [r for r in clean if r["arm"] == x]
			b = [r for r in clean if r["arm"] == y]
			summary["pairwise"][f"{y} - {x}"] = {
				"publishable_diff": round(rate("publishable")(b) - rate("publishable")(a), 4),
				"publishable_diff_ci": paired_diff_boot(a, b, rate("publishable")),
				"median_tokens_ratio": round(m_b / m_a, 2) if (m_a := pct([r["total_tokens"] for r in a], 0.5)) and (m_b := pct([r["total_tokens"] for r in b], 0.5)) else None,
				"p95_tokens_ratio": round(p_b / p_a, 2) if (p_a := pct([r["total_tokens"] for r in a], 0.95)) and (p_b := pct([r["total_tokens"] for r in b], 0.95)) else None,
			}

	for arm in sorted({r["arm"] for r in faults}):
		for fault in sorted({r["fault"] for r in faults}):
			fr = [r for r in faults if r["arm"] == arm and r["fault"] == fault]
			if fr:
				summary["faults"][f"{arm}|{fault}"] = {
					"runs": len(fr),
					"outcomes": dict(Counter(r["fault_outcome"] for r in fr)),
					"published_bad_rate": round(sum(r["fault_outcome"] == "published_bad" for r in fr) / len(fr), 4),
					"usd_total": round(sum(r["usd"] for r in fr), 6),
				}

	llm = [r for r in clean if r["arm"] != "A1-cron"]
	summary["variance_explained_text_quality"] = eta_squared(llm, "text_quality", ("model", "arm"))
	summary["variance_explained_publishable"] = eta_squared(llm, "publishable", ("model", "arm"))

	freeze = {p.stem: len([x for x in p.read_text().splitlines() if x.strip() and not x.startswith("#")]) for p in OUT.glob("*-freeze.txt")}
	images = json.loads((OUT / "image-sizes.json").read_text()) if (OUT / "image-sizes.json").exists() else {}
	summary["build"] = {
		"A1-cron": {"our_loc": loc("arms/arm1_cron.py"), "third_party_packages": 0},
		"A2-cron-llm": {"our_loc": loc("arms/arm2_llm.py"), "third_party_packages": 0},
		"A3-langgraph": {"our_loc": loc("arms/arm3_langgraph.py"), "third_party_packages": freeze.get("langgraph-freeze")},
		"A4-hermes": {"our_loc": loc("arms/arm4_hermes.sh"), "third_party_packages": freeze.get("hermes-freeze")},
		"shared_loc": loc("common/shared.py"),
		"image_sizes": images,
	}
	judge = jl("judge-usage.jsonl")
	summary["eval_cost"] = {
		"judge_calls": len(judge),
		"judge_tokens": sum((j.get("prompt_tokens") or 0) + (j.get("completion_tokens") or 0) for j in judge),
	}
	summary["experiment_usd_total"] = round(sum(r["usd"] for r in rows), 4)
	(OUT / "summary.json").write_text(json.dumps(summary, indent=1))
	print(json.dumps({k: summary[k] for k in ("pairwise", "faults", "experiment_usd_total")}, indent=1))


if __name__ == "__main__":
	main()
