"""Blind pairwise human panel (PREREGISTRATION.md "Human panel").

  python3 -I panel.py pairs      -> out/panel-pairs.json (what raters see, no labels)
                                    out/panel-key.json   (pair id -> arm/model/run id; never shown to raters)
  python3 -I panel.py analyze out/panel-votes.json
                                 -> out/panel-summary.json: Bradley-Terry strength per arm,
                                    head-to-head preference shares, Krippendorff's alpha,
                                    Spearman of the LLM text judge vs human per-output win rate

Pairs: 7 per arm pairing x 6 pairings = 42, both outputs from the same source post, drawn
from clean counted runs that produced a schema-valid output. Model is drawn at random per
side, but Hermes on llama-4-scout produced no schema-valid output, so every Hermes side is
deepseek-v4-flash while the other arms mix both models. Seed 42.
"""

from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "out"
PER_PAIRING = 7
rng = random.Random(42)


def jl(name: str) -> list[dict]:
	p = OUT / name
	return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def make_pairs() -> None:
	gates = {g["run_id"]: g for g in jl("gates.jsonl")}
	sources = {json.loads(f.read_text())["url"]: json.loads(f.read_text()) for f in (OUT / "sources").glob("*.json")}
	pool = defaultdict(list)  # (arm, source) -> run ids
	for r in jl("runs.jsonl"):
		if r["fault"] == "none" and gates.get(r["run_id"], {}).get("schema"):
			pool[(r["arm"], r["source"])].append(r)
	arms = sorted({a for a, _ in pool})
	srcs = sorted({s for _, s in pool})
	pairs, key = [], {}
	for x, y in combinations(arms, 2):
		ok = [s for s in srcs if pool[(x, s)] and pool[(y, s)]]
		for k in range(PER_PAIRING):
			s = ok[k % len(ok)]
			ra, rb = rng.choice(pool[(x, s)]), rng.choice(pool[(y, s)])
			if rng.random() < 0.5:
				ra, rb = rb, ra
			pid = f"q{len(pairs):02d}"
			load = lambda r: json.loads((OUT / "runs" / r["run_id"] / "output.json").read_text())
			pairs.append({"id": pid, "source": sources[s]["title"], "a": pick(load(ra)), "b": pick(load(rb))})
			key[pid] = {"a": side(ra), "b": side(rb)}
	rng.shuffle(pairs)
	for n, p in enumerate(pairs):
		p["n"] = n
	(OUT / "panel-pairs.json").write_text(json.dumps(pairs, indent=1))
	(OUT / "panel-key.json").write_text(json.dumps(key, indent=1))
	print(f"{len(pairs)} pairs over {len(arms)} arms")


def pick(o: dict) -> dict:
	return {
		"linkedin": o.get("linkedin", ""),
		"x_thread": [str(t) for t in o.get("x_thread", [])],
		"carousel": [{"title": str(s.get("title", "")), "body": str(s.get("body", ""))} for s in o.get("carousel", [])],
	}


def side(r: dict) -> dict:
	return {"arm": r["arm"], "model": r["model"], "run_id": r["run_id"]}


def bradley_terry(wins: dict, items: list[str], iters: int = 2000) -> dict:
	"""MM algorithm (Hunter 2004). wins[(i, j)] = times i beat j. Ties/neither excluded."""
	p = {i: 1.0 for i in items}
	for _ in range(iters):
		new = {}
		for i in items:
			w = sum(wins.get((i, j), 0) for j in items if j != i)
			d = sum((wins.get((i, j), 0) + wins.get((j, i), 0)) / (p[i] + p[j]) for j in items if j != i)
			new[i] = w / d if d else p[i]
		s = sum(new.values()) or 1
		p = {i: v * len(items) / s for i, v in new.items()}
	return {i: round(math.log(v), 4) if v > 0 else None for i, v in p.items()}


def krippendorff_nominal(units: list[list[str]]) -> float | None:
	"""units = list of the values each rater gave one pair (missing omitted)."""
	units = [u for u in units if len(u) >= 2]
	cats = sorted({v for u in units for v in u})
	o = defaultdict(float)
	for u in units:
		m = len(u)
		for a in range(m):
			for b in range(m):
				if a != b:
					o[(u[a], u[b])] += 1 / (m - 1)
	n_c = {c: sum(o[(c, k)] for k in cats) for c in cats}
	n = sum(n_c.values())
	if n <= 1:
		return None
	d_o = sum(o[(c, k)] for c in cats for k in cats if c != k) / n
	d_e = sum(n_c[c] * n_c[k] for c in cats for k in cats if c != k) / (n * (n - 1))
	return round(1 - d_o / d_e, 4) if d_e else None


def spearman(xs: list[float], ys: list[float]) -> float | None:
	if len(xs) < 3:
		return None

	def ranks(v):
		order = sorted(range(len(v)), key=lambda i: v[i])
		r = [0.0] * len(v)
		i = 0
		while i < len(v):
			j = i
			while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
				j += 1
			for k in range(i, j + 1):
				r[order[k]] = (i + j) / 2
			i = j + 1
		return r

	rx, ry = ranks(xs), ranks(ys)
	mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
	num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
	den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
	return round(num / den, 4) if den else None


def analyze(votes_path: str) -> None:
	key = json.loads((OUT / "panel-key.json").read_text())
	votes = json.loads(Path(votes_path).read_text())  # {rater_id: {rater_type, choices: {pid: a|b|neither}}}
	wins = defaultdict(int)
	h2h = defaultdict(lambda: {"wins": defaultdict(int), "neither": 0})
	per_run = defaultdict(lambda: [0, 0])  # run_id -> [wins, comparisons]
	units = defaultdict(list)
	for rater, v in votes.items():
		for pid, c in (v.get("choices") or {}).items():
			if pid not in key:
				continue
			units[pid].append(c)
			a, b = key[pid]["a"], key[pid]["b"]
			pairing = " vs ".join(sorted([a["arm"], b["arm"]]))
			if c == "neither":
				h2h[pairing]["neither"] += 1
				continue
			w, l = (a, b) if c == "a" else (b, a)
			wins[(w["arm"], l["arm"])] += 1
			h2h[pairing]["wins"][w["arm"]] += 1
			per_run[w["run_id"]][0] += 1
			for s in (a, b):
				per_run[s["run_id"]][1] += 1
	arms = sorted({s["arm"] for k in key.values() for s in k.values()})
	judge = {j["run_id"]: j["mean"] for j in jl("judge-text.jsonl") if "mean" in j}
	common = [r for r in per_run if r in judge and per_run[r][1]]
	rho = spearman([judge[r] for r in common], [per_run[r][0] / per_run[r][1] for r in common])
	alpha = krippendorff_nominal(list(units.values()))
	out = {
		"raters": {r: v.get("rater_type") for r, v in votes.items()},
		"answers": sum(len(u) for u in units.values()),
		"bradley_terry_log_strength": bradley_terry(wins, arms),
		"head_to_head": {k: {"wins": dict(v["wins"]), "neither": v["neither"]} for k, v in h2h.items()},
		"krippendorff_alpha_nominal": alpha,
		"human_result_usable": alpha is not None and alpha >= 0.4,
		"llm_judge_spearman_vs_human": rho,
		"llm_judge_reportable": rho is not None and rho >= 0.5,
		"llm_judge_n_outputs": len(common),
	}
	(OUT / "panel-summary.json").write_text(json.dumps(out, indent=1))
	print(json.dumps(out, indent=1))


if __name__ == "__main__":
	if sys.argv[1] == "pairs":
		make_pairs()
	else:
		analyze(sys.argv[2])
