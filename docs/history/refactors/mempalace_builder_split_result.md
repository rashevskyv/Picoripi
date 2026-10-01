# MemPalace builder dialog split result

Move-only split of remaining `ui/mempalace_builder_dialog.py` methods into `ui/mempalace/` mixins (section C).

## Files

| File | Lines |
|------|------:|
| `ui/mempalace_builder_dialog.py` (composition + constants + shims) | 126 |
| `ui/mempalace/mempalace_ui.py` (kept) | 642 |
| `ui/mempalace/mempalace_pipeline.py` (kept) | 169 |
| `ui/mempalace/mempalace_sleep.py` (kept) | 4 |
| `ui/mempalace/hierarchy_mixin.py` | 406 |
| `ui/mempalace/dialogue_mixin.py` | 494 |
| `ui/mempalace/analysis_mixin.py` | 532 |
| `ui/mempalace/session_mixin.py` | 337 |

## Mixin method map

- `MemePalaceHierarchyMixin` — browse script/hierarchy, load/apply markup studio project, hierarchy status, wizard step, story tree, import sync
- `MemePalaceDialogueMixin` — dialogue mapping start/progress/complete, review table, approve/reject, markup studio jump
- `MemePalaceAnalysisMixin` — timeline + character profiling, chapter mapping/analysis queue, worker progress, AI provider warn, char mining/speech
- `MemePalaceSessionMixin` — sleep toggles, finish_and_maybe_sleep, refresh_chapters_list, append_log, clear_database, load/save builder settings, reject/closeEvent, `_handle_close_or_cancel`, `_init_composer_and_client`

`MemePalaceBuilderUiMixin` and `MemePalacePipelineMixin` were left intact.

## Shim / patch notes

- Dialog keeps `__init__`, mixin composition, and `_HIERARCHY_*_KEY` constants.
- Mixin base order places mixins before `QDialog` so `closeEvent` / `reject` on `MemePalaceSessionMixin` override Qt defaults (same pattern as Script Markup Studio).
- Re-exports `QMessageBox`, `QFileDialog`, and `MemePalaceChapterAIAnalyzerWorker` on `ui.mempalace_builder_dialog` for existing test patch paths.
- Late-binds only `MemePalaceChapterAIAnalyzerWorker` onto `analysis_mixin` via `_ShimName`.
- Late-binds `_HIERARCHY_*_KEY` onto `hierarchy_mixin` / `session_mixin` so method bodies keep using those globals verbatim.
- Method AST bodies verified identical to the pre-split dialog (0 mismatches).

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_ui/test_mempalace_builder.py -q --tb=short
→ 33 passed in 11.73s

.\venv\Scripts\python.exe -m ruff check ui/mempalace ui/mempalace_builder_dialog.py
→ All checks passed
```

No full-file backup left under `.grok/`.
