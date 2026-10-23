"""Re-run, once, the counted runs that never reached the model (PREREGISTRATION.md "Design":
"Infra errors not caused by an injected fault (gateway 5xx) are re-run once and logged").

  POC_ENV_FILE=... python3 rerun_infra.py
  -> out/rerun-infra-runs.jsonl   one line per re-run, with "replaces": <original run_id>
  then: npx tsx slop.ts && python3 -I gates.py rerun-infra-runs.jsonl  -> out/rerun-infra-gates.jsonl

Found on 2026-10-23 (hermes-llama-confound.md, "Adjacent finding"): 8 A4 fault runs ended with
"Hermes couldn't start the model connection: Gateway starting: deadline. Your message was not
sent." and have no proxy transcript, yet were coded stopped_clean. The originals stay in
runs.jsonl; analysis swaps in the re-run (analyze.py reads the "replaces" field).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from run_all import FAULT_URLS, run_one  # noqa: E402

MARK = "Gateway starting: deadline"
LOG = HERE / "out" / "rerun-infra-runs.jsonl"


def infra_failed() -> list[dict]:
	out = []
	for line in (HERE / "out" / "runs.jsonl").read_text().splitlines():
		r = json.loads(line)
		f = HERE / "out" / "runs" / r["run_id"] / "agent-final.txt"
		if r["run_id"].startswith("r") and f.exists() and MARK in f.read_text():
			out.append(r)
	return out


def main() -> None:
	if not os.environ.get("POC_ENV_FILE"):
		sys.exit("set POC_ENV_FILE")
	done = {json.loads(x)["replaces"] for x in LOG.read_text().splitlines()} if LOG.exists() else set()
	todo = [r for r in infra_failed() if r["run_id"] not in done]
	print(f"{len(todo)} runs to re-run", flush=True)
	subprocess.run(["docker", "compose", "up", "-d", "proxy", "fixtures"], cwd=HERE, check=True)
	tmp = HERE / "out" / "rerun-infra-tmp.jsonl"
	for r in todo:
		url = FAULT_URLS.get(r["fault"], r["source"])
		run_one({"arm": r["arm"], "model": r["model"], "fault": r["fault"], "rep": r["rep"], "si": -1, "url": url}, tmp)
		row = json.loads(tmp.read_text().splitlines()[-1])
		with LOG.open("a") as f:
			f.write(json.dumps({**row, "replaces": r["run_id"]}) + "\n")
	tmp.unlink(missing_ok=True)


if __name__ == "__main__":
	main()
