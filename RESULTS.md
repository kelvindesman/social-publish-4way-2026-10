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
| A4 | stopped_clean 6 | recovered 3, stopped_clean 3 | infra_error 2, stopped_clean 4 | infra_error 1, recovered 3, stopped_clean 2 |

- No arm invented a number on FNONUM. Every `published_bad` there failed the length or link
  gate, not the facts gate.
- A3's six FJSON `published_bad` runs all failed the link gate.
- A3 survived F429 because `ChatOpenAI` retries by default; A2's single `urllib` call does not.
- A4's `stopped_clean` includes the llama-4-scout runs, which produce nothing with or without
  a fault. On FNONUM, stopping is safe but does not do the job.
- A4 row corrected 2026-10-23 (PREREGISTRATION.md deviation 9). 8 A4 fault runs had never
  reached the model: Hermes's own gateway timed out at start-up. The design re-runs infra
  errors once, so they were re-run. 4 recovered (all deepseek-v4-flash), 1 stopped cleanly,
  and 3 failed the same way again; those 3 are `infra_error` and count as neither outcome.
  Before the fix, the table showed A4 F429 recovered 2 / stopped_clean 4, and stopped_clean 6
  for both FJSON and FNONUM.

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
  `published_bad` run; A2 had 3 and A3 had 5 on FNONUM. The verdict holds after the re-runs (A4 still has no
  `published_bad` run). But A4's "safety" is mostly that llama-4-scout never produces anything
  under Hermes (see the 2026-10-23 update below), so H3 says little about Hermes itself.
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

## Update 2026-10-23: human panel, error analysis, and what the gates missed

Everything below is exploratory or single-rater unless it says otherwise (PREREGISTRATION.md
deviations 7-16). The pre-registered tables above stand, apart from the A4 fault row correction.

### Human panel: one rater

The owner rated all 42 pairs. No second rater was available, so alpha cannot be computed and
the pre-registration marks the human result not usable for H4 or the decision rule. Reported
as one person's judgement (`out/panel-summary.json`):

| Pairing | Wins | Neither |
|---|---|---|
| A1 vs A2 | A1 5, A2 2 | 0 |
| A1 vs A3 | A1 4, A3 0 | 3 |
| A1 vs A4 | A1 3, A4 1 | 3 |
| A2 vs A3 | A2 4, A3 1 | 2 |
| A2 vs A4 | A2 4, A4 3 | 0 |
| A3 vs A4 | A4 5, A3 1 | 1 |

Bradley-Terry log strength: A1 +0.85, A2 -0.17, A4 -0.38, A3 -1.94. The rater marked **none of
the 84 outputs fine to post as-is**. Reasons the rater gave: LLM versions distorted or padded
facts, read as generic, and missed the platform's format or length; and the hook often states a
figure that the next paragraph states again. The rater wrote the source posts, so a preference
for their own wording cannot be ruled out. The LLM judge does not track this rater (Spearman
-0.085 over 52 outputs), so judge scores are not cited as quality.

### Error analysis (one coder: Claude)

Every clean output and failure was read and coded (`error-analysis.md`, `out/error-codes.jsonl`).
The coder's "would publish" call, by arm: A1 0/10, A2 16/60 (llama 0, deepseek 16/30), A3 12/60
(2, 10), A4 25/60 (0, 25/30). **The human rater disagreed with it**: in the 20 pairs where the
coder would publish exactly one side, the rater picked that side 5 times, the other side 13, and
neither 2. So the coder's numbers are reported as one reading of the outputs, not as a quality
measure, and the article does not lead with them.

What the coding did establish, as counts anyone can recheck in the outputs:

- The gates pass a lot the coder would not publish: gate precision 34% (41 of 122 gate-passing
  clean runs). 54 outputs use the blog page's own counters or sidebar ads as content ("1427
  open Engineering roles"); the gates passed 41 of them.
- All 16 facts-gate failures are false positives on k-abbreviations ("$293k" vs "293,000").
  Forgiving only those, the clean pass rate is A1 100%, A2 78%, A3 80%, A4 50%
  (`export_article.py`, `gateCorrected`).
- The source posts contain errors the arms copy: "4,269 Remote Jobs Paying USD" (most listings
  show no pay), "the only listing with a disclosed rate" in a post that also says 23% of its 4,441
  listings show pay.
- A3's revise loop added page-chrome leaks rather than removing them (29 of 60 clean runs).
- The repeated-figure pattern the rater named (`repeat_hook.py`, years ignored): the LinkedIn hook and
  next paragraph, or tweet 1 and tweet 2, repeat a figure in A1 8/10, A2 20/60, A3 21/60, A4 17/30
  outputs. 4 of the 5 numbered source posts repeat a title figure in their description.

### Model vs architecture (decompose.py, CIs resample source posts)

| Outcome | Model | Arm | Arm x model | Source post | Residual |
|---|---|---|---|---|---|
| Gate publishable | 3% [0, 13] | 5% [0, 22] | 32% [27, 40] | 13% [2, 20] | 47% |
| Judge text quality | 36% [19, 59] | 6% [4, 10] | 0% [0, 2] | 16% [1, 29] | 47% |
| Coder would publish | 36% [29, 45] | 4% [0, 18] | 7% [3, 18] | 4% [0, 6] | 50% |

On the gates, the arm x model interaction dominates (A4 is 0% on llama and 93% on deepseek);
model alone and arm alone are both small. The judge row is shown for the record only: the judge
failed its pre-registered check against the human (Spearman -0.085, bar 0.5), and its design is
not balanced (A4 on llama-4-scout has no scored output, two cells have 29 runs), so its
interaction share is not estimable and the 0% is an artifact of clamping. The coder row is one
AI coder the human disagreed with 13 to 5. Neither supports "the model matters more than the arm".

### Sensitivity of the verdict (sensitivity.py, 80 settings per row)

Varying the gap threshold (5-25 points), cost ratio (2-5x) and prices (0.5-2x) never changes the
pick under the gate outcome: A1 for all arms, A2 among LLM arms, pooled and per model. With the
panel not usable, the rule's human condition cannot be met, so no setting moves off the
cheapest arm under any outcome. Against all arms the sweep cannot move by construction: A1 costs
$0, so every cost ratio against it is infinite.

Among LLM arms on deepseek-v4-flash alone, A4 beats A2 by +33 points on the gates (CI lower bound
+13), so the gap condition is met; the cost condition fails at 11x per publishable post against
the 3x limit, and the human condition fails as above.

### Hermes on llama-4-scout

The 30/30 empty llama runs come from the system prompt Hermes builds for llama-family model
names, not from the model being unable to call tools: replaying Hermes's first request with a
neutral prompt, or with the prompt Hermes builds for deepseek, gets proper tool calls (10-call
probe, `hermes-llama-confound.md`). Turning on Hermes's documented settings inside Hermes
(30 exploratory runs) gets llama to make real tool calls once both `tool_use_enforcement` and
`execution_guidance` are on, but no run saved output: posts written into the chat instead of
the file, malformed JSON, context overflow, gateway drops. So A4's llama result reflects both
Hermes's defaults and the model.

### Spend

Model calls in the 264 counted runs: $2.29 (`experiment_usd_total`). Not included: pilot runs
($0.38), the 30 exploratory A4-enf runs ($0.16), the 10-call probe (about $0.01), and the LLM judge.

### Corrections to the 2026-10-16 text

- Deviation 4's "failed in both streaming and non-streaming mode" is withdrawn: the pilot's
  config key (`model.stream`) is not one Hermes reads (`model.streaming`), so it always streamed.
- A4 fault row corrected for 8 runs that never reached the model (see Faults).

### Stats pre-read (2026-10-23, AI reviewer, not an independent human)

A fresh-context Claude session with no access to this analysis's reasoning read the study folder
and the draft article and returned 12 findings, 4 marked blocking. Changes made in response:
the "model mattered more than the framework" framing was replaced with the interaction result;
the judge row was dropped from the article; the sensitivity text now says the rule cannot leave
A1 by construction and reports the deepseek A4 vs A2 result; the article lists every deviation
from this plan; the headline table shows 95% CIs (unadjusted, 5 source clusters) and the
k-abbreviation-corrected pass rate; the fault prose no longer reads A4's llama stops or A2/A3's
404 exits as robustness differences; the Hermes probe claim is hedged to a first-turn probe.
Pre-registered Bonferroni over 6 comparisons was not applied; under it A4 - A3 [-45, -2] would
not hold. `panel.py`'s docstring claimed model and arm are not confounded in the panel; that is
wrong for A4 (all deepseek) and was corrected. `sensitivity.py` keyed a CI cache on `id(rows)`;
re-keyed on the run set and values, output unchanged.

### Clean-clone rerun (2026-10-23, by Claude, not an outside person)

A fresh `git clone` of the public mirror (commit 4faccee) reproduced, with no files from the
working study folder: `gates.py` gave the same 264 gate rows, and `analyze.py` gave a
`summary.json` and per-run CSV identical to the committed ones. The `py` image was then rebuilt
from the clone with `--no-cache`, and A1 was rerun once per source post: all 5 outputs are
byte-for-byte identical to the 10 counted A1 outputs (2 per post). The LLM arms were not rerun;
their outputs vary run to run, and their transcripts are in `out/transcripts.tar.gz`. An outside
rerun by someone other than the authors has not happened yet.
