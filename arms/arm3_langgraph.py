"""Arm 3 — agentic framework (LangGraph). A fixed graph with a feedback loop:
fetch -> draft -> validate (code) -> critique (LLM) -> revise -> ... (max 2 revisions).
The graph decides the path; the model never picks its own next step."""

import json
import os
import sys
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

sys.path.insert(0, "/app/common")
from shared import MODEL, TASK, extract_json, fetch_post, write_output  # noqa: E402

MAX_REVISIONS = 2


class State(TypedDict, total=False):
	url: str
	post: dict
	draft: dict
	problems: list[str]
	revisions: int


def make_llm(run_id: str) -> ChatOpenAI:
	return ChatOpenAI(
		model=MODEL,
		base_url=f"{os.environ.get('PROXY_BASE', 'http://proxy:8080')}/run/{run_id}/v1",
		api_key="via-proxy",
		temperature=0.7,
		max_tokens=8000,
	)


def build(run_id: str):
	llm = make_llm(run_id)

	def fetch(s: State) -> State:
		return {"post": fetch_post(s["url"]), "revisions": 0}

	def draft(s: State) -> State:
		p = s["post"]
		msg = llm.invoke(
			[
				("system", "You write social media posts. Reply with JSON only."),
				("user", f"{TASK}\n\nPost URL: {s['url']}\nTitle: {p['title']}\n\n{p['text']}"),
			]
		)
		try:
			return {"draft": extract_json(msg.content)}
		except (json.JSONDecodeError, ValueError):
			return {"draft": {}}

	def validate(s: State) -> State:
		d, problems = s.get("draft") or {}, []
		if not d:
			problems.append("output was not valid JSON")
		else:
			if not 600 <= len(d.get("linkedin", "")) <= 1800:
				problems.append("linkedin must be 600-1800 characters")
			xs = d.get("x_thread") or []
			if not 3 <= len(xs) <= 6 or any(len(t) > 270 for t in xs):
				problems.append("x_thread needs 3-6 tweets, each <= 270 characters")
			cs = d.get("carousel") or []
			if len(cs) != 5 or any(len(c.get("title", "")) > 40 or len(c.get("body", "")) > 160 for c in cs):
				problems.append("carousel needs exactly 5 slides, title <= 40, body <= 160 characters")
		return {"problems": problems}

	def critique(s: State) -> State:
		msg = llm.invoke(
			[
				("system", "You are a strict social media editor. Reply with JSON only."),
				(
					"user",
					"Check this draft against the source post. List concrete problems: invented facts or numbers, "
					'weak hook, unclear call to action. Reply {"problems": ["..."]} (empty list if it is good).\n\n'
					f"SOURCE:\n{s['post']['text'][:6000]}\n\nDRAFT:\n{json.dumps(s['draft'])}",
				),
			]
		)
		try:
			found = extract_json(msg.content).get("problems", [])
		except (json.JSONDecodeError, ValueError):
			found = []
		return {"problems": [str(x) for x in found][:6]}

	def revise(s: State) -> State:
		msg = llm.invoke(
			[
				("system", "You write social media posts. Reply with JSON only."),
				(
					"user",
					f"{TASK}\n\nFix these problems in the draft:\n- "
					+ "\n- ".join(s["problems"])
					+ f"\n\nDRAFT:\n{json.dumps(s['draft'])}\n\nSOURCE:\n{s['post']['text'][:6000]}",
				),
			]
		)
		try:
			new = extract_json(msg.content)
		except (json.JSONDecodeError, ValueError):
			new = s["draft"]
		return {"draft": new, "revisions": s["revisions"] + 1}

	def after_check(s: State) -> str:
		if s["problems"] and s["revisions"] < MAX_REVISIONS:
			return "revise"
		return "next"

	g = StateGraph(State)
	g.add_node("fetch", fetch)
	g.add_node("draft", draft)
	g.add_node("validate", validate)
	g.add_node("critique", critique)
	g.add_node("revise", revise)
	g.set_entry_point("fetch")
	g.add_edge("fetch", "draft")
	g.add_edge("draft", "validate")
	g.add_conditional_edges("validate", after_check, {"revise": "revise", "next": "critique"})
	g.add_conditional_edges("critique", after_check, {"revise": "revise", "next": END})
	g.add_edge("revise", "validate")
	return g.compile()


def main(run_id: str, url: str) -> None:
	final = build(run_id).invoke({"url": url}, {"recursion_limit": 20})
	if not final.get("draft"):
		raise SystemExit("no draft")
	write_output(run_id, final["draft"])


if __name__ == "__main__":
	main(sys.argv[1], sys.argv[2])
