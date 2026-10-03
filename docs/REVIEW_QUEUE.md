---
status: current
updated: 2026-10-03
owns: owner decisions and live checks
tokens: 2.7k
purpose: What is left for the owner after the audit: decisions with evidence, live runs, environment
---
# Review queue — decisions, live runs, environment

The owner does not check behaviour by hand: what a test can prove is proved by `tests/test_review/`
(old code vs new code on the same inputs; golden files from the pre-audit worktree in
`tests/fixtures/review_queue/`). What is left is of three kinds:

- **DECISION** — the owner's call. Each item gives the evidence and a recommendation.
- **LIVE** — needs a real model or the owner's proxy. An agent runs it once access is given.
- **ENV** — needs a machine or setup that is not here.

Automatable checks that are not written yet are agent work and live in `docs/OPEN_ITEMS.md`
("Review-queue test gaps"). Delete an item here once it is settled.

## DECISION

- **The line layout check loses whole chunks on the real model (live run 2026-10-03).** A reply whose item has
  fewer lines than the source («Але в ту мить, коли Дарбус простягнув руку» — 43 characters on one line, the
  source had three) fails the chunk; the retry resends all 12 lines and the model does it again, so after 4
  attempts the chunk is lost (one chunk in 3 of 4 runs of the new build; the old build stopped the whole run).
  Recommendation: keep the item if every line fits the window width and the window's line limit, and re-wrap
  it with the game's wrapper when it does not; retry only the item, not the chunk.
- **Glossary duplicates (WP3 3.1 / 3.7).** 18 groups in `translation_prompts/glossary.json` share a canonical
  key (`docs/audit/2026-10-01/glossary_canonical_report.md`). Recommendation — merge 14: Rupee/Rupees,
  Goron/Gorons, Poe/Poes, Fused Shadow(s), Gate Key(s), Giant Bomb Bag(s) (pick «сумка» or «торба»),
  Item(s) Screen, light spirit(s), Mirror Shard(s), pellet(s), Piece(s) of Heart, Poe Soul(s), tear(s),
  Tear(s) of Light; merge The Postman/POSTMAN (pick «Листоноша» or «Поштар»); keep Clawshot/Clawshots (two
  items); keep MONKEY/Monkeys and Zora/Zoras but fix their notes. A merge keeps the other spelling as an alias
  and the other translation as a variant. Afterwards `KNOWN_CANONICAL_GROUPS` drops to what is left.
- **Editor review (WP2 2.5 / WP5 5.3).** Off by default; the pass is tested (`test_rq_wp2_4_run.py`,
  `test_rq_wp5_prompts_review.py`). It is a second request per chunk (doubles proxy quota) and sees only
  source → draft pairs: no glossary, speakers or scene, so its "check the glossary / the tone" rules cannot be
  followed, and it gets the source raw (escaped `\n`, tags without aliases). Recommendation: remove it; if a fix-up
  pass is wanted, send only the lines that failed a deterministic check, with the reason.
- **NarrativeLedger (WP2 2.4).** Removed; nothing ever wrote to it. Terms are covered by the glossary (WP3/WP4),
  events by scene context and MemPalace. Recommendation: do not revive; if a live run shows ти/ви drifting
  between scenes, add a small editable table "speaker → addressee: ти/ви".
- **Translation sessions for block translation (WP2 2.4).** Removed (unreachable). Recommendation: keep removed
  — a session makes parallel translation sequential with a growing history.
- **Rules that may be deleted from the prompt (WP2 2.1).** Raw size was kept (5520 → 5474 tok per chunk). The
  shipped system prompt already says: "GLOSSARY IS MANDATORY", the glossary "Notes" rule, "TRANSCRIPTION
  RULES", and in single mode "All tags must be preserved". Say which may go.
- **"Related" terms and plural matching are noisy (WP3 3.3 / 3.4 / 3.7).** Related = a shared word compared by
  its first 5 letters: prince/princess, dragon/dragonfly, guard/guardian. Plural matching hits verbs: "Link
  warps" → `warp`, "lights it" → `light`, "bows" → `bow`. 55 families may render a shared word differently,
  many built on generic words ("power", "bar", "bag"). Recommendation: a stop-list of generic words now, a
  better relatedness measure later.
- **Reconcile anchors (WP3 3.5).** Only `confirmed` entries are untouchable; all 612 real entries have no
  status. Should hand-written entries without a status be anchors too? One condition in
  `reconcile_driver.plan_changes`.
- **Descriptions of untranslated terms in the prompt (WP3 3.4).** They are left out now;
  `get_relevant_terms(text, translated_only=False)` would show them. Say if wanted.
- **A UI switch for "re-translate confirmed entries too" (WP3 3.1).** The coordinator has
  `include_confirmed=True`; no switch. Say if wanted.
- **A hard crash during a glossary build (WP3 3.6).** The glossary is written every 20 results; a power loss
  can lose up to 19 results × up to 8 terms = 152 terms of the running pass (a stop, cancel or error saves
  everything). Accept, or write after every result.
- **Self-hosted endpoints wait at least 180 s (WP1).** Tested. Acceptable for single-string translation and
  chat too?
- **Test junk in `plugins/pokemon_fr/config.json` `context_menu_tags`** (`{boba}`, `<biba>`, an emoji). Delete?
- **A typing `Protocol` for the plugin contract (WP5 5.1).** The contract is the `HOOKS` table in
  `plugins/spec.py`, kept honest by two tests. Recommendation: no Protocol unless a type checker is used.
- **The proxy branch `audit/wp8`** (worktree `D:\git\dev\gemini-web2api-wp8`). Tested with a stubbed Gemini
  (`test_rq_wp078_proxy_e2e.py`, 12 tests in the worktree's `tests/test_rq_wp078_proxy.py`, uncommitted).
  It also passed the live run (LIVE below). Recommendation: merge now; set `"host": "0.0.0.0"` first if a phone, Docker or
  the tunnel reaches it, keep `api_keys`; check the token-like placeholder in the uncommitted
  `dashboard.html` (`docs/OPEN_ITEMS.md` → "Found during WP8").
- **Documents to skim once.** `README.md` (what a newcomer reads first), `AGENTS.md` (12 rules, language
  policy), `docs/DECISIONS.md` (2026 H1 dates are approximate), `docs/wiki/3_Plugin_Developer_Guide.md` (the
  only plugin guide now), `docs/history/` (nothing used daily moved there?).
- **The holding folder** `D:\git\dev\Picoripi_local_cleanup_2026-10-01` (562 MB) — look through, then delete.

## LIVE

The owner's working project is `E:\Emulators\RomHacking\ZELDA\TP_UA\TwilihhtPrincess`; runs use copies of it
and of `ISO\ENG\root\res\Msgus` (the project's source and translation folder), never the originals.

- **Done 2026-10-03 — old build vs new build on the real model** (old proxy, `gemini-3.7-flash`, 4 workers,
  48 lines each of `zel_01` 727– (Talo, Colin, Beth) and `zel_03` 101– (the Goron elder)). New: 45/48 lines
  in 57 s and 36/48 in 127 s. Old: 22/48 in 140 s and 12/48 in 131 s, each run stopped after 4 attempts. Both
  lose whole chunks to the line layout check (see DECISION). Quality is on a par — the model's noise is larger
  than the difference: the new build wrote «ввімкни мійку», «ЖИВЬОМ», the old one «В Інструкція», «цій
  рогатки»; gender (Beth: «Я певна») and ти between the children were right in both.
- **Done 2026-10-03 — the new proxy 1.4.0 with the owner's accounts.** `/healthz` reports 6 active accounts and
  100 usable egresses; a Ukrainian request (UTF-8 body, temporary chat) answered in 4.5 s; a 96-line Twilight
  Princess run with 8 Parallel Requests went out at most 6 at a time (capped by `/healthz`), 16 requests and
  16 responses with no transport error, p50 5.3 s — every failure was Picoripi's line layout check. Not checked:
  the dashboard with `api_keys` (none needed on loopback here) and whether the proxy honours `response_format`.
- **A short glossary build and a reconcile run on a copy of the real glossary (WP3 3.3 / 3.5).** One root per
  family (`Hylia`, `Lake Hylia`, `Hylian Shield`), compounds follow their head term, the sweep does not drop
  terms it should report; reconcile does not merge different things (Clawshot / Clawshots) or "fix" grammar
  forms. The reconcile prompt has never met a real model.
- **"Fill glossary entry with AI" and one MemPalace mining / profile request (WP5 5.3)** — their wording now
  comes from `plugins/common/defaults/prompts.json`.

## ENV

- **Linux run of the suite** (`python tasks.py test`; WP0 exit and WP7 are open until then). WSL Ubuntu-24.04
  with Python 3.12 is installed; installing the requirements needs PyPI access.
- **Old builds on a glossary this build saved (WP3 3.6).** The old build does not show deletion records as
  terms: it drops them, and the entry ids, on its next save — so a later sync brings the deleted terms back.
  Do not open one glossary with old and new builds.
- **The Companion server is deployed together with the desktop (WP3 3.6).** An old server lists deletion
  records as terms.
- **`~/.claude/skills/update-wiki/SKILL.md`** is older than `.agents/skills/update-wiki/SKILL.md`, and
  `~/.claude/CLAUDE.md` points at `.grok/skills/update-wiki/SKILL.md`, which does not exist.

## Covered by tests (no action)

| WP | Former manual checks | Tests (`tests/test_review/`) |
|---|---|---|
| WP1 | batch through a proxy, failure and retry, 429 wait, Cancel, `think`, timeout floor, legacy build strictness, glossary pipeline | `test_rq_wp1_6_ai_batch_e2e.py`, `_ai_provider.py`, `_ai_worker_paths.py`, `test_rq_wp078_proxy_e2e.py` |
| WP2 | rules moved, saving from the editor, retry reminder, block start, payload, reference languages, editor-review input, glossary rows, character cards, native JSON | `test_rq_wp2_4_prompts.py`, `test_rq_wp2_4_run.py` |
| WP3 | canonical fold, confirmed entries, settled lines, families, plurals everywhere, untranslated and nested terms, reconcile report, ids, deletion records, writes every 20 | `test_rq_wp3_*.py` |
| WP4 | UI strings, addressee, conversations, old runs, restore by source text, translation memory, folding, run memory | `test_rq_wp2_4_run.py` |
| WP5 | analyzers, short labels, plain-text tags, AI shortcuts, menus and file opening, failing hook, plugin switching, prompts and validator, TP save (synthetic and real `bmgres3.arc`), TP preview (12 window kinds, 16 presets), Pokémon keys | `test_rq_wp5_*.py` |
| WP6 | exit while busy, worker paths, block tree, log, headless switches, mixin dialogs, Companion push/pull/test/conflicts/exit/skip, second project while loading, atomic saves | `test_rq_wp1_6_*.py` |
| WP7/8 | app start, ChatMock setup, FEATURES claims, manifesto stage table, plugin `glossary.md`, proxy cap/busy/cancel | `test_rq_wp078_*.py` |

Bugs these tests found were fixed (`CHANGELOG.md` → `[Unreleased]`).
