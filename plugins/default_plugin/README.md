# Default Plugin Template

`default_plugin` is a safe, minimal Picoripi plugin intended as the starting point for new user plugins.

It is deliberately small but fully loadable:

- `config.json` makes the plugin visible in Settings.
- `rules.py` defines `GameRules`, the plugin entry point.
- `config.py` defines the default warning IDs and settings.
- `tag_manager.py` describes the game's tags. The problem analyzer and the text fixer come from `plugins/common/`;
  `GameRules` names them with class attributes (`problem_definitions`, `tag_manager_class`, `tag_style`, …) and the
  base class wires them. Add your own `problem_analyzer.py` / `text_fixer.py` only for game-specific checks.
- `fonts/default_font.json` provides a tiny working proportional font map.
- `font_map.json` contains tag/icon width overrides.
- `translation_prompts/prompts.json` provides local prompt overrides.
- `AI_PLUGIN_ASSISTANT_PROMPT.md` is a copy-paste prompt for AI-assisted plugin creation.

## How To Use

1. Create the plugin and its test folder from this template:

```powershell
.\venv\Scripts\python.exe tools/new_plugin.py <your_plugin_name> "<Display Name>" --prefix XX
```

   `--prefix` is the short uppercase tag of the plugin's problem ids (`XX_WIDTH_EXCEEDED`). The new plugin is
   listed by the application at once and its generated tests pass.
2. Replace file parsing in `rules.py`:
   - `load_data_from_json_obj()`
   - `save_data_to_json_obj()`
3. Replace tag validation in `tag_manager.py`.
4. Replace or extend font metrics in `fonts/default_font.json` and visible tag widths in `font_map.json`.
5. Put a real piece of the game's text into `SAMPLE` in `tests/test_plugins/test_<your_plugin_name>/test_rules.py`
   and add tests for the game's own rules.
6. Check and run:

```powershell
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m plugins.validate <your_plugin_name>
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/test_plugins/test_<your_plugin_name>/
```

## Beyond The Minimum

The steps above produce a working plugin. A plugin can also teach Picoripi to mine the
game's **own data** — message attributes that identify what a string *is*, dialogue flow,
scene tables — or an external lore source, and feed that into AI translation, glossary
seeding, and the Story Timeline. All of it is opt-in and nothing breaks if you skip it.

See `docs/PLUGIN_AUTHORING_GUIDE.md` section 4 for the full list of hooks, and
`plugins/zelda_bmg/` for a reference implementation that goes the whole way.

If the game has a decompilation or original layout/message files, **read those
first** the way `zelda_bmg` reads dusklight and `res/Layout`. Capabilities such
as `message_window_preview` exist so the BFN preview can draw real in-game
windows; they stay off until your plugin declares them in `get_capabilities()`.
Copy the pattern, not the Twilight Princess tables.

For detailed guidance, see:

- `docs/PLUGIN_AUTHORING_GUIDE.md`
- `docs/wiki/3_Plugin_Developer_Guide.md`
- `plugins/DEVELOPER_GUIDE.md`

