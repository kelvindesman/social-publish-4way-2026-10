"""Arm 1 — good ol' cron. No LLM. Fill fixed templates from the post's own
title, meta description and section headings. What `devto-syndicate` does in prod."""

import re
import sys

sys.path.insert(0, "/app/common")
from shared import UTM, fetch_post, write_output  # noqa: E402


def link(url: str, platform: str) -> str:
	return f"{url}?{UTM.format(platform=platform)}"


def clip(s: str, n: int) -> str:
	return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def main(run_id: str, url: str) -> None:
	post = fetch_post(url)
	heads = [h.strip("# ").strip() for h in re.findall(r"^#{2,3} .+$", post["text"], flags=re.M)][:3]
	bullets = "\n".join(f"• {h}" for h in heads)
	linkedin = f"{post['title']}\n\n{post['description']}\n\nInside:\n{bullets}\n\nRead it: {link(url, 'linkedin')}"
	x_thread = [
		clip(post["title"], 270),
		clip(post["description"], 270),
		clip(f"Full breakdown: {link(url, 'x')}", 270),
	]
	slides = [{"title": clip(post["title"], 40), "body": clip(post["description"], 160)}]
	slides += [{"title": clip(h, 40), "body": "Read the full breakdown on lokerdollar.com"} for h in heads]
	while len(slides) < 4:
		slides.append({"title": "More inside", "body": clip(post["description"], 160)})
	slides.append({"title": "Find remote USD jobs", "body": "Browse live listings at lokerdollar.com"})
	write_output(run_id, {"linkedin": linkedin, "x_thread": x_thread, "carousel": slides[:5]})


if __name__ == "__main__":
	main(sys.argv[1], sys.argv[2])
