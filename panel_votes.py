"""Collect rater answers from the panel page into the files panel.py and validity.py read.

  python3 -I panel_votes.py <file or dir> [...]
  -> out/panel-votes.json  {rater: {rater_type, choices: {pid: a|b|neither}}}  (panel.py analyze)
     out/panel-asis.json   {run_id: {yes, of}}  "fine to post as-is" ticks per output

Inputs are JSON documents with {rater_type, choices, publish}: the page's db rows exported
with the ArtifactData tool (list with out_dir) or files raters saved from the page. The rater
id is the file name without extension. Probe or empty rows are skipped.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).parent / "out"


def files(args: list[str]) -> list[Path]:
	out = []
	for a in args:
		p = Path(a)
		out += sorted(p.rglob("*.json")) if p.is_dir() else [p]
	return out


def main() -> None:
	key = json.loads((OUT / "panel-key.json").read_text())
	votes, asis = {}, defaultdict(lambda: {"yes": 0, "of": 0})
	for f in files(sys.argv[1:]):
		d = json.loads(f.read_text())
		d = d.get("data", d)  # an ArtifactData export may wrap the body
		if d.get("rater_type") not in ("technical", "non-technical") or not d.get("choices"):
			continue
		rid = f.stem
		votes[rid] = {"rater_type": d["rater_type"], "choices": {k: v for k, v in d["choices"].items() if k in key}}
		for pid, sides in (d.get("publish") or {}).items():
			if pid not in key or pid not in d["choices"]:
				continue
			for side in ("a", "b"):
				run = key[pid][side]["run_id"]
				asis[run]["of"] += 1
				asis[run]["yes"] += int(bool(sides.get(side)))
		# A rated pair with no ticks means "neither side is fine as-is".
		for pid in d["choices"]:
			if pid in key and pid not in (d.get("publish") or {}):
				for side in ("a", "b"):
					asis[key[pid][side]["run_id"]]["of"] += 1
	(OUT / "panel-votes.json").write_text(json.dumps(votes, indent=1))
	(OUT / "panel-asis.json").write_text(json.dumps(asis, indent=1))
	types = defaultdict(int)
	for v in votes.values():
		types[v["rater_type"]] += 1
	print(f"{len(votes)} raters {dict(types)}, {sum(len(v['choices']) for v in votes.values())} answers, {len(asis)} outputs with as-is ticks")


if __name__ == "__main__":
	main()
