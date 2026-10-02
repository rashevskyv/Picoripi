# Review queue — what to check by hand

Changes made while executing `docs/audit/2026-10-01/PLAN.md` that automated tests cannot vouch for. Each item
says what to do and what "good" looks like. Delete an item once it has been checked. Unfinished work lives
in `docs/OPEN_ITEMS.md`, not here.

## WP0 — foundation

- [ ] **Agent entry files.** Read `AGENTS.md` (it replaced the 300-line `GEMINI.md`). Are the 12 rules and the
      language policy what you want agents to follow? Anything from the old `GEMINI.md` you miss is in git
      history (`git show 2b65ffac:GEMINI.md`).
- [ ] **Archive.** `docs/history/` holds the old changelog (by month), walkthrough, plan, task and audit
      files. Confirm nothing you still open daily was moved there.
- [ ] **Holding folder.** `D:\git\dev\Picoripi_local_cleanup_2026-10-01` (562 MB) — look through, then delete.
- [ ] **Linux run** of the test suite (WP0 exit is open until then).

## WP1 — transport and JSON

- [ ] **One real batch translation through Web2API** (a block of 30+ lines, Parallel Requests > 1). Good: it
      completes; the status dialog shows a request summary at the end; `~/.picoripi/ai_traffic.log` has one
      JSON line per request/response with matching `request_id`.
- [ ] **Failure behaviour.** Stop the proxy mid-run. Good: finished chunks stay applied, the error names the
      failed chunks, "Retry" sends only those. With the proxy answering 429, the retry button shows the
      wait the proxy asked for.
- [ ] **Cancel.** Press Cancel while a request is in flight. Good: the dialog closes within about a second
      and the revert prompt appears (not an error box).
- [ ] **`think` on your endpoint.** Requests to a self-hosted endpoint carry `think`; requests to
      `api.openai.com` do not. If you use a hosted OpenAI-compatible service other than OpenAI/Perplexity
      that rejects unknown fields, add `"profile": "openai"` to its provider block.
- [ ] **Timeout floor.** A self-hosted endpoint now waits at least 180 s even if Request Timeout says 60.
      Decide whether that is acceptable for single-string translation and chat.
- [ ] **Legacy AI Build Glossary.** A chunk whose reply is not a term list now stops the build with an error
      (it used to be skipped silently). Check this is not too strict for your model.
- [ ] **Glossary pipeline.** Run a short build. Good: same behaviour as before; with `/healthz` absent the
      worker count is unchanged.

## WP2 — prompts and context

- [ ] **Instruction wording moved into the system prompt (2.1).** Open the prompt editor on a block
      translation and on a single string. Everything under the line
      `--- REQUEST RULES (added by Picoripi …) ---` is the engine's fixed rule block
      (`handlers/translation/prompt_composer/instructions.py`). Check: no rule you relied on is missing, the
      "if present" phrasing reads well, quality of a real translation did not drop. The user message now
      holds only the header and the JSON.
- [ ] **Saving a prompt from the editor** stores only the part above that line. Confirm that is what you
      expect when you tick "save".
- [ ] **Raw size was not reduced in 2.1** (5520 → 5474 tok per chunk): nothing was deleted without your
      review, the rules were only made stable (the cacheable prefix grew from ~2100 to ~3065 tok). Candidates
      to delete because the shipped system prompt already says them: "GLOSSARY IS MANDATORY", the glossary
      "Notes" rule, "TRANSCRIPTION RULES", and — in single mode — "All tags must be preserved". Say which
      may go.
- [ ] **Retry reminder.** A retry now appends "RETRY: … Reason: <the real error>" to the system prompt instead
      of always blaming trailing commas. Watch one retry in `ai_traffic.log`.
- [ ] **Start of a block translation (2.3).** The prompt editor preview now shows the first 12 lines only
      (the run still covers everything), and nothing is composed up front when the editor is off. Good: a
      large block or "translate all" starts sending requests without the old pause, and an edited header or
      system prompt still applies to every chunk.
- [ ] **NarrativeLedger removed (2.4) — your call.** README and wiki said Phase 1 of the pipeline records
      terms, character voices and story developments and Phase 2 reuses them. In the code nothing ever wrote
      to the ledger, so nothing was ever injected. The plan's minimal fill (glossary terms seen in earlier
      chunks, up to 30) would have added ~300 tok to every later request for terms that are not in the chunk,
      so I removed the ledger and corrected README, wiki 2, 8 and 11 instead. If you want the feature for
      real, it needs decisions extracted from the model's output (non-glossary names, chosen ти/ви per pair);
      WP4.1 (in-run translation memory) covers the repeated-string part. Restore point: commit before
      "wp2: 2.4".
- [ ] **Translation sessions removed (2.4).** The session path for translation was unreachable (two copies of
      one flag). Making it work would have turned parallel block translation into sequential requests with
      growing history. AI Chat keeps its own sessions and is untouched. Say if you ever want conversational
      (stateful) block translation.
- [ ] **Smaller batch payload (2.5).** Per item the model now gets `layout: {line_count}` plus only what
      differs; widths and lines-per-window sit once in `layout_defaults`. Unresolved speakers are omitted
      instead of `"Unknown"`. Check on a real block that line breaks, window counts and widths are still
      respected (per-item ~156 → ~89 tok in the harness).
- [ ] **Reference languages in batch requests: one per line by default** (the first loaded), none for one- or
      two-word lines. If you rely on several references (e.g. RU + DE for gender and meaning), set
      `"max_reference_languages"` in the translation settings, or tell me to change the default. Single-string
      translation still shows all of them.
- [ ] **Editor review input** is now `{id, text, translation}` triples plus an output-format line. Check one
      story-first run with review on: the editor still returns a usable polished chunk.
- [ ] **Glossary rows per chunk (2.6).** A chunk's glossary table now holds terms found in that chunk's own
      text plus the entries of its speakers and story participants. The 60-line lookahead and the matching
      against the whole story-context JSON are gone. Check on a long block that no term the lines actually
      use is missing from the table.
- [ ] **Compact character cards in batch requests (2.6).** With MemPalace, each participant is sent as
      name + role + address_and_grammar (and speech_style for the current speaker), 40 words per field at
      most, instead of the full ten-field profile. Single-string translation still gets full profiles. Check
      that tone, gender agreement and ти/ви are still right in a story block.
- [ ] **Native JSON mode (2.7)** is sent only to api.openai.com (`response_format`), native Gemini
      (`responseMimeType`) and Ollama (`format: json`) — not to your Web2API proxy. If the proxy does honour
      `response_format`, say so and it can be enabled for the `web2api` profile too.

## WP3 — glossary consistency

- [ ] **Canonical key folds new variants, never existing entries (3.1).** A build that meets "Rupees" while
      "Rupee" exists now writes into "Rupee" (keeps its translation, fills only gaps) instead of creating a
      second entry. A term you add by hand is still added as written. Check with a short build that no
      plural/article/possessive twin appears.
- [ ] **18 groups in `translation_prompts/glossary.json` share a canonical key; nothing was merged.** The list
      is in `docs/audit/2026-10-01/glossary_canonical_report.md`. The plan wanted an automatic merge when the
      glossary loads; I did not do that, because some pairs are different things (Clawshot / Clawshots). For
      each group say "merge" or "leave" — merging keeps the other spelling as an alias and the other
      translation as a variant. `GlossaryManager.merge_canonical_duplicates(dry_run=False)` merges all groups.
- [ ] **Forced re-translation skips confirmed entries (3.1).** "Re-translate all" no longer overwrites a
      translation you confirmed. If you sometimes want that, the coordinator has `include_confirmed=True`,
      but no UI switch yet.
- [ ] **Build requests carry "already decided" lines (3.3).** Translating `Clawshots` now shows the model
      `Clawshot → Кігтемет`; a sweep chunk is shown the settled entries for the words it contains. Check on a
      real build that (a) a family (`Hylia`, `Lake Hylia`, `Hylian Shield`) comes out with one root, and
      (b) the sweep does not start skipping terms it should still report — the block says "do not list these
      again unless this text shows a new sense".
- [ ] **"Related" is a crude word match (3.3).** Two terms are related when they share a word of 3+ letters,
      compared by its first 5 letters (`Hylia`/`Hylian`, `Twili`/`Twilight`). It can pull in an unrelated
      term with the same opening letters. Look at a few prompts in `ai_traffic.log` and say whether the lists
      are useful or noisy.
- [ ] **The translate pass counts families, not terms (3.3).** Progress and the "failed" number in the build
      dialog are now per family batch (up to 8 terms). One failed call sends its whole batch to the retry pass.
- [ ] **Plurals now match glossary terms everywhere (3.4).** `Rupees`, `foxes`, `fairies` in the source find
      `Rupee`, `Fox`, `Fairy` — in prompts, in the source highlighting, in the occurrence list and in the
      "term not translated" check. Look for false hits: a short entry such as `Link` now also matches `links`.
      Only plural is added; an entry stored as a plural (`Rupees`) does not match `Rupee`.
- [ ] **Entries without a translation no longer reach the prompt or the Story Inspector (3.4).** A seeded or
      described-only term used to appear as a row with an empty translation; its description was the only
      useful part. If you want the description shown for untranslated terms, say so —
      `get_relevant_terms(text, translated_only=False)` already does it.
- [ ] **At most 40 glossary rows per prompt, notes cut at 300 characters (3.4).** Order of preference:
      confirmed or hand-written entries, then machine-translated, then the rest; more mentions first. Check a
      long block: nothing important should be missing from the table.
- [ ] **A term inside a longer term is not listed separately (3.4).** "Go to Lake Hylia" gives the model
      `Lake Hylia` only. This also affects the source-side highlighting of translated terms.
- [ ] **Reconcile pass — run it once on a copy of the real glossary (3.5).** Build dialog → "Reconcile related
      terms afterwards" (with "Translate existing entries only" it runs alone). Read the "Reconciled:" list in
      the report: every merge and every changed translation is there. The previous translation stays as a
      variant, a merged spelling stays as an alias, so each change can be undone in the glossary editor.
- [ ] **Reconcile may change entries that have no status (3.5).** Only `confirmed` entries are untouchable.
      All 612 entries of `translation_prompts/glossary.json` have no status, so the pass is allowed to align
      them (the prompt tells the model to prefer "existing" over "machine" renderings). If hand-written
      entries must be anchors too, say so — it is one condition in `reconcile_driver.plan_changes`.
- [ ] **Which clusters are asked about is a heuristic (3.5).** A cluster is sent when two of its members are one
      term by spelling (plural/article/near-duplicate), or share a word while their translations share no
      three-letter word start. A pair the model decided to keep separate is asked about again on the next
      run (the answer is not stored). A family larger than 30 entries is asked in separate batches.
- [ ] **The reconcile prompt is new and untested on a real model (3.5).** `reconcile` in
      `translation_prompts/glossary_pipeline_prompts.json`. Check that it does not merge different things
      (Clawshot / Clawshots as two items) and does not "fix" grammar forms.
- [ ] **The glossary file gains an `id` line per entry on its next save (3.6).** One-time churn in
      `glossary.json` (612 entries → 612 new lines in the diff). Old files load unchanged; the id of an old
      entry is derived from its term, so the desktop and the Companion server agree on it.
- [ ] **Deleted entries stay in the file as small `deleted_at` records (3.6).** They are what stops a sync from
      restoring the entry. They are never cleaned up. An older Picoripi build opening such a file would
      show them as untranslated terms — do not mix versions on one glossary. Check with the real Companion
      server: delete a term on the desktop, sync, confirm it is gone on the phone and does not return.
- [ ] **Companion server must be updated together with the desktop (3.6).** `companion/server/storage.py`
      now hides deletion records from its lists and keeps them through an edit. An old server would list
      them as terms.
- [ ] **Sync matches entries by id, then by exact term — not by canonical key (3.6).** The plan asked for
      `id`/`canonical`; I left the canonical match out because "Clawshot" and "Clawshots" may be two real
      entries and a sync must not fold them.
- [ ] **A build pass now writes the glossary every 20 results (3.6).** A hard crash (power loss) can lose up
      to 19 results of the running pass; a normal stop, cancel or error still saves everything.

