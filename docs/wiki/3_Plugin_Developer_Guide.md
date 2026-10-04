---
status: current
updated: 2026-10-03
owns: plugins/
tokens: 4.1k
purpose: The one plugin guide: files, hooks, capabilities, tests
---
# Plugin Developer Guide

**Language:** English · [Українська](uk/3_Plugin_Developer_Guide.md)

A plugin teaches Picoripi one game or text format: how to read and write its files, what its tags are, how wide a line may be, and — optionally — what the game's own data says about each line. This page is the only plugin guide. The list of every hook is generated from the code: [docs/PLUGIN_CONTRACT.md](../PLUGIN_CONTRACT.md).

Source of truth: `plugins/base_game_rules.py` (the hooks and their defaults), `plugins/spec.py` (the contract as data), `ui/main_window/main_window_plugin_handler.py` (loading), `ui/settings/logging_mixin.py` → `find_plugins` (discovery).

---

## Start a plugin

```powershell
.\venv\Scripts\python.exe tools/new_plugin.py <id> "<Display Name>" --prefix XX
```

`<id>` is the folder name under `plugins/`; `--prefix` is the short uppercase tag of the plugin's problem ids (`XX_WIDTH_EXCEEDED`). The command copies `plugins/default_plugin`, renames the prefix and the display name, and writes `tests/test_plugins/test_<id>/test_rules.py` with three passing checks (the plugin loads, a sample survives load and save, the validator passes). The application lists the new plugin at once.

Then, in this order:

1. Parsing: `load_data_from_json_obj` / `save_data_to_json_obj` in `rules.py`. Put a real sample into `SAMPLE` in the generated test before touching anything else.
2. Tags: `tag_manager.py`.
3. Widths: `fonts/*.json`, `font_map.json`, the limits in `config.json`.
4. Prompts: `translation_prompts/prompts.json`, last.

Check and test:

```powershell
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m plugins.validate <id>
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/test_plugins/test_<id>/
```

`python -m plugins.validate` calls every hook with dummy arguments and reports a hook that raises, a wrong return type, a signature the host cannot call, a broken JSON file, per-session keys in `config.json`, and (as warnings) main-window attributes outside the allowed list.

### Collect before coding

The exact file format with sample source and translated files and the expected save output; the maximum width and lines per page; every tag and control code, which are zero-width and how wide the visible ones are; where font metrics come from; how pages break; speaker or chapter metadata; whether unknown fields must round-trip unchanged. `plugins/default_plugin/AI_PLUGIN_ASSISTANT_PROMPT.md` asks these questions in a form you can paste to an AI assistant.

---

## Discovery and load

**Discovery** (New Project and Settings → Global → Active Game Plugin): every directory under `plugins/` that contains `config.json`, except `import_plugins`. `display_name` in that file is the label and must be unique; the folder name is the plugin id.

**Load:** `importlib.import_module(f"plugins.{id}.rules")`. The module must define `GameRules`, a subclass of `BaseGameRules`, constructed as `GameRules(main_window_ref=self.mw)`. It must also build without a main window (`GameRules()`): tests and the validator do that. No network, disk-heavy or archive work in `__init__`.

If the import fails, the user gets **Plugin Load Error** and the application falls back to `BaseGameRules`. Switching plugins drops every loaded module of the plugin, so module-level caches start empty.

**Aliases:** after load, `plugins/<id>/aliases.json` (shipped defaults, read-only) and then the user's own `aliases.json` from the per-user plugin folder are merged into `default_tag_mappings`. The application saves aliases only to the per-user folder.

**Force aliases and names drawn in colour:** an alias whose name starts with `F:` (`"{F:Link}": "{Player}"`) reaches the model as the plain word, which it declines; the translation keeps that word and not the tag, so a renamed hero still reads «Лінк». If the game itself draws that name in a colour, return the colour tags from `get_force_alias_wrapping()` (`{"{F:Link}": ("{Color:Green}", "{Color:White}")}` in Minish Cap): the word is sent wrapped and the declined form comes back in the same colour; the tag warning does not count those tags as extra. Find out per game whether the engine colours the name — Twilight Princess and The Wind Waker do not, Minish Cap does.

**Menu actions:** `get_plugin_actions()` may add `QAction`s (`name`, `text`, `tooltip`, `shortcut`, `handler`, `menu`, `toolbar`). The AI translate actions belong to the application and are present for every game.

---

## Files of a plugin

```
plugins/<id>/
  config.json                         # required: at least "display_name"
  rules.py                            # required: class GameRules(BaseGameRules)
  config.py                           # problem ids and default detection / autofix settings
  tag_manager.py                      # the game's tags and their highlighting
  font_map.json, fonts/*.json         # widths
  font_sources.json                   # the game's fonts for the font editor (optional)
  translation_prompts/prompts.json    # prompt sections the game changes
```

**`config.json`** — defaults for a new project: `display_name`, `game_dialog_max_width_pixels`, `line_width_warning_threshold_pixels`, `lines_per_page`, `default_font_file`, `detection_enabled`, `autofix_enabled`, colours and wrap flags. Per-session keys (open file paths, selection, scroll positions, search history) are refused by the validator; the application stores those in `project_settings.json`.

**`config.py`** — `PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config(PREFIX, overrides=…, custom_problems=…)` from `plugins/common/config_factory.py`.

**`rules.py`** — `GameRules` declares its parts with class attributes and `BaseGameRules` wires them:

```python
class GameRules(BaseGameRules):
    problem_prefix = "XX"
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager        # default: GenericTagManager
    tag_style = "curly"                   # "square" when tags look [like this]
    analyze_whole_string_first = True
```

With these the base class builds the tag manager, the problem analyzer and the text fixer and answers the hooks that only pass a call on (problem definitions, highlighting, analysis, autofix, short problem names). Name `problem_analyzer_class` / `text_fixer_class` only for game-specific checks or fixes (subclass `GenericProblemAnalyzer` / `GenericTextFixer` from `plugins/common/`). `problem_ids = problem_ids(DEFINITIONS, PREFIX, without=(…))` leaves out standard checks the game does not use.

**`font_map.json` and `fonts/*.json`** — `fonts/*.json` are font maps (`{character: {"width": N}}`). The root `font_map.json` overrides widths of visible tags and icons: `{"[A]": {"width": 16}, "{COLOR_RED}": {"width": 0}}`. A visible icon tag is not zero-width. Widths the user sets in the application (tag width dialog, Settings → font map) are saved to `~/.picoripi/plugins/<plugin>/font_map.json`, which wins over the plugin's file; the same holds for `translation_map.json` written by the BFN editor without a project. The application never writes into `plugins/`.

**`font_sources.json`** (or the hook `get_font_sources()`) — the game's own bitmap fonts, so the font editor lists them for a project and saves them back. Each entry: `label`, `format` (`bfn`, `n64`, `g1t`, `g1n`, `bffnt` (Switch), `bcfnt` (3DS BCFNT and 3DS BFFNT), `qbf` or `gzf` (Grezzo, OoT3D / MM3D)), `path` (a path or glob relative to the project's source folder, or a list of candidates — the first that matches wins; `../` may climb out; a single-file project's file is used as it is), optional `member` (a glob of files inside the archive at `path`), `font_map` (the width map the font feeds; the editor writes it to `<project>/font_maps/` on save and the width checks read it) and `params` (the format's game constants: the cell grid and code page of a G1T atlas, the ROM id, dmadata files and width-table offset of an N64 font, which size of a G1N file; BFN, BFFNT and the 3DS formats describe themselves, but a BFFNT source may set `min_sheets`: the font opens with blank sheets up to that count, and a sheet that gets glyphs is saved as a new texture layer with its characters added to the font's character map — for a font with no room for a new alphabet). The format code in `core/font_formats/` holds no game constants. A file that holds both text and a font (an N64 ROM) keeps the font edits when the text is saved: the host carries them from the translation copy into the rebuilt file. A `translation_map.json` in the plugin folder (`{"Ж": "Æ"}`: the translated letter is drawn with that slot's glyph) seeds the editor's map for a project that has none; fonts that map Unicode characters (`bffnt`, `bcfnt`, `qbf`, `gzf`, `g1n`) take the real letters instead.

**`translation_prompts/prompts.json`** — may hold only the sections the game changes (usually `translation`); the rest is merged in key by key from `plugins/common/defaults/prompts.json`. Never add an instruction that permits changing tags.

---

## File formats and the state that goes with them

`get_file_formats()` returns `core.formats.FileFormat(extensions, mode, label)` items. `mode` is the shape in which a file's content reaches `load_data_from_json_obj` and leaves `save_data_to_json_obj`: `"json"` (parsed), `"text"` (a string) or `"bytes"`. The default is `.json` + `.txt`. A game with its own table returns `[FileFormat((".tbl",), "bytes", "Text tables"), *DEFAULT_FORMATS]` and parses the bytes itself; project import, loading, saving and the open/save dialogs follow without host changes. An archive format is added with `ContainerManager.register(MyContainer, extensions=(".pak",))`.

Inside the application the text is `List[List[str]]` — blocks of strings — plus block names. `load_data_from_json_obj` returns `(blocks, block_names)`; `save_data_to_json_obj(blocks, block_names)` returns what goes back to the file. Unknown fields of the format must survive the round trip.

If saving needs something the strings do not carry (table keys, the parsed binary file), keep it in the plugin and implement `export_runtime_state()` / `restore_runtime_state(state)` / `reset_runtime_state()` — plain JSON data that the host keeps across reloads, reverts and sessions — and `prepare_save_context(context)`, called before each project file is built (`context.block_indices`, `context.runtime_state`, `context.existing_versions()` yields the file's current bytes, translation first). The host never reads plugin attributes. Examples: `plugins/pokemon_fr/rules.py` (keys), `plugins/zelda_bmg/rules.py` (a binary file patched on save).

---

## Capabilities and the game's own data

Everything above is the required minimum. Beyond it a plugin can mine the game's own data — message attributes, dialogue graphs, scene tables — or an outside lore source, and feed that into AI translation, glossary building and the Story Timeline. All of it is opt-in; every hook has a safe default.

| If you have | What becomes possible |
|---|---|
| A decompilation or the game's source | window kinds, dialogue flow, scene tables, actor placement |
| Raw game files (message archives, stage data) | the same, by parsing the binaries |
| A community wiki | lore lookup for glossary descriptions |
| A fan script or walkthrough | scene and speaker structure for MemPalace |
| Only the extracted text | nothing here is needed — the text sweep still builds a glossary |

`get_capabilities() -> Set[str]` tells the Localization Pipeline which steps to offer. Declaring nothing is a complete answer.

| Name | Hook it promises | What appears |
|---|---|---|
| `glossary_seed` | `get_glossary_seed_entries()` | Glossary terms taken from game data without an AI request (`term`, `description`, `section`, `icon`, `source_ref`, `blocks`) |
| `external_lore` | `get_external_lore(term)` | Outside knowledge for glossary descriptions |
| `speaker_attribution` | `get_speaker_for_string()` | The **Name the speakers** step and the Speaker field |
| `message_window_preview` | `get_preview_window_style()` and the `get_window_*` hooks | In-game message windows in the preview, per-window limits in Settings |

Do not declare a capability the plugin cannot deliver.

**Slots, not values.** `get_translation_context_for_string` returns metadata under keys the engine publishes — `window_type`, `content_role`, `role_instruction`, `has_speaker`, `glossary_section`, `force_glossary`. The values are the plugin's: `content_role` may be `"BossName"` or anything the game needs, and `role_instruction` is the sentence that tells the model what the role means. The engine never compares a value to a specific game, and engine code must not learn one.

**Speakers.** `get_speaker_for_string` returns the identity the game data records; the engine fills rows the user has not set and never overwrites a user's choice. `is_placeholder_speaker(name)` says whether that identity is an internal id the script-merge step may replace with a real name (default: yes).

**Message windows.** With `message_window_preview`: `get_preview_window_style(block_idx, string_idx)` gives the style of a message; `get_window_presets()` / `get_window_preset_label()` / `get_window_style_for_preset()` feed the bar that forces a window kind; `get_window_frame(style)` returns geometry and picture read from the game's files; `get_window_item_icon()` and `get_window_text_offset_y()` cover the item slot and the game's vertical centring; `get_window_layout_groups()` / `get_window_layouts_document()` / `save_window_layouts_document()` drive the Settings table of per-window limits. `get_string_layout(block, string)` gives per-string width, font and lines per page (priority: per-string override > this hook > global settings).

**Reference implementation.** `plugins/zelda_bmg/` (Twilight Princess) reads the game's files and a decompilation: message attributes that identify the window and therefore the role of a message (`window_kinds.py`), dialogue flow graphs (`msg_flow.py`), scene tables (`stage_data.py`), per-window layout, a preview with colours, scaling and icons, window frames from a local dump (`window_frame_loader.py`). Copy the approach — find the field in the game's data that already encodes what a message is, and expose it through a hook — not the tables.

---

## Tests for a plugin

The generated test file is the start. Add, with real data: a sample that parses into the expected blocks; a save round trip that keeps every field; valid and invalid tags; a width warning on a deliberately long line; autofix returning `(str, bool)` without damaging tags. `plugins/testing.py` has the shared checks (`check_loads`, `check_round_trip`, `check_validator`).

---

## What not to do

- Do not put game dumps, archives or the publisher's assets in a plugin you commit.
- Do not import PyQt5; the application is PyQt6.
- Do not write game-specific behaviour into `plugins/common/` or into the engine. Window kinds, item ids and role names belong to the plugin.
- Do not check for `Mock` objects in plugin code.
- Do not return metadata that cannot be serialised: it ends up in the session file.
- Do not drop or reorder unknown fields of the file format on save.
- Do not copy `zelda_bmg` tables into another game's plugin.
- Do not forget `config.json` — without it the plugin never appears.
