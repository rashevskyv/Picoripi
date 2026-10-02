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
