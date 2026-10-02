---
status: current
updated: 2026-10-02
owns: engineering practice
tokens: 1.5k
purpose: Habits behind the rules: threads, performance, persistence, tests
---
# Engineering practice

The hard rules are in `AGENTS.md`; the map of the code is in `docs/ARCHITECTURE.md`. This page is the reasoning
and the habits behind them — read it before a change that touches threads, hot paths, saved files or tests.

## Working method

- Make the smallest change that fully solves the problem: a focused fix plus a regression test beats a rewrite.
- Read the nearby code first and follow its naming, error handling and signal patterns. Reuse an existing
  service or helper before adding an abstraction; add one only when it removes real duplication or isolates a
  risky lifecycle boundary.
- Do not remove old behaviour until the replacement is implemented, tested, documented and reads existing
  projects, sessions and glossaries.
- Verify the narrowest relevant test first, then the whole suite. Report what changed, what was verified and
  what remains risky.

## Ownership

- Handlers do not touch `data`, `edited_data`, block metadata or unsaved flags when `DataStateProcessor` has an
  API for it.
- A function that needs many `mw.*` attributes should take a narrower context (`core/context.py`) instead.
- Updaters coordinate rendering and own no business rules. Filtering, problem aggregation and queries belong in
  query services (`core/filter_query_api.py`). Restoring tree state must tolerate missing items and stale selections.
- Anything a game decides belongs to its plugin; a change to plugin loading, save/load contracts, font maps,
  tags or rule execution updates the default-plugin tests too.

## Threads, timers, object lifetime

- Every worker has one owner. It derives from `WorkerThread`, cancels cooperatively and is stopped with
  `safe_shutdown_thread` (`utils/thread_utils.py`); never `terminate()`.
- No long blocking `wait()` from UI event handling; where shutdown needs one, it is bounded.
- No provider call in a constructor or directly in a UI event handler.
- Deferred work that can outlive a project, dialog or handler uses `single_shot(ms, owner, fn)` or an
  instance-owned timer, cancelled on project close, dialog close and handler teardown.
- A deleted Qt wrapper is a production risk, not a test artefact: check parents and ownership when a widget,
  dialog, highlighter or worker can outlive its creator; do not keep long-lived references to widgets that
  can be destroyed independently.

## Performance

Hot paths: preview rendering and filtering, block-tree updates, text width calculation, syntax highlighting,
glossary matching, spellchecking, AI prompt context lookup, archive parsing and compression, session
save/restore, MemPalace mapping and queries.

- No full-project scan inside a paint or update loop; prefer indexed lookups for repeated filter, search and
  glossary operations.
- Cache only when invalidation is clear. A cache key includes whatever can change the result: plugin, file
  path, settings, prompt version, model/provider, source data.
- Batch UI updates; load large previews and trees lazily; time-slice background pre-caching so typing never lags.
- An optimisation that protects a latency budget gets a deterministic test in the `performance` lane: local,
  no network, with the dataset size and the reason for the threshold written down.

## AI and network

- Calls are asynchronous and cancellable; a provider error becomes a visible error state, never a silent
  failure or a crashed worker.
- Prompt construction is deterministic and testable; fixed instructions stay byte-stable so provider caches hit.
- Tests use fake providers. Nothing in the suite talks to a real model or a real network.

## Persistence

- Durable state is explicit, validated and human-readable where practical; versioned, and old data still loads.
- Writes are atomic (`utils/atomic_io.py`); temporary files are cleaned up on failure.
- No unsafe format is loaded from an untrusted path. No disk write from a fallback or test path unless the
  target is explicit and temporary.

## Tests

What to test, by kind of code:

| Code | Test |
|---|---|
| pure logic | small unit tests next to the owning subsystem |
| handler | state transitions, side effects, error paths, updater calls |
| updater | data selection and coordination, not pixel-perfect assertions |
| worker | at least one real lifecycle test: start, signal, cancel or finish, cleanup |
| persistence | round trip, corrupt input, old-version input, failed write or replace |
| plugin | load/save round trip, tags, width, problem detection, auto-fix |
| AI feature | prompt construction and response handling with a fake provider |

- A bug fix answers four questions: what failed, which test would have caught it, does that test fail without
  the fix, does it cover the risky edge and not only the happy path.
- Explicit fakes model the real contract. `MagicMock` only where observing a call is the point. Never patch
  `Mock`, builtins or Qt classes globally; special fallback behaviour lives in the fixture or fake.
- `qtbot.waitSignal` / `waitUntil` with an observable predicate instead of sleeps. Real workers and timers are
  cleaned up in `finally`; no `QThread` is left running at test exit; no mutable Qt object is shared across
  `pytest-xdist` workers.
- Lanes, markers and known risks: `docs/TESTING_STRATEGY_AND_AUDIT.md`.

## Documentation

- A change to a user workflow, a plugin contract, AI behaviour, test policy or the release process is not done
  until the owning document says so (`docs/INDEX.md` names the owner).
- Document current behaviour; mark future work as future. Concrete commands and paths; no version numbers
  outside `utils/constants.py` and `CHANGELOG.md`.
- No release tag while tests fail unless the user asks for a known-broken tag.
