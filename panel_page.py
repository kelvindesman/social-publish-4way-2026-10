"""Build the blind rater page for the human panel (PREREGISTRATION.md "Human panel").

  python3 -I panel_page.py <out.html>

Embeds out/panel-pairs.json (no arm or model labels; panel-key.json is never read here).
Each rater picks the post they would publish (A, B or neither) and, as an exploratory
addition logged under Deviations, ticks whether each side is good enough to post as-is.
Votes are saved per rater to the artifact's db (votes/<viewer id>) and can also be saved
as a JSON file. panel_votes.py turns either into out/panel-votes.json for panel.py analyze.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
# Only some arms append UTM tags to the post link, which would hint at the arm. Strip them
# for display so raters compare the copy itself (logged under Deviations).
UTM = re.compile(r"\?utm_[^\s\"]*")
PAIRS = json.loads(UTM.sub("", (HERE / "out" / "panel-pairs.json").read_text()))

TEMPLATE = r"""<title>Which Post Ships</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=Public+Sans:wght@400;600&family=IBM+Plex+Mono:wght@500&display=swap">
<style>
/* Layout: one pair per screen, two drafts side by side (stacked on phones), sticky vote bar. */
:root {
  --bg: #f6f7f4; --surface: #ffffff; --fg: #1c2321; --muted: #5d6763; --line: #d9ded9;
  --accent: #1f6f5c; --accent-fg: #ffffff; --pick: #e3f1ec; --warn: #9a5b13;
  --display: "Fraunces", Georgia, serif; --body: "Public Sans", system-ui, sans-serif; --mono: "IBM Plex Mono", ui-monospace, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #121715; --surface: #1a211e; --fg: #e6ebe8; --muted: #9aa5a0; --line: #2d3733;
  --accent: #5cc3a6; --accent-fg: #0d1412; --pick: #1d3a31; --warn: #e0a85a; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #121715; --surface: #1a211e; --fg: #e6ebe8; --muted: #9aa5a0; --line: #2d3733;
  --accent: #5cc3a6; --accent-fg: #0d1412; --pick: #1d3a31; --warn: #e0a85a; color-scheme: dark }
body { background: var(--bg); color: var(--fg); font: 15px/1.55 var(--body); }
.wrap { max-width: 1180px; margin: 0 auto; padding-block: 24px 120px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 20px; }
h1 { font: 600 clamp(26px, 4vw, 36px)/1.15 var(--display); margin: 0; text-wrap: balance; }
h2 { font: 600 20px/1.3 var(--display); margin: 0; text-wrap: balance; }
.lede { color: var(--muted); max-width: 65ch; margin: 0; }
.label { font: 500 11px/1 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
button { font: 600 14px var(--body); border-radius: 6px; border: 1px solid var(--line); background: var(--surface); color: var(--fg);
  padding: 9px 14px; cursor: pointer; }
button:focus-visible, input:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
button.primary, button[aria-pressed="true"] { background: var(--accent); color: var(--accent-fg); border-color: var(--accent); }
button:disabled { opacity: .45; cursor: default; }
.setup { display: grid; gap: 14px; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 18px; }
.setup ol { margin: 0; padding-left: 20px; max-width: 70ch; }
.meter { height: 6px; background: var(--line); border-radius: 3px; overflow: hidden; }
.meter > i { display: block; height: 100%; background: var(--accent); width: 0; transition: width .2s; }
.pair { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 760px) { .pair { grid-template-columns: 1fr; } }
.draft { min-width: 0; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 16px; display: grid; gap: 14px; align-content: start; }
.draft.chosen { border-color: var(--accent); background: var(--pick); }
.draft h3 { margin: 0; font: 600 18px var(--display); }
.block { display: grid; gap: 6px; }
.text { white-space: pre-wrap; overflow-wrap: anywhere; margin: 0; }
.tweets { margin: 0; padding-left: 20px; display: grid; gap: 6px; }
.tweets li { overflow-wrap: anywhere; }
.slides { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
.slide { aspect-ratio: 4 / 5; max-width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 10px; display: grid; align-content: start; gap: 6px; overflow: auto; background: var(--bg); }
.slide b { font: 600 13px/1.25 var(--display); overflow-wrap: anywhere; }
.slide span { font-size: 12px; line-height: 1.4; overflow-wrap: anywhere; }
.slide .n { font: 500 10px var(--mono); color: var(--muted); }
.asis { display: flex; gap: 8px; align-items: center; font-weight: 600; }
.asis input { width: 18px; height: 18px; accent-color: var(--accent); }
.bar { position: sticky; bottom: 0; background: var(--surface); border-top: 1px solid var(--line);
  padding-block: 12px calc(12px + env(safe-area-inset-bottom, 0px));
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
.bar .row { max-width: 1180px; margin: 0 auto; justify-content: space-between; }
.status { color: var(--muted); font-size: 13px; }
.status.err { color: var(--warn); }
.num { font-variant-numeric: tabular-nums; }
.done { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 18px; display: grid; gap: 12px; }
@media (prefers-reduced-motion: reduce) { .meter > i { transition: none; } }
</style>

<div class="wrap">
  <header class="row" style="justify-content: space-between; align-items: end;">
    <div style="display:grid; gap:6px; min-width:0;">
      <span class="label">lokerdollar.com · blind panel · 42 pairs</span>
      <h1>Which post would you publish?</h1>
    </div>
    <span class="label num" id="count">0 / 42 done</span>
  </header>
  <div class="meter" aria-hidden="true"><i id="meter"></i></div>

  <section class="setup" id="setup">
    <p class="lede">Each screen shows two drafts made from the same blog post: a LinkedIn post, an X thread and a 5-slide carousel. They were made by different systems; you are not told which. About 15 to 25 minutes in total.</p>
    <ol>
      <li>Read both drafts. Pick the one you would rather publish on the brand's accounts today, or <b>Neither</b> if you would publish neither.</li>
      <li>Under each draft, tick <b>Fine to post as-is</b> only if you would post it with no edits.</li>
      <li>Judge it as a reader would: is it interesting, clear, accurate to the title, worth a click? Ignore which looks more "AI".</li>
    </ol>
    <div class="row">
      <span>Your background:</span>
      <button type="button" id="t-tech" data-type="technical">I work in tech or marketing</button>
      <button type="button" id="t-non" data-type="non-technical">I don't</button>
    </div>
    <div class="row"><button type="button" class="primary" id="start" disabled>Start</button></div>
  </section>

  <section id="stage" hidden></section>

  <section class="done" id="done" hidden>
    <h2>All 42 pairs done. Thank you.</h2>
    <p class="lede" id="done-msg">Your answers are saved.</p>
    <div class="row"><button type="button" id="dl">Save my answers as a file</button><button type="button" id="review">Go back through pairs</button></div>
  </section>
</div>

<div class="bar" id="bar" hidden>
  <div class="row">
    <div class="row">
      <button type="button" id="prev">Back</button>
      <span class="status num" id="where"></span>
    </div>
    <div class="row">
      <button type="button" id="pick-a" data-c="a">Publish A</button>
      <button type="button" id="pick-n" data-c="neither">Neither</button>
      <button type="button" id="pick-b" data-c="b">Publish B</button>
      <button type="button" class="primary" id="next">Next</button>
    </div>
  </div>
  <div class="row" style="justify-content:center;"><span class="status" id="save"></span></div>
</div>

<script id="pairs" type="application/json">__PAIRS__</script>
<script>
const PAIRS = JSON.parse(document.getElementById("pairs").textContent).sort((x, y) => x.n - y.n);
const KEY = "panel-4way-draft";
let state = { rater_type: null, choices: {}, publish: {} };
try { const s = JSON.parse(localStorage.getItem(KEY) || "null"); if (s && s.choices) state = s; } catch {}
let i = 0, db = null, uid = null, saveTimer = null;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function local() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch {} }
function answered() { return PAIRS.filter((p) => state.choices[p.id]).length; }
function progress() {
  const n = answered();
  $("count").textContent = n + " / " + PAIRS.length + " done";
  $("meter").style.width = (100 * n / PAIRS.length) + "%";
}
function setSave(msg, err) { $("save").textContent = msg; $("save").className = "status" + (err ? " err" : ""); }

function persist() {
  local();
  if (!db || !uid) { setSave("Saved in this browser only. At the end, save your answers as a file and send it back."); return; }
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    try {
      await db.doc("votes/" + uid).set({ rater_type: state.rater_type, choices: state.choices, publish: state.publish, updated: new Date().toISOString() });
      setSave("Saved.");
    } catch (e) { setSave("Couldn't save online (" + (e && e.code || "error") + "). Your answers are kept in this browser; save them as a file at the end.", true); }
  }, 400);
}

function draft(side, d, pid) {
  const asis = (state.publish[pid] || {})[side] === true;
  const slides = d.carousel.map((s, k) => '<div class="slide"><span class="n">' + (k + 1) + '/' + d.carousel.length + '</span><b>' + esc(s.title) + '</b><span>' + esc(s.body) + '</span></div>').join("");
  return '<article class="draft' + (state.choices[pid] === side ? " chosen" : "") + '">' +
    '<h3>Draft ' + side.toUpperCase() + '</h3>' +
    '<div class="block"><span class="label">LinkedIn</span><p class="text">' + esc(d.linkedin) + '</p></div>' +
    '<div class="block"><span class="label">X thread · ' + d.x_thread.length + ' posts</span><ol class="tweets">' + d.x_thread.map((t) => '<li>' + esc(t) + '</li>').join("") + '</ol></div>' +
    '<div class="block"><span class="label">Carousel · ' + d.carousel.length + ' slides</span><div class="slides">' + slides + '</div></div>' +
    '<label class="asis" for="asis-' + side + '"><input type="checkbox" id="asis-' + side + '" data-side="' + side + '"' + (asis ? " checked" : "") + '> Fine to post as-is</label>' +
    '</article>';
}

function render() {
  const p = PAIRS[i];
  $("stage").innerHTML = '<div style="display:grid; gap:12px;"><span class="label">Source blog post</span><h2>' + esc(p.source) + '</h2></div>' +
    '<div class="pair" style="margin-top:14px;">' + draft("a", p.a, p.id) + draft("b", p.b, p.id) + '</div>';
  $("stage").querySelectorAll("input[type=checkbox]").forEach((c) => c.addEventListener("change", () => {
    state.publish[p.id] = Object.assign({ a: false, b: false }, state.publish[p.id], { [c.dataset.side]: c.checked });
    persist();
  }));
  ["pick-a", "pick-n", "pick-b"].forEach((id) => $(id).setAttribute("aria-pressed", String(state.choices[p.id] === $(id).dataset.c)));
  $("where").textContent = "Pair " + (i + 1) + " of " + PAIRS.length;
  $("prev").disabled = i === 0;
  $("next").disabled = !state.choices[p.id];
  $("next").textContent = i === PAIRS.length - 1 ? "Finish" : "Next";
  progress();
}

function show(view) {
  $("setup").hidden = view !== "setup";
  $("stage").hidden = view !== "stage";
  $("bar").hidden = view !== "stage";
  $("done").hidden = view !== "done";
}

function go(n) { i = Math.max(0, Math.min(PAIRS.length - 1, n)); render(); window.scrollTo({ top: 0 }); }

document.querySelectorAll("[data-type]").forEach((b) => b.addEventListener("click", () => {
  state.rater_type = b.dataset.type;
  document.querySelectorAll("[data-type]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  $("start").disabled = false;
  local();
}));
$("start").addEventListener("click", () => {
  const first = PAIRS.findIndex((p) => !state.choices[p.id]);
  if (first === -1) { show("done"); return; }
  show("stage"); go(first); persist();
});
["pick-a", "pick-n", "pick-b"].forEach((id) => $(id).addEventListener("click", () => {
  state.choices[PAIRS[i].id] = $(id).dataset.c; persist(); render();
}));
$("prev").addEventListener("click", () => go(i - 1));
$("next").addEventListener("click", () => {
  if (i < PAIRS.length - 1) { go(i + 1); return; }
  const missing = PAIRS.findIndex((p) => !state.choices[p.id]);
  if (missing !== -1) { go(missing); return; }
  show("done");
  $("done-msg").textContent = db && uid ? "Your answers are saved. You can close this page." : "Your answers are only in this browser. Save them as a file and send the file back to the person who sent you this link.";
});
$("review").addEventListener("click", () => { show("stage"); go(0); });
$("dl").addEventListener("click", async () => {
  const dl = await claude.use("downloads").catch(() => null);
  const data = JSON.stringify({ rater_type: state.rater_type, choices: state.choices, publish: state.publish, saved: new Date().toISOString() }, null, 1);
  if (!dl) { $("done-msg").textContent = "Saving a file isn't available here. Copy this text and send it back: " + data; return; }
  try { await dl.save({ filename: "panel-answers.json", data }); } catch (e) { $("done-msg").textContent = "The file wasn't saved (" + (e && e.code || "declined") + ")."; }
});

if (state.rater_type) { const b = document.querySelector('[data-type="' + state.rater_type + '"]'); if (b) b.setAttribute("aria-pressed", "true"); $("start").disabled = false; }
show("setup"); progress();

(async () => {
  try {
    db = await claude.use("db");
    const user = await claude.use("user");
    uid = user ? await user.id() : null;
    if (db && uid) {
      const snap = await db.doc("votes/" + uid).get();
      const d = snap.exists ? snap.data() : null;
      if (d && d.choices && Object.keys(d.choices).length >= Object.keys(state.choices).length) {
        state = { rater_type: d.rater_type || state.rater_type, choices: d.choices, publish: d.publish || {} };
        local(); progress();
        if (state.rater_type) { const b = document.querySelector('[data-type="' + state.rater_type + '"]'); if (b) b.setAttribute("aria-pressed", "true"); $("start").disabled = false; }
      }
    }
  } catch { db = null; }
})();
</script>
"""


def main() -> None:
	out = Path(sys.argv[1])
	data = json.dumps(PAIRS).replace("</", "<\\/")
	out.write_text(TEMPLATE.replace("__PAIRS__", data))
	print(f"{out} ({out.stat().st_size // 1024} KB, {len(PAIRS)} pairs)")


if __name__ == "__main__":
	main()
