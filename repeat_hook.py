"""Owner rater note (2026-10-23): hooks often state a figure, then the first paragraph states
it again. Mechanical count of that pattern, exploratory.

  python3 -I repeat_hook.py  -> out/repeat-hook.json

LinkedIn: a number in the first paragraph (the hook) that appears again in the second.
X: a number in tweet 1 that appears again in tweet 2. Carousel: slide 1 vs slide 2.
Source posts: a number in the title that appears again in the description (the meta line
under the title), which is the same pattern one level up.
Numbers are normalised as in gates.py ("4,280" == "4280", "22%" == "22"); years and
single digits are ignored.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # -I drops the script dir from sys.path
from gates import norm_numbers, strip_urls  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "out"


def nums(t: str) -> set[str]:
	# Years (2019-2030) are dates, not stats; a repeated year is not the pattern.
	return {n for n in norm_numbers(strip_urls(t)) if len(n.replace(".", "")) >= 2 and not (n.isdigit() and 2019 <= int(n) <= 2030)}


def repeat(a: str, b: str) -> bool:
	return bool(nums(a) & nums(b))


def main() -> None:
	reruns = {}
	p = OUT / "rerun-infra-runs.jsonl"
	if p.exists():
		reruns = {json.loads(x)["replaces"]: json.loads(x) for x in p.read_text().splitlines() if x.strip()}
	runs = [reruns.get(r["run_id"], r) for r in map(json.loads, (OUT / "runs.jsonl").read_text().splitlines()) if r["run_id"].startswith("r") and r["fault"] == "none"]
	cnt = defaultdict(lambda: defaultdict(int))
	for r in runs:
		f = OUT / "runs" / r["run_id"] / "output.json"
		try:
			o = json.loads(f.read_text())
		except (OSError, json.JSONDecodeError):
			continue
		c = cnt[r["arm"]]
		c["outputs"] += 1
		paras = [x for x in str(o.get("linkedin", "")).split("\n\n") if x.strip()]
		xs, cs = o.get("x_thread") or [], o.get("carousel") or []
		hook_has_num = bool(paras and nums(paras[0]))
		c["linkedin_hook_has_number"] += hook_has_num
		c["linkedin_repeat"] += len(paras) > 1 and repeat(paras[0], paras[1])
		c["x_repeat"] += len(xs) > 1 and repeat(str(xs[0]), str(xs[1]))
		c["carousel_repeat"] += len(cs) > 1 and repeat(json.dumps(cs[0]), json.dumps(cs[1]))
		c["any_repeat"] += (len(paras) > 1 and repeat(paras[0], paras[1])) or (len(xs) > 1 and repeat(str(xs[0]), str(xs[1])))
	src = []
	for f in sorted((OUT / "sources").glob("*.json")):
		s = json.loads(f.read_text())
		src.append({"slug": s["url"].rsplit("/", 1)[-1], "title_numbers": sorted(nums(s["title"])), "repeated_in_description": sorted(nums(s["title"]) & nums(s["description"]))})
	res = {"by_arm": {a: dict(v) for a, v in sorted(cnt.items())}, "sources": src}
	(OUT / "repeat-hook.json").write_text(json.dumps(res, indent=1))
	print(json.dumps(res, indent=1))


if __name__ == "__main__":
	main()
