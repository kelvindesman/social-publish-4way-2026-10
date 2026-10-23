"""Tables for error-analysis.md, computed from out/error-codes.jsonl.

Standard library only. Run from anywhere:

    python3 -I error_tables.py

Prints Markdown tables to stdout. Every count in error-analysis.md comes from
this output.
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS = [json.loads(line) for line in open(HERE / "out" / "error-codes.jsonl") if line.strip()]

ARMS = ["A1-cron", "A2-cron-llm", "A3-langgraph", "A4-hermes"]
MODES = [
    "no_output",
    "page_chrome_leak",
    "wrong_link",
    "thin_linkedin",
    "generic_voice",
    "filler_content",
    "factual_distortion",
    "source_error_repeated",
    "pasted_not_adapted",
    "wall_of_text",
    "spec_overrun",
]
QUALITY = ["stat_hook", "concrete_examples", "caveat", "actionable", "native_structure"]


def cells(rows):
    return sorted({(r["arm"], r["model"]) for r in rows}, key=lambda am: (ARMS.index(am[0]), am[1]))


def pct(n, d):
    return f"{n} ({100 * n / d:.0f}%)" if d else "-"


def table(header, body):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in body]
    return "\n".join(out)


def by(rows, keyf):
    groups = {}
    for r in rows:
        groups.setdefault(keyf(r), []).append(r)
    return groups


def mode_table(rows, keyf, keys, label):
    groups = by(rows, keyf)
    header = ["mode"] + [f"{label(k)} (n={len(groups.get(k, []))})" for k in keys]
    body = []
    for m in MODES:
        body.append([m] + [pct(sum(m in r["codes"] for r in groups.get(k, [])), len(groups.get(k, []))) for k in keys])
    body.append(["editor would publish"] + [pct(sum(r["would_publish"] for r in groups.get(k, [])), len(groups.get(k, []))) for k in keys])
    body.append(["gate publishable"] + [pct(sum(r["gate_publishable"] for r in groups.get(k, [])), len(groups.get(k, []))) for k in keys])
    return table(header, body)


def main():
    clean = [r for r in ROWS if r["clean"]]
    fault = [r for r in ROWS if not r["clean"]]

    print("## Coverage\n")
    body = []
    for am in cells(ROWS):
        g = [r for r in ROWS if (r["arm"], r["model"]) == am]
        c = [r for r in g if r["clean"]]
        f = [r for r in g if not r["clean"]]
        body.append([am[0], am[1], len(c), sum("no_output" not in r["codes"] for r in c),
                     len(f), sum("no_output" not in r["codes"] for r in f)])
    body.append(["all", "", len(clean), sum("no_output" not in r["codes"] for r in clean),
                 len(fault), sum("no_output" not in r["codes"] for r in fault)])
    print(table(["arm", "model", "clean runs", "clean with output", "fault runs", "fault with output"], body))

    print("\n## Failure modes, clean runs, by arm\n")
    print(mode_table(clean, lambda r: r["arm"], ARMS, lambda k: k))

    print("\n## Failure modes, clean runs, by arm x model\n")
    ks = cells(clean)
    print(mode_table(clean, lambda r: (r["arm"], r["model"]), ks, lambda k: f"{k[0]} {k[1]}"))

    print("\n## Failure modes, clean runs that produced output, by arm x model\n")
    without = [r for r in clean if "no_output" not in r["codes"]]
    ks = cells(without)
    print(mode_table(without, lambda r: (r["arm"], r["model"]), ks, lambda k: f"{k[0]} {k[1]}"))

    print("\n## Top 3 failure modes per arm (clean runs; ties broken by mode order)\n")
    body = []
    for a in ARMS:
        g = [r for r in clean if r["arm"] == a]
        cnt = Counter(m for r in g for m in r["codes"])
        top = sorted(cnt.items(), key=lambda kv: (-kv[1], MODES.index(kv[0])))[:3]
        body.append([a, len(g)] + [f"{m} {n}" for m, n in top])
    print(table(["arm", "n", "1st", "2nd", "3rd"], body))

    print("\n## Quality markers, clean runs that produced output, by arm x model\n")
    groups = by(without, lambda r: (r["arm"], r["model"]))
    ks = cells(without)
    header = ["marker"] + [f"{k[0]} {k[1]} (n={len(groups[k])})" for k in ks]
    body = [[q] + [pct(sum(q in r["quality"] for r in groups[k]), len(groups[k])) for k in ks] for q in QUALITY]
    print(table(header, body))

    print("\n## Gate verdict vs editor call, per arm, clean runs\n")
    body = []
    for a in ARMS:
        g = [r for r in clean if r["arm"] == a]
        both = sum(r["gate_publishable"] and r["would_publish"] for r in g)
        gate_only = sum(r["gate_publishable"] and not r["would_publish"] for r in g)
        editor_only = sum(r["would_publish"] and not r["gate_publishable"] for r in g)
        neither = sum(not r["gate_publishable"] and not r["would_publish"] for r in g)
        agree = both + neither
        body.append([a, len(g), both, gate_only, editor_only, neither, pct(agree, len(g))])
    print(table(["arm", "n", "gate yes / editor yes", "gate yes / editor no", "gate no / editor yes",
                 "gate no / editor no", "agreement"], body))

    print("\n## Gate verdict vs editor call, per arm x model, clean runs\n")
    body = []
    for am in cells(clean):
        g = [r for r in clean if (r["arm"], r["model"]) == am]
        body.append([am[0], am[1], len(g),
                     sum(r["gate_publishable"] and r["would_publish"] for r in g),
                     sum(r["gate_publishable"] and not r["would_publish"] for r in g),
                     sum(r["would_publish"] and not r["gate_publishable"] for r in g),
                     sum(not r["gate_publishable"] and not r["would_publish"] for r in g)])
    print(table(["arm", "model", "n", "yes/yes", "gate yes, editor no", "gate no, editor yes", "no/no"], body))

    print("\n## Gate verdict vs editor call, per arm, fault runs\n")
    body = []
    for a in ARMS:
        g = [r for r in fault if r["arm"] == a]
        body.append([a, len(g),
                     sum(r["gate_publishable"] and r["would_publish"] for r in g),
                     sum(r["gate_publishable"] and not r["would_publish"] for r in g),
                     sum(r["would_publish"] and not r["gate_publishable"] for r in g),
                     sum(not r["gate_publishable"] and not r["would_publish"] for r in g)])
    print(table(["arm", "n", "yes/yes", "gate yes, editor no", "gate no, editor yes", "no/no"], body))

    print("\n## Why the gate and the editor disagree, clean runs\n")
    gate_no_ed_yes = [r for r in clean if r["would_publish"] and not r["gate_publishable"]]
    fp = sum("facts_gate_k_abbrev_false_positive" in r["flags"] for r in gate_no_ed_yes)
    slide = sum("slide_over" in r["flags"] for r in gate_no_ed_yes)
    print(f"- gate no, editor yes: {len(gate_no_ed_yes)} runs; facts-gate k-abbreviation false positive in {fp}; slide over 160/40 in {slide}")
    gate_yes_ed_no = [r for r in clean if r["gate_publishable"] and not r["would_publish"]]
    cnt = Counter(m for r in gate_yes_ed_no for m in r["codes"])
    print(f"- gate yes, editor no: {len(gate_yes_ed_no)} runs; modes present: "
          + ", ".join(f"{m} {n}" for m, n in sorted(cnt.items(), key=lambda kv: (-kv[1], MODES.index(kv[0])))))

    print("\n## Facts gate failures, all runs with output\n")
    out_rows = [r for r in ROWS if "no_output" not in r["codes"]]
    fp_all = [r for r in out_rows if "facts_gate_k_abbrev_false_positive" in r["flags"]]
    print(f"- runs flagged as k-abbreviation false positives: {len(fp_all)}")
    leak = [r for r in out_rows if "page_chrome_leak" in r["codes"]]
    print(f"- runs with page_chrome_leak: {len(leak)}; of these the gate called publishable: {sum(r['gate_publishable'] for r in leak)}")

    print("\n## Mechanical sub-flags, clean runs with output\n")
    sub = ["li_short", "li_long", "x_count_off", "tweet_over", "slide_count", "slide_over", "url_in_slide",
           "wrong_link_target", "link_missing", "internal_url"]
    groups = by(without, lambda r: r["arm"])
    header = ["flag"] + [f"{a} (n={len(groups.get(a, []))})" for a in ARMS]
    body = [[s] + [sum(s in r["flags"] for r in groups.get(a, [])) for a in ARMS] for s in sub]
    print(table(header, body))

    print("\n## No-output causes\n")
    nos = [r for r in ROWS if "no_output" in r["codes"]]
    cnt = Counter((r["arm"], r["model"], r["fault"], r["flags"][0]) for r in nos)
    body = [[a, m, f, c, n] for (a, m, f, c), n in sorted(cnt.items(), key=lambda kv: (ARMS.index(kv[0][0]), kv[0][1:]))]
    print(table(["arm", "model", "fault", "cause", "runs"], body))

    print("\n## Fault runs that produced output: modes\n")
    fo = [r for r in fault if "no_output" not in r["codes"]]
    groups = by(fo, lambda r: (r["arm"], r["model"], r["fault"]))
    body = []
    for k in sorted(groups, key=lambda k: (ARMS.index(k[0]), k[1], k[2])):
        g = groups[k]
        cnt = Counter(m for r in g for m in r["codes"])
        body.append([k[0], k[1], k[2], len(g), sum(r["would_publish"] for r in g), sum(r["gate_publishable"] for r in g),
                     ", ".join(f"{m} {n}" for m, n in sorted(cnt.items(), key=lambda kv: (-kv[1], MODES.index(kv[0]))))])
    print(table(["arm", "model", "fault", "with output", "editor yes", "gate yes", "modes"], body))


if __name__ == "__main__":
    main()
