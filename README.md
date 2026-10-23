# Cron vs cron + LLM vs LangGraph vs autonomous agent, for social publishing (2026-10)

> Public mirror of the study folder from lokerdollar.com's private repo. Everything needed to rerun is here except `slop.ts`, which imports the site's prose scorer; the slop scores it produced are in `out/slop.jsonl`.

Pre-registered, measured comparison of four ways to automate one job: turn one published
lokerdollar.com blog post into a LinkedIn post, an X thread and a 5-slide carousel that are
ready to publish. Design, hypotheses and decision rule were committed before any counted run:
[`PREREGISTRATION.md`](PREREGISTRATION.md) (first commit bc74e0a30, 2026-10-16 04:39 +0700;
every later change is listed under its "Deviations").

Collected 2026-10-16 by Claude Code for lokerdollar.com.

## Arms

| Arm | What | Who decides the steps | Our code |
|---|---|---|---|
| A1 cron | Template fill from title, description, headings. No LLM. | Code | `arms/arm1_cron.py` |
| A2 cron + 1 LLM | One model call for all three formats, one retry on broken JSON | Code | `arms/arm2_llm.py` |
| A3 LangGraph | fetch, draft, validate, critique, revise (max 2) | Code (graph) | `arms/arm3_langgraph.py` |
| A4 Hermes Agent | Goal + terminal and file tools, 15 turns / 600 s cap | Model | `arms/arm4_hermes.sh` |
| P production | lokerdollar's live multi-role pipeline, observational | Code | `out/arm2b-prod-baseline.json` |

Models: M1 `@cf/meta/llama-4-scout-17b-16e-instruct` (the production model), M2
`@cf/deepseek-ai/deepseek-v4-flash-0731` (thinking off, see Deviations), both on Cloudflare
Workers AI through one AI Gateway. Hermes Agent pinned at commit
`60f56a6b13c8eb9a9e088c6fc1165257c92f7e11`.

## How it was measured

- **Same meter for every arm.** Every LLM call goes through `proxy/proxy.py`, which logs the
  token usage the provider reported (`out/usage.jsonl`) and keeps full request/response
  transcripts (`out/transcripts.tar.gz`). No arm relies on its own logging.
- **Same input for every arm.** The five source posts were frozen as Markdown on 2026-10-16
  (`fixtures/en/blog/`) because the live pages carry counters that change between runs.
- **Hard gates** (`gates.py`, $0, deterministic): JSON schema, platform lengths, the post's
  link present, no number absent from the source, production slop score >= 70
  (`slop.ts`, the site's own `scoreProse`). Publishable = every gate passes.
- **Faults** (`proxy/proxy.py`, `run_all.py`): a URL that 404s, an injected HTTP 429 on the
  first call, a corrupted first completion, and a post with no numbers at all
  (`fixtures/no-numbers-post.md`). Each fault run is classed `stopped_clean`, `crashed`,
  `recovered` or `published_bad`.
- **Quality**: an LLM judge (`judge.py`; text by deepseek-v4-flash with the production critic
  lenses, carousel slides by gemma-4 vision on PNGs from `render.py`), logged separately so
  judging never adds to an arm's cost. The judge counts only if it agrees with the blind human
  panel (`panel.py`, Spearman >= 0.5), per the pre-registration.
- **Statistics** (`analyze.py`): 95% percentile bootstrap, 10,000 resamples, clustered by
  source post; arm differences paired by source.
- **Isolation**: everything ran in throwaway Docker containers (`docker-compose.yml`,
  `cleanup.sh`); nothing was installed on the host.

## Rerun

```bash
export POC_ENV_FILE=/path/to/env   # UPSTREAM_BASE=<OpenAI-compatible base URL>, UPSTREAM_TOKEN=<token>
docker compose build
python3 run_all.py clean && python3 run_all.py faults
npx tsx slop.ts && python3 -I gates.py
docker compose run --rm -T --no-deps py python /app/render.py
python3 -I judge.py text && python3 -I judge.py visual
python3 -I analyze.py              # -> out/summary.json and social-publish-4way-2026-10.csv
./cleanup.sh
```

## Files

| Path | What |
|---|---|
| `out/runs.jsonl` | one line per counted run (arm, model, fault, exit, seconds) |
| `out/usage.jsonl` | one line per LLM call (tokens, status, injected fault) |
| `out/gates.jsonl` | gate results and fault outcome class per run |
| `out/judge-*.jsonl`, `out/judge-usage.jsonl` | LLM judge scores and the judge's own token use |
| `out/summary.json` | every number cited, with CIs |
| `out/runs/<id>/` | each run's output (and Hermes's stdout/stderr) |
| `out/panel-pairs.json` / `out/panel-key.json` | the 42 blind pairs shown to raters / which arm wrote which side |
| `out/pilot-runs*.jsonl` | harness-debug pilot runs, excluded from all results |
| `raw/` | 30-day social traffic by platform, social pipeline git churn |
| `error-analysis.md`, `error-coding/`, `out/error-codes.jsonl` | hand-coded failure modes per run (2026-10-23) |
| `panel-raw/`, `out/panel-votes.json`, `out/panel-summary.json` | one-rater human panel: raw export, votes, Bradley-Terry summary |
| `decompose.py`, `out/decompose.json` | model vs architecture variance split |
| `sensitivity.py`, `validity.py` | where the decision rule flips |
| `hermes-llama-confound.md`, `out/enforced-*.jsonl` | why Hermes failed on llama, with the exploratory settings runs |
| `repeat_hook.py`, `out/repeat-hook.json` | same figure repeated in the hook and the next paragraph |
| `fairness-review/` | requests to LangGraph and Hermes users to review our setup |
| `social-publish-4way-2026-10.csv` | public per-run CSV (also at https://lokerdollar.com/data/social-publish-4way-2026-10.csv) |

## Results

See [`RESULTS.md`](RESULTS.md), generated from `out/summary.json`; its "Update 2026-10-23" section adds the panel, error analysis, decomposition and Hermes follow-up. Article: https://lokerdollar.com/en/research/cron-vs-llm-vs-langgraph-vs-agent-2026
