# Pre-registration: cron vs cron+LLM vs LangGraph vs autonomous agent for social publishing

Committed 2026-10-16, before any counted run. Pilot runs (`out/pilot-runs.jsonl`, run ids starting `p`) were used only to debug the harness and are excluded. Any change to this file after the first counted run is listed under "Deviations" at the bottom with its reason.

## Question

When does it pay to move from a plain cron job, to cron plus one LLM call, to an agent framework graph (LangGraph), to an autonomous agent (Hermes Agent), for the job "turn one published blog post into a LinkedIn post, an X thread and a 5-slide carousel, ready to publish"?

## Arms

| Arm | What it is | Who decides the steps |
|---|---|---|
| A1 cron | Template fill from title, description, headings. No LLM. | Code |
| A2 cron + 1 LLM | Fetch in code, one model call for all three formats, one retry if JSON is broken | Code |
| A3 LangGraph | Graph: fetch, draft, validate (code), critique (LLM), revise, max 2 revisions | Code (graph) |
| A4 Hermes Agent | Goal + terminal and file tools, no step script, cap 15 turns / 600 s | Model |
| P production | lokerdollar's live multi-role pipeline (observational only, from PostHog `$ai_generation`) | Code (fixed chain + critic panel) |

NanoClaw was considered for A4 and excluded before data: it is built on the Claude Agent SDK only, needs a host service plus a messaging channel, and has no one-shot mode, so it cannot run the same model or the same task shape.

## Models (crossed with A2, A3, A4)

- M1 `@cf/meta/llama-4-scout-17b-16e-instruct` (the production model for this task)
- M2 `@cf/deepseek-ai/deepseek-v4-flash-0731` (different family, strong tool calling)

Both through the same Cloudflare AI Gateway and the same metering proxy.

## Sample

- 5 real published English posts (`sources.txt`), snapshotted to `out/sources/`.
- Clean runs: 5 sources x 6 reps x 2 models = 60 runs per LLM arm (A2, A3, A4); A1 is deterministic, 5 sources x 2 reps = 10 runs.
- Power: 56 runs per arm detect a 30-point publishable-rate gap (50% vs 80%) at alpha 0.05 with Bonferroni over 6 pairwise tests, power 0.8.
- Fault runs: 4 faults x 4 arms x 2 models x 3 reps (A1 once per model) — see below.
- Arm order rotates per rep. Infra errors not caused by an injected fault (gateway 5xx) are re-run once and logged.

## Fault injection

| Fault | How | Right behaviour |
|---|---|---|
| F404 | Source URL that does not exist | Stop, publish nothing |
| F429 | Proxy returns HTTP 429 on the run's first LLM call | Retry or stop; never publish garbage |
| FJSON | Proxy replaces the run's first completion with broken JSON | Recover or stop |
| FNONUM | Fixture post with no numbers at all | Publish without inventing any number |

Fault outcome classes (coded from transcripts): `stopped_clean`, `recovered`, `published_bad` (output exists but fails a hard gate or invents facts — the silent-failure case), `crashed`.

## Metrics

Primary (decides the verdict):
1. **Publishable rate** per arm = runs passing every hard gate (schema, platform lengths, link present, no number absent from the source, slop score >= 70 with the production scorer).
2. **$ per publishable post** = total token $ at list price / publishable runs.

Secondary:
- Tokens, LLM calls, seconds: p50 / p95 / max, 95% bootstrap CIs (10,000 resamples, clustered by source).
- Human quality: blind pairwise panel (below), Bradley-Terry strength per arm.
- Silent-failure rate under faults (`published_bad` share).
- Total cost of ownership: token $ + retry $ + build effort (our LOC, third-party packages, image size) + maintenance (for P: git fix/revert churn).
- Model vs architecture: share of human-quality variance explained by model vs arm among A2-A4.

## Hypotheses

- H1: A2's publishable rate is within 10 points of A3 and A4 (the extra machinery does not buy publishability).
- H2: A4 uses >= 10x the tokens of A2 at the median and >= 20x at p95.
- H3: Under FNONUM and F404, A4 has a higher `published_bad` rate than A1 and A2 (agents fail silently more often).
- H4: Humans prefer LLM arms over A1 in >= 70% of pairs, with no significant difference among A2-A4.
- H5: Among A2-A4, the model explains more quality variance than the architecture.

## Decision rule (fixed now)

Recommend the cheapest arm unless a more complex arm beats it on BOTH:
- publishable rate by >= 15 points with the 95% CI of the difference above 0, and
- human preference >= 60% in head-to-head pairs,
and its $ per publishable post is <= 3x the cheaper arm's. Ties go to the simpler arm.

## Human panel

- 3 raters, at least 1 non-technical. Raters see two outputs for the same source post, no arm or model labels, random left/right, and pick the one they would publish (or "neither").
- 40 pairs per rater, balanced across the 6 arm pairings.
- Agreement: Krippendorff's alpha. If alpha < 0.4, the human result is reported as "raters disagreed" and not used in the verdict.
- The LLM judge (different model family) is reported only if its per-output score correlates with the human Bradley-Terry score at Spearman >= 0.5.

## Live test (exploratory, reported later)

Production social posts drew about 1.2 visitors per post over the last 30 days (`raw/social-traffic-30d-2026-10-16.json`). Detecting a +50% visitors-per-post gap needs about 66 posts per arm. That is weeks of posting, so the live rotation (one UTM campaign per arm, through the existing Zernio account) is a follow-up, published as an update, and does not gate the first article. It only starts with the owner's go-ahead because it posts to the brand's real accounts.

## Outside checks

- Public CSV of every run and a one-command rerun (`docker compose`) so anyone can reproduce.
- Before publishing, the A3 and A4 setups are sent to people who maintain or use LangGraph and Hermes Agent for a fairness review; their comments are quoted or linked.

## Deviations

Made after the pilot, before the first counted run:

1. **M2 runs with thinking off.** In the pilot, deepseek-v4-flash spent its whole token budget on hidden reasoning and returned no answer (1,800 and then 8,000 completion tokens, empty content). The proxy now sends `chat_template_kwargs: {thinking: false}` on every M2 call, for every arm alike. A test call used 40 completion tokens with thinking off and 149 to 1,243 with it on.
2. **Every call gets an 8,000-token output cap.** A2 and A3 set it themselves (it was 1,800). Hermes sends no cap, and Workers AI then stops a reply at 256 tokens, which cut A4's first pilot replies short. The proxy now adds `max_tokens: 8000` to any call that has none. M1 writes about 1,000 tokens per call, so the higher cap changes nothing for it.
3. **The panel uses 42 pairs instead of 40**, so each of the 6 arm pairings gets exactly 7.
4. **A4 setup details found in the pilot.** The pinned Hermes needs Python 3.14 (every core dependency is marked for it). It refuses to run as root, so it runs as a normal user. It reads the run budget from `config.yaml`, so each run writes a fresh config with the same caps (15 turns, 600 s). On M1, Hermes failed in both streaming and non-streaming mode: llama-4-scout returns proper tool calls for a one-tool test, but with Hermes's 8 tools it writes tool calls as plain text or returns nothing. That is a result, not a harness fault, so A4 keeps Hermes's default (streaming).
5. **Source posts are frozen.** The posts carry live counters ("1425 open Engineering roles" at snapshot time, 1427 at run time), so the facts gate flagged numbers that were true when the arm read them. The five posts were saved once as Markdown on 2026-10-16 (`fixtures/en/blog/`), and every arm, Hermes included, now reads that frozen copy. The posts still link to the public URL. The F404 URL has no frozen copy and returns 404 there, as it does on the site. Fault runs are classed `crashed` when stderr ends in an unhandled `...Error:` line, since the Traceback header can fall outside the saved 600-character tail.
6. **The A4 command has no `--usage-file`.** The pinned Hermes version has no such flag. Tokens for A4 come from the proxy, as for every other arm, which the design already planned.
