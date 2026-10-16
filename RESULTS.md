# Results (2026-10-16)

Every number here comes from `out/summary.json` (`python3 -I analyze.py`). Brackets are 95%
bootstrap CIs (10,000 resamples, clustered by source post). Clean runs only unless a section
says otherwise. Prices are Workers AI list prices at collection time: llama-4-scout $0.27 /
$0.85 and deepseek-v4-flash $0.44 / $1.32 per million input / output tokens.

## Headline

| Arm | Runs | Publishable | $ per publishable post | $ / month at 12 runs/day | Tokens per run p50 / p95 / max | Seconds p50 / p95 | LLM calls p50 / max |
|---|---|---|---|---|---|---|---|
| A1 cron | 10 | 100% [100, 100] | $0 | $0 | 0 | 1.0 / 1.3 | 0 |
| A2 cron + 1 LLM | 60 | 70% [52, 87] | $0.0026 [0.0021, 0.0035] | $0.65 | 3,929 / 4,244 / 4,315 | 13.8 / 47.0 | 1 / 1 |
| A3 LangGraph | 60 | 70% [45, 95] | $0.0081 [0.0058, 0.0129] | $2.04 | 11,601 / 18,538 / 20,809 | 51.4 / 150.6 | 4 / 6 |
| A4 Hermes Agent | 60 | 46.7% [43, 50] | $0.0513 [0.041, 0.063] | $8.62 | 27,301 / 149,424 / 189,512 | 111.8 / 367.9 | 5 / 14 |
| P production (observational) | 76 ticks | not gated | $0.0099 per tick (median) | $0.94 over the 76 ticks | 83,342 (median) | n/a | 51 (median) |

P comes from PostHog `$ai_generation` events for the live pipeline, 2026-10-02 to 2026-10-16
(`out/arm2b-prod-baseline.json`). It has no per-run trace id, so one clock hour stands for one
run, and 24% of its calls failed and were retried on another model. It is not comparable on
publishability and is shown for scale only.

## Why runs failed the gates

Gate failures per arm (a run can fail several):

| Arm | schema | lengths | link | facts (number not in source) | slop |
|---|---|---|---|---|---|
| A1 | 0 | 0 | 0 | 0 | 0 |
| A2 | 0 | 9 | 4 | 5 | 0 |
| A3 | 0 | 5 | 7 | 9 | 0 |
| A4 | 30 | 30 | 30 | 32 | 30 |

A4's 30 schema failures are the 30 llama-4-scout runs: Hermes produced no output file in any
of them (completed rate 50%). On deepseek-v4-flash, A4 was the best arm: 28 of 30 publishable
(93.3%) at $0.0439 per publishable post.

By model:

| Arm | llama-4-scout publishable | $ / publishable | deepseek-v4-flash publishable | $ / publishable |
|---|---|---|---|---|
| A2 | 80% | $0.0016 | 60% | $0.0040 |
| A3 | 83% | $0.0047 | 57% | $0.0131 |
| A4 | 0% | n/a | 93.3% | $0.0439 |

## Paired differences (same source post)

| Comparison | Publishable difference | Median token ratio | p95 token ratio |
|---|---|---|---|
| A2 vs A1 | -30 pts [-48, -13] | n/a (A1 uses none) | n/a |
| A3 vs A2 | 0 pts [-13, +8] | 2.95x | 4.37x |
| A4 vs A2 | -23 pts [-38, -7] | 6.95x | 35.2x |
| A4 vs A3 | -23 pts [-45, -2] | 2.35x | 8.06x |

## Faults (6 runs per LLM arm per fault, 3 reps x 2 models; A1 once per model)

| Arm | F404 missing post | F429 rate limit | FJSON broken first reply | FNONUM post without numbers |
|---|---|---|---|---|
| A1 | crashed 1 | not applicable | not applicable | recovered 1 |
| A2 | crashed 6 | crashed 6 | recovered 6 | recovered 3, published_bad 3 |
| A3 | crashed 6 | recovered 6 | published_bad 6 | recovered 1, published_bad 5 |
| A4 | stopped_clean 6 | recovered 2, stopped_clean 4 | stopped_clean 6 | stopped_clean 6 |

- No arm invented a number on FNONUM. Every `published_bad` there failed the length or link
  gate, not the facts gate.
- A3's six FJSON `published_bad` runs all failed the link gate.
- A3 survived F429 because `ChatOpenAI` retries by default; A2's single `urllib` call does not.
- A4's `stopped_clean` includes the llama-4-scout runs, which produce nothing with or without
  a fault. On FNONUM, stopping is safe but does not do the job.

## Quality (LLM judge, provisional)

| Arm | Text quality, 1-10 (deepseek judge, production critic lenses) | Carousel, 1-10 (gemma-4 vision on rendered PNGs) | Carousel fits | Followed brief |
|---|---|---|---|---|
| A1 | 7.18 | 4.60 | 100% | 0% |
| A2 | 8.25 | 9.13 | 100% | 38% |
| A3 | 8.19 | 9.08 | 100% | 43% |
| A4 | 8.41 | 8.97 | 50% | 50% |

The judge is reported only if it agrees with the blind human panel (Spearman >= 0.5,
pre-registered). The panel (42 pairs, 3 raters) has not finished, so these scores are
provisional. 2 text and 1 visual judgement failed after retries and are missing.

Variance explained (eta squared) among A2-A4: text quality, model 0.357 vs arm 0.057;
publishable, model 0.026 vs arm 0.052.

## Build and running cost

| Arm | Our code (lines) | Third-party packages | Image size |
|---|---|---|---|
| A1 | 27 | 0 | 191 MB (shared Python image) |
| A2 | 26 | 0 | 191 MB (shared) |
| A3 | 113 | 43 | 243 MB |
| A4 | 27 | 67 | 639 MB |

Plus 65 lines of shared code (fetch, prompt, output schema). Experiment token spend
$2.18; judging used 538 calls and 1.23M tokens, logged apart from the arms.

## Hypotheses

- **H1** (A2 within 10 points of A3 and A4): A3 point estimate 0, but the CI [-13, +8] does
  not rule out a 13-point gap. A4 is 23 points *below* A2. The extra machinery did not buy
  publishability; for A4 it cost some.
- **H2** (A4 >= 10x A2 tokens at median, >= 20x at p95): median 6.95x, not met; p95 35.2x, met.
- **H3** (A4 fails silently more often under FNONUM and F404): rejected. A4 had no
  `published_bad` run; A2 had 3 and A3 had 5 on FNONUM.
- **H4** (humans prefer LLM arms over A1): pending the panel.
- **H5** (model explains more quality variance than architecture): supported by the judge
  (0.357 vs 0.057), pending the judge's check against the panel.

## Verdict under the pre-registered decision rule

The rule: recommend the cheapest arm unless a more complex arm beats it by >= 15 publishable
points with the CI above 0, AND wins >= 60% of human pairs, AND costs <= 3x per publishable post.

- No arm beats A1 on publishable rate (every difference is negative), so the rule picks
  **A1 cron**. The panel cannot change this, since both conditions must hold.
- Among the arms that use an LLM, nothing beats A2 on publishable rate (A3 +0, A4 -23), so
  **A2 cron + 1 LLM** is the LLM pick.

Caveat the rule does not capture: A1 passes every gate because it copies the source, and it
never follows the brief (0%). The gates measure "safe to publish", not "worth publishing".
That is what the human panel is for, and why H4 is reported separately when it lands.
