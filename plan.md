# Active plan: speaker identity mapping

1. [x] Preserve the existing evidence-based normalizer and per-code vote aggregation.
2. [x] Make Merge Speakers the only write boundary: show game-data names, strong Markup Studio matches, weak/AI suggestions, conflicts, and unmatched codes; save only explicit user choices.
3. [x] On confirmation, persist `speaker_aliases.json` and rename matching provisional glossary entries without treating identity as translation.
4. [x] Resolve confirmed aliases in the shared speaker display path and in both single-string and batch translation prompt paths.
5. [x] Add focused tests for manual unmatched entry, provenance colors, no pre-confirmation write, glossary migration, and prompt propagation.
6. [x] Run the focused suite in the project Windows `.venv` (WSL currently lacks pytest), then update the existing release version/docs and commit only this task's files.
