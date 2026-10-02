# Picoripi — Task checklist (audit 2026-10-01)

Tick boxes as you go. Details for every id are in `PLAN.md`; evidence in the `A_…F_…` reports.
Rule: a WP is closed only when its exit criteria in `PLAN.md` hold and the suite is green.

## WP0 — Foundation and hygiene
- [x] 0.1 `.gitattributes` + renormalize commit + strip 51 BOMs
- [x] 0.2 pin `PyQt6-Qt6`, `PyQt6-sip`, dev tools; `requires-python`
- [x] 0.3 stop writing into `plugins/` (aliases, materialised prompts); `literal_eval`; delete MagicMock/test_plugin
- [x] 0.4 test hygiene: skipif, delegate paint test, importorskip/asset skips, ruff cwd, tmp_path for settings/logs
- [x] 0.5 xdist flakiness: lambdas → slots, 3‑arg singleShot, `id()` dict
- [x] 0.6 `AGENTS.md` (≤1.5k tok) + `CLAUDE.md` stub + `GEMINI.md` stub; delete duplicate workflows
- [x] 0.7 archive logs to `docs/history/`; short current `plan.md`/`task.md`/`walkthrough.md`; `docs/OPEN_ITEMS.md`; deploy rollover
- [x] 0.8 `.graphifyignore`; single Graphify rule; `graphify .`
- [x] 0.9 local disk cleanup; `git rm --cached dummy.json .grok/skills`
- [ ] WP0 exit: suite green (Win+Linux), ruff clean, version bump, walkthrough

## WP1 — Transport and JSON robustness
- [x] 1.1 `core/translation/transport.py` (ErrorKind, TransportError, classify, TransportPolicy, semaphore, breaker); delete `retry.py`/`concurrency.py`
- [x] 1.2 wire policy into providers; fix Gemini compat path; strip `?key=`; EMPTY error; `think` only for web2api; 7×180 s → `policy.timeout`; modal after exhaustion
- [x] 1.3 `utils/json_extract.py` + replace 3 cleaners; `ParseError` never swallowed
- [x] 1.4 parallel chunk path via `run_pool`; stop on error; map by `id` first
- [x] 1.5 provider `profile` + web2api defaults; unify `max_consecutive_failures`
- [x] 1.6 harden `handle_chunk_translated` + `:568` + glossary builder (`finally` undo group)
- [x] 1.7 `ai_traffic.log` → JSONL with lock/ids/sizes/durations in SETTINGS_DIR; run summary
- [x] 1.8 cancellable non-stream requests
- [x] WP1 exit

## WP2 — Prompt and context cost
- [x] 2.0 port measure harness to `tools/measure_prompts.py`; record BEFORE numbers
- [x] 2.1 all instructions → stable system prompt; remove duplicates/absent-field mentions; real retry reason
- [x] 2.2 `_surrounding_rows` helper; synthetic blocks get neighbours
- [x] 2.3 no full-set composition at initiation; tuple fix
- [x] 2.4 NarrativeLedger populated (or removed); session flag split fixed; wiki 11 updated
- [x] 2.5 payload slimming (layout defaults, Unknown speaker, ref cap, single name replace, slim editor payload)
- [x] 2.6 chunk-only glossary relevance; compact voice cards
- [x] 2.7 native JSON mode where supported
- [x] WP2 exit: AFTER numbers in walkthrough

## WP3 — Glossary consistency
- [x] 3.1 `canonical_key`, `aliases`, `_index_of` for all mutators, `global_replace` keeps lifecycle, `force` excludes confirmed, migration report
- [x] 3.2 deterministic `run_pool` order; sorted seeding; majority spelling; family-ordered translate
- [x] 3.3 `decisions.py::select_related` + `{decided}` in extract/translate prompts + in-pass shared dict; legacy builder too
- [x] 3.4 injection hygiene (longest match, skip empty, cap 40 ranked, notes ≤300 chars, plural-tolerant matching)
- [x] 3.5 reconcile pass (driver, adapter, prompt, mode, UI toggle, report)
- [x] 3.6 storage hardening (transaction, atomic automaton swap, no re-seed reset, entry id, sync tombstones)
- [x] 3.7 regression gate test + wiki 8 (EN+UK)
- [ ] WP3 exit: real build before/after numbers in walkthrough

## WP4 — Translation memory and in-run consistency
- [ ] 4.1 in-run memory + duplicate folding + `already_translated_in_this_run`
- [ ] 4.2 cross-run TM keyed by source text
- [ ] 4.3 flow-aware chunking hook + packing
- [ ] 4.4 fixed-output UI strings; `addressee` in single prompt
- [ ] WP4 exit

## WP5 — Plugin platform
- [x] 5.1 `plugins/spec.py` + `python -m plugins.validate` + `test_validate_all`
- [x] 5.2 collapse boilerplate into base; neutral `common/tag_logic.py`; delete pass-throughs; remove dead hooks
- [x] 5.3 key-level prompt merge
- [x] 5.4 `plugins/_template/` + `tools/new_plugin.py` + shared smoke test
- [x] 5.5 `get_file_formats()` + `core/formats.py` + `ContainerManager.register`; `bmg_tool.py` into zelda_bmg; `prepare_save_context`/`export_runtime_state` hooks; host reads no plugin privates
- [x] 5.6 `safe_call`, prefix-based reload, drop zelda_mc fallback, `plugins_root()`
- [x] 5.7 BFN preview decoupled from zelda_bmg
- [x] 5.8 generated `docs/PLUGIN_CONTRACT.md`; one plugin guide; fix discovery path
- [x] WP5 exit

## WP6 — Stability
- [x] 6.1 `utils/atomic_io.py` + 12 write sites
- [x] 6.2 `safe_shutdown_thread` order; cancellation in 5 workers; no `terminate()`; rename custom `finished`; guard worker overwrite
- [x] 6.3 companion push/pull/close off the GUI thread
- [x] 6.4 remove `'pytest' in sys.modules` branches and `_ShimName` patches; delete conftest heap walk
- [ ] 6.5 split `run()` (746) and `populate_blocks` (542); enable F841; S110 warning; log in every `except: pass`
- [ ] WP6 exit

## WP7 — Documentation system
- [ ] 7.1 `docs/INDEX.md` + front matter
- [ ] 7.2 `docs/ARCHITECTURE.md` with Mermaid diagram
- [ ] 7.3 README ≤3.5k tokens; stale claims fixed
- [ ] 7.4 merges/archives per F §7 table; delete plain_text glossary copy; update-wiki ownership table
- [ ] 7.5 `tasks.py` cross-platform runner; scripts use it
- [ ] 7.6 `tests/test_docs/`; module docstrings + guard test; `docs/DECISIONS.md`
- [ ] WP7 exit

## WP8 — gemini-web2api
- [ ] 8.1 monolith → shim; 429/502 mapping in package; one version; commit missing files
- [ ] 8.2 client disconnect + total deadline
- [ ] 8.3 concurrency gate + `/healthz` + truthful `finish_reason`
- [ ] 8.4 lock down `/api/*`, bind 127.0.0.1, size cap, `temporary_chats` true, `ensure_ascii=False`
- [ ] 8.5 `test_rotation.py` → pytest
- [ ] WP8 exit
