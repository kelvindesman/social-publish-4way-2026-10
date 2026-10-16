/**
 * Slop score (0-100, production `scoreProse`, English patterns) for every run's
 * output. Writes out/slop.jsonl. No LLM. Social surface floor is 70
 * (scripts/slop-floor-baseline.json).
 */
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { scoreProse } from "../../../src/lib/content/prose-hygiene";

const runs = join(__dirname, "out", "runs");
const rows: string[] = [];
for (const id of readdirSync(runs)) {
	const p = join(runs, id, "output.json");
	if (!existsSync(p)) continue;
	try {
		const o = JSON.parse(readFileSync(p, "utf8"));
		const x = Array.isArray(o.x_thread) ? o.x_thread.join("\n\n") : "";
		const c = Array.isArray(o.carousel)
			? o.carousel
					.map(
						(s: { title?: string; body?: string }) =>
							`${s.title ?? ""}\n${s.body ?? ""}`,
					)
					.join("\n\n")
			: "";
		const all = [o.linkedin ?? "", x, c].join("\n\n");
		rows.push(
			JSON.stringify({
				run_id: id,
				slop_all: scoreProse(all, "en").score,
				slop_linkedin: scoreProse(o.linkedin ?? "", "en").score,
			}),
		);
	} catch {
		rows.push(
			JSON.stringify({ run_id: id, slop_all: null, slop_linkedin: null }),
		);
	}
}
writeFileSync(join(__dirname, "out", "slop.jsonl"), `${rows.join("\n")}\n`);
console.log(`scored ${rows.length}`);
