"""Rebuild the Hermes-on-llama-4-scout confound counts from the proxy transcripts.

Usage (stdlib only, reads untrusted data, never executes it):
    tar -xzf out/transcripts.tar.gz -C <empty dir>
    python3 -I hermes_confound.py <empty dir>/transcripts

Reads out/runs.jsonl for the list of A4 runs, classifies every model reply that
Hermes received, writes out/hermes-m1-turns.jsonl (one line per A4-m1 turn) and
prints the counts and the m1-vs-m2 request-shape comparison used in
hermes-llama-confound.md.
"""

import collections
import glob
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_NAMES = ("patch", "read_file", "search_files", "terminal", "write_file", "tool_search", "tool_describe", "tool_call")
TEXT_TOOL_RE = re.compile(
	r"(^|\n)\s*\[(%s)\s*[:(]|<\|python_start\|>|<function[=>]|\"name\"\s*:\s*\"(%s)\"" % ("|".join(TOOL_NAMES), "|".join(TOOL_NAMES))
)
TRUNC = 20000  # proxy keeps only the last 20,000 chars of a streamed reply


def parse_reply(resp: str, stream: bool) -> dict:
	out = {"content": "", "tool_calls": [], "finish": None, "usage": None, "stop_reasons": [], "truncated": False}
	if stream:
		out["truncated"] = len(resp) >= TRUNC or not resp.startswith("data: {")
		calls: dict = {}
		for line in resp.splitlines():
			if not line.startswith("data:"):
				continue
			data = line[5:].strip()
			if data == "[DONE]":
				continue
			try:
				j = json.loads(data)
			except json.JSONDecodeError:
				continue
			u = j.get("usage")
			if u and u.get("completion_tokens"):
				out["usage"] = u
			for ch in j.get("choices") or []:
				d = ch.get("delta") or {}
				out["content"] += d.get("content") or ""
				for t in d.get("tool_calls") or []:
					e = calls.setdefault(t.get("index", 0), {"name": "", "arguments": ""})
					f = t.get("function") or {}
					e["name"] += f.get("name") or ""
					e["arguments"] += f.get("arguments") or ""
				if ch.get("finish_reason"):
					out["finish"] = ch["finish_reason"]
				if ch.get("stop_reason") is not None:
					out["stop_reasons"].append(ch["stop_reason"])
		out["tool_calls"] = list(calls.values())
		return out
	try:
		j = json.loads(resp)
	except json.JSONDecodeError:
		return out
	out["usage"] = j.get("usage")
	ch = (j.get("choices") or [{}])[0]
	m = ch.get("message") or {}
	out["content"] = m.get("content") or ""
	out["finish"] = ch.get("finish_reason")
	out["tool_calls"] = [{"name": t["function"]["name"], "arguments": t["function"]["arguments"]} for t in m.get("tool_calls") or []]
	if ch.get("stop_reason") is not None:
		out["stop_reasons"].append(ch["stop_reason"])
	return out


def classify(row: dict) -> dict:
	q = row.get("request") or {}
	stream = bool(q.get("stream"))
	is_tool_turn = bool(q.get("tools"))
	rec = {"status": row.get("status"), "stream": stream, "tool_turn": is_tool_turn, "injected": row.get("injected")}
	if row.get("status") != 200:
		rec.update(kind="error_status", finish=None, has_tool_calls=False, ctok=None, notes=f"HTTP {row.get('status')} ({row.get('injected') or 'upstream'})")
		return rec
	if row.get("injected") == "fjson":
		rec.update(kind="injected_fjson", finish="stop", has_tool_calls=False, ctok=None, notes="proxy replaced the real reply with broken JSON text; original reply not kept")
		return rec
	p = parse_reply(row.get("response") or "", stream)
	ctok = (p["usage"] or {}).get("completion_tokens")
	c = p["content"]
	notes = []
	if p["truncated"]:
		notes.append("transcript keeps only the last 20,000 chars of this stream")
	if p["stop_reasons"]:
		notes.append(f"stop_reason={sorted(set(p['stop_reasons']))}")
	if not is_tool_turn:
		kind = "aux_no_tools"  # Hermes's session-title call: no tools, response_format json_schema
		notes.append("session-title call, not an agent turn")
	elif p["tool_calls"]:
		kind = "tool_calls"
		notes.append("calls=" + ",".join(t["name"] for t in p["tool_calls"]))
	elif p["finish"] == "length":
		kind = "length"
		if TEXT_TOOL_RE.search(c):
			notes.append("text tool calls in content, shape=" + repr(c[:80]))
		elif not c.strip():
			notes.append(f"{ctok} completion tokens billed, 0 content chars delivered")
	elif not c.strip():
		kind = "empty_with_tokens" if ctok else "empty"
		if ctok:
			notes.append(f"{ctok} completion tokens billed, 0 content chars, 0 tool_calls delivered")
	elif TEXT_TOOL_RE.search(c):
		kind = "text_tool_call"
		notes.append("shape=" + repr(c[:80]))
	elif any(k in c for k in ('"linkedin"', '"x_thread"', '"carousel"', '"title"')):
		kind = "answer_as_text"
		notes.append("final JSON returned as message text instead of a write_file call")
	else:
		kind = "prose"
		notes.append("text=" + repr(c[:80]))
	rec.update(kind=kind, finish=p["finish"], has_tool_calls=bool(p["tool_calls"]), ctok=ctok, notes="; ".join(notes))
	return rec


def norm_system(s: str) -> str:
	s = re.sub(r"^Model: .*$", "Model: <model>", s, flags=re.M)
	s = re.sub(r"^Conversation started: .*$", "Conversation started: <date>", s, flags=re.M)
	return s


def sha(x) -> str:
	return hashlib.sha256(json.dumps(x, sort_keys=True).encode() if not isinstance(x, str) else x.encode()).hexdigest()[:12]


def req_shape(q: dict) -> dict:
	msgs = q.get("messages") or []
	sysmsg = next((m.get("content") or "" for m in msgs if m.get("role") == "system"), "")
	tools = q.get("tools") or []
	return {
		"keys": ",".join(sorted(k for k in q if k not in ("messages", "tools", "model"))),
		"n_tools": len(tools),
		"tools_bytes": len(json.dumps(tools)),
		"tools_sha": sha(tools),
		"system_chars": len(sysmsg),
		"system_sha_normalized": sha(norm_system(sysmsg)),
		"tool_choice": q.get("tool_choice"),
		"parallel_tool_calls": q.get("parallel_tool_calls"),
		"stream": q.get("stream"),
		"max_tokens": q.get("max_tokens"),
		"reasoning_effort": q.get("reasoning_effort"),
		"temperature": q.get("temperature"),
		"chat_template_kwargs": json.dumps(q.get("chat_template_kwargs")),
	}


def main() -> None:
	if len(sys.argv) < 2:
		sys.exit("usage: python3 -I hermes_confound.py <extracted transcripts dir>")
	tdir = sys.argv[1]
	runs = [json.loads(line) for line in open(os.path.join(HERE, "out", "runs.jsonl"))]
	a4 = [r for r in runs if r["arm"] == "A4-hermes" and r["run_id"].startswith("r")]
	out_rows = []
	per_model = {"m1": collections.Counter(), "m2": collections.Counter()}
	run_summary = {"m1": collections.Counter(), "m2": collections.Counter()}
	shapes = {"m1": collections.defaultdict(collections.Counter), "m2": collections.defaultdict(collections.Counter)}
	user_norm = {"m1": collections.Counter(), "m2": collections.Counter()}
	identical_retries = collections.Counter()
	for r in a4:
		m, rid = r["model"], r["run_id"]
		group = "clean" if r["fault"] == "none" else "fault:" + r["fault"]
		path = os.path.join(tdir, rid + ".jsonl")
		if not os.path.exists(path):
			run_summary[m][(group, "no_transcript (no LLM call reached the proxy)")] += 1
			if m == "m1":
				out_rows.append({"run_id": rid, "turn": None, "finish_reason": None, "has_tool_calls": False, "content_kind": "no_llm_call", "notes": "no transcript: Hermes never reached the proxy; agent-final.txt: " + open(os.path.join(HERE, "out", "runs", rid, "agent-final.txt")).read().strip()[:120].replace("\n", " ")})
			continue
		rows = [json.loads(line) for line in open(path)]
		kinds = []
		tool_reqs = []
		for i, row in enumerate(rows):
			c = classify(row)
			kinds.append(c["kind"])
			q = row.get("request") or {}
			if q.get("tools"):
				tool_reqs.append(q)
				for k, v in req_shape(q).items():
					shapes[m][k][str(v)] += 1
				um = next((x.get("content") for x in q.get("messages", []) if x.get("role") == "user"), "")
				um = re.sub(r"/out/runs/[^/]+/output\.json", "/out/runs/<run>/output.json", um or "")
				user_norm[m][sha(um)] += 1
			key = (group, c["kind"])
			per_model[m][key] += 1
			if m == "m1":
				out_rows.append({"run_id": rid, "turn": i, "finish_reason": c["finish"], "has_tool_calls": c["has_tool_calls"], "content_kind": c["kind"], "notes": (f"stream={c['stream']}; completion_tokens={c['ctok']}; " + c["notes"]).strip("; ")})
		# identical-request retries: same messages array resent unchanged
		if m == "m1":
			sigs = [sha(q.get("messages")) for q in tool_reqs]
			identical_retries[(group, f"{len(sigs)} tool requests, {len(set(sigs))} distinct")] += 1
		agent_kinds = [k for k in kinds if k != "aux_no_tools"]
		got_tool = "tool_calls" in agent_kinds
		run_summary[m][(group, "ever_got_tool_calls" if got_tool else "never_got_tool_calls")] += 1
	with open(os.path.join(HERE, "out", "hermes-m1-turns.jsonl"), "w") as f:
		for row in out_rows:
			f.write(json.dumps(row) + "\n")

	print("# Reply classification per turn (A4, run ids starting 'r')")
	for m in ("m1", "m2"):
		print(f"\n## {m}")
		for (g, k), n in sorted(per_model[m].items()):
			print(f"  {g:14s} {k:20s} {n}")
		print("  -- per run")
		for (g, k), n in sorted(run_summary[m].items()):
			print(f"  {g:14s} {k:45s} {n}")
	print("\n## m1 requests per run (identical retries)")
	for (g, k), n in sorted(identical_retries.items()):
		print(f"  {g:14s} {k:40s} {n}")
	print("\n# Request shape of every tool-bearing request Hermes sent (value: count)")
	for k in shapes["m1"]:
		print(f"  {k:22s} m1={dict(shapes['m1'][k])}  m2={dict(shapes['m2'][k])}")
	print(f"  {'user_msg_sha(norm)':22s} m1 distinct={len(user_norm['m1'])}  m2 distinct={len(user_norm['m2'])}")

	m1_clean = [r for r in out_rows if r["run_id"].split("-")[1] != "s" and "-none-" in r["run_id"] and r["content_kind"] not in ("aux_no_tools",)]
	ctoks = [int(re.search(r"completion_tokens=(\d+)", r["notes"]).group(1)) for r in m1_clean if r["content_kind"] == "empty_with_tokens"]
	if ctoks:
		ctoks.sort()
		print(f"\nm1 clean empty_with_tokens: n={len(ctoks)} completion_tokens min={ctoks[0]} median={ctoks[len(ctoks) // 2]} max={ctoks[-1]}")
	print(f"\nwrote {os.path.join(HERE, 'out', 'hermes-m1-turns.jsonl')} ({len(out_rows)} lines)")

	# Pilot debug probes in the same archive (not counted, not Hermes-issued unless named A4-hermes)
	print("\n# Pilot probes in the archive (excluded from results)")
	for p in sorted(glob.glob(os.path.join(tdir, "p9-*.jsonl"))):
		for i, row in enumerate(json.loads(line) for line in open(p)):
			q = row.get("request") or {}
			if not q.get("tools") or "deepseek" in str(q.get("model")):
				continue
			c = classify(row)
			print(f"  {os.path.basename(p)[:-6]:38s} t{i} stream={c['stream']} n_tools={len(q['tools'])} max_tokens={q.get('max_tokens')} -> {c['kind']} finish={c['finish']} ctok={c['ctok']} {c['notes'][:110]}")


if __name__ == "__main__":
	main()
