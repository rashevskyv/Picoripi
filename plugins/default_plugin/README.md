# Default Plugin Template

`default_plugin` is a safe, minimal Picoripi plugin intended as the starting point for new user plugins.

It is deliberately small but fully loadable:

- `config.json` makes the plugin visible in Settings.
- `rules.py` defines `GameRules`, the plugin entry point.
- `config.py` defines the default warning IDs and settings.
- `tag_manager.py`, `problem_analyzer.py`, and `text_fixer.py` connect to the shared rule engine in `plugins/common/`.
- `fonts/default_font.json` provides a tiny working proportional font map.
- `font_map.json` contains tag/icon width overrides.
- `translation_prompts/prompts.json` provides local prompt overrides.
- `AI_PLUGIN_ASSISTANT_PROMPT.md` is a copy-paste prompt for AI-assisted plugin creation.

## How To Use

1. Copy `plugins/default_plugin/` to `plugins/<your_plugin_name>/`.
2. Rename the display name in `config.json`.
3. Replace file parsing in `rules.py`:
   - `load_data_from_json_obj()`
   - `save_data_to_json_obj()`
4. Replace tag validation in `tag_manager.py`.
5. Replace or extend font metrics in `fonts/default_font.json` and visible tag widths in `font_map.json`.
6. Add plugin-specific tests under `tests/test_plugins/test_<your_plugin_name>/`.
7. Run:

```powershell
$env:PYTHONPATH = "."; .\venv\Scripts\python.exe -m pytest -n auto tests/test_plugins/test_<your_plugin_name>/
```

For detailed guidance, see:

- `docs/PLUGIN_AUTHORING_GUIDE.md`
- `docs/wiki/3_Plugin_Developer_Guide.md`
- `plugins/DEVELOPER_GUIDE.md`

