# MemPalace client split result

MOVE-ONLY split of `core/mempalace/client.py` (~1461 lines) into
`core/mempalace/client_mixins/`. `core.mempalace.client.MemePalaceClient` and
`core.mempalace_client` re-export remain identity-preserving.

## Files / line counts

| File | Lines | Contents |
|------|------:|----------|
| `core/mempalace/client.py` | 290 | Composition + `__init__` / connection / preload / cache / `_init_local_db` / `is_server_available` |
| `core/mempalace/client_mixins/__init__.py` | 12 | Package re-exports |
| `core/mempalace/client_mixins/story_api_mixin.py` | 327 | Story timeline / dialogue / character getters through `get_story_timeline_position` |
| `core/mempalace/client_mixins/palace_write_mixin.py` | 206 | `has_room`, `add_wing` / `add_room` / `add_drawer` / `add_relation` |
| `core/mempalace/client_mixins/palace_read_mixin.py` | 317 | `search_context`, visual/relations, clear_*, get_wings/rooms/drawers |
| `core/mempalace/client_mixins/chapter_mixin.py` | 364 | Chapter/script mappings, saves, `get_all_character_lines` |
| `core/mempalace_client.py` | 7 | Unchanged re-export facade |

## Mixin method map

- `StoryApiMixin` — `sync_story_timeline` … `get_story_timeline_position` (story/dialogue/character API)
- `PalaceWriteMixin` — `has_room`, `add_wing`, `add_room`, `add_drawer`, `add_relation`
- `PalaceReadMixin` — `search_context`, `get_room_visual_context`, `get_relations`, `clear_wing`, `clear_all_local_data`, `get_wings`, `get_rooms`, `get_room_drawers`
- `ChapterMixin` — chapter/script mapping getters + `save_chapter_summary` / `save_chapters_to_db` / `save_mappings_to_db` / `get_all_character_lines`

`is_server_available` stays on the composed client (connection/server infrastructure used by write/read mixins).

## Shim / patch notes

- `from core.mempalace.client import MemePalaceClient` and
  `from core.mempalace_client import MemePalaceClient` both resolve to the same class (`is` identity).
- No `_ShimName` late-binds required (no `patch("core.mempalace.client.*")` call sites that need module globals on mixins).

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_core/test_mempalace_client.py -q --tb=short
→ 20 passed in 1.02s

.\venv\Scripts\python.exe -m ruff check core/mempalace/client.py core/mempalace
→ All checks passed!
```

Re-export check: `core.mempalace.client.MemePalaceClient is core.mempalace_client.MemePalaceClient` → `True`.

No full-file backup left under `.grok/`.
