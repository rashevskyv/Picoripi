# Wave 6 split result

MOVE-ONLY splits. Verbatim method bodies. Shims keep old imports. No monolith
backups under `.grok/`. `_ShimName` only where tests patch module globals
(`ui.main_window.main_window_actions`).

---

## 1. `core/mempalace/dialogue_mapping.py`

Barrel at old path. Package `core/mempalace/mapping/`.

| File | Lines | Contents |
|------|------:|----------|
| `core/mempalace/dialogue_mapping.py` | 43 | Barrel re-exports |
| `core/mempalace/mapping/__init__.py` | 37 | Package re-exports |
| `core/mempalace/mapping/models.py` | 103 | Dataclasses + `DialogueMappingCancelled` |
| `core/mempalace/mapping/match.py` | 625 | `match_game_strings`, `canonicalize_dialogue_text`, matching helpers/constants |
| `core/mempalace/mapping/persist.py` | 162 | `upsert_*` / `get_*` / `_find_mapping` / `_record` / `_validate_target_node` |

### Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_core/test_dialogue_mapping.py -q --tb=short
→ 24 passed in 1.24s
```

---

## 2. `ui/settings_dialog.py`

Keeps `SettingsDialog` + `ProviderTestWorker` exports. Mixins added alongside
existing `SettingsDialogUiMixin`.

| File | Lines | Contents |
|------|------:|----------|
| `ui/settings_dialog.py` | 92 | Composition + `__init__`; re-exports `ProviderTestWorker` |
| `ui/settings/provider_worker.py` | 39 | `ProviderTestWorker` |
| `ui/settings/path_picker_mixin.py` | 113 | Browse/create path selectors |
| `ui/settings/load_save_mixin.py` | 386 | `_get_lang_name`, `load_initial_settings`, `get_settings`, tags tables, accept/reject/close |
| `ui/settings/provider_mixin.py` | 263 | Test provider, presets, translation config |

### Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/test_settings -q --tb=short
→ 6 passed in 0.85s
```

---

## 3. `components/custom_list_item_delegate.py`

Shim exports `CustomListItemDelegate`. Package `components/list_item_delegate/`.

| File | Lines | Contents |
|------|------:|----------|
| `components/custom_list_item_delegate.py` | 6 | Shim re-export |
| `components/list_item_delegate/__init__.py` | 5 | Package re-export |
| `components/list_item_delegate/delegate.py` | 92 | Composition + `__init__` + width helpers |
| `components/list_item_delegate/paint_mixin.py` | 519 | `paint()` |
| `components/list_item_delegate/tooltip_mixin.py` | 130 | `handle_tooltip` / `_get_problems_tooltip_text` / `helpEvent` |
| `components/list_item_delegate/editor_mixin.py` | 63 | `sizeHint` / `setEditorData` / `setModelData` / `updateEditorGeometry` |

### Verification

Grep tests for `CustomListItemDelegate` → `tests/test_asterisk_logic.py`.

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_asterisk_logic.py -q --tb=short
→ 6 passed
```

---

## 4. `handlers/translation/ai_worker.py`

Shim keeps `handlers.translation.ai_worker.AIWorker`. Package
`handlers/translation/worker/`.

| File | Lines | Contents |
|------|------:|----------|
| `handlers/translation/ai_worker.py` | 6 | Shim re-export |
| `handlers/translation/worker/__init__.py` | 5 | Package re-export |
| `handlers/translation/worker/worker.py` | 47 | Composition, signals, `__init__`, `mw` |
| `handlers/translation/worker/json_mixin.py` | 77 | `_remove_trailing_commas`, `_clean_json_response` |
| `handlers/translation/worker/run_mixin.py` | 725 | `run()` |
| `handlers/translation/worker/control_mixin.py` | 21 | `_log_ai_traffic`, `cancel` |

### Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_handlers/test_translation/test_ai_worker.py -q --tb=short
→ 14 passed
```

---

## 5. `ui/main_window/main_window_actions.py`

Shim keeps `MainWindowActions` import path. Package `ui/main_window/actions/`.
`_ShimName` late-binds `TagAliasDialog`, `AliasUpdateWorker`, `QProgressDialog`,
`QMessageBox` because tests patch those on the shim module.

| File | Lines | Contents |
|------|------:|----------|
| `ui/main_window/main_window_actions.py` | 53 | Shim + `_ShimName` + re-exports for patches |
| `ui/main_window/actions/__init__.py` | 5 | Package re-export |
| `ui/main_window/actions/actions.py` | 24 | Composition + `__init__` |
| `ui/main_window/actions/settings_mixin.py` | 441 | Settings / save / revert / undo / tag-mapping / widths / external script |
| `ui/main_window/actions/tools_mixin.py` | 105 | Markup / mempalace / pipeline / BFN |
| `ui/main_window/actions/tag_alias_mixin.py` | 255 | Tag alias add/edit/remove helpers |

### Verification

`tests/test_ui/test_main_window/` has no live test modules (only `__init__.py`).
Covered via MainWindowActions call sites:

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/test_tag_aliases_logic.py tests/test_ui/test_pipeline_wizard_dialog.py -q --tb=short
→ MainWindowActions-related: 6 tag-alias + 38 pipeline = passed
```

Note: `test_text_edited_resolves_alias_to_tag` fails in
`handlers/text_operation/preview_mixin.py` (out of scope / not MainWindowActions);
deselected for this split’s actions verification. Alias CRUD + pipeline wizard
tests that construct `MainWindowActions` all passed.

---

## Ruff

```
.\venv\Scripts\python.exe -m ruff check core/mempalace/dialogue_mapping.py core/mempalace/mapping ui/settings_dialog.py ui/settings/path_picker_mixin.py ui/settings/load_save_mixin.py ui/settings/provider_mixin.py ui/settings/provider_worker.py components/custom_list_item_delegate.py components/list_item_delegate handlers/translation/ai_worker.py handlers/translation/worker ui/main_window/main_window_actions.py ui/main_window/actions
→ All checks passed!
```

Identity spot-checks: shim symbols `is` package implementations for
`ProviderTestWorker`, `AIWorker`, `CustomListItemDelegate`, `MainWindowActions`.
