"""Merge hand codes with mechanical codes and write out/error-codes.jsonl.

Run: python3 -I build_codes.py
"""
import json
import re
from pathlib import Path

STUDY = Path(__file__).resolve().parent
SCR = STUDY / "error-coding"  # one coder's hand codes, one file per batch
OUT = STUDY / "out"

# Open code -> axial failure mode. None = dropped (recomputed mechanically or not a failure).
OPEN_TO_MODE = {
    "widget_content": "page_chrome_leak",
    "widget_number": "page_chrome_leak",
    "generic_hook": "generic_voice",
    "generic_padding": "generic_voice",
    "hype": "generic_voice",
    "wrong_platform_cta": "generic_voice",
    "filler_tweet": "filler_content",
    "filler_slides": "filler_content",
    "thin_x_thread": "filler_content",
    "repetition": "filler_content",
    "repetitive_cta": "filler_content",
    "url_only_tweet": "filler_content",
    "misattributed_fact": "factual_distortion",
    "unsupported_claim": "factual_distortion",
    "muddled_stat": "factual_distortion",
    "source_error_copied": "source_error_repeated",
    "misleading_claim_copied": "source_error_repeated",
    "copies_title_desc": "pasted_not_adapted",
    "headings_as_slides": "pasted_not_adapted",
    "slide_title_truncated": "pasted_not_adapted",
    "boilerplate_heading": "pasted_not_adapted",
    "verbatim_copy": "pasted_not_adapted",
    "wall_of_text": "wall_of_text",
    # recomputed mechanically from the output, so the hand version is dropped
    "li_stub": None,
    "thin_linkedin": None,
    "slide_body_over": None,
    "url_in_slide": None,
    "internal_url": None,
    "no_output_crash": None,
}
QUALITY_MAP = {
    "stat_hook": "stat_hook",
    "concrete_examples": "concrete_examples",
    "caveat": "caveat",
    "actionable": "actionable",
    "audience_fit": "actionable",
    "native_structure": "native_structure",
}

NUM = re.compile(r"(?<![\w/])\$?\d[\d,]*(?:\.\d+)?%?")
URL = re.compile(r"https?://\S+")


def nums(text):
    out = set()
    for m in NUM.findall(text):
        n = m.replace("$", "").replace(",", "").rstrip("%")
        if n.endswith(".0"):
            n = n[:-2]
        out.add(n)
    return out


def load_jsonl(p):
    return [json.loads(line) for line in open(p) if line.strip()]


def key_of(run_id):
    return re.sub(r"-\d+$", "", run_id)


def load_hand():
    hand = {}
    for f in sorted(SCR.glob("codes_*.txt")):
        for line in open(f):
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("|", 4)
            if len(parts) != 5:
                raise SystemExit(f"bad line in {f.name}: {line[:80]}")
            k, codes, qual, pub, reason = (p.strip() for p in parts)
            if k in hand:
                raise SystemExit(f"duplicate key {k}")
            hand[k] = {
                "open": [c for c in codes.split(",") if c],
                "quality": [q for q in qual.split(",") if q],
                "pub": pub == "1",
                "reason": reason,
            }
    return hand


def mechanical(o, slug):
    """Codes computed from the output itself."""
    modes, flags = set(), set()
    li = str(o.get("linkedin", ""))
    xs = [str(t) for t in o.get("x_thread", [])]
    cs = [c for c in o.get("carousel", []) if isinstance(c, dict)]
    if len(li) < 450:
        modes.add("thin_linkedin")
    spec = []
    if 450 <= len(li) < 600:
        spec.append("li_short")
    if len(li) > 1800:
        spec.append("li_long")
    if not 3 <= len(xs) <= 6:
        spec.append("x_count_off")
    if any(len(t) > 270 for t in xs):
        spec.append("tweet_over")
    if len(cs) != 5:
        spec.append("slide_count")
    if any(len(str(c.get("title", ""))) > 40 or len(str(c.get("body", ""))) > 160 for c in cs):
        spec.append("slide_over")
    if spec:
        modes.add("spec_overrun")
        flags.update(spec)
    slides_text = " ".join(f"{c.get('title', '')} {c.get('body', '')}" for c in cs)
    if URL.search(slides_text):
        flags.add("url_in_slide")
    all_text = "\n".join([li, *xs, slides_text])
    if "fixtures:8000" in all_text:
        modes.add("wrong_link")
        flags.add("internal_url")
    elif not (slug in li and any(slug in t for t in xs)):
        modes.add("wrong_link")
        flags.add("wrong_link_target" if "lokerdollar.com" in all_text else "link_missing")
    return modes, flags


def k_abbrev_fp(invented, source_nums):
    if not invented:
        return False
    vals = []
    for s in source_nums:
        try:
            vals.append(float(s))
        except ValueError:
            pass
    for n in invented:
        try:
            v = float(n) * 1000
        except ValueError:
            return False
        # "132k" for 132,400 or "1.5k" for 1,500: a source figure within 1,000 of n*1000
        if not any(0 <= s - v < 1000 or abs(s - v) < 1e-6 for s in vals):
            return False
    return True


def no_output_cause(run_dir, run):
    final = (run_dir / "agent-final.txt").read_text() if (run_dir / "agent-final.txt").exists() else ""
    tail = run.get("stderr_tail", "")
    if "No reply" in final:
        return "model_no_reply", "The agent never got a reply from llama-4-scout; no file was written."
    if "Gateway starting: deadline" in final:
        return "infra_gateway_timeout", "Hermes could not open the model connection (gateway deadline); infrastructure failure, no file."
    if "broken" in final and "x_thread" in final:
        return "echoed_broken_json", "The agent echoed the injected broken JSON as its final text and wrote no file."
    if "fabricat" in final or "won't invent" in final or "not created output.json" in final or "did **not** write" in final:
        return "declined_missing_source", "Correctly refused to write anything for a missing post and explained why."
    if "404" in tail:
        return "crash_404", "Unhandled HTTP 404 traceback; nothing published, which is the right outcome reached untidily."
    if "429" in tail:
        return "crash_429", "Unhandled HTTP 429 traceback; no retry, so a transient rate limit lost the post."
    if final:
        return "no_file_written", "The agent wrote draft text to its reply but never wrote the output file."
    return "unknown", "No output file and no explanation."


def main():
    # Late infra re-runs (PREREGISTRATION.md deviation 9) replace the run they re-ran.
    rr = OUT / "rerun-infra-runs.jsonl"
    reruns = {r["replaces"]: r for r in load_jsonl(rr)} if rr.exists() else {}
    runs = [reruns.get(r["run_id"], r) for r in load_jsonl(OUT / "runs.jsonl") if r["run_id"].startswith("r")]
    gates = {g["run_id"]: g for g in load_jsonl(OUT / "gates.jsonl")}
    rg = OUT / "rerun-infra-gates.jsonl"
    if rg.exists():
        gates.update({g["run_id"]: g for g in load_jsonl(rg)})
    sources = {}
    for f in (OUT / "sources").glob("*.json"):
        d = json.loads(f.read_text())
        sources[d["url"]] = d
    hand = load_hand()
    used = set()
    rows = []
    for r in sorted(runs, key=lambda x: x["run_id"]):
        rid = r["run_id"]
        k = key_of(rid)
        slug = r["source"].rstrip("/").rsplit("/", 1)[-1]
        g = gates.get(rid, {})
        run_dir = OUT / "runs" / rid
        out_p = run_dir / "output.json"
        row = {
            "run_id": rid,
            "arm": r["arm"],
            "model": r["model"],
            "fault": r["fault"],
            "source_slug": slug,
            "clean": r["fault"] == "none",
            "gate_publishable": bool(g.get("publishable")),
        }
        output = None
        if out_p.exists():
            try:
                output = json.loads(out_p.read_text())
            except json.JSONDecodeError:
                output = None
        if output is None:
            cause, reason = no_output_cause(run_dir, r)
            h = hand.get(k)
            if h:
                used.add(k)
            row.update(codes=["no_output"], quality=[], open_codes=[], flags=[cause],
                       would_publish=False, reason=reason)
            rows.append(row)
            continue
        h = hand.get(k)
        if h is None:
            raise SystemExit(f"output present but no hand code for {k}")
        used.add(k)
        modes, flags = mechanical(output, slug)
        for c in h["open"]:
            if c not in OPEN_TO_MODE:
                raise SystemExit(f"unmapped open code {c} in {k}")
            m = OPEN_TO_MODE[c]
            if m:
                modes.add(m)
        src = sources.get(r["source"])
        if src is not None:
            src_nums = nums(src["title"] + "\n" + src["description"] + "\n" + src["text"])
            if not g.get("facts", True) and k_abbrev_fp(g.get("invented_numbers") or [], src_nums):
                flags.add("facts_gate_k_abbrev_false_positive")
        qual = sorted({QUALITY_MAP[q] for q in h["quality"]})
        row.update(codes=sorted(modes), quality=qual, open_codes=h["open"], flags=sorted(flags),
                   would_publish=h["pub"], reason=h["reason"])
        rows.append(row)
    unused = set(hand) - used
    if unused:
        raise SystemExit(f"hand codes with no matching run: {sorted(unused)[:5]}")
    with open(OUT / "error-codes.jsonl", "w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} rows; hand-coded {len(used)}")


if __name__ == "__main__":
    main()
