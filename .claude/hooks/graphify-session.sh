#!/usr/bin/env bash
# SessionStart hook: make sure the Graphify graph exists and is current. Never blocks the session.
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || { echo "Graphify: cannot cd to project"; exit 0; }
command -v graphify >/dev/null 2>&1 || { echo "Graphify: CLI not on PATH — graph not refreshed"; exit 0; }
report="graphify-out/GRAPH_REPORT.md"
if [ ! -f "$report" ]; then
  echo "Graphify: no graph — generating (slow, once)"; graphify . >/dev/null 2>&1 || echo "Graphify: generation failed"
elif [ -n "$(find . -type f -name '*.py' -newer "$report" \
      -not -path './graphify-out/*' -not -path './.git/*' -not -path './venv/*' -not -path './.venv/*' \
      -not -path './scratch/*' -not -path '*/__pycache__/*' 2>/dev/null | head -1)" ]; then
  echo "Graphify: stale — updating"; graphify update . >/dev/null 2>&1 || echo "Graphify: update failed"
else
  echo "Graphify: current"
fi
exit 0
