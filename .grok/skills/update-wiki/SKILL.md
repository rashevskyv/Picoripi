---
name: update-wiki
description: Keep Picoripi docs/wiki (and the README documentation map) in sync with user-visible product changes. Use after shipping UI, pipeline, AI, or settings behavior, or when the user runs /update-wiki or asks to refresh the wiki or README.
---

# Update Picoripi wiki

User-facing how-to lives in `docs/wiki/`. `README.md` is the map plus a short pitch. `CHANGELOG.md` is dated shipping notes. Do not copy a full how-to into all three.

## When to run

- The user says `/update-wiki`, "онови вікі", "update the wiki/README".
- You just changed behavior a translator can see, a setting, a pipeline step, or AI provider setup.

Skip for pure refactors, tests-only, or comments.

## Steps

1. Read `docs/wiki/7_Maintaining_This_Wiki.md` (ownership table). Do not invent a new page if an existing one owns the fact.
2. `git diff` / `git status` (and the files you edited this turn). List user-visible deltas in one sentence each.
3. Re-read the **Python/UI source** for that fact. Existing `docs/*.md` and plugin READMEs may be stale — do not copy them forward as truth.
4. Patch **only** the owning wiki page. Typical homes:
   - UI / hotkeys / Settings tabs → `docs/wiki/1_User_Guide_and_Workflow_Pipeline.md`
   - Which module implements a control → `docs/wiki/2_API_Reference.md`
   - Plugins (`BaseGameRules`, capabilities) → `docs/wiki/3_Plugin_Developer_Guide.md`
   - settings.json / .env / session → `docs/wiki/4_Configuration_Guide.md`
   - Gemini Web2API, WebTOP, Parallel Requests, local `/v1` proxy → `docs/wiki/5_Gemini_Web2API.md`
   - Virtual folders, TP window preview, Show Unsaved Only → `docs/wiki/6_Virtual_Navigation_and_Preview.md`
   - Localization Pipeline wizard, glossary auto-pass → `docs/wiki/8_Localization_Pipeline.md`
   - Script Markup Studio → `docs/wiki/9_Script_Markup.md`
   - AI Translate / Variation / Chat / providers → `docs/wiki/11_AI_Translation.md`
5. If the **entry point** moved (new menu, new recommended provider), add or fix one link in `README.md` Documentation Map and at most a short paragraph. Do not paste the wiki page into README.
6. Add a dated bullet to `CHANGELOG.md` only when this is a shipped behavior change, not a docs-only tidy.
7. If no wiki page fits and the fact will stay, add a row to `7_Maintaining_This_Wiki.md` **and** a link in `docs/wiki/README.md` before creating a new page.

## Rules

- One home per fact. If the wiki already says it, fix that sentence; do not append a second copy.
- Name controls as the UI shows them (English labels).
- Do not document unshipped `PIPELINE_ROADMAP.md` items as if they exist.
- Do not put Google cookies, API keys, or machine-local absolute paths in the wiki. Web2API checkout is "the `gemini-web2api` repo"; endpoint is `http://127.0.0.1:8081/v1`.
