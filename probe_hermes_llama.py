"""Decisive probe for the A4 / llama-4-scout confound (hermes-llama-confound.md, "Decisive probe").

  UPSTREAM_BASE=... UPSTREAM_TOKEN=... python3 -I probe_hermes_llama.py <transcripts dir>
  -> out/probe-hermes-llama.jsonl (one line per call: cell, request change, raw reply summary)

Replays the exact turn-0 request Hermes sent in r0-s0-A4-hermes-m1-none-334864000 from a
plain stdlib client (no agent framework), then varies one thing per cell. 10 calls in total.
Exploratory, run 2026-10-23, logged under PREREGISTRATION.md "Deviations".
"""

from __future__ import annotations

import copy
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "out" / "probe-hermes-llama.jsonl"
BASE_RUN = "r0-s0-A4-hermes-m1-none-334864000"
NEUTRAL = "You are a helpful assistant that uses tools to complete tasks."
UPSTREAM = os.environ["UPSTREAM_BASE"].rstrip("/")
TOKEN = os.environ["UPSTREAM_TOKEN"]


def first_request(tdir: Path, run_prefix: str) -> dict:
	f = next(tdir.glob(f"{run_prefix}*.jsonl"))
	return json.loads(f.read_text().splitlines()[0])["request"]


def m2_system_prompt(tdir: Path) -> str:
	f = next(tdir.glob("r0-s0-A4-hermes-m2-none-*.jsonl"))
	req = json.loads(f.read_text().splitlines()[0])["request"]
	return next(m["content"] for m in req["messages"] if m["role"] == "system")


def set_system(req: dict, text: str) -> dict:
	r = copy.deepcopy(req)
	r["messages"] = [{"role": "system", "content": text}] + [m for m in r["messages"] if m["role"] != "system"]
	return r


def call(req: dict) -> dict:
	body = json.dumps(req).encode()
	q = urllib.request.Request(UPSTREAM + "/chat/completions", data=body, method="POST")
	q.add_header("Content-Type", "application/json")
	q.add_header("User-Agent", "lokerdollar-research-proxy/1.0")
	q.add_header("Authorization", f"Bearer {TOKEN}")
	q.add_header("cf-aig-authorization", f"Bearer {TOKEN}")
	t = time.time()
	try:
		resp = urllib.request.urlopen(q, timeout=300)
		status, raw = resp.status, resp.read().decode("utf-8", "replace")
	except urllib.error.HTTPError as e:
		status, raw = e.code, e.read().decode("utf-8", "replace")
	return {"status": status, "ms": int((time.time() - t) * 1000), **summarize(raw, req.get("stream", False))}


def summarize(raw: str, stream: bool) -> dict:
	content, tool_calls, finish, usage = "", {}, None, None
	chunks = []
	if stream:
		for line in raw.splitlines():
			if line.startswith("data: ") and line[6:].strip() not in ("", "[DONE]"):
				try:
					chunks.append(json.loads(line[6:]))
				except json.JSONDecodeError:
					pass
	else:
		try:
			chunks = [json.loads(raw)]
		except json.JSONDecodeError:
			return {"kind": "unparseable", "raw_head": raw[:300]}
	for c in chunks:
		usage = c.get("usage") or usage
		for ch in c.get("choices") or []:
			d = ch.get("delta") or ch.get("message") or {}
			content += d.get("content") or ""
			for tc in d.get("tool_calls") or []:
				k = tc.get("index", len(tool_calls))
				fn = tc.get("function") or {}
				cur = tool_calls.setdefault(k, {"name": "", "arguments": ""})
				cur["name"] += fn.get("name") or ""
				cur["arguments"] += fn.get("arguments") or ""
			finish = ch.get("finish_reason") or finish
	kind = "tool_calls" if tool_calls else ("text" if content.strip() else "empty")
	return {
		"kind": kind,
		"finish_reason": finish,
		"tool_names": [v["name"] for v in tool_calls.values()],
		"content_head": content[:400],
		"usage": usage,
	}


def main() -> None:
	tdir = Path(sys.argv[1])
	r = first_request(tdir, BASE_RUN)
	no_effort = {k: v for k, v in r.items() if k != "reasoning_effort"}
	neutral = set_system(no_effort, NEUTRAL)
	m2_sys = m2_system_prompt(tdir).replace("deepseek-v4-flash", "llama-4-scout")
	two_tools = copy.deepcopy(r)
	two_tools["tools"] = [t for t in r["tools"] if t["function"]["name"] in ("terminal", "write_file")]
	ns = lambda x: {**{k: v for k, v in x.items() if k != "stream_options"}, "stream": False}
	st = lambda x: {**x, "stream": True, "stream_options": {"include_usage": True}}
	cells = [
		("C1 control", "none", st(r), 1),
		("C2 non-streamed", "stream false", ns(r), 2),
		("C3 neutral agent", "neutral system prompt, no reasoning_effort", ns(neutral), 2),
		("C4 neutral agent streamed", "as C3, streamed", st(neutral), 2),
		("C5 no reasoning_effort", "drop reasoning_effort", ns(no_effort), 1),
		("C6 m2 system prompt", "deepseek's longer system prompt", ns(set_system(r, m2_sys)), 1),
		("C7 two tools", "tools = terminal + write_file", ns(two_tools), 1),
	]
	OUT.parent.mkdir(exist_ok=True)
	with OUT.open("a") as f:
		for name, change, req, n in cells:
			for i in range(n):
				res = call(req)
				row = {"cell": name, "change": change, "i": i, "ts": time.time(), "n_tools": len(req["tools"]), "stream": req.get("stream", False), **res}
				f.write(json.dumps(row) + "\n")
				print(f"{name:28} #{i} {res['status']} {res.get('kind'):10} finish={res.get('finish_reason')} tools={res.get('tool_names')} {res.get('content_head', '')[:80]!r}")


if __name__ == "__main__":
	main()
