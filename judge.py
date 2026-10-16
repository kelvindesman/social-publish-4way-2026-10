"""Blind quality judge. Two passes, both logged apart from arm spend
(out/judge-usage.jsonl), so judging never inflates an arm's token count.

  text   : the production social critic lenses (src/lib/social/generate/critic-panel.ts),
           scored 1-10 by a judge model from a different family than the generator.
           Outputs are shown without arm labels, in shuffled order.
  visual : each carousel slide PNG (out/renders/<run>/slide-N.png) scored 1-10 by a
           vision model for readability, hierarchy and one-idea-per-slide.

  python3 -I judge.py text|visual  (env: POC_ENV_FILE with UPSTREAM_BASE / UPSTREAM_TOKEN)
"""

import base64
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "out"
TEXT_JUDGE = "@cf/deepseek-ai/deepseek-v4-flash-0731"
VISION_JUDGE = os.environ.get("VISION_JUDGE", "@cf/google/gemma-4-26b-a4b-it")
LENSES = ["hookStrength", "platformNativeFit", "factualAccuracy", "brandSafety", "ctaClarity", "credibilityJournalism"]


def env() -> dict:
	vals = {}
	for line in Path(os.environ["POC_ENV_FILE"]).read_text().splitlines():
		k, _, v = line.partition("=")
		vals[k] = v
	return vals


def call(e: dict, model: str, messages: list, kind: str, ref: str, max_tokens: int = 700) -> str:
	body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0}
	if "deepseek" in model:  # same setting as the arms (PREREGISTRATION.md, Deviations 1)
		body["chat_template_kwargs"] = {"thinking": False}
	req = urllib.request.Request(
		e["UPSTREAM_BASE"] + "/chat/completions",
		data=json.dumps(body).encode(),
		headers={
			"Content-Type": "application/json",
			"User-Agent": "lokerdollar-research-judge/1.0",
			"Authorization": f"Bearer {e['UPSTREAM_TOKEN']}",
			"cf-aig-authorization": f"Bearer {e['UPSTREAM_TOKEN']}",
		},
	)
	t0 = time.time()
	for attempt in range(5):  # gateway 429s under load: back off and retry
		try:
			r = json.loads(urllib.request.urlopen(req, timeout=300).read())
			break
		except urllib.error.HTTPError as ex:
			if ex.code != 429 or attempt == 4:
				raise
			time.sleep(10 * (attempt + 1))
	u = r.get("usage") or {}
	with (OUT / "judge-usage.jsonl").open("a") as f:
		f.write(
			json.dumps(
				{
					"kind": kind,
					"ref": ref,
					"model": model,
					"ms": round((time.time() - t0) * 1000),
					"prompt_tokens": u.get("prompt_tokens"),
					"completion_tokens": u.get("completion_tokens"),
				}
			)
			+ "\n"
		)
	return r["choices"][0]["message"]["content"] or ""


def parse(text: str) -> dict:
	text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.M)
	return json.loads(text[text.find("{") : text.rfind("}") + 1])


def text_pass(e: dict) -> None:
	runs = [json.loads(x) for x in (OUT / "runs.jsonl").read_text().splitlines()]
	runs = [r for r in runs if r["fault"] == "none"]  # quality is judged on clean runs only
	sources = {json.loads(f.read_text())["url"]: json.loads(f.read_text()) for f in (OUT / "sources").glob("*.json")}
	done = set()
	dest = OUT / "judge-text.jsonl"
	if dest.exists():
		done = {j["run_id"] for x in dest.read_text().splitlines() if "mean" in (j := json.loads(x))}
	random.Random(42).shuffle(runs)
	for run in runs:
		p = OUT / "runs" / run["run_id"] / "output.json"
		if run["run_id"] in done or not p.exists():
			continue
		src = sources[run["source"]]
		prompt = (
			"You judge social media drafts for a remote-jobs site. Score each lens 1-10 "
			f"({', '.join(LENSES)}). factualAccuracy: every claim must be traceable to the SOURCE. "
			"Score the whole draft set (LinkedIn post, X thread and carousel together) once per lens. Reply JSON only, "
			'exactly these keys: {"scores": {' + ", ".join(f'"{k}": n' for k in LENSES) + '}, "note": "<one sentence>"}.\n\n'
			f"SOURCE (excerpt):\n{src['text'][:6000]}\n\nDRAFT:\n{p.read_text()[:6000]}"
		)
		try:
			v = parse(call(e, TEXT_JUDGE, [{"role": "user", "content": prompt}], "text", run["run_id"]))
			scores = {k: float(v["scores"][k]) for k in LENSES}
			row = {"run_id": run["run_id"], "scores": scores, "mean": round(sum(scores.values()) / len(LENSES), 2), "note": v.get("note", "")}
		except Exception as ex:  # noqa: BLE001 - research script: record and move on
			row = {"run_id": run["run_id"], "error": str(ex)[:200]}
		with dest.open("a") as f:
			f.write(json.dumps(row) + "\n")
		print("text", run["run_id"], row.get("mean", row.get("error")), flush=True)


def visual_pass(e: dict) -> None:
	dest = OUT / "judge-visual.jsonl"
	done = set()
	if dest.exists():
		done = {j["run_id"] for x in dest.read_text().splitlines() if "overall" in (j := json.loads(x))}
	clean = {json.loads(x)["run_id"] for x in (OUT / "runs.jsonl").read_text().splitlines() if json.loads(x)["fault"] == "none"}
	for d in sorted((OUT / "renders").iterdir()):
		if d.name in done or d.name not in clean:
			continue
		content: list = [
			{
				"type": "text",
				"text": "These are the 5 slides of one Instagram/LinkedIn carousel. Score 1-10: readability "
				"(text size, density), hierarchy (title vs body), oneIdeaPerSlide, overall. Reply JSON only: "
				'{"readability": n, "hierarchy": n, "oneIdeaPerSlide": n, "overall": n}.',
			}
		]
		for png in sorted(d.glob("slide-*.png")):
			b64 = base64.b64encode(png.read_bytes()).decode()
			content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
		try:
			v = parse(call(e, VISION_JUDGE, [{"role": "user", "content": content}], "visual", d.name, max_tokens=4000))
			row = {"run_id": d.name, **{k: float(v[k]) for k in ("readability", "hierarchy", "oneIdeaPerSlide", "overall")}}
		except Exception as ex:  # noqa: BLE001
			row = {"run_id": d.name, "error": str(ex)[:200]}
		with dest.open("a") as f:
			f.write(json.dumps(row) + "\n")
		print("visual", d.name, row.get("overall", row.get("error")), flush=True)


if __name__ == "__main__":
	{"text": text_pass, "visual": visual_pass}[sys.argv[1]](env())
