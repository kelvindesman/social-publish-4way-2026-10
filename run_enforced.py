"""Exploratory arm A4-enf: Hermes on llama-4-scout with `agent.tool_use_enforcement: true`
(PREREGISTRATION.md deviation 15). Not part of the pre-registered comparison.

  POC_ENV_FILE=... python3 run_enforced.py              -> out/enforced-runs.jsonl
  POC_ENV_FILE=... python3 run_enforced.py --no-stream  -> same log, arm A4-hermes-enf-nostream
  POC_ENV_FILE=... python3 run_enforced.py --exec-guidance -> same log, arm A4-hermes-enf-exec
  then: npx tsx slop.ts && python3 -I gates.py enforced-runs.jsonl -> out/enforced-gates.jsonl

Why: hermes-llama-confound.md showed that Hermes's default ("auto") leaves its tool-use
enforcement prompt out for llama-family model names, and that llama-4-scout returns proper
tool calls once that prompt is in. A Hermes user would turn the documented setting on.
Design: the 5 frozen source posts x 2 reps, clean (no fault), same caps, proxy and gates as A4.
Run ids start with "x" so no counted-run filter picks them up.
--no-stream also sets `model.stream: false`: the probe cell that got proper tool calls with the
enforcement prompt (C6) was a non-streamed call, while Hermes streams by default.
--exec-guidance also sets `agent.execution_guidance: true`: C6's prompt (Hermes's deepseek prompt)
carries that "Execution discipline" block as well, and tool_use_enforcement alone does not add it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
MODEL = "@cf/meta/llama-4-scout-17b-16e-instruct"
LOG = HERE / "out" / "enforced-runs.jsonl"
REPS = 2


def main() -> None:
	if not os.environ.get("POC_ENV_FILE"):
		sys.exit("set POC_ENV_FILE")
	stream = "--no-stream" not in sys.argv
	guide = "--exec-guidance" in sys.argv
	arm = "A4-hermes-enf-exec" if guide else ("A4-hermes-enf" if stream else "A4-hermes-enf-nostream")
	tag = "enfeg" if guide else ("enf" if stream else "enfns")
	subprocess.run(["docker", "compose", "up", "-d", "proxy", "fixtures"], cwd=HERE, check=True)
	urls = (HERE / "sources.txt").read_text().split()
	for rep in range(REPS):
		for si, url in enumerate(urls):
			run_id = f"x{rep}-s{si}-A4-hermes-{tag}-m1-none-{time.time_ns() % 10**10}"
			t0 = time.time()
			try:
				p = subprocess.run(
					["docker", "compose", "run", "--rm", "-T", "-e", f"MODEL={MODEL}", "-e", "HERMES_ENFORCE=1", "-e", f"HERMES_STREAM={str(stream).lower()}", "-e", f"HERMES_EXEC_GUIDANCE={'1' if guide else ''}", "hermes", "bash", "/app/arms/arm4_hermes.sh", run_id, url],
					cwd=HERE,
					capture_output=True,
					text=True,
					timeout=900,
				)
				code, err = p.returncode, p.stderr
			except subprocess.TimeoutExpired:
				code, err = -9, "runner timeout 900s"
			row = {
				"run_id": run_id,
				"arm": arm,
				"model": "m1",
				"fault": "none",
				"rep": rep,
				"source": url,
				"exit": code,
				"wall_s": round(time.time() - t0, 2),
				"has_output": (HERE / "out" / "runs" / run_id / "output.json").exists(),
				"stderr_tail": err[-600:] if code else "",
			}
			with LOG.open("a") as f:
				f.write(json.dumps(row) + "\n")
			print(rep, si, code, row["wall_s"], row["has_output"], flush=True)


if __name__ == "__main__":
	main()
