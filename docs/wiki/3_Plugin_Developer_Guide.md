# Plugin Developer Guide

**Language:** English · [Українська](uk/3_Plugin_Developer_Guide.md)

This page is the plugin contract as implemented in code. Source of truth: `plugins/base_game_rules.py`, `ui/main_window/main_window_plugin_handler.py`, `handlers/project_action_handler.py` (discovery), `ui/settings/logging_mixin.py` (`find_plugins`).

Do not treat `docs/PLUGIN_AUTHORING_GUIDE.md` or plugin READMEs as current unless you have just checked them against those files.

---

## Discovery and load

**Discovery** (New Project and Settings → Global → Active Game Plugin): every **directory** under `plugins/` that contains `config.json`. `import_plugins` is skipped in Settings. `display_name` in that JSON is the label; the folder name is the plugin id.

**Load:** `importlib.import_module(f"plugins.{active_game_plugin}.rules")`. The module must define `GameRules`, a subclass of `BaseGameRules`. Constructor: `GameRules(main_window_ref=self.mw)`.

If import fails, the user gets **Plugin Load Error** and the app falls back to `BaseGameRules` itself.

Related modules are force-reloaded with the plugin: `config`, `tag_checker_handler`, `tag_manager`, `problem_analyzer`, `text_fixer`, `tag_logic`.

**Aliases:** `plugins/<id>/aliases.json` is merged into `default_tag_mappings` after load.

**Project actions:** `get_plugin_actions()` may add menu/toolbar `QAction`s (`text`, `tooltip`, `shortcut`, `handler`, `menu`, `toolbar`).

---

## Minimal plugin layout

Copy `plugins/default_plugin/` to `plugins/<your_id>/`. Required for discovery + load:

```
plugins/<your_id>/
  config.json          # at least "display_name"
  rules.py             # class GameRules(BaseGameRules)
```

Typical extra files (template has them): `config.py`, `tag_manager.py`, `problem_analyzer.py`, `text_fixer.py`, `font_map.json`, `fonts/`, `translation_prompts/prompts.json`, `aliases.json`.

`default_plugin.GameRules.get_display_name()` returns `Default Plugin Template`. `get_capabilities()` returns `set()` on purpose.

---

## `config.json`

Loaded for the display name and as a bag of plugin defaults. The template includes (non-exhaustive): `display_name`, `newline_display_symbol`, wrap flags, `game_dialog_max_width_pixels`, `line_width_warning_threshold_pixels`, `lines_per_page`, `default_font_file`, `autofix_enabled`, `detection_enabled`, tag/newline colours.

Shipped ids and labels:

| Folder | `display_name` |
|--------|----------------|
| `zelda_bmg` | Zelda: Twilight Princess BMG |
| `zelda_mc` | The Legend of Zelda: The Minish Cap |
| `zelda_ww` | Zelda: The Wind Waker |
| `plain_text` | Zelda: The Wind Waker |
| `pokemon_fr` | Pokemon FireRed/LeafGreen |
| `default_plugin` | Default Plugin Template |

---

## Capabilities

`get_capabilities() -> Set[str]`. Empty means: pipeline still offers markup, context, glossary, and text translation. Optional names:

| Name | Hook | Who uses it |
|------|------|-------------|
| `glossary_seed` | `get_glossary_seed_entries()` | Glossary auto-pass |
| `external_lore` | `get_external_lore(term)` | Describe pass |
| `speaker_attribution` | `get_speaker_for_string()` | Pipeline **Name the speakers**; Speaker field |
| `message_window_preview` | preview chrome / pagination | BFN preview window bar |

`zelda_bmg` returns all four. Settings default `active_game_plugin` is `"zelda_mc"` until a project says otherwise (`core/settings/global_settings.py`).

Optional hooks **not** on the base class, used if present: `get_preview_window_style(block, string)` (window chrome when `message_window_preview` is set), `msg_to_editor_text`, `export_runtime_session_state` / `restore_runtime_session_state`, `replace_runtime_names_for_ai`. `zelda_bmg.prepare_preview_glyph_text` may return a 4-tuple `(text, colors, scales, icons)`; the preview accepts the base 2-tuple as well.

There is no `get_plugin()` / `PluginManager`. Import plugins under `plugins/import_plugins/` (`BaseImportRules`) are a separate paste-import path, not this loader.

Seed dict keys: `term` (required), `description`, `section`, `icon`, `source_ref`.

`is_placeholder_speaker(name)`: `True` (default) = merge step may replace this identity with a script name. Return `False` for already-display names (`System`, curated names).

---

## Data in and out

Internal store is `List[List[str]]` (blocks of strings) plus block names.

| Method | Role |
|--------|------|
| `load_data_from_json_obj(json_data)` | File bytes/JSON/text → `(blocks, extra_dict)`. `zelda_bmg` accepts **bytes** via `bmg_tool.BMGFile` |
| `save_data_to_json_obj(data, block_names)` | Inverse; may return text **or packed bytes** (BMG) |
| `convert_editor_text_to_data(text)` | Editor → stored (default: aliases → tags) |
| `get_text_representation_for_editor(subline)` | Stored → editor (default: tags → aliases) |
| `get_text_representation_for_preview(data_string)` | Preview list; newlines become `newline_display_symbol` |
| `prepare_preview_glyph_text(text)` | Visual BFN preview: strip tags, optional per-char colours |
| `get_enter_char` / `get_shift_enter_char` / `get_ctrl_enter_char` | What Enter inserts |

Base `load_data_from_json_obj` understands a list, `{ "strings": [...] }`, and Kruptar `{END}` text.

---

## Layout, tags, issues

| Method | Role |
|--------|------|
| `get_string_layout(block, string)` | Optional `{warn_width, max_width, font_file, lines_per_page}`. Priority: per-string metadata > this hook > global plugin settings |
| `get_problem_definitions()` | `{id: {name, …}}` for Detection / Auto-fix / Warnings filter |
| `analyze_subline(...)` | Return a set of problem ids for one visual line |
| `autofix_data_string(..., page_local=False)` | Return `(new_text, changed)` |
| `get_short_problem_name(id)` | Label |
| `get_default_tag_mappings()` | alias → original tag |
| `get_dynamic_name_tags()` | `{tag: display_name}` substituted before script matching |
| `get_spellcheck_ignore_pattern()` | Regex of tags/control codes to skip |
| `get_legitimate_tags()` | Default empty |
| `get_syntax_highlighting_rules()` | `List[Tuple[pattern, QTextCharFormat]]` |
| `get_tag_tooltip(tag)` | Hover text |
| `get_tag_checker_handler()` | Optional checker object |
| `get_custom_context_tags()` / `save_custom_context_tags` | Context Tags settings |
| `get_context_menu_actions(editor, selected_text)` | Extra editor menu items |
| `get_editor_page_size()` | Default 2 |
| `calculate_string_width_override(...)` | Optional pixel width |
| `process_pasted_segment(...)` | Paste sanitiser |

---

## Speakers, scene, AI metadata

| Method | Role |
|--------|------|
| `get_speaker_for_string(block, string)` | Game-data speaker; engine fills rows the user has not set; never overwrites a user choice |
| `get_addressee_for_string(block, string, speaker=)` | T–V / gendered address |
| `should_auto_match_story_context(block, string)` | Default True; skip automatic dialogue matching if False |
| `get_translation_context_for_string(block, string)` | See [11](11_AI_Translation.md). Engine never compares values to a specific game |
| `get_ai_flow_context_for_string` / `get_ai_flow_overview` | Dialogue-graph notes in the prompt |
| `get_scene_context_for_string` | Story Timeline evidence (`resource`, `msg_group`, `flow_ids`, `candidate_actors`, …) |

---

## What not to do

- Do not put game dumps, `.arc`, or Nintendo assets in a plugin you commit.
- Do not hard-code Twilight Princess window kind integers in the **engine**. Put them in the plugin (`zelda_bmg` already does).
- Do not teach the engine a new `content_role` string; return `role_instruction` from the plugin instead.
- Do not declare `speaker_attribution` unless `get_speaker_for_string` actually returns identities.
- Do not copy `zelda_bmg` tables into a new game plugin; copy the **approach** (read this game’s files, advertise capabilities).
- Do not forget `config.json` — without it the plugin never appears in New Project / Settings.
