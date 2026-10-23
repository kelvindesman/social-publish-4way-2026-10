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
- With llama-4-scout, Hermes produced no output in any of the 30 counted runs. Every streamed turn came back empty (finish_reason `stop`, no content, no tool_calls).
- We replayed Hermes's exact first request outside Hermes. Unchanged, llama writes the tool call as text (`[terminal: curl ...]`) or returns an empty stream. With a one-line neutral system prompt, or with the system prompt Hermes builds for deepseek (the one that includes the "Tool-use enforcement" block), llama returns proper `tool_calls`. Dropping `reasoning_effort` or cutting the tools to two did not help. So the difference seems to be the system prompt Hermes picks for this model.
- We then reran llama inside Hermes with the documented settings, 10 runs each. With `agent.tool_use_enforcement: true` alone, streamed turns were still empty, and with streaming off llama wrote the tool call as text and the run ended. With `execution_guidance: true` as well, llama made real tool calls (23 across the runs), but none of the 10 runs saved output. 4 put the posts in the chat reply instead of the file, 1 had its JSON refused by `write_file`, 2 ran out of context, and 3 lost the gateway. Probe and results: https://github.com/kelvindesman/social-publish-4way-2026-10/blob/main/hermes-llama-confound.md
- With deepseek-v4-flash, Hermes was the best arm we tested: 28 of 30 runs passed every gate.
- Workers AI caps replies at 256 tokens when `max_tokens` is not sent, so our proxy sets 8,000 for every arm.

- Wrapper script: https://github.com/kelvindesman/social-publish-4way-2026-10/blob/main/arms/arm4_hermes.sh
- Dockerfile: https://github.com/kelvindesman/social-publish-4way-2026-10/blob/main/Dockerfile.hermes
- Every model call, request and response: https://github.com/kelvindesman/social-publish-4way-2026-10/blob/main/out/transcripts.tar.gz

Questions:
1. Is this how you'd run Hermes for a one-shot task like this? Are there flags, toolsets or config we're missing?
2. Llama-family names get neither the enforcement nor the execution-guidance block under "auto". Is that deliberate? Would you add llama to the execution-guidance list, as was done for GLM's plain-text tool-call stall (#53847)?
3. For a small model like this, is there a setting we missed that would make it save the file and finish, or is "use a bigger model" the honest answer?

We'll quote or link your reply in the article. Thanks.
