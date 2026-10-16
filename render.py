"""Visual gate: render every run's 5 carousel slides with ONE fixed template
(1080x1350, brand colours) so only the copy differs between arms, then run
automatic checks. Runs inside the ld-poc-py image (rsvg-convert).

Auto checks per run -> out/visual-checks.jsonl
  slides      exactly 5 slides
  fits        every title fits in 3 lines and every body in 6 lines at >= the
              minimum font size (title 52 px, body 34 px) — else clipped/overflow
  min_font    smallest font size the auto-shrink had to use (smaller = denser)

  docker compose run --rm py python /app/render.py
"""

import json
import subprocess
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path("/out")
W, H, PAD = 1080, 1350, 80
PRIMARY, FG, BG, MUTED = "#006edc", "#1d1d1f", "#ffffff", "#6e6e73"


def fit(text: str, sizes: range, max_lines: int, width: int = W - 2 * PAD) -> tuple[list[str], int, bool]:
	for size in sizes:
		chars = max(8, int(width / (size * 0.56)))
		lines = textwrap.wrap(text, chars) or [""]
		if len(lines) <= max_lines:
			return lines, size, True
	size = sizes[-1]
	lines = textwrap.wrap(text, max(8, int((W - 2 * PAD) / (size * 0.56))))
	return lines[:max_lines], size, False


def slide_svg(i: int, title: str, body: str) -> tuple[str, int, bool]:
	t_lines, t_size, t_ok = fit(title, range(72, 51, -4), 3)
	b_lines, b_size, b_ok = fit(body, range(44, 33, -2), 6)
	y = 300
	parts = [
		f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">',
		f'<rect width="{W}" height="{H}" fill="{BG}"/>',
		f'<rect width="{W}" height="140" fill="{PRIMARY}"/>',
		f'<text x="{PAD}" y="92" font-family="DejaVu Sans" font-size="40" fill="{BG}">{i}/5</text>',
	]
	for line in t_lines:
		parts.append(f'<text x="{PAD}" y="{y}" font-family="DejaVu Sans" font-weight="bold" font-size="{t_size}" fill="{FG}">{escape(line)}</text>')
		y += int(t_size * 1.2)
	y += 60
	for line in b_lines:
		parts.append(f'<text x="{PAD}" y="{y}" font-family="DejaVu Sans" font-size="{b_size}" fill="{FG}">{escape(line)}</text>')
		y += int(b_size * 1.4)
	parts.append(f'<text x="{PAD}" y="{H - 70}" font-family="DejaVu Sans" font-size="34" fill="{MUTED}">lokerdollar.com</text></svg>')
	return "".join(parts), min(t_size, b_size), t_ok and b_ok


def main() -> None:
	rows = []
	for run in sorted((OUT / "runs").iterdir()):
		if not run.name.startswith("r"):  # counted runs only; pilot ids start with "p"
			continue
		p = run / "output.json"
		row = {"run_id": run.name, "slides": 0, "fits": False, "min_font": None}
		try:
			slides = json.loads(p.read_text()).get("carousel") or []
		except (OSError, json.JSONDecodeError, AttributeError):
			rows.append(row)
			continue
		d = OUT / "renders" / run.name
		d.mkdir(parents=True, exist_ok=True)
		fits, fonts = True, []
		for i, s in enumerate(slides[:5], 1):
			svg, font, ok = slide_svg(i, str(s.get("title", "")), str(s.get("body", "")))
			fits &= ok
			fonts.append(font)
			(d / f"slide-{i}.svg").write_text(svg)
			subprocess.run(["rsvg-convert", "-w", "540", "-o", str(d / f"slide-{i}.png"), str(d / f"slide-{i}.svg")], check=True)
			(d / f"slide-{i}.svg").unlink()
		row.update(slides=len(slides), fits=fits and len(slides) == 5, min_font=min(fonts) if fonts else None)
		rows.append(row)
	(OUT / "visual-checks.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
	print(f"rendered {len(rows)}")


if __name__ == "__main__":
	main()
