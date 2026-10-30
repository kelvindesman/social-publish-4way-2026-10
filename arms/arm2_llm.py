"""Arm 2a — cron + one LLM call. Fetch deterministically, ask the model once
for all three formats, parse JSON, save. One retry if the JSON is broken."""

import json
import sys

sys.path.insert(0, "/app/common")
from shared import TASK, chat, extract_json, write_output  # noqa: E402
from shared import fetch_post  # noqa: E402


def main(run_id: str, url: str) -> None:
	post = fetch_post(url)
	messages = [
		{"role": "system", "content": "You write social media posts. Reply with JSON only."},
		{"role": "user", "content": f"{TASK}\n\nPost URL: {url}\nTitle: {post['title']}\n\n{post['text']}"},
	]
	for _attempt in range(2):
		reply = chat(run_id, messages, max_tokens=8000, temperature=0.7)
		text = reply["choices"][0]["message"]["content"] or ""
		try:
			write_output(run_id, extract_json(text))
			return
		except (json.JSONDecodeError, ValueError):
			messages += [
				{"role": "assistant", "content": text},
				{"role": "user", "content": "That was not valid JSON. Reply with the JSON object only."},
			]
	raise SystemExit("no valid JSON after retry")


if __name__ == "__main__":
	main(sys.argv[1], sys.argv[2])
