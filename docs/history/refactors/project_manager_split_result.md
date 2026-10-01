# ProjectManager split result

MOVE-ONLY split of working-tree `core/project_manager.py` (~944 lines, including unpublished user edits) into `core/project/`.
`core/project_manager.py` remains an identity-preserving barrel so existing
`from core.project_manager import X` imports keep working.

`core/project_models.py` was left untouched.

## Files / line counts

| File | Lines | Contents |
|------|------:|----------|
| `core/project_manager.py` | 55 | Barrel re-exports + `_ShimName` late-binds |
| `core/project/__init__.py` | 6 | Package re-export of `ProjectManager` |
| `core/project/manager.py` | 93 | `ProjectManager` composition, constants, `__init__`, `current_project` |
| `core/project/persist_mixin.py` | 261 | create/load/save, settings to/from project, bookmark migrate |
| `core/project/blocks_mixin.py` | 329 | add_block, sync, import_directory, paths, archive cache, uncategorized lines |
| `core/project/folders_mixin.py` | 299 | virtual folders, migrate, move block/folder, find, merge, categories |

## Method map

- **manager.py**: `__init__`, `current_project`, `PROJECT_*` constants
- **persist_mixin.py**: `create_new_project`, `load`, `save`, `save_settings_to_project`, `load_settings_from_project`, `_maybe_migrate_legacy_bookmarks`
- **blocks_mixin.py**: `add_block`, `sync_project_files`, `import_directory`, `get_uncategorized_lines`, `get_absolute_path`, `cleanup_temp_dir`, `get_archive_container`, `clear_archive_cache`, `get_relative_path`
- **folders_mixin.py**: `_migrate_file_structure_to_virtual_folders`, `create_virtual_folder`, `move_strings_to_category`, `merge_folders`, `find_virtual_folder`, `is_descendant_of`, `move_folder_to_folder`, `move_block_to_folder`, `_remove_block_id_from_any_folder`, `get_all_block_indices_under_folder`, `_remove_folder_from_anywhere`

## Shim / import notes

- Callers still import from `core.project_manager` (12 sites grepped; left unchanged).
- Barrel re-exports: `ProjectManager`, `Category`, `Block`, `Project`, `VirtualFolder`, plus `Path` / `ContainerManager` for patch targets.
- Late-bound via `_ShimName` onto mixins:
  - `Path` → `persist_mixin`, `blocks_mixin`, `folders_mixin`
  - `ContainerManager` → `blocks_mixin`
- Package path `core/project/` did not collide; `core/project_mgr/` unused.

## Verification

```
$env:PYTHONPATH="."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_core/test_project_manager.py tests/test_handlers/test_project_action_handler.py -q --tb=short
# -> 45 passed

.\venv\Scripts\python.exe -m ruff check core/project_manager.py core/project
# -> All checks passed!
```
