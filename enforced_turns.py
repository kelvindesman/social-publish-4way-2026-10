"""Classify every model reply in the exploratory A4-enf runs (deviation 15).

  python3 -I enforced_turns.py  -> out/enforced-turns.json

Per run and per cell: how each agent turn came back from llama-4-scout. Kinds:
  tool_calls  proper OpenAI tool_calls (the agent can act on them)
  text_tool   a tool call written as plain text in content, e.g. "[terminal: curl ...]"
  text        other non-empty content
  empty       no content and no tool_calls
Auxiliary calls Hermes makes without tools (session title) are counted apart.
Each run also gets an outcome from Hermes's own final message (agent-final.txt / stderr).
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "out"
TEXT_TOOL = re.compile(r"^\s*\[?\s*(terminal|read_file|write_file|patch|search_files|execute_code)\b|\"name\"\s*:\s*\"(terminal|read_file|write_file)\"")


def reply(resp) -> tuple[str, list]:
	"""(content, tool_calls) from a JSON body or an SSE stream."""
	if isinstance(resp, dict):
		m = (resp.get("choices") or [{}])[0].get("message") or {}
		return m.get("content") or "", m.get("tool_calls") or []
	content, calls = "", []
	for line in str(resp or "").splitlines():
		if not line.startswith("data: ") or line.strip() == "data: [DONE]":
			continue
		try:
			d = json.loads(line[6:])
		except json.JSONDecodeError:
			continue
		for c in d.get("choices") or []:
			delta = c.get("delta") or {}
			content += delta.get("content") or ""
			calls += delta.get("tool_calls") or []
	return content, calls


def kind(content: str, calls: list) -> str:
	if calls:
		return "tool_calls"
	if not content.strip():
		return "empty"
	return "text_tool" if TEXT_TOOL.search(content) else "text"


OUTCOMES = (
	("infra_start", ("Gateway connection failed", "Gateway starting: deadline")),
	("gateway_disconnect", ("session_replay_gap",)),
	("context_overflow", ("grown too long",)),
	("write_refused_invalid_json", ("fails .json syntax validation",)),
	("answered_in_chat_not_saved", ("linkedin",)),
)


def outcome(run_dir: Path) -> str:
	if (run_dir / "output.json").exists():
		return "saved_output"
	text = "".join((run_dir / n).read_text() for n in ("agent-final.txt", "agent-stderr.txt") if (run_dir / n).exists())
	for name, marks in OUTCOMES:
		if any(m in text for m in marks):
			return name
	return "no_reply" if "No reply" in text or not text.strip() else "other"


def main() -> None:
	arms = {json.loads(x)["run_id"]: json.loads(x)["arm"] for x in (OUT / "enforced-runs.jsonl").read_text().splitlines() if x.strip()}
	per_run, per_cell = {}, defaultdict(Counter)
	for rid, arm in sorted(arms.items()):
		f = OUT / "transcripts" / f"{rid}.jsonl"
		kinds = []
		if f.exists():
			for line in f.read_text().splitlines():
				r = json.loads(line)
				resp = r.get("response")
				if isinstance(resp, str):
					try:
						resp = json.loads(resp)
					except json.JSONDecodeError:
						pass
				aux = not (r.get("request") or {}).get("tools")
				k = "aux" if aux else kind(*reply(resp))
				kinds.append(k)
				per_cell[arm][k] += 1
		per_run[rid] = {"arm": arm, "turns": kinds, "first_agent_turn": next((k for k in kinds if k != "aux"), None), "outcome": outcome(OUT / "runs" / rid)}
		last = next((k for k in reversed(kinds) if k != "aux"), None)
		# Hermes ends the run when the reply has no tool_calls, so a text-form tool call is the stop.
		if last == "text_tool" and per_run[rid]["outcome"] in ("answered_in_chat_not_saved", "other"):
			per_run[rid]["outcome"] = "stopped_on_text_tool_call"
	first, outs = defaultdict(Counter), defaultdict(Counter)
	for v in per_run.values():
		first[v["arm"]][v["first_agent_turn"]] += 1
		outs[v["arm"]][v["outcome"]] += 1
	res = {"per_cell_turns": {a: dict(c) for a, c in per_cell.items()}, "per_cell_first_turn": {a: dict(c) for a, c in first.items()}, "per_cell_outcome": {a: dict(c) for a, c in outs.items()}, "runs": per_run}
	(OUT / "enforced-turns.json").write_text(json.dumps(res, indent=1))
	print(json.dumps({k: res[k] for k in ("per_cell_turns", "per_cell_first_turn", "per_cell_outcome")}, indent=1))


if __name__ == "__main__":
	main()
