# Project action handler split result

Move-only split of working-tree `handlers/project_action_handler.py` (was ~1232 lines, including unpublished edits) into `handlers/project_action/`.

## Files

| File | Lines |
|------|------:|
| `handlers/project_action_handler.py` (shim) | 66 |
| `handlers/project_action/__init__.py` | 5 |
| `handlers/project_action/handler.py` | 99 |
| `handlers/project_action/load_worker.py` | 233 |
| `handlers/project_action/lifecycle_mixin.py` | 241 |
| `handlers/project_action/blocks_mixin.py` | 169 |
| `handlers/project_action/session_mixin.py` | 278 |
| `handlers/project_action/recent_mixin.py` | 215 |
| `handlers/project_action/tree_mixin.py` | 46 |

## Spec notes

- Method bodies copied verbatim from the current working-tree monolith (not HEAD).
- Preserved unpublished edit in `close_project_action` (glossary reset on project close) — only method that differed from HEAD.
- Prescribed package layout followed; all 24 methods accounted for (2 worker + 22 handler).

## Shim / patch notes

- Callers still import from `handlers.project_action_handler`.
- Shim re-exports: `ProjectActionHandler`, `ProjectLoadWorker`, `ProjectManager`, `QMessageBox`, `QFileDialog`, `Path`, `load_json_file`.
- Late-bound via `_ShimName` onto mixins that use them as globals:
  - `Path` → `load_worker`, `lifecycle_mixin`, `blocks_mixin`, `recent_mixin`
  - `ProjectManager` → `handler`, `lifecycle_mixin`, `recent_mixin`
  - `load_json_file` → `load_worker`
  - `ProjectLoadWorker` → `session_mixin` (tests patch this name)
  - `QMessageBox` → `lifecycle_mixin`, `blocks_mixin`, `session_mixin`, `recent_mixin` (tests replace the whole class on the shim; class-attribute-only patches would not need this)
- `QFileDialog.getOpenFileName` / `getExistingDirectory` class-attribute patches remain effective on the shared Qt class.

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_handlers/test_project_action_handler.py tests/test_dialogs/test_real_workers_lifecycle.py tests/test_ui/test_preview_font_loading.py -q --tb=short
→ 44 passed in 5.29s

.\venv\Scripts\python.exe -m ruff check handlers/project_action handlers/project_action_handler.py
→ All checks passed
```
