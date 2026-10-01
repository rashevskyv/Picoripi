# Plugin + speaker merge split result (wave 5 H)

MOVE-ONLY split of `ui/settings/plugin_mixin.py` (~1001 lines) and `components/speaker_merge_dialog.py` (~944 lines).

## Plugin settings files

| File | Lines |
|------|------:|
| `ui/settings/plugin_mixin.py` (composition) | 24 |
| `ui/settings/plugin_tabs_mixin.py` — setup/rebuild, font list, display, rules, Zelda BMG window rules | 346 |
| `ui/settings/plugin_tables_mixin.py` — context tags tables | 194 |
| `ui/settings/plugin_paths_mixin.py` — paths subtab | 102 |
| `ui/settings/plugin_checkboxes_mixin.py` — detection/autofix populate | 86 |
| `ui/settings/plugin_aliases_mixin.py` — aliases | 146 |
| `ui/settings/plugin_fontmap_mixin.py` — font map table | 176 |

`SettingsPluginMixin` MRO: `PluginTabsMixin`, `PluginTablesMixin`, `PluginPathsMixin`, `PluginCheckboxesMixin`, `PluginAliasesMixin`, `PluginFontmapMixin`.

## Speaker merge files

| File | Lines |
|------|------:|
| `components/speaker_merge_dialog.py` (shim) | 19 |
| `components/speaker_merge/__init__.py` | 14 |
| `components/speaker_merge/widgets.py` — roles/colors, `NameOnlyDelegate`, `_votes_line`/`_top_name`/`extract_candidates`/`describe_code` | 118 |
| `components/speaker_merge/dialog.py` — `__init__` + composition | 191 |
| `components/speaker_merge/tree_mixin.py` — populate, groups, filter, check | 344 |
| `components/speaker_merge/inspector_mixin.py` — inspector, names, apply | 341 |

`SpeakerMergeDialog` MRO: `TreeMixin`, `InspectorMixin`, `QDialog`.

## Spec notes

- Class/method bodies copied verbatim; AST dumps verified vs git HEAD originals: plugin 37/37, speaker merge 42/42, 0 mismatches.
- Callers keep `from ui.settings.plugin_mixin import SettingsPluginMixin` and `from components.speaker_merge_dialog import SpeakerMergeDialog` (plus `describe_code` / `extract_candidates` / `NameOnlyDelegate`).
- Helpers and item-role/color constants live in `widgets.py` beside `NameOnlyDelegate` so mixins can share them; shim re-exports the public symbols.
- Unused import trim limited to what ruff required after the move (`NAME_SEPARATOR` added on tree mixin); no behavior changes.
- No `_ShimName` (handler tests patch `handlers.speaker_merge_handler.SpeakerMergeDialog`, not mixin globals).
- No monolith backup under `.grok/`.

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m ruff check ui/settings components/speaker_merge components/speaker_merge_dialog.py
→ All checks passed!

.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/test_settings tests/test_handlers/test_speaker_merge_handler.py tests/test_components/test_speaker_merge_dialog.py -q --tb=short
→ 71 passed in 2.53s
```

Note: spec path `tests/test_ui/test_settings_dialog.py` is absent (settings UI tests live under `tests/test_ui/test_settings/`). Added `tests/test_components/test_speaker_merge_dialog.py` because that module was split.
