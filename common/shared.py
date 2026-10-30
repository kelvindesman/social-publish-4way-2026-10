"""Shared pieces every arm uses: the task spec, the blog-post fetcher, a tiny
OpenAI-compatible client, and the output writer. Stdlib only, so arms 1 and 2a
need no third-party packages at all.
"""

import html
import json
import os
import re
import urllib.request
from pathlib import Path

MODEL = os.environ.get("MODEL", "@cf/meta/llama-4-scout-17b-16e-instruct")
OUT = Path(os.environ.get("OUT_DIR", "/out"))
UTM = "utm_source={platform}&utm_medium=social&utm_campaign=4way-poc"

TASK = """Turn the blog post into social posts for example.com (a job board).
Produce ONE JSON object with exactly these keys:
- "linkedin": string, 600-1800 characters, first line is a hook, ends with the post URL.
- "x_thread": array of 3-6 strings, each <= 270 characters, last one contains the post URL.
- "carousel": array of exactly 5 objects {"title": <= 40 chars, "body": <= 160 chars}; slide 1 = hook, slide 5 = call to action.
Rules: use only facts and numbers that appear in the post. No hashtags spam (max 3). Plain English, no hype words."""


FIXTURES = os.environ.get("FIXTURES_BASE", "http://fixtures:8000")


def fetch_url(url: str) -> str:
	"""Where to read a post from. example.com posts are read from a frozen copy
	(fixtures/en/blog/<slug>.md, saved once with Accept: text/markdown) so live
	counters on the page cannot change between runs. A post with no frozen copy
	404s there, just as it does on the site. Other URLs are fetched as given."""
	prefix = "https://example.com/"
	return f"{FIXTURES}/{url[len(prefix):]}.md" if url.startswith(prefix) else url


def fetch_post(url: str) -> dict:
	"""Fetch a published example.com blog post as Markdown (the site serves
	text/markdown on Accept negotiation) and return title, description, text.
	`url` stays the public URL that the posts link to."""
	req = urllib.request.Request(
		fetch_url(url), headers={"User-Agent": "research-4way/1.0", "Accept": "text/markdown"}
	)
	raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
	meta: dict[str, str] = {}
	body = raw
	m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, flags=re.S)
	if m:
		for line in m.group(1).splitlines():
			k, _, v = line.partition(":")
			meta[k.strip()] = html.unescape(v.strip()).strip("\"")
		body = m.group(2)
	return {
		"url": url,
		"title": meta.get("title", ""),
		"description": meta.get("description", ""),
		"text": body.strip()[:12000],
	}


def chat(run_id: str, messages: list[dict], **kw) -> dict:
	"""One chat completion through the metering proxy. Returns the parsed response."""
	base = os.environ.get("PROXY_BASE", "http://proxy:8080")
	body = {"model": MODEL, "messages": messages, **kw}
	req = urllib.request.Request(
		f"{base}/run/{run_id}/v1/chat/completions",
		data=json.dumps(body).encode(),
		headers={"Content-Type": "application/json"},
		method="POST",
	)
	return json.loads(urllib.request.urlopen(req, timeout=600).read())


def extract_json(text: str) -> dict:
	"""Pull the first JSON object out of a model reply (models love code fences)."""
	text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
	start, end = text.find("{"), text.rfind("}")
	return json.loads(text[start : end + 1])


def write_output(run_id: str, output: dict) -> Path:
	d = OUT / "runs" / run_id
	d.mkdir(parents=True, exist_ok=True)
	p = d / "output.json"
	p.write_text(json.dumps(output, indent=1, ensure_ascii=False))
	return p
