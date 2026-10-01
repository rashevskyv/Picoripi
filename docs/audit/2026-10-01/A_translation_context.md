# Audit A — AI Translation Context Pipeline (Picoripi)

Scope: how context is assembled into prompts for single/batch translation; token waste; missing context; consistency; fragility; prioritized fixes. Measured with a harness (`/home/claude/audit/scratch/measure_prompts.py`, PyQt6 offscreen, real `AIPromptComposer` + real `GlossaryManager`, 12 glossary entries, 40-string block, no MemPalace DB, fake plugin flow/addressee/reference data). Token estimates: ~4 chars/tok Latin, ~2.5 chars/tok Cyrillic.

## 0. Key structural facts (affect everything below)

1. **Sessions are dead for translation.** `AILifecycleManager._prepare_provider` sets `self._provider_supports_sessions` on *itself* (`handlers/translation/ai_lifecycle_manager.py:99`), but the facade reads its own never-updated attribute (`facade/handler.py:43`, `facade/session_mixin.py:92`). So `_should_use_session()` is always False, `session_state` is always None, `TranslationSessionState.compress_history` (`core/translation/session_manager.py:66`) is unreachable from translation, and chunked runs always take the **parallel** path (`worker/run_mixin.py:384`, `workers` default 6 from `core/translation/config.py:26`). Tests set the flag by hand (`tests/test_handlers/test_translation_handler.py:125`) so this is untested in production wiring.
2. **NarrativeLedger is never written.** `record_term/record_speaker_voice/record_story_event` have zero call sites outside the class (only instantiated at `batch_translator.py:301-306`). `format_for_prompt()` always returns `""`, so `established_narrative_context` never appears, yet the instruction "NARRATIVE CANON: … established_narrative_context" is always sent (`batch_mixin.py:480`). The wiki (`docs/wiki/11_AI_Translation.md:81-84`) describes behaviour that does not exist.
3. **"Consilium"** = optional second call per chunk, `_maybe_run_editor_review` (`run_mixin.py:352-381`), enabled only for story-first / remaining / all-chronological runs (`translate_mixin.py:487,569,769`), not for block/chapter/selection. It re-sends the chunk's source items + draft; failure silently keeps the draft.

## 1. Prompt trace

### 1a. Single string (`translate_single`) — `messages_mixin.compose_messages` (`:106-432`), launched from `facade/apply_mixin.py:69-139`

| # | Section | Produced at | Size (harness) |
|---|---|---|---|
| S1 | `translation.system_prompt` with `[IF_TARGET_LANG]` resolved (`utils/text_misc.py:34`) | `messages_mixin.py:188` | 7452→7818 ch, **~2060 tok** |
| S2 | "CONTEXT PRIORITY … OUTPUT SHAPE IS IMMUTABLE" | `:190-197` | 370 ch, ~90 tok |
| U1 | Header: Game / Block / Row / Speaker / Mode / Window Type / Content Role / Role Instruction / Story Structure / Reference Item / Translator Note | `:200-235` | ~100 ch |
| U2 | `MEMORY PALACE CONTEXT` JSON (indent=2) from `build_story_context_bundle` (`core/translation/story_context_bundle.py:8`) | `:236-240` | 0 w/o DB; realistically 1–4 KB (full character profiles for every participant) |
| U3 | `SOURCE LAYOUT TARGET` JSON (8 keys) | `:241-250` | 190 ch, ~50 tok |
| U4 | `Story Context:` (`_fetch_story_context`, `story_mixin.py:23`) | `:252-256` | 0–1 KB |
| U5 | `REFERENCE TRANSLATIONS` (all loaded ref languages) | `:258-281` | ~40 ch/lang |
| U6 | `Dialogue Flow`: plugin `get_ai_flow_context_for_string` + `get_ai_flow_overview(block,[idx])` | `:286-304` | plugin-dependent, ~100–600 ch |
| U7 | `Surrounding Dialogue Context`: ±3 rows, originals + current translations | `:306-335` | ~500 ch, ~130 tok |
| U8 | Instructions (9 base + 2–4 conditional) | `:368-397` | **2311 ch, ~580 tok** |
| U9 | `GLOSSARY` markdown table: terms matched in source (+ story bundle JSON) + speaker entries | `:168-177, 400` | 150 ch per entry-ish |
| U10 | `TAG ALIAS LEGEND` (only aliases present) | `:179-186, 402` | small |
| U11 | `Input text (Original source):` + text | `:423-424` | source |

Harness total: **~3010 tok** for a 12-token source line (≈250× overhead); static share (S1+S2+U8) ≈ 2730 tok = 90%.

### 1b. Batch / chunked (`translate_block_chunked`, `translate_preview`) — `batch_mixin.compose_batch_request` (`:16-581`)

Per chunk of ≤12 items (`run_mixin.py:266-270`), rebuilt from scratch per chunk inside the worker (`run_mixin.py:283-304`), and additionally **twice over the whole item set** at initiation (`batch_translator.py:343` prompt preview, `:400` only to obtain `placeholder_map`).

| # | Section | Produced at | Size (chunk 12/40) |
|---|---|---|---|
| S1 | system prompt + `system_prompt_addition` ("IMPORTANT: All text chunks… OUTPUT SHAPE IS IMMUTABLE") | `batch_mixin.py:547-559` | 7985 ch, **~2100 tok** |
| U1 | Header Game / Mode / Block | `:561-567` | 48 ch |
| U2 | `INSTRUCTIONS:` 13 base (or 13 retry) + DIALOGUE FLOW + role_instructions + ADDRESSEE + TAG ALIAS + ANCHORED TAGS + REFERENCE | `:467-544` | **4006 ch, ~1000 tok** |
| U3 | `JSON DATA TO PROCESS` (indent=2): | `:448-464, 572` | 9363 ch, ~2400 tok |
|  | `strings_to_translate[]` — per item: id, text, speaker, `layout`{8 keys}, reference_translations, window_type/content_role/role_instruction (plugin dict spread), story_structure, reference_item, translator_note, story_context_ref, scene_context, addressee, flow_context | `:105-188` | **~156 tok/item**, of which layout ≈ 70 tok |
|  | `story_context_catalog` (deduped bundles) | `:152-161, 451` | 0 w/o DB; 1–4 KB per distinct event |
|  | `scene_context` (MemPalace room + visual + relations + ±3 surrounding rows, or fallback surrounding rows) | `:190-381` | 269 ch |
|  | `dialogue_flow` (`get_ai_flow_overview` per real block) | `:417-440` | plugin |
|  | `glossary` markdown table — matched against **60 items of lookahead** + story catalog JSON + speaker names | `:383-415` | 600 ch for 10 entries (~20 tok/entry) |
|  | `tag_alias_legend` | `:443-446` | small |
|  | `established_narrative_context` | `:461-464` | always absent (§0.2) |

Harness: **~5520 tok/chunk**; 4 chunks for 40 short strings = **20.6k input tok for 372 tok of source**. Static share (S1+U2) ≈ 3100 tok = 56% per request; with realistic 20-tok lines it is ~45%. Editor review (when on) adds a second request of ≈ 1163-ch system + chunk items + draft ≈ 2–3k tok.

Prompt ordering is static→semi-static→dynamic in both modes, which is cache-friendly *only if* U2 is byte-identical between chunks — it is not (conditional lines depend on chunk contents, `retry_reason`, role instructions), and it sits in the *user* message after a dynamic header (`Mode:`, `Block:`), so provider prefix caches cover only S1.

## 2. Waste

- **W1 Instructions duplicated per chunk** (~1000 tok, `batch_mixin.py:467-544`) and single (~580 tok): pure boilerplate resent on every request; several lines restate system-prompt rules (tags, glossary mandatory, transcription with the same examples as the system prompt's rule 12).
- **W2 Cohesion sentence sent twice**: already the last paragraph of `prompts.json` system prompt, re-appended at `batch_mixin.py:548`. "CONTEXT PRIORITY" paragraph (`messages_mixin.py:190`) duplicates batch addition text.
- **W3 Instructions referencing absent fields**: `story_context_ref/story_context_catalog` (`:477`), `established_narrative_context` (`:480`), single-mode `MEMORY PALACE CONTEXT` (`messages_mixin.py:375`) are emitted even when the field is absent — ~150 tok of noise and a known cause of models hallucinating "context".
- **W4 Per-item `layout` object** repeats `lines_per_window`, `warning_line_width_px`, `max_line_width_px`, `ends_with_newline:false`, `blank_line_indices:[]` for every item (~70 tok × 12 = 840 tok/chunk). `visible_line_count` duplicates `line_count` whenever there is no trailing newline.
- **W5 `"speaker": "Unknown"`** emitted for every unresolved item (`batch_mixin.py:97-98`); should be omitted.
- **W6 Glossary lookahead of 60 items** (`:399`) injects terms for 5 chunks ahead; with scene-grouped chunk order (`run_mixin.py:252-270`) the "lookahead" is taken from `all_source_items` *original* order, so it is neither the chunk nor what follows it. Story-catalog JSON is also matched (`:406-409`), pulling in every name in every participant profile.
- **W7 Full-set composition at initiation**: `batch_translator.py:400` composes the prompt for *all* items (N × speaker resolution + MemPalace + plugin calls, ~O(N) sqlite queries) only to get `placeholder_map`; `:343` does it again for the preview dialog. For a 2 000-line project this is thousands of lookups producing a user prompt that is then discarded (and `final_user_prompt` is actually the *system* string — tuple order `(system, user, map)` misread).
- **W8 Reference translations for every loaded language per item** (`:114-133`), with no cap; for 3 reference languages this is ~40 tok/item.
- **W9 `_replace_runtime_names_for_ai` applied twice** to item text (`:61` and over the whole user string `:575`, which can also rewrite glossary/scene text and JSON keys).
- **W10 Editor review resends `chunk_items`** including layout/reference/flow blobs (`run_mixin.py:362-366`) — ~2× the chunk payload for a polish pass.
- **W11 Retry boilerplate doubled**: composer `is_retry` instruction block (`batch_mixin.py:485-501`) *and* system-prompt "IMPORTANT REMINDER FOR RETRY" (`run_mixin.py:394-403, 500-509, 728-737`) — the latter always claims a JSON parsing error even when the failure was a layout mismatch.

## 3. Gaps (context that would help and is missing)

- **G1 No translation memory by source text.** `SavedTranslationsManager` keys by position (`core/saved_translations_manager.py:30-43`); identical/near-identical sources elsewhere are retranslated from scratch and may diverge. `current_session_translations` (`batch_translator.py:481`) is collected but never fed back into later chunk prompts.
- **G2 Neighbours' fresh translations invisible in batch.** Surrounding context uses `data_processor.get_current_string_text` for ±3 rows outside the chunk (`batch_mixin.py:291-314`). With 6 parallel workers those rows are usually not yet translated; nothing shows already-accepted translations of exact-duplicate strings inside the same run.
- **G3 Ledger empty (§0.2)**: no accumulated term decisions / speaker voices / recent events across chunks or phases.
- **G4 Glossary matching is exact-form**: `_build_regex` (`core/glossary/pattern_mixin.py:62-84`) matches `goat` but not `goats`/`Link's`; plural/possessive sources miss their entry (seen in the harness: "goats" → no `goat` entry).
- **G5 No glossary usage examples / translation variants in the prompt**: `GlossaryEntry.translation_variants` and `fragments` exist (`core/glossary/models.py:63-64`) but `glossary_entries_to_text` (`core/translation/glossary_formatter.py:9-21`) emits only Original/Translation/Notes.
- **G6 No per-speaker voice notes outside MemPalace**: speaker glossary entries are appended (`glossary_formatter.py:23-57`) only when the speaker name is itself a glossary term; `address_and_grammar`/`speech_style` live only in MemPalace profiles and are dumped whole (not a compact "voice card").
- **G7 Recurring UI strings (Yes/No/OK/Back) have no fixed-output table**; they are re-sent and re-translated per occurrence.
- **G8 Chunk boundaries ignore dialogue flow**: fixed 12-item split (`run_mixin.py:266-270`) can separate a choice prompt from its "Yes/No" answers or a question from its reply, even though `get_ai_flow_overview` already knows conversation membership.
- **G9 Single-string prompt gets no `addressee`** (batch has it, `batch_mixin.py:168-176`; single does not).
- **G10 Surrounding context for synthetic blocks (999997/8/9) is never built** — `0 <= real_block_idx < len(ds.data)` fails (`batch_mixin.py:286,348`), so project-wide/story-first runs get no neighbour rows at all.

## 4. Consistency

Within a run: none beyond what fits in one 12-item chunk. Chunks run in parallel (§0.1) with independent prompts; no shared state; ledger empty; editor review sees one chunk. Same source string in chunks 3 and 9 → independent translations. Across runs: positional saved-translation cache only (`_filter_already_saved_translations`, `batch_translator.py:120-265`) restores the *same row*; a different row with identical text is retranslated. The only cross-row signal is the ±3 neighbour window and the glossary. Fails for: duplicated UI strings, repeated NPC barks, item names in different blocks, and anything beyond the 60-item glossary lookahead.

## 5. Bugs / fragility

- **B1 Wrong neighbour rows for temp-id runs**: `translate_specific_strings` and `translate_preview` assign ids 0..n (`translate_mixin.py:60-63`) with `block_idx=first_block_idx`; `batch_mixin.py:282-284` then treats `min/max(item_ids)` as *string indices of that block*, so "Dialogue BEFORE/AFTER" shows rows 0..3 of the first block regardless of selection (only `block_idx == -2` resolves through `temp_id_map`, `:267-280`).
- **B2 Ledger never populated** (§0.2) — docs/tests describe a feature that is a no-op.
- **B3 Session flag split** (§0.1) — latent: if fixed naïvely, `batch_translator.py:400` would feed the *system* text as the session user message and `final_system_prompt` is the raw unresolved prompt (no `[IF_TARGET_LANG]` resolution, no batch addition) → `TranslationSessionState.current_system_prompt` would lose both.
- **B4 Parallel path error handling**: first failing future emits `error` and `return`s inside `with ThreadPoolExecutor` (`run_mixin.py:431-436`), which blocks until the other 5 in-flight HTTP calls finish (up to 180 s each); their results are discarded and recomposed on retry. Cancellation (`:419-420`) has the same wait.
- **B5 Thread-safety**: `_build_chunk_request` runs the full composer from pool threads — `GlossaryManager`, `StoryContextManager` caches (`_wing_name_cache`, `_script_lines_cache`), `resolve_speaker_for_string`, plugin lazy caches (`zelda_bmg/rules.py:657-661`) are mutated without locks; MemPalace uses thread-local sqlite (ok). `self._last_messages` is not set in the parallel path, so the outer `except` logs the wrong messages.
- **B6 JSON parsing**: `_clean_json_response` (`worker/json_mixin.py:43-77`) takes the first `{`…last `}`; a translation containing `}` after the object's end or a model that emits two JSON objects breaks it; no JSON-mode/`response_format` is requested from providers that support it. Retry reminder (B11 above) misdiagnoses the cause.
- **B7 Id mapping by position first** (`batch_translator.py:429-440`): if the model drops one item and appends another, `len` check passes only when counts match, but *reordering* is silently mapped by position, ignoring returned ids.
- **B8 Legacy `"Ukrainian"→target_lang` replace** (`text_misc.py:68`) rewrites any literal "Ukrainian" in the system prompt (incl. examples) for non-Ukrainian targets.
- **B9 `_prepare_glossary_for_prompt` is a stub** returning the input (`glossary_mixin.py:25-31`); vestigial.
- **B10 `translate_specific_strings`** ignores `_filter_already_saved_translations` dialog cancel when `force_prompt` (returns items) but then `is_chunked` path never shows the prompt editor for Ctrl-click because `should_edit_prompt` keys off `force_prompt`/`is_resume` — minor UX inconsistency.

## 6. Proposals

### P0

**P0-1 Move static instructions into the system prompt; make the user message dynamic-only.**
Files: `batch_mixin.py:467-559`, `messages_mixin.py:188-197,368-397`, `translation_prompts/prompts.json`.
Design: build one `batch_instructions` string with *all* conditional lines always present (phrased "if present"), append it to `final_system_prompt` after `system_prompt_addition`; user message = `Game/Mode/Block` + JSON only. Same for single mode (`instructions` → system). Delete the duplicated cohesion/CONTEXT PRIORITY paragraphs (W2) and the absent-field references (W3) unless the field is present.
Gain: ~1000 tok/chunk and ~600 tok/single become a byte-identical prefix → cacheable (Anthropic/OpenAI/Gemini prefix caching); ~15–20% raw reduction even without caching. Risk: low (text only). Test: `compose_batch_request` for two different chunks yields identical system prompts; user prompt contains no "INSTRUCTIONS:" block; snapshot test on instruction text.

**P0-2 Fix neighbour-row resolution for temp-id runs (B1) and synthetic blocks (G10).**
Files: `batch_mixin.py:254-381` → extract one helper `_surrounding_rows(real_pairs: list[(b,s)], K=3)` that groups by real block via `temp_id_map`, takes min/max per block, and returns before/after rows; call it from both branches (remove the duplicated 60-line block).
Gain: correct context; -60 LOC. Risk: low. Test: items with ids 0..2 mapped to (5, 40..42) → context rows 37–39 and 43–45 of block 5; ids spanning two blocks → two groups.

**P0-3 Populate NarrativeLedger from accepted chunk results, or drop it.**
Files: `batch_translator.py:handle_chunk_translated` (after `:481`), `narrative_ledger.py`, `batch_mixin.py:461`.
Design (minimal): after each chunk is applied, for every glossary entry matched in that chunk's sources call `ledger.record_term(entry.original, entry.translation, entry.section)`; record `speaker → addressee form` pairs when `addressee` was present; keep `max 30` terms LRU. Persist via `to_dict()` in project metadata next to `translation_progress`. Because chunks run in parallel, treat the ledger as "what finished so far" (read under a lock).
Gain: cross-chunk/cross-phase consistency the docs already promise. Risk: medium (needs lock; parallel order non-deterministic). Test: two sequential chunks → second prompt contains `established_narrative_context` with the first chunk's terms.

**P0-4 Stop composing the full prompt at initiation (W7).**
Files: `batch_translator.py:340-402`. Compute `placeholder_map` with a cheap `prepare_text_for_ai` loop over items (same as `batch_mixin.py:58-63`), compose the preview only for `chunks[0]` (or first 12 items). Fix tuple order at `:400`.
Gain: O(N)→O(12) MemPalace/speaker lookups before the first request (seconds→ms on 2k-line projects). Risk: low. Test: mock composer, assert `compose_batch_request` called with ≤12 items at initiation.

### P1

**P1-1 Hoist shared layout defaults; omit `Unknown` speaker (W4, W5).**
Files: `batch_mixin.py:105-112`, `story_mixin.py:_layout_contract_for_string`, instructions text. Emit `layout_defaults: {lines_per_window, warning_line_width_px, max_line_width_px}` once at payload top; per item keep only `line_count` and non-default keys (`blank_line_indices` if non-empty, `ends_with_newline` if true, `window_count` if >1, width overrides if different). Drop `"speaker"` when Unknown.
Gain: ~60–70 tok/item ≈ 800 tok/chunk (≈15%). Risk: low; validator (`layout_contract.validate_translation_layout`) is independent of the prompt. Test: payload item for a plain 2-line string has exactly `{id,text,layout:{line_count:2}}`.

**P1-2 In-run translation memory + duplicate folding.**
Files: new `core/translation/run_memory.py` (dict `normalized_source → translation`, lock), `batch_translator.py:handle_chunk_translated` (write), `run_mixin.py` chunk builder (pre-pass: exact-duplicate sources within the run get one representative item; others resolved from memory after the chunk returns), `batch_mixin.py` (add `already_translated_in_this_run: [{text, translation}]` for sources whose normalized text equals an item's, cap 10).
Gain: identical UI strings/barks cost one request and are guaranteed identical; typical game data has 10–30% exact duplicates. Risk: medium (must respect `layout` and tag differences — normalize on tag-stripped text, compare raw text for folding). Test: block with "Yes" ×5 → one item sent, five rows filled identically.

**P1-3 Source-text-keyed saved translations (cross-run TM).**
Files: `core/saved_translations_manager.py` (add secondary index `sha1(normalized source) → text`), `batch_translator.py:_filter_already_saved_translations` (offer TM hits as "restore" candidates with the same layout check), `messages_mixin.py` (add `TRANSLATION MEMORY (same source elsewhere)` section when hit).
Gain: consistency across runs/blocks; fewer requests. Risk: low (opt-in via existing CachedTranslationDialog). Test: save (0,3) "Yes"→"Так"; translating (7,10) "Yes" is restored without AI.

**P1-4 Flow-aware chunking.** Files: `run_mixin.py:252-270`. When `rules.get_ai_flow_overview` exists, group items by the conversation id the plugin reports (expose `get_ai_flow_group_for_string(b,s) -> Optional[str]` in `base_game_rules.py`), then pack whole groups up to 12 (split a group only if it exceeds 12). Gain: Q/A and choice/answers stay together (G8). Risk: low. Test: 3 conversations of 5 lines → chunks [5+5],[5], never a split group.

**P1-5 Glossary relevance = chunk only + speaker entries; inflection-tolerant matching.** Files: `batch_mixin.py:389-409` (lookahead → chunk text only, keep speaker/story names), `pattern_mixin.py:_build_regex` (allow `(?:s|es|'s)?` suffix for Latin terms). Gain: ~50% fewer glossary rows per chunk on long blocks, fewer missed plurals. Risk: low–medium (false positives on short terms; keep `(?<!\w)`). Test: "goats" matches `goat`; "boats" does not match `oat`.

**P1-6 Parallel-path robustness (B4, B5).** Files: `run_mixin.py:383-439`. On first error/cancel: set `is_cancelled`, call `provider.cancel_active_stream` if any, `pool.shutdown(wait=False, cancel_futures=True)`; still emit already-complete results. Build chunk prompts on the worker thread *before* submitting (`_build_chunk_request` is CPU-cheap once P0-4 lands), so pool threads only do HTTP + validation. Test: fake provider where chunk 2 raises; assert chunks 1,3 results still emitted and `error` emitted once.

### P2

- **P2-1 Request native JSON output** (`response_format: json_object` / Gemini `responseMimeType`) in `providers.py:150-170,579-595`; keep `_clean_json_response` as fallback; make the retry reminder quote the actual `last_error` (drop the "trailing commas" guess). Test: provider body contains `response_format` when `settings_override['json']`.
- **P2-2 Compact voice cards instead of full profiles**: in `story_context_bundle.py:36-50` emit only `role, speech_style, address_and_grammar` (≤ 40 words each) for `is_current_speaker` participants; full profile only for the first chunk of a scene. Gain: 1–3 KB/chunk with MemPalace. Test: bundle size cap.
- **P2-3 Fixed-output table for recurring UI strings**: glossary section `UI` with `fixed_output: true` → items whose whole text equals the term are filled from the glossary without AI (`_filter_already_saved_translations` pre-pass). Test: "OK" → fixed.
- **P2-4 Editor review: send only `{id, text, translation}` triples** (`run_mixin.py:362-366`); drop layout/reference/flow blobs. Test: editor user payload has no `layout` key.
- **P2-5 Reference-translation cap**: configurable max languages per item (default 1) and skip when text ≤ 2 words. Test: 3 ref langs, cap 1 → one key.
- **P2-6 Remove dead code**: `_prepare_glossary_for_prompt` stub, session attach for translation (or fix the flag split properly in one place: make the facade attribute a property proxying `ai_lifecycle_manager`), duplicated surrounding-context block. Test: existing suite.

## 7. Expected effect (batch, chunk of 12 realistic 20-tok lines)

Today ≈ 5.5–7k tok/request (56% static). After P0-1 + P1-1 + P1-5 + P2-5: ≈ 3.4–4k tok raw, of which ≈ 3.1k is a stable cacheable prefix → effective billed input ≈ 1–1.5k tok/chunk on cache-capable providers (≈ 3–5× cheaper), plus fewer requests from P1-2/P1-3 duplicate folding. Quality: correct neighbour rows (P0-2), live canon (P0-3), in-run/cross-run TM (P1-2/3), flow-safe chunks (P1-4).
