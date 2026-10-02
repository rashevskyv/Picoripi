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
