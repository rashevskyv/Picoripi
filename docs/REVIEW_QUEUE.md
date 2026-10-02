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
      run (the answer is not stored). A family larger than 30 entries is asked in separate batches. A family
      is checked only within itself: `Zora Guard` (guards family) is not compared with `Zora`.
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
- [ ] **The consistency gate allows the 18 known duplicate groups (3.7).** The plan wanted zero canonical
      collisions in `translation_prompts/glossary.json`; that needs the merge you have not approved yet (see
      the 3.1 item above). The test fails if the number grows, and checks on a copy that the merge leaves no
      collision and loses no translation. After you merge, lower `KNOWN_CANONICAL_GROUPS` to 0.
- [ ] **55 families in the real glossary may render a shared word differently (3.7).** The gate prints them as a
      warning (`pytest tests/test_core/test_glossary_consistency.py`); a reconcile run would send 55 requests,
      about 49k input tokens in total (`docs/audit/2026-10-01/wp3_glossary_numbers.json`). Look at the list:
      groups built around a generic word ("power", "bar", "bag") are noise and may need a stop-list.
- [ ] **How terms are grouped into families (3.3, reworked at the WP3 exit).** Each entry joins the family of the
      rarest word it shares with another entry (161 families on the real glossary, the largest has 12
      members). So `Zora Guard #1` sits with the other guards, not with the Zora terms. To still give it the
      settled `Zora`, translation runs in three tiers — one-word terms, then two-word, then longer — and
      every request lists the related entries decided so far. Check on a real build that compound names
      follow their head term.

## WP5 — plugin platform

- [ ] **The contract is a table, not a `typing.Protocol` (5.1).** The plan named `GameRulesProtocol(Protocol)`;
      `plugins/spec.py` has `HOOKS` (name, summary, on the base class or looked for, dummy call, return type)
      instead — one source for the validator and for the generated contract page (5.8). Two tests keep it
      honest: every public method of `BaseGameRules` is listed, and every attribute host code reads on a
      rules object is listed. Say if you want a real Protocol for type checkers as well.
- [ ] **Session keys removed from the six shipped `config.json` files (5.1).** `original_file_path`,
      `last_selected_*`, scroll positions, `search_history`, `string_metadata` — all were at their default
      values, and the application writes them to `project_settings.json`, not to the plugin. Check that each
      plugin still opens with its usual defaults.
- [ ] **`pokemon_fr/config.json` carries test junk in `context_menu_tags`** (`{boba}`, `<biba>`, an emoji tag).
      Left as is; delete it if it is not yours.
- [ ] **Run `python -m plugins.validate`** and read the warnings: today every plugin gets one about prompt
      sections that are not merged from the common defaults (5.3 removes the cause).
- [ ] **The "empty" plugin files were not empty: their module names decided behaviour (5.2).**
      `GenericProblemAnalyzer` picked square or curly tags, and the star-tag mode, by looking for "ww",
      "plain_text" or "bmg" in the module name of its subclass, and the text fixer looked for "pokemon". These
      are now declared (`tag_style`, `star_section_mode`, `escaped_line_breaks`). The old guessing stays as a
      fallback for plugins that declare nothing. Check each game: width warnings, autofix and short-line
      merging must behave as before.
- [ ] **AI translate actions are now in the Tools menu of every game (5.2).** `Ctrl+Alt+T` (string),
      `Ctrl+Alt+L` (selected lines), `Ctrl+Alt+B` (block) and "AI Reset Translation Session" used to be added by
      the Minish Cap plugin only; their labels no longer say "(UA)". Check they do not clash with a shortcut
      you use in Twilight Princess.
- [ ] **Minish Cap and the template plugin now expose `problem_ids` (5.2).** The preview therefore marks an
      "empty odd subline" in them the way it already did for Wind Waker and Twilight Princess. One more
      highlight for a problem that was already reported.
- [ ] **Short problem labels were unified (5.2).** Missing ones now come from a common table ("Tag", "Empty1st",
      "Width", …) instead of falling back to the long name. Nothing in the host calls
      `get_short_problem_name`, so this is not visible today.
- [ ] **Plain text checks pasted tags kind by kind (5.2).** It used a copy of the Wind Waker check (`[Name]`,
      `[Color:…]`, `[/C]`); now `[Color:Red]` vs `[Color:Blue]` is fine, any other difference in the number of
      a tag kind (square or curly) is a warning.
- [ ] **`zelda_bmg/text_fixer.py` and `problem_analyzer.py` were kept (5.2)**, because three of your scripts in
      `scratch/` import `plugins.zelda_bmg.text_fixer`. They are four-line named subclasses now.
- [ ] **The editor-review pass never ran, for any game (5.3).** Its prompt loader imported
      `core.translation.prompt_language`, a module that does not exist; the error was swallowed and the pass
      was skipped. On top of that, every shipped plugin's `prompts.json` hid the `editor_review` section. Both
      are fixed, but the pass is now **off by default** behind `translation_config["editor_review_enabled"]`,
      because it is a second request per chunk. Decide whether you want it: turn it on for one block and
      compare.
- [ ] **Glossary and MemPalace prompts now come from `plugins/common/defaults/prompts.json` (5.3).** For every
      shipped plugin they used to come from constants in the code, because the plugin's `translation`-only
      file replaced the common one as a whole. "Fill glossary entry with AI" and the MemPalace mining and
      profile requests therefore use different wording than before. Check one of each.
- [ ] **An override copy of `prompts.json` no longer freezes the other sections (5.3).** "Edit Prompts JSON"
      copies the plugin file into the project; sections missing from that copy are now filled from the
      common file instead of being absent.
- [ ] **The plugin template stays `plugins/default_plugin`; there is no `plugins/_template/` (5.4).** The
      generator copies the plugin that already exists, is tested and can be selected in the application —
      a second copy would have to be kept in step with it. The shared smoke checks are in
      `plugins/testing.py` rather than under `tests/` so that a generated test file can import them. The
      template's `prompts.json` is not the full common file: since 5.3 the missing sections are merged in.
      Try it: `python tools/new_plugin.py demo "Demo" --prefix DM`, start the application, pick "Demo", then
      delete `plugins/demo` and `tests/test_plugins/test_demo`.
- [ ] **Saving a Twilight Princess project goes through new plumbing (5.5) — check it first.** Before a BMG is
      built the plugin itself now loads the existing file (`prepare_save_context`; translation archive first,
      then the source); the host used to do that and set `last_loaded_bmg` on the plugin. Writing the `.bmg`
      and packing the archive are unchanged, except that the `.bmg` is written to a temporary file and
      renamed. Test on a copy of the project: edit one line, save, reopen, and compare the packed archive
      with one saved by the previous build.
- [ ] **Opening a file needs a plugin that claims its extension (5.5).** `.bmg` used to be readable with any
      plugin active; now only `zelda_bmg` declares it. Other extensions behave as before (`.json`, `.txt`;
      inside a project an unclaimed extension is still read as text).
- [ ] **Files inside an archive are decoded by their extension (5.5).** A `.json` or `.txt` member used to be
      handed to the plugin as raw bytes; it now arrives parsed / as text, like a file on disk. `.bmg`
      members are unchanged (bytes).
- [ ] **Pokémon FireRed key handling moved into the plugin (5.5).** Save, revert and session restore must still
      produce files with the original keys. Check one save and one revert if you still use that plugin.
- [ ] **The plugins folder is found from the program's location, not the current directory (5.6).**
      `plugins_root()` is `<folder of the code>/plugins`. If you start Picoripi from another directory or
      from a packaged build, check that the plugin list, fonts and prompts still load.
- [ ] **A plugin that fails while opening a file shows "could not parse the file" (5.6)** instead of the
      crash dialog; the reason is in the log (`Plugin hook load_data_from_json_obj() failed: …`). Saving is
      not wrapped: a failing save still fails loudly.
- [ ] **Switching plugins reloads all of the plugin's modules (5.6).** For Twilight Princess that is 15+
      modules instead of 6, so caches kept in module variables start empty after a switch. Switch
      zelda_bmg → another plugin → zelda_bmg and check the preview and the speaker data still work.
- [ ] **The game-like preview of Twilight Princess now gets everything through plugin hooks (5.7) — look at
      it.** Open strings of several window kinds (dialogue, item with icon, sign, location plate, subtitles):
      the frame, the icon in the item window, the vertical position of the text and the "Auto / forced
      window" bar under the preview must look as before. Then Settings → the "limits by window type" table:
      change a value, press OK, reopen — the value must be kept.
- [ ] **Hooks differ from the three names in the plan (5.7).** The plan named `get_window_presets`,
      `get_window_layout(kind)`, `get_window_frame(kind)`; the preview actually needed nine things (labels,
      the style of a forced preset, the item icon, the text offset, the Settings table), so there are nine
      hooks. The full list with descriptions is in `plugins/spec.py`.
- [ ] **One plugin guide (5.8) — read it once.** `docs/wiki/3_Plugin_Developer_Guide.md` (and `uk/`) is now the
      only guide; `docs/PLUGIN_AUTHORING_GUIDE.md` and `plugins/DEVELOPER_GUIDE.md` are deleted (their text is
      in git history), `plugins/default_plugin/README.md` is a short pointer. The hook tables were dropped
      from the wiki in favour of the generated `docs/PLUGIN_CONTRACT.md`. Tell me if something you relied on
      in the old guides is missing.
- [ ] **The plain-text plugin is labelled "Plain Text" (5.8).** Its `config.json` said "Zelda: The Wind
      Waker", the same label as the Wind Waker plugin, so the plugin list could show only one of them.

## WP6 — stability

- [ ] **Exit while something runs in the background (WP6).** Start a search, a spellcheck analysis or a
      glossary build and close the application at once: it may take a few seconds to leave the process list
      (every running thread is asked to stop and waited for, 8 s at most) and must not show a crash dialog.
- [ ] **One batch translation of a block, sequential and parallel (6.5).** `AIWorker.run()` was cut into
      methods; the 23 worker tests pass, but run one real block with 1 worker and one with several: progress
      text ("Translating chunk i/n"), the detail line (chapter / file / line), applying of each chunk, Cancel in
      the middle, and an error on one chunk (the others are kept).
- [ ] **Build Glossary (legacy one-shot), a glossary term update over many occurrences, a single-string
      translation and a variation (6.5)** — the other four paths of the same worker.
- [ ] **The block tree (6.5).** `populate_blocks` was cut into steps: project folders and root blocks, the
      Story root (loading placeholder, then chapters), Speakers, Items / Notated / Windows / "None", selection
      and scroll position kept after a rebuild, "show unsaved only".
- [ ] **The log (6.5).** 166 places that used to swallow an exception silently now write a debug line
      `module.function: ignored <exception>`. Look through `app_debug.log` after a normal session: a line that
      repeats constantly is either noise to silence or a real fault that was hidden until now.
- [ ] **The application behaves as before with the test switches gone (6.4).** What the tests used to skip now
      depends on `utils.app_mode.headless` being `False` in the real application — which it is by default.
      One pass over: save (Ctrl+S: progress window, then saved), project open (progress window), search
      (results arrive after a moment, not instantly), spellcheck window, the AI "done" popup, global hotkeys
      (Alt+Shift+…), spell-check underlines appearing while typing.
- [ ] **Dialogs that the mixins open (6.4).** The mixins use the real `QMessageBox`, `Path`, `QTextCursor`
      again instead of a proxy. Anything that compared types (`isinstance(x, Path)`) now works where it could
      raise `TypeError` before; look for behaviour that *changed* in: project open/import/delete block, glossary
      edit and delete confirmations, autofix confirmation, paste block.
- [ ] **Companion Push / Pull / Test Connection from the glossary window and from Settings (6.3).** Each shows a
      progress window with Cancel; the result message appears after it. With a real server: push, then pull —
      the glossary view refreshes as before. With an unreachable server: Cancel returns at once.
- [ ] **Conflicts during a Companion sync (6.3).** Change the same term on the phone and on the desktop, sync,
      resolve in the conflict window: the sync window must go back to its progress bar and finish with the
      counts, not freeze while it pushes.
- [ ] **Exit with Companion auto-sync on and the server off (6.3).** The "Closing Picoripi" window must close by
      itself after about 6 s (or at once on "Skip & Close"); if it shows an error first, "Close Anyway" works.
- [ ] **Companion sync to a server that does not answer, then "Skip" (6.2).** Point the Companion URL at an
      address that swallows packets (e.g. `http://10.255.255.1:8000`), open the glossary, start a sync and press
      "Skip & Work Offline": the window must close at once and the editor stay responsive. Do the same on exit
      ("Skip & Close"): the application may take up to ~6 s to leave the process list, without a crash dialog.
- [ ] **Open a second project while the first is still loading (6.2).** The first load is stopped; the second
      project must show its own blocks, not a mix.
- [ ] **MemPalace builder: every analysis button still reports its result (6.2).** The seven workers emit
      `finished_with_result` now; run one analysis that needs no AI (chapter mapping) and check the status line.
- [ ] **Every save goes through a temporary file now (6.1).** Save a translation, a project with archives, the
      glossary and the settings as usual; the files must be byte-for-byte what they were before (line endings
      included — covered by a test, but look at one `.txt` game file in your diff tool). While a save runs you
      may see a short-lived `name.ext.<random>.tmp` next to the file; it must be gone afterwards. If an
      antivirus or a sync client locks the target, the save is retried three times and then reports an error
      instead of leaving a half-written file.
- [ ] **The session autosave is pickled in memory first (6.1).** For a very large project that is one extra
      copy of the snapshot in RAM during the autosave. Tell me if autosave became noticeably slower.

