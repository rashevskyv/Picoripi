---
status: design
updated: 2026-10-02
owns: core/mempalace, ui/mempalace
tokens: 2.3k
purpose: MemPalace contract: principles, data flow, stage status
---
# MemPalace context: the contract

MemPalace is the story memory of a project: the marked-up walkthrough script as a timeline, each game string
tied to its place in it, and (planned) what every character knows, how they speak and how they address each
other at that moment. Its purpose is that every line is translated with verified context of where it stands.

This page is the contract. The full plan with per-stage checklists and the progress log up to 2026-07-16 is
archived in `docs/history/MEMPALACE_CONTEXT_MANIFESTO-2026-07.md` (large; grep, do not read whole). Stage
status below is as recorded there — confirm against the code before relying on it.

## Principles

1. **Script Markup Studio is the source of structure.** `script_markup_project.json` is the machine source of
   truth for text, line ranges, nesting, node types, speaker/dialogue/action/context/glossary marks, their
   origin and approval. MemPalace never re-guesses Act, Chapter or Scene from raw text when an approved
   markup exists. The Markdown export is a readable copy, not the integration format.
2. **An algorithm decides what can be decided exactly**: order and nesting of Act → Chapter → Scene, line
   ranges, speaker and dialogue from the markup, a line's position on the timeline, glossary occurrences, the
   game string ↔ dialogue link with its confidence, neighbouring lines and existing translation.
3. **AI draws semantic conclusions**: event summaries, participants and addressees when not explicit,
   character traits, manner of speech, attitudes, what characters know, how relations change, advice to the
   translator. Every AI conclusion carries evidence, confidence and a review status; it is a suggestion until
   a person approves it.
4. **Relations are directed and dated.** "A respects B" says nothing about B. A relation holds from one story
   node until another. A record has: source character, relation type, target character, valid from, valid
   to (or open), evidence, confidence, review status.
5. **The glossary and MemPalace have different jobs.** The glossary is the translator's contract: original,
   approved translation, category, short stable notes, a short approved speech profile. MemPalace is the full
   memory: timeline, evidence, full profiles, changes over time, knowledge, relations, scenes, the history of
   AI analyses and human decisions. Structured data is never flattened into one Notes field for good.
6. **The most useful context, not the most text.** Context is layered: translation rules and game style →
   approved glossary and global profiles → story state at the start of the chapter → the current scene →
   participants, their current relations and knowledge → neighbouring lines and earlier translation → the
   strings to translate. The stable chapter part is cached or sent once per session; only the changing scene
   part is added per request.

## Data flow

```text
Markup Studio hierarchy project
        ↓ deterministic import
Story timeline: Act → Chapter → Scene → content nodes
        ↓ deterministic / assisted mapping
Game block/string ↔ marked dialogue node
        ↓ sequential AI analysis
Scene events + state changes + character observations + evidence
        ↓ human review and approval
Canonical MemPalace knowledge + glossary projection
        ↓ context assembly
Chapter context → Scene context → translation batch
        ↓ validation
Terminology + address + character voice + continuity checks
```

## Stages

| # | Stage | Status | What the user gets |
|--:|---|---|---|
| 0 | Builder interface | done | consistent button semantics in the Builder |
| 1 | Markup Studio → MemPalace import contract | done | the hierarchy project is the only script source; import shows `Not imported` / `Up to date` / `Source changed` / `Import error` |
| 2 | Normalized story timeline | done | `story_documents` and `story_nodes` in SQLite; Scene is a real node; re-import makes no duplicates |
| 3 | Game strings ↔ dialogue nodes | checklist complete, stage left open | every mapping has a method and confidence; ambiguous duplicates go to a review queue; a locked mapping survives re-import |
| 4 | Virtual tree and Context Inspector | partly | tree built from `story_nodes`, a Scene selectable as a virtual block. **Open:** timeline position, Context Inspector, mapping method/confidence/source lines in the UI, Prompt Preview |
| 5 | Sequential AI analysis of the story | not started | per scene: summary, state before/after, evidence lines |
| 6 | Characters, speech, dated relations | not started | reviewed profiles and relations instead of one Notes text |
| 7 | Managed sync with the glossary | not started | approved knowledge is offered to the glossary with a diff; manual translations are never overwritten |
| 8 | Context Package and translation by chapter | not started | a reproducible package per scene, visible in Prompt Preview before a run |
| 9 | Context-aware quality checks | not started | violations of terms, gender, form of address, register, knowledge, with rule and evidence |
| 10 | Migration, documentation, acceptance | not started | backup before DB migration, recovery procedure, one full chapter accepted by hand |

A stage is done only when the code exists, automated tests cover it and pass, the visible result was checked,
no hidden fallback to the old model remains, and this page is updated.

### Contracts fixed for the stages not built yet

- **Scene analysis (5):** summary, participants, location/time, events, state before, state changes, state
  after, facts revealed, knowledge changes per character, relationship and character observations,
  terminology candidates, evidence node ids, confidence per inference. State after a scene is state before
  the next; the same between chapters. A chapter is chunked deliberately, never cut by `text[:N]`. The raw
  response, parsed result, model, prompt version and time are stored; JSON is validated before anything
  canonical is written; an invalid answer does not damage the previous analysis; a rerun creates no duplicates.
- **Character profile (6):** canonical name and aliases, approved translation of the name, gender and age
  group, role/status, personality, register/tone/tempo/vocabulary, grammatical recommendations, form of
  address per target character, valid from/to, evidence, confidence, review status. System and narrator
  tags are not characters.
- **Context Package (8):** schema version, game and target language, Act/Chapter/Scene path, timeline
  position, chapter state before, scene summary and state, participants with speaker and addressee, active
  profiles, active directed relations, relevant knowledge, relevant glossary plus a stable cached prefix,
  actions/conditions, surrounding original and already translated dialogue, strings to translate, source
  ids, token budget and a report of what was left out. Same data, same package; its hash is stored with the
  translation, and a cached translation is invalidated when the relevant context changes.

## What must not be done

- Build the main structure from `.txt` again when a hierarchy project exists.
- Keep scenes only as unstructured JSON in `ai_summary`.
- Treat a global character profile as valid for every moment of the story, or give a character knowledge
  from later scenes.
- Keep directed, pair-specific relations only as free text in Notes.
- Overwrite a manual or locked decision with an AI result.
- Hide a fuzzy mapping or a low confidence from the user.
- Cut context without reporting which sections were dropped.
- Mark a stage done because the code compiles, or change this plan silently.

## Acceptance set (to prepare before stage 10)

Ten fixed scenes, each with the expected Context Package and expected check results: nested structure (an Act
with several Chapters and Scenes); the same line in different scenes; a female character speaking in the
first person; mentor → pupil and pupil → mentor formality; a relation that turns from formal to informal
after an event; a fact a character learns mid-chapter; a mandatory glossary term that is declined; two
characters with clearly different registers; a line with placeholders and formatting tags; a locked mapping
or profile that survives a new AI analysis.

## Code

`core/mempalace/` (client, import, mapping, workers), `core/mempalace_client.py`, `ui/mempalace/` (Builder,
viewer); the translation side reads it through `core/translation/story_context_manager.py`. User-facing
steps: wiki 8, step 3 "Build the story context".
