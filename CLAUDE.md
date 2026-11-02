@AGENTS.md

Project rules live in AGENTS.md (imported above). Work queue: plan.md. Shipped history: CHANGELOG.md.
Claude Code specifics: `.claude/settings.json` runs `.claude/hooks/graphify-session.sh` at session start —
trust its `Graphify:` line, do not re-check. Pre-report gate: `python tasks.py check`. Skills are canonical in
`.agents/skills/*`; `.claude/skills/*` only point there.
