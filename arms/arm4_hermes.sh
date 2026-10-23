#!/usr/bin/env bash
# Arm 4 — autonomous agent (Hermes Agent). Gets the goal and two toolsets
# (terminal + file). No step script: the agent decides how to fetch, draft,
# check and save. Turn cap 15, wall cap 600 s.
set -euo pipefail
RUN_ID="$1"; URL="$2"
OUTDIR="/out/runs/$RUN_ID"; mkdir -p "$OUTDIR" "$HERMES_HOME"
TASK="$(python -c 'import sys; sys.path.insert(0,"/app/common"); from shared import TASK; print(TASK)')"
FETCH_URL="$(python -c 'import sys; sys.path.insert(0,"/app/common"); from shared import fetch_url; print(fetch_url(sys.argv[1]))' "$URL")"
PROMPT="Goal: publish-ready social posts for this blog post: $URL
Fetch it with: curl -s -H 'Accept: text/markdown' '$FETCH_URL'
Link the posts to: $URL
$TASK
Check your own lengths before saving. Save the final JSON object (nothing else) to $OUTDIR/output.json, then stop."
MODEL="${MODEL:-@cf/meta/llama-4-scout-17b-16e-instruct}"
# Fresh Hermes home per run: config is the only setup. Same caps as the CLI flags.
cat > "$HERMES_HOME/config.yaml" <<YAML
model:
  default: "$MODEL"
  provider: "custom"
  base_url: "$PROXY_BASE/run/$RUN_ID/v1"
  api_key: "via-proxy"
  stream: ${HERMES_STREAM:-true}
agent:
  max_turns: 15
  run_budget_seconds: 600
YAML
# Exploratory A4-enf (run_enforced.py): force Hermes's documented tool-use enforcement prompt,
# which "auto" gives only to gpt/gemini/qwen/deepseek-class model names. Unset for counted runs.
if [ -n "${HERMES_ENFORCE:-}" ]; then
	printf '  tool_use_enforcement: true\n' >> "$HERMES_HOME/config.yaml"
fi
# Exploratory A4-enf-exec: also the "Execution discipline" block (agent.execution_guidance), which
# "auto" gives deepseek but not llama. Both blocks on = the prompt the probe's C6 cell used.
if [ -n "${HERMES_EXEC_GUIDANCE:-}" ]; then
	printf '  execution_guidance: true\n' >> "$HERMES_HOME/config.yaml"
fi
# Hermes reads `model.streaming`, not `model.stream` (agent/agent_init.py), so the line above
# never turned streaming off. Counted runs streamed, as intended; only A4-enf-nostream sets this.
if [ "${HERMES_STREAM:-true}" = "false" ]; then
	sed -i 's/^  stream: false$/  streaming: false/' "$HERMES_HOME/config.yaml"
fi
exec hermes chat -Q -q "$PROMPT" \
	--provider custom --base-url "$PROXY_BASE/run/$RUN_ID/v1" --api-key via-proxy \
	-m "$MODEL" \
	--max-turns 15 --run-budget 600 --yolo --ignore-rules -t terminal,file \
	> "$OUTDIR/agent-final.txt" 2> "$OUTDIR/agent-stderr.txt"
