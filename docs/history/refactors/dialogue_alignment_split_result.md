# dialogue_alignment split result

MOVE-ONLY split of `core/mempalace/dialogue_alignment.py` (~941 lines) into
`core/mempalace/alignment/`. `core/mempalace/dialogue_alignment.py` remains an
identity-preserving barrel so existing
`from core.mempalace.dialogue_alignment import ...` imports keep working.

## Files / line counts

| File | Lines | Contents |
|------|------:|----------|
| `core/mempalace/dialogue_alignment.py` | 43 | Barrel re-exports + `__main__` |
| `core/mempalace/alignment/__init__.py` | 33 | Package re-exports |
| `core/mempalace/alignment/models.py` | 35 | `MarkedDialogue`, `GameMessage`, `Proposal` |
| `core/mempalace/alignment/normalize.py` | 131 | `normalize_tokens`, `is_stage_direction`, `classify_alignment_exclusions`, `infer_tag_equivalents` + tag/direction/exclusion constants |
| `core/mempalace/alignment/simulate.py` | 509 | `simulate` + `_features` / `_proposal` / `_resolve_*` / `_ratio` helpers + `_BRIDGE_WORDS` |
| `core/mempalace/alignment/persist.py` | 290 | `load_dialogues`, `load_messages`, `save_relations`, `lock_relation_choice`, `main` |

## Barrel re-exports (grep coverage)

Every name imported via `from core.mempalace.dialogue_alignment import ...` is
re-exported, including:

- Models: `MarkedDialogue`, `GameMessage`, `Proposal`
- Normalize: `normalize_tokens`, `is_stage_direction`, `classify_alignment_exclusions`,
  `infer_tag_equivalents`
- Simulate: `simulate`
- Persist/CLI: `load_dialogues`, `load_messages`, `save_relations`,
  `lock_relation_choice`, `main`

No `_ShimName` late-binds required (no `patch("core.mempalace.dialogue_alignment.*")`
call sites that mixins depend on).

## Verification

```
$env:PYTHONPATH = "."
.\venv\Scripts\python.exe -m pytest -p no:xdist --timeout=120 tests/test_core/test_dialogue_mapping.py tests/test_core/test_mempalace_flow_validation.py -q --tb=short
→ 25 passed in 1.27s

.\venv\Scripts\python.exe -m ruff check core/mempalace/dialogue_alignment.py core/mempalace/alignment
→ All checks passed!
```

Identity spot-check: barrel symbols `is` the alignment package implementations.
