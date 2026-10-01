# Audit C — Plugin system (adding new games)

Scope: `plugins/`, loader (`ui/main_window/main_window_plugin_handler.py`), config (`core/settings/plugin_settings.py`), format dispatch (`handlers/app_action_handler.py`, `handlers/project_action/load_worker.py`, `core/project/blocks_mixin.py`, `core/data_processor/save_mixin.py`), containers (`core/containers/`), docs. `gemini/`, `ENG/`, `UA/` ignored.

**Verdict.** The *text-rules* half of the base is adequate: `BaseGameRules` (54 methods, `plugins/base_game_rules.py:6`) has safe defaults for everything and `plugins/common/` (rule engine, `GenericTagManager/ProblemAnalyzer/TextFixer`, `config_factory`) already absorbs most game-agnostic logic, so a *text-only* game plugin is ~150 lines of real code. The *file-format* half is not a plugin API at all: the host hard-codes `.json/.txt/.bmg/.arc` by extension in 5 places, the UI imports `plugins.zelda_bmg.*` directly (10 sites), and host code reads two plugins' private attributes (`original_keys` from pokemon_fr, `last_loaded_bmg` from zelda_bmg). There is no Protocol, no validator, no scaffold, no all-plugins smoke test; three guides disagree with the code.

---

## 1. Contract — what the host actually calls

**Loading** (`main_window_plugin_handler.py:56-105`): `importlib.import_module("plugins.<name>.rules")`, requires class `GameRules` subclassing `BaseGameRules` (`:85`), instantiated with `main_window_ref=mw`. Discovery (`ui/settings/logging_mixin.py:10-28`): any dir under CWD-relative `plugins/` with `config.json` (except `import_plugins`). Then `importlib.import_module("plugins.<name>.config")` for `DEFAULT_AUTOFIX_SETTINGS` / `DEFAULT_DETECTION_SETTINGS` (`plugin_settings.py:160-167`, duplicated in `main.py:290-300`).

**Required (host breaks or plugin is invisible without them):**
| Item | Where consumed |
|---|---|
| `config.json` with `display_name` | `logging_mixin.py:19-22` |
| `rules.GameRules(BaseGameRules)` | `main_window_plugin_handler.py:85` |
| `load_data_from_json_obj`, `save_data_to_json_obj` (9 + 4 call sites) | `load_worker.py:85,172`, `save_mixin.py`, `blocks_mixin.py:159` |
| `get_display_name`, `get_problem_definitions`, `get_text_representation_for_editor/preview`, `convert_editor_text_to_data` | 11–17 sites each |

**Optional, on base, documented** (safe default): 40+ hooks — `analyze_subline`, `autofix_data_string`, `get_capabilities`, `get_string_layout`, `get_speaker_for_string`, `get_translation_context_for_string`, `get_ai_flow_*`, `prepare_preview_glyph_text`, `load_reference_patch`, `get_plugin_actions`, … (full list = public methods of `base_game_rules.py`). Documented in `docs/PLUGIN_AUTHORING_GUIDE.md` §4.1–4.2 and `docs/wiki/3_Plugin_Developer_Guide.md`.

**Undocumented hooks — host reaches past the base class (16 found):**
| Hook | Kind | Host site | Owner |
|---|---|---|---|
| `original_keys` | attr, read **and written** | `save_mixin.py:45,100,246,285-291`, `revert_manager.py:324-416`, `session_manager.py:83-107`, `load_worker.py:129`, `app_action_handler.py:154-160` (18 refs) | pokemon_fr only (`pokemon_fr/rules.py:42`) |
| `last_loaded_bmg` | attr, written by host | `save_mixin.py:108,165` (+ imports top-level `bmg_tool`) | zelda_bmg |
| `msg_to_editor_text(bmg_msg)` | method, called **unconditionally** | `ui/main_window/bfn_actions.py:333` | zelda_bmg |
| `get_preview_window_style` | method | `paint_mixin.py:135-143`, `string_settings_updater.py:699`, `layout_contract.py:34` | zelda_bmg |
| `get_message_attributes` | method | `paint_mixin.py:257` | zelda_bmg |
| `_get_window_layouts`, `_window_layouts` | **private** | `paint_mixin.py:153-155`, `plugin_tabs_mixin.py:343-344` | zelda_bmg |
| `replace_runtime_names_for_ai` | method | `prompt_composer/composer.py:45` | zelda_bmg |
| `export/restore_runtime_session_state` | method | `session_manager.py:89,109` | no implementer |
| `problem_analyzer` (+ `.registry.get_prefixed_id`, `.analyze_data_string`) | attr | `issue_scan_handler.py:145`, `scan_mixin.py:42-149`, `text_autofix_logic.py:196-264`, `width_calculation_worker.py:50` (11 sites) | all real plugins |
| `problem_ids` | attr | 2 sites | zelda_ww comment says "so UI can access" |
| `tag_manager._legitimate_exact_tags_cache` | private | `tag_alias_mixin.py:222-224` | zelda_mc |
| `PROBLEM_MISSING_ICON_SPACING` | class attr | `utils/syntax/highlight_mixin.py:409` | none (ProblemIDs has it, GameRules doesn't) |
| `CONTROL_CODES` | module constant, read via `sys.modules` | `base_game_rules.py:311-318` | — |
| `DEFAULT_AUTOFIX/DETECTION_SETTINGS` | `config.py` constants | `plugin_settings.py:163-165` | — |
| `is_tag_legitimate`, `get_tag_pattern` | defined in every plugin / documented as "most important" | **never called by host** (dead) | — |

Three mechanisms coexist for the same thing: base-class default, `hasattr` probe, and `getattr(..., None)`; 7 host sites `hasattr`-probe `get_text_representation_for_editor` even though it is on the base.

## 2. Base adequacy — boilerplate vs. game logic

Per-plugin file sizes (lines): `rules.py` 187–245 (bmg 1692), `config.py` 54–96, `tag_manager.py` 17–68, `text_fixer.py` 6–8, `problem_analyzer.py` 6–15, `tag_logic.py` 53–108.

- `text_fixer.py` and `problem_analyzer.py` are **pure pass-through subclasses** in zelda_mc, zelda_ww, plain_text, zelda_bmg, default (6 lines each, only the docstring differs). pokemon_fr's adds one real override (line-break normalisation, `pokemon_fr/problem_analyzer.py:11-15`).
- `plugins/plain_text/tag_logic.py` is **byte-identical** to `zelda_ww/tag_logic.py` (md5 `ac0f93a2…`): it still defines `PLAYER_TAG_WW = "[Name]"`, `process_segment_tags_aggressively_zww`. A "plain text" plugin carries Wind Waker paste logic.
- `rules.py` across mc/ww/pokemon/plain/default: ~70% is identical delegation (`analyze_subline` → `problem_analyzer`, `autofix_data_string` → `text_fixer`, `get_syntax_highlighting_rules` → `tag_manager`, `get_legitimate_tags`, `get_problem_definitions`, `get_short_problem_name` if-chains, `get_text_representation_for_preview` with the `newline_display_symbol`/`show_multiple_spaces_as_dots` dance, the `ProblemIDs` class re-exporting config constants, `__init__` wiring). Genuine game logic per plugin: zelda_mc ≈ `tag_logic.py` + `tag_checker_handler.py` (335 lines, 22 `self.mw.` touches) + 1 URL; zelda_ww ≈ `tag_logic.py` + width override; pokemon_fr ≈ parser with `original_keys` + `text_fixer.py` (88 lines); zelda_bmg ≈ everything (BMG parser, flow graphs, window kinds — real).
- `config.py`: already factory-driven (`generate_base_config(prefix, overrides)`), but each plugin re-declares the 9 `PROBLEM_*` strings and a `ProblemIDs` class that `config_factory` could emit.
- `tag_manager.py`: zelda_mc/ww/bmg each re-implement `_ensure_exact_tags_loaded` + `get_legitimate_tags` from `mw.default_tag_mappings` (same 15 lines).
- `get_plugin_actions` in zelda_mc (`rules.py:112-162`) registers *generic* AI-translate actions ("Ctrl+Alt+T") — host features masquerading as plugin actions; other plugins lack them.

**Move to base/common:** (a) `__init__` wiring + all delegation methods → `BaseGameRules` (or a `CompositeGameRules` in common) so a plugin overrides only `tag_manager_class`/`problem_prefix`; (b) `ProblemIDs` generation + `get_short_problem_name` table → `config_factory`; (c) `get_text_representation_for_preview` dots/newline logic → base (it already reads `mw`); (d) `_ensure_exact_tags_loaded` → `GenericTagManager`; (e) delete `is_tag_legitimate`/`get_tag_pattern` or wire them; (f) replace `plain_text/tag_logic.py` with a neutral one.

## 3. Separation of concerns

**Game vs. format vs. language — not separated.**
- *Format dispatch lives in the host, keyed by extension*: `app_action_handler.py:103,120,133-142,271,319,375`; `load_worker.py:66-69,154-157`; `blocks_mixin.py:111,127` (`supported_extensions = {'.json','.txt','.bmg','.arc','.rarc','.ark','.bfn'}`); `save_mixin.py:177,267`; `physical_selection_mixin.py:384`. A plugin has no `get_supported_extensions()` / `read_file(bytes)` / `write_file()` hook. `.bmg` is read as raw bytes and shoved into `load_data_from_json_obj` (`app_action_handler.py:136-141`) — the method name lies about its input. A **PS1 game with a custom `.bin` table** hits `Unsupported file type` at `app_action_handler.py:142` before the plugin is consulted; a **GBA Fire Emblem** with a `.txt`/`.json` dump works, but any raw-ROM reading needs host edits.
- *Containers*: `core/containers/container_manager.py:36-70` is a clean magic-bytes factory, but `_CONTAINER_TYPES` is a module tuple (U8, RARC; Yaz0) with no registration API; `blocks_mixin.py:118-129` only looks inside archives for the hard-coded inner extension set.
- *BMG parser* is a top-level module `bmg_tool.py` imported by core (`save_mixin.py:109`) — a Nintendo format in the host, not the plugin.
- *Host imports a plugin*: `ui/components/bfn_preview/{chrome.py:131, geometry_mixin.py:127,154, paint_mixin.py:160,165,185,201,251,692}` import `plugins.zelda_bmg.window_kinds` / `window_frame_loader`; `handlers/text_autofix_logic.py:44` instantiates `plugins.zelda_mc.rules.GameRules` as the fallback ruleset. The BFN preview is therefore a Twilight Princess preview with a generic facade.
- *Language*: target language is a global (`target_language`, default `"Ukrainian"`, `glossary_prompt_manager.py:277-279`); plugin prompts hard-code "(UA)" in action labels (`zelda_mc/rules.py:130-148`); reference-language default `"Russian (RU)"` (`base_game_rules.py:260`, `plugin_settings.py:197`). Acceptable for this user, but not a plugin axis.
- 278 host lines mention zelda/bmg/pokemon/kruptar (`grep -rniE` over core/handlers/ui/utils); hotspots `bfn_actions.py` (48), `save_mixin.py` (29), `plugin_tabs_mixin.py` (20), `script_speaker_finder.py:72` (a literal `e:\Emulators\RomHacking\ZELDA\TP_UA\zelda_tp_script.txt`).
- Positive: the "slots not values" rule is enforced by `tests/test_plugins/test_plugin_capability_contract.py:25-37` for 3 engine modules; `core/translation/layout_contract.py:26-45` is a good model of a tolerant hook call.

## 4. Config & data

- `config.json`: **no schema, no validation, no version**. Loader (`plugin_settings.py:47-150`) merges `defaults → plugin config.json → project_settings.json` and then `setattr(mw, key, value)` for *any* key (`:146-148`) — a typo silently creates a MainWindow attribute; an unknown key is never reported. Every real `config.json` contains per-session state (`last_selected_block_index`, scroll positions, `search_history`, `original_file_path`) because the same dict is the save schema (`plugin_settings.py:255-312`). `string_metadata` keys are deserialised with **`eval()`** (`plugin_settings.py:139`). `_substitute_env_vars` runs on all strings (`:31-44`), undocumented.
- `config.py` defaults vs `config.json` `autofix_enabled/detection_enabled`: both exist; `config.json` wins on merge; zelda_mc's JSON has empty dicts, zelda_ww's lists only 6 of 10 IDs — inconsistent across plugins.
- `font_map.json`: two formats in the wild — rich glyph atlas (`zelda_mc`, keys with `start_x/file`) and `{tag: {width}}` overrides (`common/defaults`, `pokemon_fr`); loader keeps only `width` (`font_map_loader.py:262-268`). `DEVELOPER_GUIDE.md:190-205` documents a *third* format (`"widths": {"32": 4}`, `"aliases"`) that **no code reads**. Fallback: plugin file → `plugins/common/defaults/font_map.json` (`:254-257`).
- `aliases.json`: written on every settings save into the **plugin dir** (`plugin_settings.py:228-237`, `mkdir(parents=True)`), merged over `get_default_tag_mappings()` (`main_window_plugin_handler.py:112-130`). Plugin dir is thus mutable user state → explains `plugins/test_plugin/aliases.json` and the `plugins/MagicMock/` directory (tests with a mock `active_game_plugin` ran `save()`).
- `translation_prompts/prompts.json`: resolution is **file-level**, not key-level (`glossary_prompt_manager.py:50-56`: plugin → `common/defaults` → root). Consequence: zelda_mc/ww/bmg/pokemon/plain ship a `prompts.json` with only `translation`, so `editor_review` returns `None` (`:156-170`, feature silently off) and `glossary` falls back to the Python constant `_DEFAULT_GLOSSARY_PROMPT`, **not** to `common/defaults/prompts.json` (`:252-260`). `mempalace` key likewise unreachable for those plugins. Also, "Edit prompts" and `save_prompt_section` *materialise* a copy into the plugin dir (`provider_mixin.py:21-41`, `glossary_prompt_manager.py:293-301`) — further plugin-dir mutation.

## 5. Developer experience today

Steps a developer/AI must do: (1) copy `plugins/default_plugin/` (manual; no script); (2) edit `config.json` display name + widths; (3) edit `config.py` prefix; (4) rewrite `load_data_from_json_obj/save_data_to_json_obj` — knowing that `.txt` arrives as `str`, `.json` as parsed obj, `.bmg` as `bytes`, and that any other extension is rejected by the host; (5) edit `tag_manager.py` regexes; (6) supply `fonts/*.json` + `font_map.json` in the `{char:{width}}` shape; (7) copy `translation_prompts/prompts.json` from `common/defaults` **in full** (or lose glossary/editor-review prompts — not stated anywhere); (8) write `tests/test_plugins/test_<name>/test_rules.py` by hand; (9) start the app and pick it in Settings. No `python -m plugins.validate`, no scaffold, no all-plugins parametrized test (each plugin has its own ad-hoc test file; `test_common/` is empty).

Docs vs. code: `plugins/DEVELOPER_GUIDE.md` is the most wrong — `ProblemAnalyzer(mw, tag_manager, PROBLEM_DEFINITIONS)` 3-arg ctor (`:60-62`) vs real 4-arg (`common/problem_analyzer.py:11`); `autofix_data_string` 3-param signature (`:123-126`) vs 9 real; `font_map.json` format (`:190-205`) fictional; refers to `BaseProblemAnalyzer` (`:215`, real name `GenericProblemAnalyzer`); "discovers … directories containing `rules.py`" (`:16`, really `config.json`); problem-definition dict shape (`:156-178`) differs from `config_factory` output. `docs/PLUGIN_AUTHORING_GUIDE.md` is current but lists `get_tag_pattern()` as "most important" (`:84`) though nothing calls it, and omits the `.bmg`-bytes contract, the prompts file-level fallback and the `original_keys` protocol. `docs/wiki/3_Plugin_Developer_Guide.md:5` names `handlers/project_action_handler.py` (discovery) — the file exists but discovery is in `logging_mixin.py`. Four overlapping guides + README + AI prompt = 1032 lines with no single source of truth.

## 6. Bugs / fragility

1. **Host writes plugin private state**: `original_keys` (pokemon_fr) is backed-up/restored by core save/revert/session code (`save_mixin.py:100,246`, `revert_manager.py:377-416`); `last_loaded_bmg` assigned by `save_mixin.py:165`. Any plugin that happens to define these names inherits undocumented semantics.
2. **`eval()` on settings keys** (`plugin_settings.py:139`) — `project_settings.json` is attacker-controlled input.
3. **Plugin crash isolation is inconsistent**: load errors → QMessageBox + fallback (`main_window_plugin_handler.py:98-105`, good), but runtime hooks are called bare in hot paths (`text_views_mixin.py:114`, `bfn_actions.py:333`, `app_action_handler.py:154`); an exception there goes to `sys.excepthook` (`main.py:731`), not to a plugin-scoped handler.
4. **Module reload hack**: `del sys.modules[...]` for a fixed list of 6 submodules (`main_window_plugin_handler.py:67-81`); zelda_bmg has 15 modules → stale state after switching plugins.
5. **CWD-relative paths**: 30 `Path("plugins")` sites in 10 host files; running from another directory finds no plugins.
6. **Test pollution**: `PluginSettings.save()` writes `aliases.json` into `plugins/<active_game_plugin>/` with `mkdir(parents=True)` → `plugins/test_plugin/`, `plugins/MagicMock/` created by tests; `find_plugins` will list any such dir that acquires a `config.json`.
7. **Global mutable state**: `clear_width_caches()` module-level; `mw.default_tag_mappings` mutated in place by both the plugin (`zelda_mc/rules.py:67-74` returns a copy of mw's own dict — circular) and `_load_custom_aliases`.
8. `handlers/text_autofix_logic.py:44` silently substitutes **zelda_mc** rules when `mw` is not a QWidget — tests for other plugins exercise Minish Cap logic.
9. `import_plugins/` (`BaseImportRules`, `kruptar_format`) is never referenced by host code — dead layer with its own second "base".
10. Duplicate default-merging of `DEFAULT_AUTOFIX_SETTINGS` in `main.py:290-300` and `plugin_settings.py:160-175` with different precedence rules.

## 7. Proposals

**P0-a — `PluginSpec` Protocol + `python -m plugins.validate <name>`** (new `plugins/spec.py`, `plugins/validate.py`; ~250 lines).
Sketch: `class GameRulesProtocol(Protocol)` listing every method the host calls (take the table in §1, incl. the 16 undocumented ones, each marked `required`/`optional`); `KNOWN_CONFIG_KEYS` frozenset + `SESSION_KEYS` (to be rejected in `config.json`); validator: imports `plugins.<name>.rules`, checks `issubclass`, calls every optional hook with dummy `(0,0)` and asserts return types, parses `config.json`/`font_map.json`/`prompts.json` against the key sets, warns on missing prompt sections (`glossary`, `editor_review`, `mempalace`) given the file-level fallback, flags `self.mw.<attr>` accesses outside an allow-list via `ast`. Gain: contract becomes executable; mid-tier model gets a red/green loop. Risk: low (read-only). Test: `tests/test_plugins/test_validate_all.py` parametrised over `plugins/*/config.json` must pass for the 6 shipped plugins.

**P0-b — Format hook: `get_file_formats()` on `BaseGameRules`** (returns `[FileFormat(extensions={'.bin'}, mode='bytes'|'text'|'json', read=callable, write=callable)]`; default = current json/txt behaviour). Replace the 5 extension switches (`app_action_handler.py:133-142,319-324,375-380`, `load_worker.py:66-69,154-157`, `blocks_mixin.py:111,127`, `save_mixin.py:177,267`) with `core/formats.py:resolve(rules, path)`. Move `bmg_tool.py` into `plugins/zelda_bmg/` and make zelda_bmg register `.bmg/.bfn`; add `ContainerManager.register(cls)` so a plugin can add a PS1 archive. Gain: a new game with a custom table format touches only its plugin dir. Risk: medium — save path for BMG inside archives (`save_mixin.py:107-165`) must keep `last_loaded_bmg` behaviour; do it behind the hook (`rules.prepare_save_context(...)`). Test: round-trip tests for zelda_bmg archive save + plain_text txt unchanged; a fixture plugin with a fake `.tbl` format loads/saves through the UI handler.

**P0-c — Stop writing into `plugins/`**: `aliases.json` and materialised `prompts.json` → `<project_dir>/plugin_overrides/` (`plugin_settings.py:228-237`, `provider_mixin.py:21-41`, `glossary_prompt_manager.py:293-301`); `rm -r plugins/MagicMock plugins/test_plugin`; add a conftest autouse fixture that `monkeypatch`es `Path("plugins")` resolution to `tmp_path`. Replace `eval` at `plugin_settings.py:139` with `ast.literal_eval`. Gain: immutable, git-clean plugin packages; no test junk. Risk: one-time migration of existing `aliases.json` (copy on first load). Test: run suite, assert `git status plugins/` clean.

**P1-a — `plugins/_template/` + `tools/new_plugin.py <id> "<Display Name>" --prefix XX`**: copies the template, substitutes prefix/name, generates `tests/test_plugins/test_<id>/test_rules.py` from a shared parametrised smoke test (`tests/test_plugins/plugin_smoke.py`: loads, parses sample, saves round-trip, runs validator). Ship the template's `prompts.json` as the **full** `common/defaults/prompts.json` copy. Gain: 5-minute bootstrap; the test exists from minute one.

**P1-b — Collapse boilerplate into the base**: add `tag_manager_class`, `problem_analyzer_class`, `text_fixer_class`, `problem_prefix` class attributes on `BaseGameRules`; move the `__init__` wiring and the 9 delegation methods from `zelda_mc/rules.py:41-48,80-110,189-221` into the base; have `config_factory.generate_base_config` also return a `ProblemIDs` namespace and a `short_names` map. Delete `text_fixer.py`/`problem_analyzer.py` from mc/ww/plain/bmg; replace `plain_text/tag_logic.py` with `common/tag_logic.py` (generic bracket/curly matcher). Expected: zelda_mc/rules.py 245 → ~80 lines. Risk: low if done plugin by plugin with existing `test_zelda_*_rules.py` green.

**P1-c — Key-level prompt merge**: `glossary_prompt_manager._load_prompts()` = deep-merge of root → common/defaults → plugin JSON; `load_editor_review_prompt` / `get_glossary_prompt_template` read from the merged dict. Test: zelda_mc with `translation`-only file still yields `editor_review` and `glossary` from common.

**P2-a — Decouple BFN preview from zelda_bmg**: define `WindowKindProvider` hooks on base (`get_window_presets()`, `get_window_layout(kind)`, `get_window_frame(kind)`); move the 10 `from plugins.zelda_bmg…` imports in `ui/components/bfn_preview/*` and `plugin_tabs_mixin.py` behind `rules.get_capabilities() ∋ "message_window_preview"`. Drop `handlers/text_autofix_logic.py:44` fallback (use `BaseGameRules`).

**P2-b — One `docs/PLUGIN_CONTRACT.md` generated** from `plugins/spec.py` (`python -m plugins.spec --md`), with a test asserting the committed file equals the generated one; delete `plugins/DEVELOPER_GUIDE.md` sections 2–4 (wrong) and make the authoring guide and wiki link to the generated file. Fix `wiki/3:5` discovery path.

**P2-c — Plugin reload**: replace the 6-name `del sys.modules` list with `for m in list(sys.modules) if m.startswith(f"plugins.{name}.")`; wrap hook calls in `core/plugin_call.py:safe_call(rules, "hook", *a, default=…)` and use it at the bare sites (`text_views_mixin.py:114`, `bfn_actions.py:333`, `app_action_handler.py:154-160`).
