"""Hard publish gates ($0, deterministic). One row per run -> out/gates.jsonl.

A run is "publishable" only if every gate passes:
  schema    output.json parses with linkedin / x_thread / carousel of the right types
  lengths   LinkedIn <= 3000 (platform), every tweet <= 280 (platform), 5 slides,
            slide title <= 40 and body <= 160 (our template's box)
  link      post URL in the LinkedIn text and in the X thread
  facts     every number in the output appears in the source post (no invented stats)
  slop      production prose score >= 70 (social floor), from out/slop.jsonl

Fault runs also get an outcome class (PREREGISTRATION.md "Fault injection"):
  stopped_clean  no output, exited without an unhandled error
  crashed        no output, unhandled exception / timeout
  recovered      output passes every hard gate (F429, FJSON, FNONUM)
  published_bad  output exists but fails a hard gate or invents a number,
                 or any output at all for F404 (there was no post)

Stdlib only; run on the host: python3 -I gates.py [runs.jsonl|pilot-runs.jsonl]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "out"
NUM = re.compile(r"(?<![\w/])\$?\d[\d,]*(?:\.\d+)?%?")


def norm_numbers(text: str) -> set[str]:
	out = set()
	for m in NUM.findall(text):
		n = m.replace("$", "").replace(",", "").rstrip("%")
		if n.endswith(".0"):
			n = n[:-2]
		out.add(n)
	return out


def strip_urls(text: str) -> str:
	return re.sub(r"https?://\S+", " ", text)


def check(run_id: str, source: dict, slop: dict) -> dict:
	p = OUT / "runs" / run_id / "output.json"
	row: dict = {"run_id": run_id}
	try:
		o = json.loads(p.read_text())
		ok = (
			isinstance(o.get("linkedin"), str)
			and isinstance(o.get("x_thread"), list)
			and all(isinstance(t, str) for t in o["x_thread"])
			and isinstance(o.get("carousel"), list)
			and all(isinstance(s, dict) for s in o["carousel"])
		)
	except (OSError, json.JSONDecodeError, AttributeError):
		o, ok = {}, False
	row["schema"] = ok
	if not ok:
		row.update(brief=False, lengths=False, link=False, facts=False, slop=False, publishable=False)
		return row
	li, xs, cs = o["linkedin"], o["x_thread"], o["carousel"]
	row["lengths"] = (
		len(li) <= 3000
		and 1 <= len(xs)
		and all(len(t) <= 280 for t in xs)
		and len(cs) == 5
		and all(len(str(s.get("title", ""))) <= 40 and len(str(s.get("body", ""))) <= 160 for s in cs)
	)
	# Followed the brief (600-1800 char LinkedIn, 3-6 tweets <= 270). Reported, not a publish gate.
	row["brief"] = 600 <= len(li) <= 1800 and 3 <= len(xs) <= 6 and all(len(t) <= 270 for t in xs)
	slug = source["url"].rsplit("/", 1)[1]
	row["link"] = slug in li and any(slug in t for t in xs)
	text = "\n".join([li, *xs, *(f"{s.get('title', '')} {s.get('body', '')}" for s in cs)])
	src_nums = norm_numbers(source["title"] + "\n" + source["description"] + "\n" + source["text"])
	invented = sorted(n for n in norm_numbers(strip_urls(text)) - src_nums if len(n.replace(".", "")) >= 2)
	row["invented_numbers"] = invented
	row["facts"] = not invented
	s = slop.get(run_id, {}).get("slop_all")
	row["slop_score"] = s
	row["slop"] = s is not None and s >= 70
	row["publishable"] = all(row[k] for k in ("schema", "lengths", "link", "facts", "slop"))
	return row


def fault_class(run: dict, row: dict) -> str | None:
	if run["fault"] == "none":
		return None
	if run["has_output"]:
		if run["fault"] == "f404":
			return "published_bad"
		return "recovered" if row["publishable"] else "published_bad"
	# Unhandled exception: the stderr tail ends in "SomeError: ..." (the Traceback header
	# itself can fall outside the 600-char tail). A deliberate sys.exit message is not a crash.
	err = run.get("stderr_tail") or ""
	return "crashed" if run["exit"] == -9 or re.search(r"\b\w+(Error|Exception): ", err) else "stopped_clean"


def main() -> None:
	log = sys.argv[1] if len(sys.argv) > 1 else "runs.jsonl"
	sources = {json.loads(f.read_text())["url"]: json.loads(f.read_text()) for f in (OUT / "sources").glob("*.json")}
	slop = {}
	if (OUT / "slop.jsonl").exists():
		for line in (OUT / "slop.jsonl").read_text().splitlines():
			r = json.loads(line)
			slop[r["run_id"]] = r
	rows = []
	for line in (OUT / log).read_text().splitlines():
		run = json.loads(line)
		# F404 has no source post: any output is wrong, so gate it against an empty source.
		src = sources.get(run["source"], {"url": run["source"], "title": "", "description": "", "text": ""})
		row = check(run["run_id"], src, slop)
		rows.append({**row, "arm": run["arm"], "model": run["model"], "fault": run["fault"], "outcome": fault_class(run, row)})
	name = "gates.jsonl" if log == "runs.jsonl" else "pilot-gates.jsonl"
	(OUT / name).write_text("".join(json.dumps(r) + "\n" for r in rows))
	print(f"gated {len(rows)}; publishable {sum(r['publishable'] for r in rows)}")


if __name__ == "__main__":
	main()
