# Hermes on llama-4-scout: is the 0/30 a Hermes problem or a model/provider problem?

Analysis of the finished benchmark's proxy transcripts only, done 2026-10-23. No new model calls.
Reproduce: `tar -xzf out/transcripts.tar.gz -C <empty dir>` then
`python3 -I hermes_confound.py <empty dir>/transcripts`. That script prints every count below and
writes `out/hermes-m1-turns.jsonl` (one line per A4-m1 reply).

## Question

A4 Hermes Agent (commit 60f56a6) wrote no output file in any of the 30 counted clean runs on M1
(`@cf/meta/llama-4-scout-17b-16e-instruct`), but 28 of 30 on M2 (`deepseek-v4-flash`). Was that
Hermes (its prompt, tool schemas or parser), or a tool-calling limitation of llama-4-scout on
Workers AI that any tool-using agent would hit? A2 and A3 send no `tools` on M1, so they say
nothing either way.

## Method

- Source: `out/transcripts.tar.gz`. The proxy writes one line per chat call: the request after
  the proxy's own edits (`max_tokens: 8000` if missing, `stream_options.include_usage`, and on M2
  `chat_template_kwargs.thinking=false`), the HTTP status, and the raw upstream reply. For a
  streamed reply it keeps the raw SSE bytes as Workers AI sent them (last 20,000 characters).
  So an empty reply in the transcript was empty when it left Workers AI. Hermes's client code
  never touched it.
- Every A4 run in `out/runs.jsonl` with a run id starting `r` (30 clean plus 12 fault runs per
  model). Each reply is classed by rebuilding the streamed deltas (content, tool_calls,
  finish_reason, usage):
  `tool_calls` (proper OpenAI tool calls), `text_tool_call` (a tool call written as plain text in
  content), `empty_with_tokens` (no content and no tool_calls, but completion tokens billed),
  `length`, `error_status`, `answer_as_text` (the final JSON sent as text, not saved with
  `write_file`), `prose`, `injected_fjson` (the proxy replaced the reply), `aux_no_tools` (Hermes's
  session-title call, which sends no tools and is not an agent turn).
- Request shape: every request that carries `tools`, compared field by field between M1 and M2.
  System prompts are compared after masking the `Model:` and `Conversation started:` lines.
- The pilot probes in the same archive (`p9-*`, excluded from results) are reported separately.

## Per-run classification, A4 on M1

| Set | Runs | What the model returned | Turns |
|---|---|---|---|
| Clean | 30 | `empty_with_tokens` on every agent call: finish_reason `stop`, 0 content characters, 0 tool_calls | 120 of 120 |
| F404 | 3 | `empty_with_tokens` | 12 of 12 |
| F429 | 3 | injected 429, then `empty_with_tokens` | 3 + 12 |
| FJSON | 3 | 2 runs: reply replaced by the proxy (original not kept). 1 run: no LLM call at all | 2 |
| FNONUM | 3 | 1 run: proper `tool_calls` (read_file + terminal in parallel), then `answer_as_text`. 2 runs: no LLM call at all | 1 + 1 |

- No reply in any counted M1 run was `text_tool_call`, `length` or an upstream error status.
- Billed completion tokens on the 120 clean empty replies: min 109, median 481, max 1,663. The
  model generated text every time. None of it reached the client.
- Hermes's behaviour on an empty reply is the same every time: it resends the byte-identical
  request 3 more times (4 tool requests per clean run, 1 distinct `messages` array in all 30),
  makes its title call, prints `⚠️ No reply: @cf/meta/llama-4-scout-17b-16e-instruct didn't produce
  a reply this time, even after retries.` and exits 0 (`out/runs/r0-s0-A4-hermes-m1-none-334864000/agent-final.txt`).
  No clean M1 run got past turn 0.
- Across all M1 turn-0 attempts with the full Hermes request (145, clean and fault), exactly 1
  came back with proper tool_calls (`r1-s-1-A4-hermes-m1-fnonum-8613166000`). So 8 tools plus the
  Hermes prompt do not always fail. They fail about 99% of the time on these prompts.

On M2 the same client produced no `empty_with_tokens` turn at all: 172 `tool_calls` turns and
30 final `prose` turns across the 30 clean runs. Every clean M2 run got proper tool calls on
turn 0 (for example `"I'll fetch the blog post first."` plus a `terminal` call).

## Request shape, M1 vs M2 (every request with tools)

| Field | M1 (151 requests) | M2 (236 requests) | Same? |
|---|---|---|---|
| tools | 8 (patch, read_file, search_files, terminal, write_file, tool_search, tool_describe, tool_call), 10,715 bytes, sha `f24881ce8fe4` | same 8, 10,715 bytes, same sha | yes |
| tool_choice | not sent | not sent | yes |
| parallel_tool_calls | not sent | not sent | yes |
| stream | true (2 false: the FJSON calls the proxy forced to non-streaming) | same | yes |
| max_tokens | 8000 (added by the proxy) | 8000 (added by the proxy) | yes |
| reasoning_effort | `medium` | `medium` | yes |
| temperature | not sent | not sent | yes |
| chat_template_kwargs | none | `{"thinking": false}` (added by the proxy) | no, by design |
| **system prompt** | **4,995 characters** | **9,774 characters** | **no** |
| user message | the arm's goal text | same text | yes |

The requests are **not** identical apart from the model. Hermes builds a model-dependent system
prompt: for deepseek it adds a block of about 4,780 characters headed `# Tool-use enforcement`
and `# Execution discipline` (`You MUST use your tools to take action ...`,
`<tool_persistence>`, `<mandatory_tool_use>`, `<verification>`, and more). For llama-4-scout it
leaves that block out. The rest of the two prompts is byte-identical after masking the model
name and date. Hermes also sends `reasoning_effort: medium` to llama-4-scout, which is not a
reasoning model. What Workers AI does with that field for this model is not visible in the
transcripts.

## Evidence (short excerpts)

1. **The endpoint generated tokens and streamed none of them.** `r0-s0-A4-hermes-m1-none-334864000`,
   turn 0, raw SSE from Workers AI, in full apart from ids:
   `{"delta":{"content":"","role":"assistant"},"finish_reason":null}` then
   `{"delta":{},"finish_reason":"stop"}` then
   `"usage":{"prompt_tokens":4417,"completion_tokens":157,...}` then `[DONE]`.
   The same thing happened on all 120 clean agent calls.
2. **One stream shows how the model stopped.** `p9-s0-A4-hermes-m1-stfalse-26003`, turn 0
   (pilot): `"finish_reason":"stop", ... "stop_reason":200007` with 146 completion tokens and no
   content. In the Llama 4 tokenizer, 200007 is most likely `<|eom|>`, the token the model emits
   after a tool call (it ends on `<|eot|>` when it has finished answering). If so, the model
   believed it had made a tool call. The endpoint returned neither the call nor the text.
3. **What the model actually writes, seen once without streaming.** `p9-dbg-replay` (pilot,
   sent by hand rather than by Hermes, exact Hermes turn-0 request with `stream:false`, no
   `max_tokens` so capped at 256): finish_reason `length`, content
   `"[terminal: curl -s -H 'Accept: text/markdown' '...global-remote-jobs-2026' > /tmp/hermes-home/cache/scratch/blog_post.md]\n\n[read_file: /tmp/hermes-home/cache/scratch/blog_post.md]\n\n[tool_search: [\"remote job market trends 2026\"]]\n\n[tool_describe: [\"process_manage\"]] ..."`.
   That is a list of calls written as `[name: args]` text. It is neither the OpenAI `tool_calls`
   format nor Llama 4's own `[name(arg=value)]` format, so the server's tool parser did not
   recognise it. Without streaming, it came back as plain text content.
4. **The same endpoint does tool calling fine on a small request.** `p9-dbg-tools`, 1 tool
   (`get_weather`), 45-character prompt: proper `tool_calls` both non-streamed and streamed
   (`{"delta":{"tool_calls":[{"function":{"arguments":"{\"city\": \"","name":"get_weather"}...`).
5. **The full Hermes request can also succeed on llama, rarely.** `r1-s-1-A4-hermes-m1-fnonum-8613166000`
   turn 0: streamed proper `tool_calls` for `read_file` and `terminal`. On turn 1 the model sent
   the finished JSON as message text instead of calling `write_file`. Hermes took that as the
   final answer, so no file was written (`agent-final.txt` holds the JSON).

### The "non-streaming" claim needs a correction

PREREGISTRATION Deviation 4 and the Hermes draft in `fairness-review/DRAFTS.md` say Hermes failed
on M1 "in both streaming and non-streaming mode". The transcripts do not show Hermes ever
sending a non-streaming tool request that reached the model unaltered. In the pilot run meant to
test non-streaming (`p9-s0-A4-hermes-m1-stfalse-26003`, `stream: false` in config.yaml), every
request still had `stream: true`, so that config key did not take effect. The only 2 M1
non-streaming tool requests are FJSON calls, where the proxy forced non-streaming and overwrote
the reply. The only non-streaming evidence is the one manual replay in point 3 above. That
replay supports "tool calls written as plain text", but it was sent by hand, not by Hermes.

## Conclusion

**The proximate cause is the model and provider, not Hermes's parser (high confidence).** The
transcript holds the raw upstream stream. In 120 of 120 clean agent calls, Workers AI billed
109 to 1,663 completion tokens and delivered no content and no tool_calls. No client-side parser,
Hermes's or anyone else's, can recover output that the server never sent. The one look at the
hidden output (point 3) shows llama-4-scout writing its tool calls as `[name: args]` text, which
the Workers AI tool parser does not recognise. Streaming then loses that text completely, and a
non-streaming call would return it as plain text. Either way no valid tool call reaches the agent.
The likely mechanism is a streaming tool parser that holds back output starting with `[` as a
possible Llama-style tool call and drops it when parsing fails. That is a hypothesis: the
response fields (`token_ids`, `routed_experts`, `stop_reason`) look like a vLLM backend, but
nothing here confirms it.

**Whether any tool-using agent would hit it is undecided (c).** Hermes's request has three
features that a different agent might not send, and the transcripts cannot rule any of them out
as the trigger:
- the Hermes system prompt as sent to llama, which lacks the tool-use enforcement block that
  deepseek gets and includes a "batch your tool calls" section, which fits the model writing a
  list of calls as text;
- `reasoning_effort: medium` on a non-reasoning model;
- the 8-tool set with the deferred-tool meta tools (`tool_search`, `tool_describe`, `tool_call`)
  and long descriptions (10.7 KB).

The 1-tool test only shows that the endpoint can do tool calling. It changes tool count, prompt
length and system prompt all at once, so it cannot isolate the trigger. The one fnonum success
shows the full Hermes request does not fail every time.

**Hermes's own share, which is certain but secondary:** on an empty reply it resends the
identical request 3 times with no nudge, then exits 0 with a "No reply" message. It also
accepted a JSON-as-text reply as finished work without checking that the requested file
existed. These choices waste calls and fail quietly, but they do not cause the empty replies.

Suggested wording for the article: "On llama-4-scout via Workers AI, the model's replies to
Hermes's tool requests arrived empty: tokens billed, no text and no tool calls in the stream.
In the one non-streamed sample the model wrote its tool calls as plain text. Whether a
different agent's request would avoid this is untested; see the probe below."

**Confidence:** high that the empty replies are produced upstream and that Hermes's parsing is
not the cause. Low (undecided) on whether the trigger is Hermes-specific request content or
generic to multi-tool agent requests on this model and endpoint.

## Decisive probe (10 calls, about $0.03)

Send through the same proxy with run ids `p9-probe-<cell>-<n>`, so transcripts are kept. Use a
plain stdlib client (urllib, the same as `proxy.py`), so no agent framework is involved. Base
request R = the exact turn-0 request body of `r0-s0-A4-hermes-m1-none-334864000`, line 0 of its
transcript (8 tools, Hermes's llama system prompt, `reasoning_effort: medium`, `max_tokens: 8000`).

| Cell | Change from R | stream | Calls |
|---|---|---|---|
| C1 control | none | true | 1 |
| C2 | none | false | 2 |
| C3 neutral agent | system prompt = `You are a helpful assistant that uses tools to complete tasks.`, same 8 tools, same user message, no `reasoning_effort` | false | 2 |
| C4 neutral agent, streamed | as C3 | true | 2 |
| C5 | R without `reasoning_effort` | false | 1 |
| C6 | R with the M2 system prompt (enforcement block in, model line set to llama) | false | 1 |
| C7 | R with tools cut to `terminal` + `write_file` | false | 1 |

Expected results and how to read them:
- C1 should reproduce `empty_with_tokens`, and C2 should show text tool calls in content. If
  not, the failure has changed since 2026-10-16, so stop and report that.
- **If C3 and C4 also give no proper `tool_calls`** (text calls, or an empty stream): this is a
  model/provider limitation that a plain agent with the same tools and task also hits. That is
  verdict (b). The article can say "llama-4-scout on Workers AI could not drive this tool set".
- **If C3 and C4 give proper `tool_calls` while C1 and C2 do not:** the trigger is in Hermes's
  request. That is verdict (a) at the request level, and C5, C6 and C7 name the part:
  `reasoning_effort` (C5 flips), the missing enforcement block (C6 flips) or tool count or meta
  tools (C7 flips). Then the Hermes fairness question becomes "should Hermes send llama the
  enforcement prompt, or skip `reasoning_effort` for non-reasoning models?"
- Cost: about 4.4k prompt tokens plus up to 1.5k completion tokens per call, at $0.27 and
  $0.85 per million tokens, so under $0.003 per call and under $0.03 in total. The baseline
  fails 144 of 145 times, so 2 runs per cell for the deciding cells (C3, C4) is enough. A single
  proper tool call there already rules out (b).

## Adjacent finding (same archive, affects the fault table)

8 A4 fault runs never reached the model. `agent-final.txt` reads `Hermes couldn't start the
model connection: Gateway starting: deadline. Your message was not sent.`, and the proxy has no
transcript for them. On M1 that is r0 FJSON, r0 FNONUM and r2 FNONUM. On M2 it is r0 FJSON,
r1 F429, and all 3 FNONUM runs. `out/gates.jsonl` codes all of them `stopped_clean`. So A4's
"FNONUM: stopped_clean 6" in RESULTS.md has 5 Hermes start-up failures and 1 run that answered
as text, and none of the 6 was a real test of the fault. Under the pre-registration ("Infra
errors not caused by an injected fault are re-run once and logged"), these should have been
re-run, or coded separately from `stopped_clean`.

## Probe result (run 2026-10-23)

Ran `probe_hermes_llama.py` once: 10 calls, same AI Gateway and Workers AI endpoint, plain
urllib client, no agent framework. 38,906 prompt and 1,888 completion tokens reported, about
$0.012. Every call returned HTTP 200. Raw summaries: `out/probe-hermes-llama.jsonl`.

| Cell | Change from Hermes's exact turn-0 request | stream | Result |
|---|---|---|---|
| C1 control | none | true | empty, finish `stop` (reproduces the counted runs) |
| C2 | none | false | 2/2 text tool calls in content (`[terminal: curl ...]`) |
| C3 | neutral one-line system prompt, no `reasoning_effort` | false | 2/2 proper `tool_calls` |
| C4 | as C3 | true | 2/2 proper `tool_calls` |
| C5 | drop `reasoning_effort` only | false | text tool call |
| C6 | Hermes's deepseek system prompt (with the tool-use enforcement block) | false | proper `tool_calls` (`read_file`, `terminal`) |
| C7 | tools cut to `terminal` + `write_file` | false | text tool call |

Verdict: **(a), at the request level.** llama-4-scout on Workers AI can emit proper tool calls
for this exact task, tool set and endpoint, streamed or not. It stops doing so with the system
prompt Hermes builds for it. The part that matters is the prompt: adding the "Tool-use
enforcement / Execution discipline" block that Hermes gives deepseek (C6) flips it, while
dropping `reasoning_effort` (C5) or cutting the tools to two (C7) does not.

Limits: one or two calls per cell, turn 0 only. A proper first tool call is not a finished
task; whether Hermes with the enforcement block would then complete the job on llama is
untested. The 0/30 A4 result on llama therefore measures Hermes's default prompt for this
model, not the model's ability to drive tools, and the article must say so. The fairness
request to the Hermes maintainers should ask whether the enforcement block is meant to be
off for llama-family models, and whether there is a supported setting to turn it on.

## Follow-up: Hermes's own settings on llama (run 2026-10-23)

The probe changed the request by hand. A Hermes user cannot do that, but can change two
documented settings that "auto" leaves off for llama-family model names:
`agent.tool_use_enforcement` (the "Tool-use enforcement" block) and `agent.execution_guidance`
(the "Execution discipline" block). Hermes's deepseek prompt, which flipped the probe (C6),
carries both. Three exploratory cells, 10 runs each (5 frozen posts x 2), llama-4-scout, clean,
same caps, proxy and gates as A4 (PREREGISTRATION.md deviation 15; `run_enforced.py`,
`enforced_turns.py`, `out/enforced-turns.json`, `out/enforced-gates.jsonl`).

| Cell | Settings | Agent turns, by kind | Runs that saved output | Gate publishable |
|---|---|---|---|---|
| A4-enf | enforcement on, streamed (Hermes default) | 40 empty | 0/10 | 0/10 |
| A4-enf-nostream | enforcement on, `model.streaming: false` | 10 text-form tool calls | 0/10 | 0/10 |
| A4-enf-exec | enforcement + execution guidance on, streamed | 23 proper tool calls, 6 text, 6 empty | 0/10 | 0/10 |

How the A4-enf-exec runs ended: 4 wrote the posts into the chat reply instead of saving the file
the task asked for; 1 tried to save but Hermes's `write_file` refused malformed JSON; 2 hit
"conversation has grown too long" for llama's context; 1 lost the gateway mid-turn; 2 never
reached the model (gateway failed at start, the same infra error as deviation 9).

What this changes:

- Enforcement alone does not help. Streamed, every turn still comes back empty; not streamed,
  llama writes the tool call as text and Hermes ends the run on it (Hermes treats a reply
  without `tool_calls` as final).
- Both blocks together do make llama drive the tools, which confirms the probe: the prompt is
  the switch. It still does not finish the job, for reasons that are about the model (context,
  JSON discipline, ignoring "save to file") rather than about Hermes's defaults.
- So the counted 0/30 is not only a Hermes-default artifact. With the best settings Hermes
  documents, llama-4-scout still produced nothing usable in 10 runs. The article reports both:
  the default prompt is what silences llama, and turning on the right settings gets tool use
  but not a finished post.
- The empty streamed replies are billed (completion tokens > 0) while the same request
  not streamed returns a text-form tool call (C1 vs C2, A4-enf vs A4-enf-nostream). One
  reading is that the Workers AI streaming path drops tool calls the model writes as text.
  That is a hypothesis; this study does not test it.
- Hermes's source names the same stall for another family ("GLM's tool-calls-as-plain-text
  stall (#53847)", `agent/prompt_builder.py`), handled by the execution-guidance list.
