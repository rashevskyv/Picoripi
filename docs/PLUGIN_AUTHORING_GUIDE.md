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

## 4. Development Workflow

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

## 5. Questions To Answer Before Coding

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

## 6. Tests For A New Plugin

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

## 7. Common Mistakes

- Importing `PyQt5` instead of `PyQt6`.
- Creating `rules.py` without `config.json`, which prevents UI discovery.
- Writing plugin-specific parser behavior in shared `plugins/common/`.
- Adding `Mock`/`MagicMock` checks to production plugin code.
- Returning metadata that cannot be serialized during session save.
- Treating visible icon tags as zero-width.
- Splitting or deleting unknown data fields during save.
- Adding AI prompt instructions that permit changing tags.

## 8. Release Checklist

- Plugin appears in Settings.
- `GameRules` imports without side effects.
- No network, disk-heavy, or archive-heavy work happens in `GameRules.__init__`.
- Fonts load and default width warnings work.
- Sample files parse and save correctly.
- Targeted plugin tests pass with `pytest -n auto`.
- Full suite passes with `pytest -n auto`.
- Documentation links point to the plugin README and prompt file.

