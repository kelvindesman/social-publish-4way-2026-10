"""Runner for the pre-registered design (PREREGISTRATION.md).

Clean runs : sources x reps x models x arms (A1 has no model: 2 reps only).
Fault runs : faults x arms x models x 3 reps (A1 once per model).
Each run is one `docker compose run --rm` (the container is gone afterwards).
Two runs execute in parallel; arm order rotates per rep. One line per run
goes to out/runs.jsonl; token usage comes from the proxy (out/usage.jsonl),
full request/response transcripts from out/transcripts/<run_id>.jsonl.

  python3 run_all.py clean
  python3 run_all.py faults
  python3 run_all.py pilot   # 1 source, 1 rep, both models, all arms + all faults; out/pilot-runs.jsonl
"""

import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
ARMS = {
	"A1-cron": ["py", "python", "/app/arms/arm1_cron.py"],
	"A2-cron-llm": ["py", "python", "/app/arms/arm2_llm.py"],
	"A3-langgraph": ["langgraph", "python", "/app/arms/arm3_langgraph.py"],
	"A4-hermes": ["hermes", "bash", "/app/arms/arm4_hermes.sh"],
}
MODELS = {"m1": "@cf/meta/llama-4-scout-17b-16e-instruct", "m2": "@cf/deepseek-ai/deepseek-v4-flash-0731"}
FAULT_URLS = {
	"f404": "https://lokerdollar.com/en/blog/this-post-does-not-exist-4way",
	"fnonum": "http://fixtures:8000/no-numbers-post.md",
}
_lock = threading.Lock()


def jobs(mode: str) -> list[dict]:
	urls = (HERE / "sources.txt").read_text().split()
	out = []
	if mode in ("clean", "pilot"):
		reps = 1 if mode == "pilot" else 6
		srcs = urls[:1] if mode == "pilot" else urls
		for rep in range(reps):
			arms = list(ARMS)
			k = rep % len(arms)
			for si, url in enumerate(srcs):
				for arm in arms[k:] + arms[:k]:
					if arm == "A1-cron":
						if rep < 2:
							out.append({"arm": arm, "model": "none", "fault": "none", "rep": rep, "si": si, "url": url})
						continue
					for m in MODELS:
						out.append({"arm": arm, "model": m, "fault": "none", "rep": rep, "si": si, "url": url})
	if mode in ("faults", "pilot"):
		reps = 1 if mode == "pilot" else 3
		for rep in range(reps):
			for fault in ("f404", "f429", "fjson", "fnonum"):
				url = FAULT_URLS.get(fault, urls[rep % len(urls)])
				for arm in ARMS:
					for m in (["none"] if arm == "A1-cron" else list(MODELS)):
						if arm == "A1-cron" and rep > 0:
							continue
						if arm == "A1-cron" and fault in ("f429", "fjson"):
							continue  # no LLM call to fault
						out.append({"arm": arm, "model": m, "fault": fault, "rep": rep, "si": -1, "url": url})
	return out


def run_one(j: dict, log: Path) -> None:
	run_id = f"{'p' if log.name.startswith('pilot') else 'r'}{j['rep']}-s{j['si']}-{j['arm']}-{j['model']}-{j['fault']}-{time.time_ns() % 10**10}"
	svc, *cmd = ARMS[j["arm"]]
	env_args = ["-e", f"MODEL={MODELS.get(j['model'], '')}"]
	t0 = time.time()
	try:
		p = subprocess.run(
			["docker", "compose", "run", "--rm", "-T", *env_args, svc, *cmd, run_id, j["url"]],
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
		**{k: j[k] for k in ("arm", "model", "fault", "rep")},
		"source": j["url"],
		"exit": code,
		"wall_s": round(time.time() - t0, 2),
		"has_output": (HERE / "out" / "runs" / run_id / "output.json").exists(),
		"stderr_tail": err[-600:] if code else "",
	}
	with _lock, log.open("a") as f:
		f.write(json.dumps(row) + "\n")
	print(j["arm"], j["model"], j["fault"], j["rep"], j["si"], code, row["wall_s"], row["has_output"], flush=True)


def main() -> None:
	mode = sys.argv[1]
	log = HERE / "out" / ("pilot-runs.jsonl" if mode == "pilot" else "runs.jsonl")
	if not os.environ.get("POC_ENV_FILE"):
		sys.exit("set POC_ENV_FILE")
	subprocess.run(["docker", "compose", "up", "-d", "proxy", "fixtures"], cwd=HERE, check=True)
	todo = jobs(mode)
	print(f"{len(todo)} runs", flush=True)
	with ThreadPoolExecutor(max_workers=int(os.environ.get("LANES", "2"))) as ex:
		list(ex.map(lambda j: run_one(j, log), todo))


if __name__ == "__main__":
	main()
