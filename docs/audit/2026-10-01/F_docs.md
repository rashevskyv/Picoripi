> **Auditor's correction (2026-10-01):** The "MemPalace mismatch" finding is an artefact of the audit snapshot — `core/mempalace*`, `ui/mempalace*`, `tools/mempalace_*` are present and tracked (64 files). Keep the MemPalace manifesto verdict (cut to a short contract + archive) for size reasons only, not because the feature is gone. `gemini/`, `.grok/*` (except `skills`), `.claude/` are already git-ignored — their removal is local cleanup.

# F. Documentation and AI-friendliness audit — Picoripi v0.3.141-dev

Method: static read of the snapshot at `/home/claude/pico`. Token figures are estimates (ASCII ~3.8 chars/token, code/symbol text ~3.2, Cyrillic ~2.3), ±25%. Cyrillic text costs about 1.7x more tokens per KB than English.

## 0. Verdict

The wiki (EN+UK) is accurate, in sync and well owned. Everything around it is the problem:
- **The entry path is too expensive.** README + GEMINI.md + wiki README already cost about 25k tokens. Following GEMINI.md's graph rule literally adds a 71k-token `GRAPH_REPORT.md`.
- **~240k tokens of process logs sit in the repo root**, mostly Ukrainian and closed.
- **Roughly 190KB of MemPalace docs describe code that is absent from this snapshot.**
- **There is no short agent entry file** (`AGENTS.md` or `CLAUDE.md`) and no doc index.

## 1. Entry-point quality

| Read | KB | ~tokens |
|---|---|---|
| `README.md` (66% is "Key Features", which duplicates the wiki) | 62.6 | 16.6k |
| `GEMINI.md` (rules 2.4k + project overview 5.1k) | 28.3 | 7.5k |
| `docs/wiki/README.md` | 2.0 | 0.55k |
| **Minimum "orientation" total** | | **~24.7k (25% of 100k)** |
| `docs/AI_DEVELOPMENT_MANIFESTO.md` (rules that GEMINI.md already holds) | 14.6 | 3.9k |
| `graphify-out/GRAPH_REPORT.md` (3,396 lines; `graph.json` is 20MB) | 241 | **~71k** |

- **No "read this, then this" path exists.** GEMINI.md is read automatically only by Gemini tools, so Claude, Codex and Grok models never see the "operating contract". There is no `CLAUDE.md` or `AGENTS.md`.
- **README says the wiki is the start, GEMINI.md says README is the map, and the wiki README says README is the map.** Three docs say other docs "may be stale" (README, wiki README, wiki 7) but none says which ones.
- **Graphify-first is stated in 4 places with 3 conflicting variants:**
  - `GEMINI.md`: refresh (`graphify update`) at the start of every conversation, then "start from god nodes, communities". That invites reading the 71k-token report.
  - `.agents/rules/graphify.md` (always_on): `graphify query/path/explain` first, report only for broad review, update after edits. This is the best variant.
  - `.agents/workflows/graphify.md`: points to `~/.gemini/config/skills/graphify/SKILL.md`, a path outside the repo.
  - README §6: install plus `extract . --backend openai`, which costs API money, whereas `update` is free.
- **The graph itself is noisy:**
  - Tests are 28% of nodes, and `CHANGELOG`/`walkthrough`/`AUDIT`/`plan`/`docs` markdown adds ~1.6k nodes.
  - There is no `.graphifyignore`.
  - 890 communities have cohesion around 0.03 and are named after a random member ("test_translation_handler.py", "_dialog", "._rules").
  - God nodes are `tr()` (638 edges) and `log_*`, which is useless for architecture.
  - `graphify explain "DataStateProcessor"` is cheap (~1k tokens) but half of it is test files.
- **GEMINI.md rules, actionable (keep):**
  - `tr("English")` plus the same key in `locales/uk.json` in the same change.
  - Never add Russian.
  - No `Mock` in product code; `tests/test_architecture/` enforces part of this.
  - No `processEvents()`, no sync I/O on the UI thread.
  - Test commands.
  - The 3-file plugin-capability propagation rule.
  - The doc update list.
- **GEMINI.md rules, vague (cut or sharpen):**
  - "Prefer small verified changes", "narrowest complete fix", "read nearby code".
  - "Cache only when invalidation is clear".
  - "Update docs when behavior changes", with no behavior-to-file map.
  - The self-checklist, which restates the rules above.
- **The user's most important process rules are buried.** They are 3 Ukrainian lines at the very bottom, after 300 lines: bump version on commit, update audit/gemini/readme/changelog, write plans and walkthroughs in Ukrainian.
- **Language conflict:**
  - GEMINI.md says walkthroughs and plans are Ukrainian.
  - `AUDIT.md` §11.2 says `walkthrough.md (English)`.
  - The files themselves are Ukrainian.

## 2. Redundancy and drift

**The same fact lives in many places.**
- **Plugin authoring:** `docs/PLUGIN_AUTHORING_GUIDE.md`, `plugins/DEVELOPER_GUIDE.md`, `wiki/3`, `plugins/default_plugin/README.md`, `AI_PLUGIN_ASSISTANT_PROMPT.md`. That is 5 docs, and 2 of them already disagree with the code.
- **Release/deploy:** GEMINI.md "Release Rules", `.agents/skills/deploy/SKILL.md` (138 lines), `.agents/workflows/deploy.md` (91 lines, different text), `scripts/deploy.py`, `scripts/bump_version.py`.
  - `deploy.py` bumps constants, README and CHANGELOG but not GEMINI.md or AUDIT.md.
  - Hence GEMINI.md carries `v0.3.141-dev` in its title and `v0.3.133-dev` in its overview.
- **Directory layout:** GEMINI.md, README "Directory Structure", `wiki/2` and `FEATURE_REFERENCE`.
- **Feature lists:** README Key Features, GEMINI.md Core Features, `FEATURE_REFERENCE`, wiki 1.
- **One release (v0.3.141, glossary sync on close) in 6 files:** CHANGELOG, walkthrough, plan, task, GEMINI.md, README. Per commit, 8 files must be touched (constants, README, GEMINI, AUDIT, CHANGELOG, plan, task, walkthrough).
- **Skills:** `.grok/skills/*` is byte-identical to `.agents/skills/*`. GEMINI.md still points to `.grok/skills/update-wiki`.
- **Data in the wrong place:** `plugins/plain_text/translation_prompts/glossary.md` is a near-copy of the Zelda WW glossary (24 diff lines, 38KB), shipped in the "generic" plugin. `gemini/` has its own copies (1.7MB).

**Claim spot-check (13 items): 6 correct, 7 stale.**
- **Correct:**
  - Default translation config: provider `disabled`, workers 6, OpenAI timeout 60 s, Gemini 120 s.
  - Parallel Requests 1–16 (default 6), in `ui/settings/ai_mixin.py`.
  - Auto-Sleep 5 min (`300` s), tooltip font 11.
  - The Perplexity provider exists.
  - The glossary pipeline raises timeout to at least 180 s (`glossary_pipeline_handler.py:197`).
  - Menus Tools/Navigation/Bookmarks/Language, Settings under File, and the 5 pipeline steps all match.
- **Stale:**
  - README "Settings → Preferences → AI Translation": there is no Preferences menu.
  - README and GEMINI.md say "DeepL" and `DEEPL_API_KEY`: no DeepL code exists.
  - `wiki/2` points at `ui/mempalace_builder_dialog.py`, which is gone, and `dialogs/ai_batch_translation_dialog.py`, which is now `components/`.
  - `FEATURE_REFERENCE` has 8 dead paths (12% of its path references), for example `components/line_numbered_text_edit.py` (now `components/editor/`), `core/yaz0.py` (now `core/containers/`) and `handlers/translation/providers.py` (now `core/translation/`).
  - `PLUGIN_AUTHORING_GUIDE` lists `get_tag_pattern()` as required on `BaseGameRules`; it is only defined in `plain_text` and `default_plugin`. `get_preview_window_style` is not on the base class either.
  - GEMINI.md has `checkable_combobox.py` (not found), `file:///d:/git/dev/...` absolute links (the wiki's own rule forbids machine paths), and two versions.
  - README Directory Structure omits `core/glossary/`, `core/glossary_build/`, `core/translation/`, `core/project/`, `core/script_markup/`, `plugins/zelda_bmg/` (the main plugin), `dialogs/` and `companion/`.
- **MemPalace mismatch, the biggest finding:**
  - No `core/mempalace*`, `ui/mempalace*`, `tools/mempalace*` or MemPalace tests exist in this snapshot.
  - Only the stub `get_mempalace_client()` and context-menu hooks remain.
  - 18 of 46 path references in `MEMPALACE_CONTEXT_MANIFESTO.md` (39%) are dead. README §8 and the CHANGELOG still describe it as shipped.
  - Either the snapshot is pruned or the feature was removed. Verify upstream.
- **Path-reference drift rate:** ~0–7% in GEMINI.md, wiki and `wiki/2`; 12% in FEATURE_REFERENCE; 39% in the MemPalace manifesto.
- **EN vs UK wiki:**
  - Line counts are identical for 10 of 12 pages (1:374/374, 11:163/163, 4:107/107, 3:145/145 …).
  - README (29 vs 23) and `7_Maintaining` (41 vs 26) differ. Both UK versions are shorter but complete; UK 7 carries an EN/UK mapping table instead of prose.
  - Inline-code token sets of pages 1 and 11 are identical, and page 4 is a line-by-line mirror.
  - UK is ~1.35x the bytes and ~1.5x the tokens. Page mtimes are paired.
  - Verdict: in sync. Weak point: wiki mtimes stop at 2026-09-27, while code changed through 09-29.

## 3. Process files

| File | KB / ~tok | What it is | State |
|---|---|---|---|
| `CHANGELOG.md` | 335 / 89k | 272 releases, 2026-03-17 to 09-29, 1.2KB each; 100 releases in June alone | Append-only, newest on top |
| `walkthrough.md` | 294 / 70k | 43 per-task reports; **newest-first, but order is not chronological** (0.3.088 sits after 0.3.120) | Nobody reads it |
| `AUDIT.md` | 172 / 42k | Header dated 2026-09-29, **last real audit content 2026-07-09** (§11); 74 `[x]` vs 3 `[ ]` | Open: DOC03, "keep FEATURE_REFERENCE current", a "plugin from template" idea |
| `plan.md` | 80 / 19k | Stages 1–65, appended, no dates | 0 open boxes |
| `task.md` | 81 / 19k | One flat list (66 items), 0 open, ordered 0.3.088 to 0.3.141 | Same history as `plan.md` |
| `implementation_plan.md` | 9 / 2k | 2 Sep speaker-sync plan | Done and stale |

These are logs, not working docs. They exist because of the Junior/Senior (`audit` skill) loop, which needs `plan/task/walkthrough/AUDIT` to be current. That need is satisfied by a small current file, not by six months of history. They are also mostly Ukrainian, so token cost is high. The graph indexes them too, which pollutes it.

**Archival scheme (keeps the audit skill's file names):**
- `docs/history/` holds the frozen logs, one file per period, never loaded by default:
  - `changelog/2026-03.md … 2026-09.md`
  - `walkthroughs/v0.3.1xx.md`, one file per release
  - `AUDIT-2026-H1.md`
  - `plan-task-0.3.088-0.3.141.md`
  - `refactors/` (from `.grok/`)
- Root `plan.md`, `task.md` and `walkthrough.md` become **current-iteration only**:
  - Each is ≤2k tokens, rewritten per task.
  - Each is rolled into `docs/history/` at `/deploy`; extend `scripts/deploy.py` to do this.
- `CHANGELOG.md` keeps only the last ~14 days or the current minor (≤5k tokens), terse (one line per change).
- New `docs/OPEN_ITEMS.md` (≤1.5k tokens) holds every unchecked item, extracted once and owned afterwards.
- Add `docs/history/README.md`: "do not read; grep only".
- Mark one language for agent-facing files, since the Ukrainian logs cost ~1.7x in tokens. Recommend an English `plan.md`/`task.md`, with Ukrainian kept for chat and the user's reports.

## 4. Module-level documentation

- **No package has a README**, except `default_plugin` and `companion`.
- **Module docstrings are patchy.** 229 of 476 product modules (48%) have no docstring.

| Area | No docstring |
|---|---|
| core | 27% |
| ui | 43% |
| components | 40% |
| handlers | 55% |
| plugins | 70% |
| tools | 76% |
| scripts | 83% |

- **Recently decomposed packages have `__init__` docstrings.** `core/glossary_build`, `core/glossary`, `core/project`, `core/script_markup`, `core/containers`, `handlers/translation/facade`, `components/glossary`.
- **Weak spots:**
  - `core/translation` 7/12 modules undocumented.
  - `handlers/translation/{glossary,prompt_composer,worker}` and `handlers/project_action`: 100% undocumented.
  - `ui/settings` 14/17.
  - `plugins/common/problem_rules` 5/5, with no `__init__` doc.
  - `core/data_processor` 3/6, no `__init__` doc.
- **No architecture page and no diagram.** There is no mermaid or ASCII art anywhere.
  - "AppDataStore → DataStateProcessor → handlers → updaters" exists only as one-line bullets (GEMINI.md:52,284 and Manifesto §3.1).
  - Since the refactor, `core/glossary_manager.py` (56 lines) and `core/project_manager.py` (55) are facades, yet docs describe them as the implementation. A weak model that opens them finds almost nothing.
- **`docs/wiki/2_API_Reference.md` is hand-written, not generated.**
  - It is a 60-line list of module → role, honestly labelled "not a generated dump".
  - It is accurate except for 2 dead paths.
  - It has no module → tests mapping.
  - No test checks doc paths. `tests/test_architecture/` has 3 tests, none about docs.

## 5. AI tooling

| Item | Observation |
|---|---|
| `.agents/skills/deploy`, `update-wiki` | Good, concrete. The `update-wiki` ownership table lacks page 12 (Companion) |
| `.agents/workflows/deploy.md` | Duplicates the deploy skill with different text; merge |
| `.agents/workflows/graphify.md` | Depends on `~/.gemini/…`; delete |
| `.agents/rules/graphify.md` | The best graph rule; make it the single source |
| `.claude/settings.local.json` | 3.4KB of stale permissions: a pasted commit message, `git filter-repo`, `C:\Users\Administrator` paths. Local file; gitignore and delete |
| `.grok/` (40 md + 2 py, 248KB) | Finished split specs and results. It also holds `_line_numbered_text_edit_original.py` (45KB) and `merge_bfn_uk.py`, which pollute grep and the graph. Archive or delete |
| `gemini/` (1.7MB) | An old copy of the codebase with 5 md files. It is untracked, but sits in the workspace. Delete or exclude |
| `tools/` | 3 py scripts, `i18n-translate/` (6 files) and `bfn_editor/` (26 files). `bfn_editor` is product code, not a tool; consider moving it to `components/` or `ui/` |
| `scripts/` | `deploy`, `bump_version`, `benchmark*`, `cleanup_project`, `build_gemini_dir`. They overlap and have no docstrings (5/6) or `--help` |
| Task runner | Only `test_all.ps1`, `run_stress_tests.ps1` and `run.bat`. All hard-code `venv\Scripts`, so they break on Linux and macOS and inside any agent sandbox |
| Root clutter | `app_debug.txt`, `session_state.json`, `settings.json`, `dummy.json` (a test fixture), `bmg_tool.py` |

**Missing:**
- A short `AGENTS.md`/`CLAUDE.md`.
- `docs/INDEX.md`.
- `docs/ARCHITECTURE.md` with a diagram.
- An ownership map (module → doc → tests).
- A cross-platform task runner (`make` or `tasks.py`, with `test`/`lint`/`graph`/`smoke`).
- `docs/DECISIONS.md`. The reasoning is scattered across AUDIT and CHANGELOG.
- A `.graphifyignore`.
- Doc-link lint.

## 6. Proposals

### P0 (this week, low risk, biggest win)

**P0-1. Short agent entry.**
- Create `AGENTS.md` (≤1.5k tokens). Contents:
  - 12 hard rules (i18n pair, no Mock in product, no sync UI work, no Russian, version bump, doc-sync checklist pointer).
  - The 4 commands (`test`, `lint`, `graph`, `smoke`).
  - "Read next: `docs/INDEX.md`".
  - The Graphify rule, exactly once.
  - The user's 3 Ukrainian process rules, translated or kept bilingual.
- Make `CLAUDE.md` contain only `@AGENTS.md`. Reduce `GEMINI.md` to a 5-line pointer.
- Risk: duplicate rules diverge, so the rules live only in `AGENTS.md` and the other two are stubs.
- Verify: a new model told only "fix X" cites AGENTS.md rules. Size check with a token counter in CI.

**P0-2. Fix the Graphify rule and the graph.**
- One rule: query/path/explain first, read the report last, `graphify update .` after code edits only.
- Delete the GEMINI.md graph bullets, `workflows/graphify.md`, and README §6's `extract --backend openai` path (move it to `docs/GRAPHIFY.md`).
- Add `.graphifyignore`: `tests/`, `gemini/`, `.grok/`, `docs/history/`, `*.md`, `locales/`, `translation_prompts/glossary.json`.
- Add a ≤3k-token `graphify-out/ARCHITECTURE_DIGEST.md` generated from layers/god nodes, and exclude `tr`/`log_*`.
- Verify: node count drops from 15.9k to ~10k; `graphify explain DataStateProcessor` shows no tests.

**P0-3. Archive the logs.**
- Move `AUDIT.md`, the CHANGELOG body, `walkthrough.md`, `plan.md`, `task.md`, `implementation_plan.md`, `.grok/` and `gemini/` into `docs/history/`. Create `docs/OPEN_ITEMS.md`.
- Result: 241k tokens leave the root path.
- Risk: the `audit` skill expects those files, so leave stub current files.
- Verify: root holds only README, AGENTS, CHANGELOG, OPEN_ITEMS-link and the three small current plan/task/walkthrough files.

**P0-4. Fix the 7 stale claims** (Preferences, DeepL, dead paths, two GEMINI versions, `get_tag_pattern`) and settle the MemPalace question (feature present or removed). If removed, archive the 152KB manifesto and README §8.

### P1 (next two weeks)

**P1-1. `docs/INDEX.md` (≤1.2k tokens).**
- One line per doc: path, 1-line purpose, ~tokens, status (`current`/`design`/`archive`), owner module.
- Add front matter to every doc: `status`, `updated`, `owns`, `tokens`.

**P1-2. `docs/ARCHITECTURE.md` (≤3k tokens).**
- Mermaid diagram: `MainWindow → handlers (BaseHandler/ProjectContext) → DataStateProcessor (SessionManager/RevertManager/SetCalculator) → AppDataStore → updaters → widgets`.
- A table of layers with the one facade file per package, the "where to change X" table, and the module → tests → doc map.
- Include the facade warning for `glossary_manager.py` and `project_manager.py`.

**P1-3. Shrink README to ≤3.5k tokens.**
- Keep: pitch, install, run, tests, the doc map.
- Delete: Key Features (11k), AI subsystem and Directory Structure (duplicates of wiki 5, 11, 2).
- Wiki 1 then owns the features list.

**P1-4. Merge docs.**
- `AI_DEVELOPMENT_MANIFESTO` → `AGENTS.md` plus a ≤2k `docs/ENGINEERING.md`.
- `PLUGIN_AUTHORING_GUIDE` + `plugins/DEVELOPER_GUIDE.md` → `wiki/3` plus the default-plugin README.
- `FEATURE_REFERENCE` → wiki 1, then delete.
- `.agents/workflows/deploy.md` → the deploy skill.
- `GLOSSARY_BUILD_TESTING_GUIDE` → an appendix of wiki 8.

**P1-5. Task runner.** `tasks.py` (or a Makefile with a PowerShell fallback) with `test`, `lint`, `graph`, `smoke`, `docs-check`, `bump`. Resolve the interpreter from the active env, not `venv\Scripts`.

### P2

- **P2-1. Docstrings:** a one-line module docstring on all 229 bare modules, starting with `core/translation`, `handlers/translation/*`, `ui/settings` and `plugins/common/problem_rules`. Add a test that fails on new bare modules.
- **P2-2. `tests/test_docs/`:** check that backticked paths in README, wiki, ARCHITECTURE and INDEX exist; that EN/UK wiki files have the same headings; that the version appears once (`utils/constants.py`); that `AGENTS.md` is under 2k tokens.
- **P2-3. `docs/DECISIONS.md`:** an ADR log, 10 lines per decision. Seed it from AUDIT §2/§8 (why `DataStateProcessor`, why Pickle+JSON session, why plugin capabilities).
- **P2-4. Language policy:** agent-facing docs in English, user-facing wiki in EN+UK. Translate `PIPELINE_ROADMAP`, `TRANSLATION_PROMPTING_STRATEGY`, `GLOSSARY_BUILD_TESTING_GUIDE` and `chatmock_setup`, which are Ukrainian.
- **P2-5. Version stamp:** only `utils/constants.py` carries a version; `deploy.py` stamps docs.

### Single source of truth

| Fact | Lives in only |
|---|---|
| Agent rules, commands | `AGENTS.md` |
| Doc map and status | `docs/INDEX.md` |
| Architecture, data flow | `docs/ARCHITECTURE.md` |
| UI behaviour, menus, settings | wiki 1/4 (EN, UK mirrored) |
| Module → file map | wiki 2 plus `ARCHITECTURE.md` |
| Plugin contract | wiki 3, with `BaseGameRules` as the code authority |
| Open work | `docs/OPEN_ITEMS.md` |
| What shipped | `CHANGELOG.md` (terse) |
| Why we chose X | `docs/DECISIONS.md` |
| Version | `utils/constants.py` |

### PR checklist (put it in `AGENTS.md` and the PR template)

1. User-visible change? Patch the owning wiki page (EN and UK) and add one CHANGELOG line.
2. New or moved module? Add a module docstring, and update the table in `ARCHITECTURE.md` if a package changed.
3. New `tr("…")`? Add the key to `locales/uk.json`.
4. New plugin hook? Update the authoring doc, the roadmap and the assistant prompt, or write "single-game".
5. Closed or opened a TODO? Update `OPEN_ITEMS.md`.
6. Run `tasks docs-check`: dead paths, EN/UK parity, `AGENTS.md` size.
7. Run `graph update` last.

## 7. Table of all doc files (verdicts)

| Path | KB | ~tok | Purpose | Verdict |
|---|---|---|---|---|
| `README.md` | 62.6 | 16.6k | Pitch + feature dump + setup | **Trim** to 3.5k |
| `GEMINI.md` | 28.3 | 7.5k | Rules + overview | **Split** into AGENTS.md + stub |
| `AGENTS.md`, `CLAUDE.md` | – | – | – | **Create** (≤1.5k / stub) |
| `AUDIT.md` | 172 | 42k | Audit log, mostly closed | **Archive**; extract open items |
| `CHANGELOG.md` | 335 | 89k | Release log | **Archive** by month; keep 2 weeks |
| `walkthrough.md` | 294 | 70k | Task reports | **Archive**; keep current only |
| `plan.md` / `task.md` | 80 / 81 | 19k each | Stage and checkbox logs | **Archive**; keep current only |
| `implementation_plan.md` | 9.4 | 2.2k | Done 2 Sep plan | **Archive** |
| `docs/AI_DEVELOPMENT_MANIFESTO.md` | 14.6 | 3.9k | Long-form rules, repeats GEMINI | **Merge** into AGENTS.md / ENGINEERING.md |
| `docs/FEATURE_REFERENCE.md` | 11.8 | 3.1k | Feature inventory, 8 dead paths | **Merge** into wiki 1, delete |
| `docs/GLOSSARY_BUILD_TESTING_GUIDE.md` | 6.7 | 1.5k | Glossary pass (UA) | **Merge** into wiki 8 |
| `docs/MEMPALACE_CONTEXT_MANIFESTO.md` | 152 | 35.7k | Design doc; code absent here | **Archive**, or cut to a ≤4k contract |
| `docs/PIPELINE_ROADMAP.md` | 40.6 | 9.3k | Design of record (UA) | **Keep**, split shipped vs planned |
| `docs/PLUGIN_AUTHORING_GUIDE.md` | 14.5 | 3.8k | Plugin contract | **Merge** into wiki 3 (fix `get_tag_pattern`) |
| `docs/SCRIPT_MARKUP_SCENE_AUTOFILL_PLAN.md` | 2.8 | 0.7k | Agreed behaviour | **Merge** into wiki 9 |
| `docs/TESTING_STRATEGY_AND_AUDIT.md` | 8.8 | 2.3k | Dated 2026-06-20 | **Keep** as TESTING.md, refresh |
| `docs/TRANSLATION_PROMPTING_STRATEGY.md` | 25.8 | 6.2k | "Draft", target design (UA) | **Keep**, mark `design` |
| `docs/chatmock_setup.md` (+`gemini/` copy) | 3.8 | 0.9k | ChatMock how-to, with a stray "START OF FILE" header | **Merge** into wiki 5 |
| `docs/wiki/README` (EN/UK) | 2.0/2.4 | 0.5k | Wiki index | **Keep** |
| `wiki/1_User_Guide` | 22.2/32.0 | 6.0k/7.7k | Interface | **Keep** (take over FEATURE_REFERENCE) |
| `wiki/2_API_Reference` | 3.1/3.9 | 0.8k/1.0k | Code map | **Keep**, fix 2 paths, add test map |
| `wiki/3_Plugin_Developer_Guide` | 7.8/10.1 | 2.1k/2.5k | Plugins | **Keep** (single plugin doc) |
| `wiki/4_Configuration_Guide` | 5.3/7.0 | 1.4k/1.7k | Settings, files | **Keep** (verified) |
| `wiki/5_Gemini_Web2API` | 4.4/6.1 | 1.2k/1.5k | Proxy | **Keep** |
| `wiki/6_Virtual_Navigation` | 4.2/6.7 | 1.1k/1.6k | Virtual views | **Keep** |
| `wiki/7_Maintaining` | 2.3/2.1 | 0.6k/0.5k | Ownership table | **Keep**, add page 12 and the PR checklist |
| `wiki/8_Localization_Pipeline` | 8.5/12.4 | 2.3k/3.0k | Wizard | **Keep** (verified) |
| `wiki/9_Script_Markup` | 5.3/7.6 | 1.4k/1.8k | Studio | **Keep** |
| `wiki/11_AI_Translation` | 9.5/13.9 | 2.5k/3.3k | Providers | **Keep** (verified) |
| `wiki/12_Picoripi_Companion` | 6.3/10.8 | 1.7k/2.5k | PWA | **Keep** |
| `plugins/DEVELOPER_GUIDE.md` | 8.8 | 2.3k | Plugin guide #3 | **Merge** into wiki 3 |
| `plugins/default_plugin/README.md`, `AI_PLUGIN_ASSISTANT_PROMPT.md` | 2.4 / 6.0 | 0.6k / 1.6k | Template and prompt | **Keep** |
| `plugins/script_template.md`, `script_preparation_guideline.md` | 4.0 / 3.3 | 1.1k / 0.9k | Script format | **Keep**; link from wiki 9 |
| `plugins/zelda_bmg/TAGS.md` | 27 | 6.4k | Tag reference | **Keep**, add to INDEX (not loaded by default) |
| `plugins/{zelda_ww,zelda_mc,plain_text}/translation_prompts/glossary.md` | 38.5/18.4/38.5 | ~9k/4.4k/9k | Glossary data | **Keep ww/mc as data**; **delete** the plain_text copy |
| `companion/README.md` | 3.0 | 0.8k | Server setup | **Keep** |
| `tools/i18n-translate/README.md` | 0.7 | 0.2k | i18n tool | **Keep** |
| `.agents/rules/graphify.md` | 0.9 | 0.25k | Graph rule | **Keep** as the single rule |
| `.agents/skills/{deploy,update-wiki}` | 4.8 / 5.7 | 1.3k / 1.5k | Skills | **Keep** (update ownership table) |
| `.agents/workflows/{deploy,graphify}.md` | 5.6 / 0.3 | 1.5k / 0.1k | Duplicates | **Delete** |
| `.grok/*` (40 md + 2 py) | 248 | ~30k + code | Finished refactor specs; duplicate skills | **Archive** to `docs/history/refactors/`, delete duplicates and py |
| `gemini/*` (5 md + code copy) | 1.7MB | – | Old code copy | **Delete** |
| `.claude/settings.local.json` | 3.4 | 0.9k | Stale permissions | **Delete**, gitignore |
| `translation_prompts/glossary.json` | 814 | ~230k | Data. Never read in full | **Keep**; add to `.graphifyignore` and AGENTS.md "do not read" |
| `graphify-out/GRAPH_REPORT.md` | 241 | ~71k | Graph report | **Keep** as an artifact; never an entry point |
