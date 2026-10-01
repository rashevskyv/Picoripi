# Audit B — Glossary subsystem (build, store, match, inject)

Scope: `core/glossary_build/*`, `core/glossary/*`, `handlers/translation/glossary_*`, `translation_prompts/glossary*.json`, companion sync. All paths relative to `/home/claude/pico`. Script used for the data analysis: `/home/claude/audit/scratch/glossary_consistency.py`.

**Verdict on the user's complaint:** correct, and structural. Every AI request in both builders is *stateless per unit* (per chunk, per term). No stage ever sees what another unit decided; there is no canonicalization beyond case/whitespace, no term-family notion, no reconciliation pass, and the storage layer itself has key-matching bugs that silently create or lose variant entries.

---

## 1. Pipeline trace

There are **two** independent builders that write into the same store.

### 1a. Legacy "Build Glossary from Text" (`GlossaryBuilderHandler`)
- `handlers/translation/glossary_builder_handler.py:62` `build_glossary_for_block` → `AIWorker` task `build_glossary` (`handlers/translation/worker/run_mixin.py:82-222`).
- Chunking: all target strings joined, tags masked, then **raw character slicing** `masked_text[i:i+chunk_size]` (`run_mixin.py:152`) when no string metadata — strings are cut mid-sentence. Default 8000 chars, clamp 1000..32000 (`run_mixin.py:96`). With metadata, records are packed whole (`:132-150`).
- Per chunk one call: system = `glossary_builder_prompts.json:system_prompt`, user = chunk text only. The model returns `term/translation/notes/section` **in one shot — translation decided inside the chunk with zero knowledge of other chunks or the existing glossary**.
- Sequential, `settings_override={"think":1}`, no retry; first `JSONDecodeError` aborts the whole run (`run_mixin.py:201-206`) — all previous chunks' output is discarded (nothing was written yet).
- Merge (`glossary_builder_handler.py:200-250`): list concatenation; dedup only *within the run* by `normalize_term` (first chunk wins, `seen_in_batch`); then `manager.add_entry(term, translation, ...)` which **overwrites** an existing entry's translation (`mutation_mixin.py:56-60`) — including user-confirmed ones, and drops nothing but `status` is carried… except `add_entry` matches by **exact** `original` while the handler's "existing" check used `normalize_term` → a case-variant creates a *second* entry (verified: `['Hylian Shield', 'Hylian shield']`).

### 1b. New pipeline (`GlossaryBuildCoordinator`, `core/glossary_build/pipeline_coordinator.py`)
Modes `:46-58`; the user-facing `auto` mode (`:236-251`) runs:

| Stage | Code | AI request content | Unit | Output merge |
|---|---|---|---|---|
| structural seed | `:319-369` | none | – | `seed_entry`/`update_entry`, gap-fill only |
| sweep (1a) | `:388-404`, `text_sweep.py:66`, `ai_adapters.py:99` | system `extract`, user = one chunk (whole strings packed to 2000/4000/8000 chars by preset `text_sweep.py:21`) | chunk | `merge_raw_terms` by `normalize_term` into `AggregatedTerm` (`sweep_driver.py:67`), section by vote, ≤30 fragments |
| seed_all | `:406-425` | none | term | `_write_seed` |
| describe (2/2b) | `:443-477`, `describe_driver.py:51` | system `describe`, user = term + stack of context windows (≤40 occurrences, 8000-char stack, 4000-char window `context_window.py:22-25`); overflow → per-batch fragments folded 5→1 by `fold` | term | `update_entry(notes=…, status=synthesized)` |
| suggest names | `:480-510` | term + its description | provisional term | `suggest_name` |
| translate (3) | `:270-315`, `translate_driver.py:46`, `ai_adapters.py:238` | system `translate` (orthography rules), user = **`Term: X` + `Description:`** — nothing else | term | ≤3 variants deduped by `normalize_term`, first = active, `status=translated` |

**What "already decided" entries reach later requests: nothing.** The `extract` user prompt is only the chunk (`glossary_pipeline_prompts.json:13`); `describe` is only the term + excerpts; `translate` is only the term + description. No existing glossary, no sibling terms, no few-shot of prior decisions. The code comments admit this: "the sweep is not told what is already seeded" (`pipeline_coordinator.py:227`).

**Parallelism/ordering.** Every pass goes through `run_with_retry_pass` → `run_pool` (`parallel.py:99-185`), 6 workers (`DEFAULT_WORKERS`), rolling window. `on_result` is invoked **in completion order** (`wait(..., FIRST_COMPLETED)` `:155-166`), contradicting the docstring "in the order the items were given" (`:111`). Consequences:
- `AggregatedTerm.term` = "first spelling seen" (`sweep_driver.py:41`) → the stored `original` casing ("Hylian Shield" vs "Hylian shield") is **nondeterministic across runs**; section ties in `Counter.most_common` likewise.
- `aggregated` dict order → `_seed_all` order → entry order in `glossary.json` → noisy diffs, and `get_entry` returns the *first* normalize-equal entry, so which duplicate "wins" matching is order-dependent.
- Translate pass is per-entry parallel, so even a future "decisions so far" context would race unless ordered by family.

Chunk sizes: sweep 2000/4000/8000 chars (`text_sweep.py:21`), legacy 8000; describe stack 8000; translate 1 term/request (600-entry glossary = 600 calls + describe calls + sweep calls ≈ 1300+ requests).

---

## 2. Consistency failure modes

Canonicalization available: only `GlossaryManager.normalize_term` (`core/glossary/manager.py:51-59`): NFKD strip accents, lowercase, `#`→space, collapse whitespace. No plural, no article, no possessive, no punctuation, no lemma. No family/parent link, no alias list, no reconciliation step. The only "duplicate" tooling is `possible_duplicate_pairs` (`core/glossary/notes.py:91`), a display-only fuzzy heuristic (section-restricted, ≥0.88 ratio) counted in the post-run report (`glossary_pipeline_handler.py:678`) and highlighted in the table; it merges nothing.

Where two near-identical source terms diverge:

1. **Sweep emits variant spellings** ("Hylian Shields" vs "Hylian Shield") — distinct `normalize_term` keys → two `AggregatedTerm`s → two seeds → two independent describe calls → two independent translate calls. No stage compares them.
2. **Legacy builder**: same term in two chunks → two translations; first wins in-run, but across runs `add_entry` overwrites with the newer run's guess (`mutation_mixin.py:56`). Case variants become separate rows (verified).
3. **Coordinator `_write_seed`/`_seed_structural`** (`pipeline_coordinator.py:359,434`): `get_entry` finds the entry by normalized key, but `update_entry(term, …)` matches **exact** `original` (`mutation_mixin.py:92`) → returns `None` silently when casing differs (verified: `update_entry('lake hylia') -> None`). Sweep fragments/sections for a case-variant are **dropped**, not merged.
4. **Translate pass per term with no siblings**: "Hylia", "Lake Hylia", "Great Bridge of Hylia", "Hylian" are translated by four unrelated calls; only the hard-coded orthography hint in the system prompt (`glossary_pipeline_prompts.json:22`) keeps "Гайлія" aligned. Any family not in that hint (Ooccoo, Reekfish, Clawshot, Sacred Grove…) is free to diverge.
5. **Re-sweep regression**: `_seed_all` skips only `translation and not is_unconfirmed` (`:415`), so an entry that is `translated` but not confirmed is reset to `status=seeded`, fragments replaced (`:434-441`), re-described (new `notes` overwrite the old), while its translation is kept — notes and translation can now disagree with each other.
6. **Matching side**: "Rupees" does not hit entry "Rupee" (verified `[]`), so plural-only entries get created by the sweep because the describe/occurrence index never links them; and "Lake Hylia" injects **both** "Lake Hylia" and "Hylia" (verified) with no longest-match precedence — the translator sees two possibly conflicting rows.

### Empirical analysis of `translation_prompts/glossary.json` (612 entries, legacy schema: no `status`, no `{{TERM}}` in notes, 0 multi-variant)
- Exact / `normalize_term` duplicates: **0** (the only guard that exists works).
- **Canonical collisions** (case + plural + article + punctuation): **18 groups / 36 entries** (5.9% of the glossary). Examples: `Rupee/Rupees`, `Goron/Gorons`, `Zora/Zoras`, `Poe/Poes`, `Fused Shadow(s)`, `Gate Key/gate keys`, `Piece(s) of Heart`, `Tear(s) of Light`, `Item Screen/Items screen`, `The Postman/POSTMAN`, `Clawshot/Clawshots`, `Monkeys(Terms)/MONKEY(Characters)` — the last also crosses sections, so `possible_duplicate_pairs` never flags it.
- Of those, **translations genuinely diverge** in: `Clawshot→Кігтемет` vs `Clawshots→Подвійні гаки`; `The Postman→Листоноша` vs `POSTMAN→Поштар`; plus capitalisation drift (`Сльоза Світла` vs `сльози світла`, `Ордонський ліс` vs `Фаронський Ліс`).
- **Shared-token families** (same ≥4-char English token, generic words excluded): **149**; **19** have no shared Ukrainian stem across members, i.e. the token was rendered differently: `Ooccoo→Уку` vs `Ooccoo Jr.→Окку-молодший`; `reekfish→гнилка` vs `Reekfish Scent→Запах Рікфіша`; `Sacred Grove→Священна гаща` vs `…Sacred Grove→…Священної Гаї`; `Hylia`: `Великий міст Гайлії` vs `озеро Гайлія` (OK) — but note "Hylia" itself has no entry.
- Same stemmed translation → different originals: **18** (`basement/cellar→підвал`, `LOUISE/LOUIS→Луїз`, `attack power/attack strength`, `Mirror of Twilight/Twilight Mirror`).
- `possible_duplicate_pairs` heuristic: **93** pairs, mostly `GORON #1/#2…` noise (the `#`→space normalization makes numbered speakers look like duplicates of each other but not of `Goron`).
- Term-inside-longer-term pairs (both injected on a hit): **348** (e.g. `Rupee ⊂ 7 colour Rupees`, `Chu Jelly ⊂ 7 colours`, `oil ⊂ lantern oil`).
- Notes average **647 chars (max 17 233)** — relevant to injection cost (§4).

---

## 3. Storage / schema

`GlossaryEntry` (`core/glossary/models.py:49-86`, frozen dataclass): `original` (the **only key**), `translation` (semicolon-separated variants are tolerated by `build_translation_regex` but the builder never writes them), `notes` (with `{{TERM}}` placeholder, `TERM_PLACEHOLDER` `:26`), `section`, `profiled`, `status` ∈ {"", seeded, fragments, synthesized, translated, confirmed} (`:10-14`), `icon`, `fragments[]` (text+coords), `translation_variants[]` (translation+rationale), `provisional`, `suggested_name(+evidence)`, `user_notes`, `updated_at`. Serialized by `_entry_to_dict` (`notes.py:154`), omitting defaults.

Missing: **no stable ID**, no `family`/`parent`/`canonical` link, no `aliases`, no decision log (only `updated_at`), no `source` provenance (which builder/run produced the translation), no `confirmed_by/at`. `GlossaryOccurrence` (`models.py:107`) is derived, not stored (occurrence index rebuilt from Aho-Corasick + speaker ownership `occurrence_mixin.py:69-170`).

Store semantics: `_entries` is a list; every mutation does `self._persist()` = full JSON rewrite + **pattern-cache rebuild** (`parse_mixin.py:231-262`). Markdown round-trip drops seed-only rows (`parse_mixin.py:243` comment).

**Companion sync** (`core/companion_sync.py:96-180`, `companion/server/storage.py:174`): merge keyed on exact `original`. Consequences: a local `rename_original` (`mutation_mixin.py:170`) or delete is **resurrected** on the next pull as a "term added remotely" (`:139-142`, no tombstones — grep confirms none); a case-variant duplicate on one side becomes two rows on both; `entries_differ` compares `translation_variants` lists so a re-ordered variant list is a "conflict". Field `fragments` is excluded from diff, so fragment-only changes never sync.

---

## 4. Matching & injection during translation

- Selection: `get_relevant_terms(text)` (`occurrence_mixin.py:365`) → `find_matches` (`:22-62`): phase 1 pyahocorasick on `text.lower()` with alnum word-boundary check; phase 2 regex per entry (`pattern_mixin.py:67-92`, case-insensitive, tolerates tags/whitespace between words). **No inflection/plural on the source side** (English "Rupees" ≠ "Rupee"); the Slavic stem regex (`pattern_mixin.py:95-139`) is only for finding *translations* in target text.
- Text matched: single-string path = source + selected text + story context JSON (`messages_mixin.py:168-174`); batch path = **60-item lookahead** of source items + story catalog (`batch_mixin.py:383-413`), plus speaker-name entries appended (`glossary_formatter.py:23`).
- **No cap, no ranking, no dedup of contained terms, no filtering of unconfirmed/empty-translation entries**: a seeded entry with `translation=""` is injected as `| Term |  | notes |`. Format = markdown table `Original | Translation | Notes` with `{{TERM}}` rendered (`glossary_formatter.py:9-21`); no usage note / register field beyond `notes`.
- Prompt instruction: "GLOSSARY IS MANDATORY … only inflect endings" (`batch_mixin.py:475`, `messages_mixin.py:373`). With two rows for `Hylia` and `Lake Hylia`, or `Clawshot` vs `Clawshots`, "mandatory" is self-contradictory.
- Cost: avg row ≈ 678 chars ≈ 250–350 tokens (Cyrillic). A 60-string lookahead in a name-dense block matches 30–60 entries → **8–20k tokens of glossary per batch request**, repeated for every batch. The 17 kB note alone is ~6k tokens.

---

## 5. Bugs / fragility

| # | Where | Issue |
|---|---|---|
| B1 | `mutation_mixin.py:56,92,236` vs `manager.py:66` | `add_entry`/`update_entry`/`seed_entry`/`delete_entry` match **exact** `original`; `get_entry` matches normalized. Creates case-variant duplicates (legacy builder) and silently no-ops updates (coordinator `_write_seed`, `_seed_structural` → `update_entry` returns `None`, unchecked). |
| B2 | `mutation_mixin.py:364-371` | `global_replace` rebuilds `GlossaryEntry` with 5 fields → **drops `status`, variants, fragments, provisional, user_notes** (verified: confirmed → ''). |
| B3 | `pipeline_coordinator.py:286-308` | `run_translate(force=True)` targets **confirmed** entries and rewrites translation + `status=translated` → lost confirmations (only a `.bak` protects). |
| B4 | `parallel.py:111` vs `:155` | Docstring promises item order; code delivers completion order → nondeterministic `original` casing, section, file order. |
| B5 | `parse_mixin.py:231-262` + `pattern_mixin.py:32-57` | Worker thread calls `_persist()` per entry → `_compiled_patterns.clear()` and `self._automaton = Automaton()` *before* `make_automaton()`; UI thread (`utils/syntax/cache_mixin.py`, highlighter) and `find_matches` read these concurrently → transient misses or `iter()` on an unbuilt automaton. Also O(n) full-file rewrites per entry → O(n²) I/O for a 600-entry run. |
| B6 | `run_mixin.py:152,201` | Legacy builder slices text mid-string and aborts the whole run on the first unparsable chunk, discarding all prior chunks. |
| B7 | `ai_adapters.py:55-78` | `parse_json_array` silently returns `[]` on malformed JSON → unit counts as *success* with zero terms (sweep) or no variants (translate: `tr.active` empty → entry skipped, `translated` not incremented, no failure recorded). Truncated replies are invisible. |
| B8 | `pipeline_coordinator.py:415-441` | Re-run resets unconfirmed-translated entries to `seeded`, replaces fragments, re-describes (cost + notes/translation drift). |
| B9 | `companion_sync.py:139` | No tombstones → deleted/renamed entries resurrected on pull. |
| B10 | `glossary_formatter.py` / `occurrence_mixin.py:365` | Injection unbounded; untranslated and contained-term rows injected; `notes` up to 17 kB. |
| B11 | `sweep_driver.py:23` | `DEFAULT_MAX_FRAGMENTS=30` dedups by exact text only; `AggregatedTerm.mentions` is never persisted (frequency lost for ranking). |

---

## 6. Proposals

### P0-a — Canonical key + manager key-consistency (prereq for everything)
**Files:** `core/glossary/manager.py`, `core/glossary/mutation_mixin.py`, `core/glossary/models.py`, `core/glossary/notes.py`.
**Design:** add `GlossaryManager.canonical_key(term)` = `normalize_term` + strip punctuation/possessive + drop leading articles + English plural fold (`-ies→y`, `-es` after s/x/z, `-s` not `-ss`), with an exception list (e.g. "Zoras" when a dedicated plural entry is wanted). Make **all** mutators resolve the target row via one private `_index_of(original)` that tries exact, then `normalize_term`, then `canonical_key`; `add_entry` on a canonical hit must `update` (preserving status unless the caller passes `status`), never append. Add `GlossaryEntry.canonical: str` and `aliases: Tuple[str,...]` (serialized only when set; loader back-fills `canonical`). `possible_duplicate_pairs` should first group by `canonical_key` (exact groups, cross-section) and only then run the fuzzy pass.
**Gain:** removes B1; folds the 18 collision groups in the sample; ensures every later stage sees one row per concept. **Risk:** over-folding ("Poe"/"Poes" if both intentional) — mitigated by `aliases` + a one-time migration report listing merges before applying. **Tests:** `tests/test_core/test_glossary_entry_lifecycle.py`: add_entry on case variant updates not appends; update_entry via normalized key succeeds; `canonical_key("Hylian Shields")=="hylian shield"`, `("The Postman")=="postman"`, `("Fairy's Tears")=="fairy tear"`.

### P0-b — "Decisions so far" context in builder requests
**Files:** `core/glossary_build/ai_adapters.py` (`make_extract`, `make_propose`), `pipeline_coordinator.py` (`_sweep`, `run_translate`), `translation_prompts/glossary_pipeline_prompts.json`, `glossary_builder_prompts.json`, `run_mixin.py` legacy path.
**Design:** new pure helper `core/glossary_build/decisions.py::select_related(entries, text, limit=40) -> str` that tokenizes `text` (chunk text, or `term + description`), scores each decided entry (has translation, status ∈ {confirmed, translated}) by shared canonical tokens (confirmed first, then token overlap, then shorter term first), and renders a compact block `term → translation` (≤ ~1.5k tokens, no notes). Add a `{decided}` placeholder to the `extract` and `translate` user templates with instruction: "These are settled renderings; reuse the same root for related terms; return `term` exactly as the source spells it; do not re-propose terms already listed unless the chunk shows a new sense." For the translate pass, build the related list from the *current* manager snapshot taken **before** the pass plus a thread-safe `dict` of translations stored during this pass (append in `store()`; read under a lock) so siblings translated earlier in the same run are seen.
**Gain:** directly answers the complaint; e.g. `Clawshots` would see `Clawshot → Кігтемет`. **Risk:** token cost (+1–2k/request); race in parallel translate (siblings in flight simultaneously) — addressed by P1-d ordering. **Tests:** fake `call` that records the prompt; assert `select_related` ranks `Lake Hylia` above `Rupee` for term `Great Bridge of Hylia`; assert the translate prompt for the second member of a family contains the first member's translation when run sequentially (`workers=1`).

### P1-c — Post-build reconciliation pass (`reconcile`)
**Files:** new `core/glossary_build/reconcile_driver.py`, `ai_adapters.py::make_reconcile`, `pipeline_coordinator.py` (call after `run_translate`; new `MODE_RECONCILE`), prompt `reconcile` in `glossary_pipeline_prompts.json`, UI toggle in `components/glossary/…build dialog`.
**Design:** cluster entries by (1) `canonical_key` equality, (2) shared non-generic token (stop-list of generic nouns), (3) `possible_duplicate_pairs`. For each cluster with ≥2 members and any divergence (different stemmed translation of the shared token, or different casing policy), one request: `[{term, translation, section, status, short note}]` → model returns `{merge:[[a,b,…]], canonical_translation_by_term:{…}, keep_separate:[…], reason}`. Apply: never touch `confirmed` entries (they become the anchor the others must align to); set aligned entries to `status=translated` with the previous translation pushed into `translation_variants` (so the user can revert); for `merge` groups create `aliases` on the surviving row and delete the rest (with occurrences re-pointed through `rename_original`-style merge, which already exists `mutation_mixin.py:170`). Deterministic: clusters sorted by canonical key; one call per cluster; `workers` allowed because clusters are disjoint.
**Gain:** fixes families even when P0-b missed them (parallel races, legacy data like the sample's 19 divergent families). **Risk:** wrong merges — mitigated by anchoring on confirmed entries and recording old values in variants; UI report lists every change. **Tests:** fixture of 6 entries (`Clawshot/Clawshots/Postman…`) + fake call returning a canned reconcile JSON → assert merged aliases, variants, untouched confirmed entry, idempotence on second run.

### P1-d — Deterministic ordering
**Files:** `core/glossary_build/parallel.py`, `sweep_driver.py`, `pipeline_coordinator.py`.
**Design:** in `run_pool`, buffer results and release `on_result` in item order (keep a `next_to_emit` cursor; results arriving early wait in a dict) — the docstring already promises this. Sort `aggregated` by `(section, canonical_key)` before `_seed_all`; pick `AggregatedTerm.term` display form by majority spelling (Counter) rather than first-seen; order translate targets by family (canonical first token) so P0-b sees the head term first, and optionally run families on one worker (group items into family-batches as the pool unit).
**Gain:** reproducible glossaries, stable diffs, removes order-dependent casing. **Risk:** slightly lower pool utilisation when one early unit is slow (bounded by window). **Tests:** `tests/test_core/test_glossary_parallel.py`: `work` that sleeps inversely to index → `on_result` order equals input order; sweep of two chunks returning `Hylian shield`/`Hylian Shield` yields the same `original` regardless of completion order.

### P1-e — Injection hygiene
**Files:** `core/glossary/occurrence_mixin.py::get_relevant_terms`, `core/translation/glossary_formatter.py`, `pattern_mixin.py`.
**Design:** (1) drop contained matches when a longer match covers the span (keep `Lake Hylia`, drop `Hylia` unless it also matches elsewhere); (2) skip entries with empty translation; (3) cap rows (e.g. 40) ranked by confirmed > translated > others, then match count, then length; (4) truncate `notes` to ~300 chars in the prompt table, keep full notes for the editor; (5) add plural-tolerant automaton words (`term`, `term+s`, `term+es`) built from `canonical_key`. **Gain:** 2–5× fewer glossary tokens per batch, no contradictory rows. **Tests:** `find_matches("Rupees")` hits `Rupee`; `get_relevant_terms("Go to Lake Hylia")` returns only `Lake Hylia`; seeded entry without translation is excluded.

### P2-f — Storage hardening
- `global_replace`: use `dataclasses.replace` to keep lifecycle fields (B2). Test: confirmed status survives replace.
- `run_translate(force=True)`: exclude `confirmed` unless an explicit `include_confirmed` flag is set; demote to `translated` only entries that were not confirmed (B3).
- `_write_seed`/`_seed_structural`: check `update_entry` return value and log/raise on `None`.
- Batch persistence: add `manager.transaction()` context manager that defers `_persist()` until exit; the coordinator wraps each `store` callback batch (e.g. every 20 results) — removes O(n²) writes and most of the B5 window; rebuild the automaton into a local variable and swap atomically.
- `parse_json_array`: return `None` on parse failure and let the adapter raise so the pool records a failed unit (B7).
- Companion: add `deleted_at` tombstones and sync on `canonical` key; include `aliases` in `entries_differ`.
- Add `GlossaryEntry.id` (uuid, persisted) so renames/merges survive sync.

### P2-g — Test scaffolding to add
`tests/test_core/test_glossary_consistency.py` reusing the scratch script's logic as a regression gate: load any project glossary, assert zero `canonical_key` collisions after P0-a migration, and emit the family-divergence list as a warning (not failure) so the reconcile pass can be benchmarked over time.

---

### Priority order
P0-a (key consistency) → P1-d (deterministic order, small) → P0-b (decisions context) → P1-e (injection) → P1-c (reconcile) → P2.
