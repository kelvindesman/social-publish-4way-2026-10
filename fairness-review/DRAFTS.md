# Fairness review requests (drafts, not sent)

Pre-registration "Outside checks": before the article is published, people who
maintain or use LangGraph and Hermes Agent review how we set up their arm.
These are drafts. They go out only after the owner approves them, from
kelvin@lokerdollar.com, as a GitHub Discussion or the project's community channel.
Code links point at a public mirror of this study folder
(github.com/kelvindesman/social-publish-4way-2026-10), because the main repo is private.

---

## LangGraph (GitHub Discussions, langchain-ai/langgraph)

**Title:** Review request: is this a fair LangGraph setup for a "blog post to social posts" benchmark?

Hi all. We're comparing four ways to turn one blog post into a LinkedIn post, an X thread and a 5-slide carousel: a plain cron job, cron plus one LLM call, a LangGraph graph, and an autonomous agent (Hermes Agent). Same models, same metering proxy, same gates for every arm. The design was pre-registered before any counted run.

Our LangGraph arm is a StateGraph: fetch, draft, validate (code), critique (LLM), revise, with at most 2 revisions and `recursion_limit` 20. It uses `ChatOpenAI` against an OpenAI-compatible Workers AI endpoint (llama-4-scout and deepseek-v4-flash).

- Graph code (about 100 lines): https://github.com/kelvindesman/social-publish-4way-2026-10/blob/main/arms/arm3_langgraph.py
- Pre-registration and deviations: https://github.com/kelvindesman/social-publish-4way-2026-10/blob/main/PREREGISTRATION.md
- Per-run results: https://lokerdollar.com/data/social-publish-4way-2026-10.csv

Two questions:
1. Is there anything in the graph that a LangGraph user would call a strawman, such as a node or edge you'd build differently for this job?
2. Is anything missing that would change publishability or cost, like structured output or a different retry policy?

We'll quote or link your answer in the write-up, including disagreement. Thanks for looking.

---

## Hermes Agent (GitHub Discussions, NousResearch/hermes-agent)

**Title:** Review request: Hermes Agent setup in a pre-registered agent vs pipeline benchmark

Hi all. We ran Hermes Agent (commit 60f56a6) as the "autonomous agent" arm in a benchmark that turns one blog post into social posts. The other arms are a cron job, cron plus one LLM call, and a LangGraph graph.

Setup: Docker on Python 3.14, running as a non-root user, with a fresh `HERMES_HOME` per run. Command: `hermes chat -Q -q <goal> --provider custom --base-url <metering proxy> -m <model> --max-turns 15 --run-budget 600 --yolo --ignore-rules -t terminal,file`, plus a per-run `config.yaml` with the same caps. Models are llama-4-scout-17b and deepseek-v4-flash on Cloudflare Workers AI.

What we saw:
- With llama-4-scout, Hermes gets empty replies or tool calls written as plain text, in both streaming and non-streaming mode. It produced no output in any of the 30 counted runs. The same endpoint returns proper `tool_calls` for a one-tool test.
- With deepseek-v4-flash, Hermes was the best arm we tested: 28 of 30 runs passed every gate.
- Workers AI caps replies at 256 tokens when `max_tokens` is not sent, so our proxy sets 8,000 for every arm.

- Wrapper script: https://github.com/kelvindesman/social-publish-4way-2026-10/blob/main/arms/arm4_hermes.sh
- Dockerfile: https://github.com/kelvindesman/social-publish-4way-2026-10/blob/main/Dockerfile.hermes
- Every model call, request and response: https://github.com/kelvindesman/social-publish-4way-2026-10/blob/main/out/transcripts.tar.gz

Questions:
1. Is this how you'd run Hermes for a one-shot task like this? Are there flags, toolsets or config we're missing?
2. Is the llama-4-scout behaviour a known limitation, or is there a setting that fixes it?

We'll quote or link your reply in the article. Thanks.
