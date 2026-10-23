# Error analysis: what goes wrong in each arm

This is an exploratory, single-coder error analysis of the counted runs in this
study. It was not in PREREGISTRATION.md, so it is a deviation from the
pre-registered plan. Read it as hypothesis-generating, not as a confirmatory
result. It does not change the pre-registered numbers in RESULTS.md.

Every count below comes from `out/error-codes.jsonl` via `python3 -I error_tables.py`.
The full tables printed by that script are reproduced at the end of this file.

## Method

**What was read.** All 264 counted runs (run_id starting with `r`; pilot `p` runs
excluded): 190 clean runs (fault `none`) and 74 fault-injection runs. 193 runs
produced an `output.json`; each of those was read in full (LinkedIn post, every
tweet, every slide) next to the source post. For the 71 runs with no output, the
`agent-final.txt`, `agent-stderr.txt` and `stderr_tail` were read instead. For
the A1 template arm, all 10 clean runs and both fault runs were read (reps 0 and
1 are byte-identical per source, so A1 has 5 distinct clean outputs).

**Open coding.** Each output got short descriptive codes for problems and for
things done well. Code names were made up while reading, then revised once all
arms had been read.

**Axial coding.** Open codes were grouped into 11 failure modes and 5 quality
markers (codebook below). Four modes are computed mechanically from the output
(no output, which URL is linked, LinkedIn length, the brief's soft limits); the
rest come from the hand codes. Both the open codes and the final modes are kept
on each row of `error-codes.jsonl` (`open_codes`, `codes`).

**Editor call.** For every run the coder answered "would a careful social editor
publish this set as-is?" with a one-line reason. Blockers: a factual error or a
claim the post does not support, page-widget content presented as article
content, a missing or wrong link (anything other than the post itself), a
LinkedIn post under 450 characters, filler tweets or slides, generic marketing
voice or hype carrying the post, template text pasted without adaptation, and no
output. Tolerated (coded, not blocking): one dense LinkedIn paragraph, a slide
slightly over 160 characters that still renders, a URL inside a slide, a
LinkedIn post of 450-599 characters, and repeating a minor slip that is in the
source itself. After a final consistency pass, the editor call equals "none of
the blocking modes is present" on all 264 rows, so it can be reproduced from the
codes.

**Limits.** One coder, no second rater, no agreement statistic. The coder knew
the arm and model of every run while coding (run_ids are not blind). The editor
call is one person's judgment, not ground truth. Cells hold 30 runs or fewer, so
a difference of a few runs is noise.

## Codebook

Failure modes (a run can have several):

| mode | definition | coded |
|---|---|---|
| no_output | No output file was produced. The cause is kept in `flags`: crash, model never replied, gateway timeout, echoed broken JSON, or declined because the post was missing. | mechanical |
| page_chrome_leak | Uses page furniture as if it were article content: live category counters ("1427 open Engineering roles · 276 posted this week"), sidebar job ads (6sense, Pendo, Salesforce), or numbers from related-article links. | hand |
| wrong_link | The LinkedIn post or the X thread does not link the blog post. It links /en/jobs, a category page, the homepage, the internal fixture host, or nothing. | mechanical |
| thin_linkedin | LinkedIn post under 450 characters, too short to stand alone. | mechanical |
| generic_voice | Generic hook or padding ("Did you know", "Discover the latest trends", "Learn more about market trends"), or hype and exclamation marks carrying the post instead of the data. | hand |
| filler_content | Tweets or slides with no content of their own ("Read the full breakdown on lokerdollar.com", "Ready to apply?" plus a URL), or a thread too thin to say anything. | hand |
| factual_distortion | A claim the post does not make or that contradicts it: misattributed figures, unsupported claims, statistics that contradict each other. | hand |
| source_error_repeated | Repeats an error or misleading framing that is in the source post itself: the "only listing with a disclosed rate" TL;DR, the "$1,500-3,000 retainer" slip, the "4,269 Remote Jobs Paying USD" title. It blocks only when it makes the output contradict itself, and then the run is also coded factual_distortion. | hand |
| pasted_not_adapted | Copies the post's title, description, headings or paragraphs instead of writing for the platform. | hand |
| wall_of_text | The LinkedIn post is one dense paragraph. Tolerated. | hand |
| spec_overrun | Misses a soft limit of the brief: LinkedIn 450-599 or over 1800 characters, not 3-6 tweets, a tweet over 270 characters, not 5 slides, a slide title over 40 or body over 160 characters. Tolerated. | mechanical |

Quality markers (coded on runs with output):

| marker | definition |
|---|---|
| stat_hook | Opens with a specific number from the post. |
| concrete_examples | Names real companies, roles or pay ranges from the post. |
| caveat | Carries the post's own caveats (most listings hide pay, hidden pay is not low pay, AI is no guaranteed premium). |
| actionable | Gives the reader a concrete next step, or frames the data for the target reader (Indonesian job seekers). |
| native_structure | Each format is shaped for its platform: line breaks or bullets on LinkedIn, one point per tweet, one idea per slide. |

Each row also has `flags`, which are not failure modes: mechanical sub-flags
(`li_short`, `slide_over`, `url_in_slide`, `wrong_link_target`, `internal_url`
and others), the no-output cause, and `facts_gate_k_abbrev_false_positive`
(explained below).

## Main findings

Top 3 failure modes per arm, clean runs:

| arm | n | 1st | 2nd | 3rd | editor would publish |
|---|---|---|---|---|---|
| A1-cron | 10 | filler_content 10 | pasted_not_adapted 10 | spec_overrun 8 | 0 |
| A2-cron-llm | 60 | thin_linkedin 34 | generic_voice 29 | page_chrome_leak 14 | 16 |
| A3-langgraph | 60 | page_chrome_leak 29 | wall_of_text 27 | generic_voice 24 | 12 |
| A4-hermes | 60 | no_output 30 | source_error_repeated 6 | factual_distortion 5 | 25 |

**A1 (template, no LLM).** 0 of 10 clean runs would be published. Every run
pastes the SEO title and description, turns question headings into truncated
slide titles ("Which high‑paying roles are visible in…") with the body "Read
the full breakdown on lokerdollar.com", and has a three-tweet thread that
repeats the title. On best-remote-usd-jobs it repeats the source's misleading
headline "4,269 Remote Jobs Paying USD" and "2,725 worldwide‑open roles list
USD compensation", although only 22% of listings disclose pay. The gates
passed all 10.

**A2 (one LLM call).** The model matters more than the arm here. On m1
(llama-4-scout) 0 of 30 would be published: every LinkedIn post is a 200-320
character "Did you know" stub (thin_linkedin 30 of 30, generic_voice 28 of 30),
and 10 of 30 pull in the live counters or sidebar ads. On m2
(deepseek-v4-flash) 16 of 30 would be published. Its failures are page-chrome
leaks (4), links to /en/jobs instead of the post on the AI-skills source (4)
and distortions (5), for example "Only 64% of all listings accept worldwide
remote talent" (r4-s2), which turns the majority into a minority.

**A3 (draft, critique, revise).** The revise loop did not fix the main problems
and added one. On m1 it padded the stub into a single 450-700 character
paragraph (wall_of_text 22 of 30, generic_voice 24 of 30); 2 of 30 would be
published. Page-chrome leaks are more common in A3 than in A2 on both models
(m1 16 vs 10, m2 13 vs 4). One plausible reading is that the critique asks for
more specifics and the model reaches for the counters and sidebar ads on the
page. On m2, 10 of 30 would be published, against 16 of 30 for A2 m2.

**A4 (Hermes agent).** On m1 nothing was produced in 30 of 30 clean runs:
llama-4-scout never returned a usable reply inside Hermes. On m2, 25 of 30
would be published, the best cell in the study. None of the 30 m2 runs leaked
page chrome, had a thin LinkedIn post, used generic voice, or linked the wrong
page. All five rejections are about a single claim each. Four repeat or inflate
the global-remote-jobs TL;DR ("the only listing with a disclosed rate") into a
statement that contradicts the same post's 1,000 pay-disclosing listings. One
(r5-s4) extends the source's AI-pay correlation to communication skills.

**Faults.** The A2 and A3 scripts have no error handling for a missing post:
every f404 run in A1, A2 and A3 ends in an unhandled traceback. Nothing gets
published, which is the right outcome, but the exit is untidy. A2 also crashed
on all 6 f429 runs, so a transient rate limit loses the post; A3 recovered from
429 in 6 of 6. All 6 A3 fjson runs recovered, but every one linked the
homepage, /en or a category page instead of the post, and so did all 3 A3 m1
fnonum runs. The fnonum fixture's URL is `http://fixtures:8000/no-numbers-post.md`.
Arms that linked it faithfully produced an internal URL that no editor would
publish, so the fnonum results are mostly a harness artifact. A4 m2 refused
cleanly on all 3 f404 runs and explained why. Most other A4 fault runs ended on
a gateway timeout (an infrastructure failure), not on the injected fault.

## Gate verdict against the editor call

Clean runs, per arm:

| arm | n | gate yes, editor yes | gate yes, editor no | gate no, editor yes | gate no, editor no | agreement |
|---|---|---|---|---|---|---|
| A1-cron | 10 | 0 | 10 | 0 | 0 | 0 (0%) |
| A2-cron-llm | 60 | 11 | 31 | 5 | 13 | 24 (40%) |
| A3-langgraph | 60 | 7 | 35 | 5 | 13 | 20 (33%) |
| A4-hermes | 60 | 23 | 5 | 2 | 30 | 53 (88%) |

The per-model split and the fault-run version are in the tables at the end. Two
things drive the disagreement:

1. **The gates pass what an editor rejects.** 81 clean runs pass the gates but
   would not be published. The gates check length ceilings and links. They do
   not check length floors (a 204-character LinkedIn post passes), voice,
   filler, or page chrome. Of the 54 runs with output that leak page chrome,
   the gate passed 41. The facts gate treats every number on the fetched page,
   counters and sidebar ads included, as "in the source".
2. **The facts gate rejects what an editor accepts.** Every facts-gate failure
   among runs with output (16 of 16) is a false positive from abbreviated money:
   "$293k–325k" is read as 293, which is not in the source (the source says
   293,000). 12 clean runs fail the gates but would be published; 10 of these
   are this abbreviation, and 2 are a slide body a few characters over 160 that
   still renders. In this sample the facts gate never caught a real invented
   number.

A4 has the highest agreement mostly because its m1 half is 30 runs that both
sides reject (no output). The gates rank A1 highest; the editor ranks A1 lowest
and A4 m2 highest. Conclusions drawn from gate pass rates alone should account
for this.

## One example per failure mode

| mode | run_id | quote |
|---|---|---|
| no_output | r0-s0-A4-hermes-m1-none-334864000 | agent-final.txt: "@cf/meta/llama-4-scout-17b-16e-instruct didn't produce a reply this time, even after retries." |
| page_chrome_leak | r4-s4-A3-langgraph-m2-none-4193109000 | tweet 1: "601 open Marketing roles, 134 posted this week." This is the page's live category counter, in a post about USD pay. |
| wrong_link | r2-s4-A3-langgraph-m2-none | tweet 5: "See Marketing jobs: https://lokerdollar.com/en/remote-jobs/marketing". The post itself is never linked. |
| thin_linkedin | r0-s1-A2-cron-llm-m1-none | the whole LinkedIn post: "Did you know 22% of remote job listings disclose a salary figure? Learn what DOE (determined on experience) means for you and how to negotiate effectively. https://lokerdollar.com/en/blog/what-is-doe-wage" |
| generic_voice | r0-s2-A3-langgraph-m1-none | LinkedIn: "Discover the latest salary trends for remote brand designers in 2026. ... Learn more about market trends, job opportunities, and how to land a gig. Check out the latest insights and find your next opportunity" |
| filler_content | r0-s0-A1-cron-none-none | slides 3 and 4: title "Which remote roles are most in demand…", body "Read the full breakdown on lokerdollar.com" |
| factual_distortion | r4-s2-A2-cron-llm-m2-none | "Only 64% of all listings accept worldwide remote talent". The post presents 64% as the majority. |
| source_error_repeated | r5-s0-A4-hermes-m2-none | "Neo Financial's entry-level client services role is the only listing with a disclosed rate at $5/hour", in the same post that says 1,000 listings disclose pay |
| pasted_not_adapted | r0-s4-A1-cron-none-none | LinkedIn opens with the SEO title and description verbatim: "4,269 Remote Jobs Paying USD: What the Data Shows in 2026" / "2,725 worldwide‑open roles list USD compensation as of Oct 13 2026." |
| wall_of_text | r4-s0-A3-langgraph-m2-none | the 738-character LinkedIn post is one paragraph, from "Neo Financial – Remote Bilingual Client Services pays $5 USD/hour" to the URL |
| spec_overrun | r3-s2-A3-langgraph-m2-none | slide 5 body, 163 characters: "See all 5 companies, methodology, and contrarian take on fixed vs retainer. Read the blog: https://lokerdollar.com/en/blog/remote-brand-designer-salary-trends-2026" |

Run_ids shown without the timestamp suffix are still unique in `error-codes.jsonl`.

## Surprises

- The source posts contain errors that the arms faithfully copy. The
  best-remote-usd-jobs headline and description overstate how many jobs show
  USD pay. Its example listings are marked "active until" dates before the
  query date. global-remote-jobs calls Neo Financial "the only listing with a
  disclosed rate" next to 1,000 listings that disclose pay. The brand-designer
  post calls a $1,500-3,000 fixed project a "retainer". A check that only
  compares the output to the source cannot catch any of these.
- The critique-and-revise loop in A3 made outputs longer but not better, and
  more likely to leak page chrome than the single call in A2.
- A4 m2 is both the best cell here and the most expensive one (RESULTS.md:
  $0.0439 per gate-publishable post, against $0.0040 for A2 m2). A4 m1 is the
  worst, because the agent loop never got a reply from llama-4-scout. For A4,
  the arm effect cannot be separated from the model effect.
- The LLM judge (`out/judge-text.jsonl`) scored every judged clean run in the
  LLM arms between 7.5 and 8.83. Its notes mention page chrome in 2 of the 43
  judged runs that leak it, and a link problem in 2 of the 11 judged runs with
  a wrong link. It does not substitute for reading the outputs either.

## Files

- `out/error-codes.jsonl`: one row per counted run with `run_id`, `arm`,
  `model`, `fault`, `source_slug`, `codes` (failure modes), `quality`,
  `would_publish` and `reason`, plus `clean`, `gate_publishable`, `open_codes`
  and `flags`.
- `error_tables.py`: prints every table below from that file (standard library
  only: `python3 -I error_tables.py`).

# Tables (output of error_tables.py)

## Coverage

| arm | model | clean runs | clean with output | fault runs | fault with output |
|---|---|---|---|---|---|
| A1-cron | none | 10 | 10 | 2 | 1 |
| A2-cron-llm | m1 | 30 | 30 | 12 | 6 |
| A2-cron-llm | m2 | 30 | 30 | 12 | 6 |
| A3-langgraph | m1 | 30 | 30 | 12 | 9 |
| A3-langgraph | m2 | 30 | 30 | 12 | 9 |
| A4-hermes | m1 | 30 | 0 | 12 | 0 |
| A4-hermes | m2 | 30 | 30 | 12 | 2 |
| all |  | 190 | 160 | 74 | 33 |

## Failure modes, clean runs, by arm

| mode | A1-cron (n=10) | A2-cron-llm (n=60) | A3-langgraph (n=60) | A4-hermes (n=60) |
|---|---|---|---|---|
| no_output | 0 (0%) | 0 (0%) | 0 (0%) | 30 (50%) |
| page_chrome_leak | 0 (0%) | 14 (23%) | 29 (48%) | 0 (0%) |
| wrong_link | 0 (0%) | 4 (7%) | 7 (12%) | 0 (0%) |
| thin_linkedin | 2 (20%) | 34 (57%) | 11 (18%) | 0 (0%) |
| generic_voice | 0 (0%) | 29 (48%) | 24 (40%) | 0 (0%) |
| filler_content | 10 (100%) | 8 (13%) | 8 (13%) | 0 (0%) |
| factual_distortion | 0 (0%) | 9 (15%) | 9 (15%) | 5 (8%) |
| source_error_repeated | 2 (20%) | 0 (0%) | 5 (8%) | 6 (10%) |
| pasted_not_adapted | 10 (100%) | 0 (0%) | 0 (0%) | 0 (0%) |
| wall_of_text | 0 (0%) | 1 (2%) | 27 (45%) | 1 (2%) |
| spec_overrun | 8 (80%) | 12 (20%) | 24 (40%) | 0 (0%) |
| editor would publish | 0 (0%) | 16 (27%) | 12 (20%) | 25 (42%) |
| gate publishable | 10 (100%) | 42 (70%) | 42 (70%) | 28 (47%) |

## Failure modes, clean runs, by arm x model

| mode | A1-cron none (n=10) | A2-cron-llm m1 (n=30) | A2-cron-llm m2 (n=30) | A3-langgraph m1 (n=30) | A3-langgraph m2 (n=30) | A4-hermes m1 (n=30) | A4-hermes m2 (n=30) |
|---|---|---|---|---|---|---|---|
| no_output | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) | 30 (100%) | 0 (0%) |
| page_chrome_leak | 0 (0%) | 10 (33%) | 4 (13%) | 16 (53%) | 13 (43%) | 0 (0%) | 0 (0%) |
| wrong_link | 0 (0%) | 0 (0%) | 4 (13%) | 2 (7%) | 5 (17%) | 0 (0%) | 0 (0%) |
| thin_linkedin | 2 (20%) | 30 (100%) | 4 (13%) | 6 (20%) | 5 (17%) | 0 (0%) | 0 (0%) |
| generic_voice | 0 (0%) | 28 (93%) | 1 (3%) | 24 (80%) | 0 (0%) | 0 (0%) | 0 (0%) |
| filler_content | 10 (100%) | 8 (27%) | 0 (0%) | 8 (27%) | 0 (0%) | 0 (0%) | 0 (0%) |
| factual_distortion | 0 (0%) | 4 (13%) | 5 (17%) | 6 (20%) | 3 (10%) | 0 (0%) | 5 (17%) |
| source_error_repeated | 2 (20%) | 0 (0%) | 0 (0%) | 0 (0%) | 5 (17%) | 0 (0%) | 6 (20%) |
| pasted_not_adapted | 10 (100%) | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| wall_of_text | 0 (0%) | 0 (0%) | 1 (3%) | 22 (73%) | 5 (17%) | 0 (0%) | 1 (3%) |
| spec_overrun | 8 (80%) | 6 (20%) | 6 (20%) | 18 (60%) | 6 (20%) | 0 (0%) | 0 (0%) |
| editor would publish | 0 (0%) | 0 (0%) | 16 (53%) | 2 (7%) | 10 (33%) | 0 (0%) | 25 (83%) |
| gate publishable | 10 (100%) | 24 (80%) | 18 (60%) | 25 (83%) | 17 (57%) | 0 (0%) | 28 (93%) |

## Failure modes, clean runs that produced output, by arm x model

| mode | A1-cron none (n=10) | A2-cron-llm m1 (n=30) | A2-cron-llm m2 (n=30) | A3-langgraph m1 (n=30) | A3-langgraph m2 (n=30) | A4-hermes m2 (n=30) |
|---|---|---|---|---|---|---|
| no_output | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| page_chrome_leak | 0 (0%) | 10 (33%) | 4 (13%) | 16 (53%) | 13 (43%) | 0 (0%) |
| wrong_link | 0 (0%) | 0 (0%) | 4 (13%) | 2 (7%) | 5 (17%) | 0 (0%) |
| thin_linkedin | 2 (20%) | 30 (100%) | 4 (13%) | 6 (20%) | 5 (17%) | 0 (0%) |
| generic_voice | 0 (0%) | 28 (93%) | 1 (3%) | 24 (80%) | 0 (0%) | 0 (0%) |
| filler_content | 10 (100%) | 8 (27%) | 0 (0%) | 8 (27%) | 0 (0%) | 0 (0%) |
| factual_distortion | 0 (0%) | 4 (13%) | 5 (17%) | 6 (20%) | 3 (10%) | 5 (17%) |
| source_error_repeated | 2 (20%) | 0 (0%) | 0 (0%) | 0 (0%) | 5 (17%) | 6 (20%) |
| pasted_not_adapted | 10 (100%) | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) | 0 (0%) |
| wall_of_text | 0 (0%) | 0 (0%) | 1 (3%) | 22 (73%) | 5 (17%) | 1 (3%) |
| spec_overrun | 8 (80%) | 6 (20%) | 6 (20%) | 18 (60%) | 6 (20%) | 0 (0%) |
| editor would publish | 0 (0%) | 0 (0%) | 16 (53%) | 2 (7%) | 10 (33%) | 25 (83%) |
| gate publishable | 10 (100%) | 24 (80%) | 18 (60%) | 25 (83%) | 17 (57%) | 28 (93%) |

## Top 3 failure modes per arm (clean runs; ties broken by mode order)

| arm | n | 1st | 2nd | 3rd |
|---|---|---|---|---|
| A1-cron | 10 | filler_content 10 | pasted_not_adapted 10 | spec_overrun 8 |
| A2-cron-llm | 60 | thin_linkedin 34 | generic_voice 29 | page_chrome_leak 14 |
| A3-langgraph | 60 | page_chrome_leak 29 | wall_of_text 27 | generic_voice 24 |
| A4-hermes | 60 | no_output 30 | source_error_repeated 6 | factual_distortion 5 |

## Quality markers, clean runs that produced output, by arm x model

| marker | A1-cron none (n=10) | A2-cron-llm m1 (n=30) | A2-cron-llm m2 (n=30) | A3-langgraph m1 (n=30) | A3-langgraph m2 (n=30) | A4-hermes m2 (n=30) |
|---|---|---|---|---|---|---|
| stat_hook | 8 (80%) | 29 (97%) | 30 (100%) | 30 (100%) | 30 (100%) | 30 (100%) |
| concrete_examples | 0 (0%) | 15 (50%) | 30 (100%) | 18 (60%) | 28 (93%) | 30 (100%) |
| caveat | 0 (0%) | 6 (20%) | 28 (93%) | 12 (40%) | 16 (53%) | 30 (100%) |
| actionable | 0 (0%) | 10 (33%) | 14 (47%) | 9 (30%) | 16 (53%) | 26 (87%) |
| native_structure | 0 (0%) | 0 (0%) | 19 (63%) | 0 (0%) | 14 (47%) | 29 (97%) |

## Gate verdict vs editor call, per arm, clean runs

| arm | n | gate yes / editor yes | gate yes / editor no | gate no / editor yes | gate no / editor no | agreement |
|---|---|---|---|---|---|---|
| A1-cron | 10 | 0 | 10 | 0 | 0 | 0 (0%) |
| A2-cron-llm | 60 | 11 | 31 | 5 | 13 | 24 (40%) |
| A3-langgraph | 60 | 7 | 35 | 5 | 13 | 20 (33%) |
| A4-hermes | 60 | 23 | 5 | 2 | 30 | 53 (88%) |

## Gate verdict vs editor call, per arm x model, clean runs

| arm | model | n | yes/yes | gate yes, editor no | gate no, editor yes | no/no |
|---|---|---|---|---|---|---|
| A1-cron | none | 10 | 0 | 10 | 0 | 0 |
| A2-cron-llm | m1 | 30 | 0 | 24 | 0 | 6 |
| A2-cron-llm | m2 | 30 | 11 | 7 | 5 | 7 |
| A3-langgraph | m1 | 30 | 1 | 24 | 1 | 4 |
| A3-langgraph | m2 | 30 | 6 | 11 | 4 | 9 |
| A4-hermes | m1 | 30 | 0 | 0 | 0 | 30 |
| A4-hermes | m2 | 30 | 23 | 5 | 2 | 0 |

## Gate verdict vs editor call, per arm, fault runs

| arm | n | yes/yes | gate yes, editor no | gate no, editor yes | no/no |
|---|---|---|---|---|---|
| A1-cron | 2 | 0 | 1 | 0 | 1 |
| A2-cron-llm | 24 | 1 | 8 | 0 | 15 |
| A3-langgraph | 24 | 1 | 6 | 0 | 17 |
| A4-hermes | 24 | 0 | 2 | 0 | 22 |

## Why the gate and the editor disagree, clean runs

- gate no, editor yes: 12 runs; facts-gate k-abbreviation false positive in 10; slide over 160/40 in 2
- gate yes, editor no: 81 runs; modes present: generic_voice 45, thin_linkedin 39, page_chrome_leak 33, filler_content 24, spec_overrun 23, wall_of_text 18, factual_distortion 17, pasted_not_adapted 10, source_error_repeated 7

## Facts gate failures, all runs with output

- runs flagged as k-abbreviation false positives: 16
- runs with page_chrome_leak: 54; of these the gate called publishable: 41

## Mechanical sub-flags, clean runs with output

| flag | A1-cron (n=10) | A2-cron-llm (n=60) | A3-langgraph (n=60) | A4-hermes (n=30) |
|---|---|---|---|---|
| li_short | 8 | 3 | 23 | 0 |
| li_long | 0 | 0 | 0 | 0 |
| x_count_off | 0 | 0 | 0 | 0 |
| tweet_over | 0 | 0 | 0 | 0 |
| slide_count | 0 | 0 | 0 | 0 |
| slide_over | 0 | 9 | 5 | 0 |
| url_in_slide | 0 | 38 | 43 | 25 |
| wrong_link_target | 0 | 4 | 7 | 0 |
| link_missing | 0 | 0 | 0 | 0 |
| internal_url | 0 | 0 | 0 | 0 |

## No-output causes

| arm | model | fault | cause | runs |
|---|---|---|---|---|
| A1-cron | none | f404 | crash_404 | 1 |
| A2-cron-llm | m1 | f404 | crash_404 | 3 |
| A2-cron-llm | m1 | f429 | crash_429 | 3 |
| A2-cron-llm | m2 | f404 | crash_404 | 3 |
| A2-cron-llm | m2 | f429 | crash_429 | 3 |
| A3-langgraph | m1 | f404 | crash_404 | 3 |
| A3-langgraph | m2 | f404 | crash_404 | 3 |
| A4-hermes | m1 | f404 | model_no_reply | 3 |
| A4-hermes | m1 | f429 | model_no_reply | 3 |
| A4-hermes | m1 | fjson | echoed_broken_json | 2 |
| A4-hermes | m1 | fjson | infra_gateway_timeout | 1 |
| A4-hermes | m1 | fnonum | infra_gateway_timeout | 2 |
| A4-hermes | m1 | fnonum | no_file_written | 1 |
| A4-hermes | m1 | none | model_no_reply | 30 |
| A4-hermes | m2 | f404 | declined_missing_source | 3 |
| A4-hermes | m2 | f429 | infra_gateway_timeout | 1 |
| A4-hermes | m2 | fjson | echoed_broken_json | 2 |
| A4-hermes | m2 | fjson | infra_gateway_timeout | 1 |
| A4-hermes | m2 | fnonum | infra_gateway_timeout | 3 |

## Fault runs that produced output: modes

| arm | model | fault | with output | editor yes | gate yes | modes |
|---|---|---|---|---|---|---|
| A1-cron | none | fnonum | 1 | 0 | 1 | wrong_link 1, thin_linkedin 1, filler_content 1, pasted_not_adapted 1 |
| A2-cron-llm | m1 | fjson | 3 | 0 | 3 | thin_linkedin 3, generic_voice 3, page_chrome_leak 2, filler_content 2 |
| A2-cron-llm | m1 | fnonum | 3 | 0 | 2 | wrong_link 3, thin_linkedin 3, generic_voice 1, filler_content 1, spec_overrun 1 |
| A2-cron-llm | m2 | fjson | 3 | 1 | 3 | thin_linkedin 2, page_chrome_leak 1 |
| A2-cron-llm | m2 | fnonum | 3 | 0 | 1 | wrong_link 3, pasted_not_adapted 2, spec_overrun 2 |
| A3-langgraph | m1 | f429 | 3 | 0 | 3 | page_chrome_leak 3, generic_voice 3, thin_linkedin 2, spec_overrun 1 |
| A3-langgraph | m1 | fjson | 3 | 0 | 0 | wrong_link 3, generic_voice 2, page_chrome_leak 1, thin_linkedin 1, factual_distortion 1, spec_overrun 1 |
| A3-langgraph | m1 | fnonum | 3 | 0 | 0 | wrong_link 3, spec_overrun 2, generic_voice 1, filler_content 1 |
| A3-langgraph | m2 | f429 | 3 | 1 | 3 | page_chrome_leak 1, thin_linkedin 1 |
| A3-langgraph | m2 | fjson | 3 | 0 | 0 | wrong_link 3, page_chrome_leak 2, spec_overrun 1 |
| A3-langgraph | m2 | fnonum | 3 | 0 | 1 | wrong_link 3, pasted_not_adapted 2, spec_overrun 1 |
| A4-hermes | m2 | f429 | 2 | 0 | 2 | source_error_repeated 2, page_chrome_leak 1, factual_distortion 1 |
