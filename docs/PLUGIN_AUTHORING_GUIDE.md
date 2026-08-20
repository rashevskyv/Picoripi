# Picoripi Plugin Authoring Guide

This guide explains how to create a new Picoripi plugin using `plugins/default_plugin/` as the baseline.

Use it together with:

- `plugins/default_plugin/README.md`
- `plugins/default_plugin/AI_PLUGIN_ASSISTANT_PROMPT.md`
- `docs/wiki/3_Plugin_Developer_Guide.md`
- `plugins/DEVELOPER_GUIDE.md`

## 1. What A Plugin Provides

A plugin teaches Picoripi how to understand a specific text format or game.

At minimum, it provides:

- a visible plugin entry through `config.json`;
- a `GameRules` class in `rules.py`;
- file load and save conversion;
- problem/warning definitions;
- tag recognition and syntax highlighting;
- font metrics and visible tag widths;
- optional AI prompt overrides and script metadata.

Picoripi discovers selectable plugins by scanning `plugins/*/config.json`. When a plugin is active, `ui/main_window/main_window_plugin_handler.py` imports `plugins.<plugin_name>.rules` and instantiates `GameRules`.

## 2. Recommended Starting Point

Start by copying:

```text
plugins/default_plugin/
```

to:

```text
plugins/<your_plugin_name>/
```

Then update:

- `config.json`: display name, width limits, default font file, detection/autofix settings.
- `rules.py`: parser, serializer, display name, page size, default script name.
- `tag_manager.py`: valid tags and syntax highlighting behavior.
- `font_map.json`: visible control-code widths and root-level overrides.
- `fonts/default_font.json`: baseline character widths.
- `translation_prompts/prompts.json`: plugin-specific AI behavior.
- `README.md`: plugin-specific setup notes.

## 3. Required Files

### `config.json`

This file makes the plugin visible in Settings.

Required practical fields:

- `display_name`
- `line_width_warning_threshold_pixels`
- `game_dialog_max_width_pixels`
- `lines_per_page`
- `default_font_file`
- `detection_enabled`
- `autofix_enabled`

Keep warning IDs aligned with `config.py`.

### `rules.py`

This is the entry point. It must expose:

```python
class GameRules(BaseGameRules):
    ...
```

The most important methods are:

- `load_data_from_json_obj()`
- `save_data_to_json_obj()`
- `get_display_name()`
- `get_problem_definitions()`
- `get_tag_pattern()`
- `get_syntax_highlighting_rules()`
- `get_legitimate_tags()`
- `analyze_subline()`
- `autofix_data_string()`
- `calculate_string_width_override()`
- `get_editor_page_size()`
- `get_default_script_name()`

Use PyQt6 imports only.

### `config.py`

Defines problem IDs and default problem settings.

Recommended pattern:

```python
from plugins.common.config_factory import generate_base_config

PLUGIN_PREFIX = "MYGAME"
PROBLEM_WIDTH_EXCEEDED = f"{PLUGIN_PREFIX}_WIDTH_EXCEEDED"
...
PROBLEM_DEFINITIONS, DEFAULT_DETECTION_SETTINGS, DEFAULT_AUTOFIX_SETTINGS = generate_base_config(PLUGIN_PREFIX)
```

### `tag_manager.py`

Defines valid tags and editor highlighting.

Use literal strings or regular expressions for:

- zero-width formatting tags;
- visible icon/button tags;
- page breaks;
- speaker/name placeholders;
- color tags.

### `font_map.json` And `fonts/*.json`

`fonts/*.json` files are loaded as font maps.

Root-level `font_map.json` is loaded as an override map. It is useful for visible tags and icon widths:

```json
{
  "[A]": { "width": 16 },
  "[PLAYER]": { "width": 32 },
  "{COLOR_RED}": { "width": 0 }
}
```

### `translation_prompts/prompts.json`

Use this for plugin-specific AI behavior:

- translation system prompt;
- glossary prompt;
- glossary occurrence update prompt;
- optional MemePalace prompt overrides.

## 4. Optional Advanced Capabilities: Mining The Game's Own Data

Everything in section 3 is the required minimum. Beyond it, a plugin can teach Picoripi to
mine the game's **own data** — message attributes, dialogue graphs, scene tables, actor
placement — or an external lore source, and feed that into AI translation, glossary
building, and the Story Timeline.

All of these are **opt-in**. Every hook has a safe default on `BaseGameRules`, and the
application degrades gracefully when a plugin does not implement it. A plugin that skips
this entire section still works: the universal AI text sweep operates on extracted text alone.

Start by asking what you actually have:

| If you have | What becomes possible |
| :--- | :--- |
| A decompilation or the game's source | window kinds, dialogue flow, scene tables, actor placement |
| Raw game files (message archives, stage/room data) | the same, by parsing the binaries directly |
| A community wiki for the game | external lore lookup for glossary descriptions |
| A fan script or walkthrough transcript | scene and speaker structure for MemePalace |
| Only the extracted text | nothing here is required — the text sweep still builds a glossary |

### 4.1 Capabilities Available Today

| Hook | What it unlocks in the app | Default |
| :--- | :--- | :--- |
| `get_translation_context_for_string` | Injects per-string game metadata into AI translation and glossary-building prompts. The engine recognises the keys `window_type`, `content_role`, `glossary_section`, and `force_glossary`, and treats their **values as opaque** — see the note below | `{}` |
| `get_ai_flow_context_for_string` | Per-line conversation context in the translation prompt: which dialogue the line belongs to, its position, branch conditions | `None` |
| `get_ai_flow_overview` | Chunk-level conversation outlines for batch translation | `None` |
| `get_scene_context_for_string` | Story Timeline evidence: message resource, group, flow ids, `candidate_actors`, `flow_summary`, `location_candidates` | `{}` |
| `get_string_layout` | Per-string width, font, and lines-per-page derived from game data instead of one global setting | `None` |
| `prepare_preview_glyph_text` | Visual preview with per-character colors (and, if you extend it, scales and inline icons) | text with tags stripped |
| `get_dynamic_name_tags` | Substitutes runtime name tags with real names before script matching, so `{escape:0:0022}` can match `Epona` in a script | `{}` |
| `should_auto_match_story_context` | Excludes non-dialogue strings (captions, signs) from automatic script matching | `True` |
| `parse_walkthrough_transcript` | Parses a game script into rooms, scenes, and speakers for MemePalace | generic text parser |
| `get_tag_tooltip` | Human-readable explanations for control codes in the editor | `""` |
| `get_plugin_actions`, `get_context_menu_actions` | Custom toolbar and context-menu actions | `[]` |
| `export_runtime_session_state`, `restore_runtime_session_state` | Persists plugin-derived runtime state across sessions | not defined on base |

**Slots versus values.** The metadata keys above are *slots* the engine publishes; the values
you put in them are yours. `content_role` may be `"BossName"`, `"PokemonName"`,
`"ChoiceOption"`, or anything your game needs — the engine passes it through without
interpreting it. Do not expect the engine to understand a role by name, and do not add engine
code that compares against a specific value.

### 4.2 Declared Capabilities

`get_capabilities()` returns the set of names below. It is what the **Localization Pipeline**
wizard (`Tools → Localization Pipeline…`) reads to decide which steps to offer, so a step
that needs the game's own data never appears for a plugin that cannot supply it.

Declaring nothing is a complete answer. The wizard still offers the whole path that runs on
extracted text alone — collect, describe, translate and confirm the glossary, then translate
the text — because none of that needs anything from the game beyond the text itself.

| Name | Hook it promises | What appears once declared |
| :--- | :--- | :--- |
| `glossary_seed` | `get_glossary_seed_entries()` | "Structural seed only" mode: ready-made glossary material straight from game data (`{term, description?, section, icon?, source_ref}`), with **no AI involved at all** |
| `external_lore` | `get_external_lore(term)` | external knowledge lookup grounding glossary descriptions |
| `speaker_attribution` | `get_speaker_for_string()` | the **Name the speakers** step, which joins a marked-up script onto the speaker codes the game data produced |

Also implemented, and needing no declaration:

- `get_addressee_for_string()` — who a line is addressed to, for the Story Timeline and
  translation prompts.
- A `role_instruction` key alongside `content_role`, so a plugin supplies not just the name of
  a role but the sentence explaining what it means to the AI.

### 4.3 Reference Implementation

`plugins/zelda_bmg/` (The Legend of Zelda: Twilight Princess) is the reference for how far
this can go. From the game's own files and a decompilation it mines:

- **message attributes** — each message carries a byte identifying which on-screen window
  the game draws it in, which in turn identifies the message's *role*: an item-acquisition
  window pairs an item name with its description and icon; a location plate holds a place
  name; a boss card holds a boss name. This turns whole categories of message into
  ready-made glossary entries (`window_kinds.py`, `get_translation_context_for_string`);
- **dialogue flow graphs** — reconstructs conversations, branches, and follow-up actions
  from the message archive's flow tables (`get_ai_flow_context_for_string`);
- **scene tables** — maps message groups to stages and candidate actors
  (`get_scene_context_for_string`, `stage_data.py`);
- **per-window layout** — derives text width and lines-per-page per message from its window
  kind rather than one global limit (`get_string_layout`);
- **rich preview** — per-character colors, text scaling, and inline button icons
  (`prepare_preview_glyph_text`);
- **external lore** — descriptions from a community wiki (currently in
  `core/mempalace/character_profiler.py`; moving into the plugin, see the roadmap).

Copy the *approach*, not the code: the specific tables are game-specific, but the pattern —
find the field in the game's data that already encodes a message's role, then expose it
through a hook — transfers to most games.

## 5. Development Workflow

1. Copy `plugins/default_plugin/`.
2. Rename the folder and display name.
3. Add realistic sample source and translated files outside the plugin package.
4. Implement parsing first.
5. Add round-trip tests before adding AutoFix complexity.
6. Add tag tests.
7. Add width and wrapping tests.
8. Add AI prompt overrides last.
9. Run targeted tests in parallel.
10. Run the full suite in parallel before release.

## 6. Questions To Answer Before Coding

Before implementing a new plugin, collect:

- exact file format;
- sample source files;
- sample translated files;
- expected save output;
- max width and lines per page;
- all known tags/control codes;
- visible tag widths;
- zero-width tag list;
- font metric source;
- page-break behavior;
- speaker/chapter metadata;
- whether unknown metadata must round-trip unchanged;
- at least 5 parser examples;
- at least 5 tag edge cases;
- at least 3 width/wrapping cases.

The prompt in `plugins/default_plugin/AI_PLUGIN_ASSISTANT_PROMPT.md` asks these questions in a structured way.

## 7. Tests For A New Plugin

Create:

```text
tests/test_plugins/test_<your_plugin_name>/test_rules.py
```

Minimum tests:

- plugin loads and exposes `GameRules`;
- `config.json` display name matches `get_display_name()`;
- plain or structured sample parses into expected blocks;
- save round-trip preserves required data;
- tag validity works for valid and invalid examples;
- width warning triggers on a deliberately long line;
- AutoFix returns `(str, bool)` and does not corrupt tags;
- default prompt JSON is valid.

Command:

```powershell
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/test_plugins/test_<your_plugin_name>/
```

## 8. Common Mistakes

- Importing `PyQt5` instead of `PyQt6`.
- Creating `rules.py` without `config.json`, which prevents UI discovery.
- Writing plugin-specific parser behavior in shared `plugins/common/`.
- Adding `Mock`/`MagicMock` checks to production plugin code.
- Returning metadata that cannot be serialized during session save.
- Treating visible icon tags as zero-width.
- Splitting or deleting unknown data fields during save.
- Adding AI prompt instructions that permit changing tags.

## 9. Release Checklist

- Plugin appears in Settings.
- `GameRules` imports without side effects.
- No network, disk-heavy, or archive-heavy work happens in `GameRules.__init__`.
- Fonts load and default width warnings work.
- Sample files parse and save correctly.
- Targeted plugin tests pass with `pytest -n auto`.
- Full suite passes with `pytest -n auto`.
- Documentation links point to the plugin README and prompt file.

