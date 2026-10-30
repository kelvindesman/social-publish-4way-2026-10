# Deterministic vs agentic workflows: cron, cron + LLM, LangGraph, autonomous agent (2026-10)

A pre-registered comparison of four ways to automate one content-pipeline job: turn one
published blog post into three structured outputs (a short post, a thread and a 5-slide
carousel) that pass fixed gates. Design, hypotheses and decision rule were written down before
any counted run: [`PREREGISTRATION.md`](PREREGISTRATION.md). Every later change is listed under
its "Deviations".

This is an anonymized copy. The source site, its posts and everything that could identify it
or the people involved were removed (see "What was removed"). Sources are named `doc-1` to
`doc-5`; `doc-missing` is the 404 fault and `doc-no-numbers` the no-numbers fault.

## Arms

| Arm | What | Who decides the steps | Code |
|---|---|---|---|
| A1 cron | Template fill from title, description, headings. No LLM. | Code | `arms/arm1_cron.py` |
| A2 cron + 1 LLM | One model call for all three formats, one retry on broken JSON | Code | `arms/arm2_llm.py` |
| A3 LangGraph | fetch, draft, validate, critique, revise (max 2) | Code (graph) | `arms/arm3_langgraph.py` |
| A4 Hermes Agent | Goal + terminal and file tools, 15 turns / 600 s cap | Model | `arms/arm4_hermes.sh` |

Models: m1 `@cf/meta/llama-4-scout-17b-16e-instruct`, m2 `@cf/deepseek-ai/deepseek-v4-flash-0731`
(thinking off), both on Cloudflare Workers AI. Hermes Agent pinned at commit
`60f56a6b13c8eb9a9e088c6fc1165257c92f7e11`.

## How it was measured

- **Same meter for every arm.** Every LLM call goes through `proxy/proxy.py`, which logs the
  token usage the provider reported (`out/usage.jsonl`). No arm relies on its own logging.
- **Same input for every arm.** The five source posts were frozen as Markdown before the runs.
- **Hard gates** (`gates.py`, deterministic): JSON schema, platform lengths, the post's link
  present, no number absent from the source, prose score >= 70. Publishable = every gate passes.
- **Faults** (`proxy/proxy.py`, `run_all.py`): a URL that 404s, an injected HTTP 429 on the
  first call, a corrupted first completion, and a post with no numbers. Each fault run is
  classed `stopped_clean`, `crashed`, `recovered` or `published_bad`.
- **Statistics** (`analyze.py`): 95% percentile bootstrap, 10,000 resamples, clustered by
  source; arm differences paired by source.
- **Isolation**: throwaway Docker containers (`docker-compose.yml`, `cleanup.sh`).

## Files

| Path | What |
|---|---|
| `social-publish-4way-2026-10.csv` | one row per counted run: arm, model, fault, tokens, $, gates, outcome |
| `out/runs.jsonl` | one line per counted run (arm, model, fault, exit, seconds, stderr tail) |
| `out/usage.jsonl` | one line per LLM call (tokens, status, injected fault) |
| `out/gates.jsonl` | gate results and fault outcome per run (A4 fault rows corrected by `out/rerun-infra-*.jsonl`) |
| `out/summary.json` | every number cited, with CIs |
| `out/hermes-m1-turns.jsonl` | every Hermes call on llama, classified (empty reply, tool call, text) |
| `hermes-llama-confound.md`, `out/enforced-*.jsonl` | why Hermes failed on llama, with exploratory settings runs |
| `decompose.py`, `out/decompose.json` | model vs architecture variance split |
| `sensitivity.py`, `validity.py` | where the decision rule flips |
| `out/pilot-runs*.jsonl` | harness-debug pilot runs, excluded from all results |

## What was removed

- The source posts, the generated outputs and the full proxy transcripts (they contain the
  source text). Per-call token counts and gate results are kept.
- The human panel pairs and votes, the hand-coded error analysis and the LLM judge text
  (they quote outputs).
- The private analytics export used for the power estimate.
- The site name in the task prompt was replaced with `example.com`; `slop.ts` imports a
  private prose scorer that is not included. Scores it produced are in the CSV (`slop_score`).

So the code shows exactly how each arm ran, but a rerun needs your own source documents.

## Rerun

```bash
export POC_ENV_FILE=/path/to/env   # UPSTREAM_BASE=<OpenAI-compatible base URL>, UPSTREAM_TOKEN=<token>
docker compose build
python3 run_all.py clean && python3 run_all.py faults
python3 -I gates.py && python3 -I analyze.py
./cleanup.sh
```

## Results

See [`RESULTS.md`](RESULTS.md), generated from `out/summary.json`.
