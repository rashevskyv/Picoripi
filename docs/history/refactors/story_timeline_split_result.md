# story_timeline split result

MOVE-ONLY split of `core/mempalace/story_timeline.py` (~1183 lines) into
`core/mempalace/timeline/`. `core/mempalace/story_timeline.py` remains an
identity-preserving barrel so existing
`from core.mempalace.story_timeline import ...` imports keep working.

## Files / line counts

| File | Lines | Contents |
|------|------:|----------|
| `core/mempalace/story_timeline.py` | 95 | Barrel re-exports |
| `core/mempalace/timeline/__init__.py` | 89 | Package re-exports |
| `core/mempalace/timeline/models.py` | 150 | Exceptions + dataclasses |
| `core/mempalace/timeline/projection.py` | 80 | `story_virtual_projection_to_dict` / `from_dict` |
| `core/mempalace/timeline/normalize.py` | 200 | `normalize_*`, `story_stable_id_for_mark`, mark helpers |
| `core/mempalace/timeline/sync.py` | 271 | `sync_hierarchy_project` + conflict record/get/resolve |
| `core/mempalace/timeline/queries.py` | 492 | All `get_story_*` / `get_reference_*` + `_story_timeline` / `_record` |

## Barrel re-exports (grep coverage)

Every name imported via `from core.mempalace.story_timeline import ...` is
re-exported, including:

- Models: `StoryTimelineConflictError`, `StoryNodeRecord`, `StorySyncConflictRecord`,
  `StoryTimelinePosition`, `StoryTimelineSyncResult`, `StoryVirtualProjection`,
  `StoryVirtualFolder`, `StoryVirtualMapping`, `StoryVirtualSpeaker`,
  `StoryStringContext`, `ReferenceItemRecord` (+ unused-by-callers public
  `StoryNode` / `ReferenceItem`)
- Normalize: `normalize_hierarchy_project`, `normalize_reference_items`,
  `story_stable_id_for_mark`
- Projection: `story_virtual_projection_to_dict`,
  `story_virtual_projection_from_dict`
- Sync: `sync_hierarchy_project`, `record_story_sync_conflict`,
  `get_story_sync_conflicts`, `resolve_story_sync_conflict`
- Queries: `get_story_node`, `get_story_document_id`, `get_reference_items`,
  `get_story_timeline`, `get_story_virtual_projection`,
  `get_story_speakers_for_game_string`, `get_story_navigation_target`,
  `get_story_string_contexts`, `get_story_mappings_for_node`,
  `get_reference_item_context`, `get_story_document_source_path`,
  `get_story_ancestors`, `get_story_descendants`, `get_story_neighbors`,
  `get_story_timeline_position`

No `_ShimName` late-binds required (no `patch("core.mempalace.story_timeline.*")`
call sites).

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_core/test_story_timeline.py tests/test_core/test_hierarchy_project.py tests/test_handlers/test_speaker_folders.py -q --tb=short
→ 38 passed in 1.56s

.\venv\Scripts\python.exe -m ruff check core/mempalace/story_timeline.py core/mempalace/timeline
→ All checks passed!
```

Identity spot-check: barrel symbols `is` the timeline package implementations.
