---
status: current
updated: 2026-10-02
owns: handlers/translation, core/translation
tokens: 5.1k
purpose: Providers, prompts, chunks, run memory, translation memory
---
# AI Translation

**Language:** English · [Українська](uk/11_AI_Translation.md)

Picoripi talks to LLMs through **Settings → AI Translation**. Glossary builds use **Settings → AI Glossary** (optionally the same key). Recommended local proxy: [5. Gemini Web2API](5_Gemini_Web2API.md).

Handlers: `handlers/translation_handler.py`, `handlers/translation/`. Providers: `core/translation/providers.py`. Defaults: `core/translation/config.py`. Prompts: **Edit Prompts JSON** and plugin `translation_prompts/prompts.json`.

Prompt files are merged **key by key**, later ones winning: `translation_prompts/prompts.json` → `plugins/common/defaults/prompts.json` → `plugins/<name>/translation_prompts/prompts.json` → the project's or user's override copy. A plugin file that holds only a `translation` section still gets the `glossary`, `glossary_occurrence_update` and `mempalace` sections from the common file (`core/translation/prompt_files.py`).

**Review pass** is an optional second request per chunk in the translation's own conversation: the model sees the same rules, glossary rows, speakers, addressees and scene, its draft, and a request to fix only real errors (meaning, untranslated words, glossary terms, gender and case, ти/ви, typos, calques). It returns only the lines it corrects, each with a reason (in the debug log); a correction passes the same checks as a draft, and anything that fails keeps the draft. On by default; `"review_enabled": false` in the translation config turns it off, and `"review_model"` names another model for it. It adds one request per chunk. Measured on the proofread Minish Cap (2026-10-04): it changes about one line in twelve and makes it better in two cases out of three.

**One source, one translation per run.** Before a block (or project) run starts, strings with exactly the same text are folded: one of them is sent, and the others receive its translation when the chunk returns. Two strings fold only when everything else that decides the wording is equal too — speaker, addressee, the window the text must fit, what the plugin says about the row and your manual story overrides; so a line spoken by two different characters is still translated twice. A string that already has a translation is not overwritten by a fold, exactly as it is not overwritten by the model. Set `"fold_duplicates": false` in the translation config to send every string. Each run also keeps a **run memory**: when a later chunk contains a string that differs from an already translated one only in tags, case or spacing, the request carries `already_translated_in_this_run` (at most 10 rows) and the model is told to keep the wording. The memory is emptied when a new run starts; the second phase of *Story first, then the rest* continues the first one's memory.

**Series translation memory.** A project that has series glossaries (wiki 8, *Series glossaries*) registers itself in `projects.json` beside each of them (project name → its `translation_memory.json`) and, when it opens, reads the memory files of the other projects listed there (`core/translation/series_memory.py`; read once in the load worker, nothing is copied). Then: a name or a single term is never taken from another game; the series glossary translates it (wiki 8, *Fill Terms from the Glossary*). A sentence (more than two words, `series_sentence_words`) of another game is offered only when **Offer sentences translated in other games of the series** is on (Settings, AI page; off by default). The text must match exactly. The speaker is compared by the English name; a line without one never starts ticked. Each offered line has a check box in the list **Sentences From Other Games of the Series**, with the English text, the other game's translation and game, both speaker names and a reason. A safe match starts ticked when **Safe matches start ticked** is on (the default); a doubtful one (speakers differ or missing, addressee differs, the text is too long for this window, the tags do not match) starts unticked. **Select safe**, **Select all** and **Clear** change the checks. **Apply selected** writes only the ticked lines, as undoable edits; a line that fails the width or tag check stays untouched and goes on to the AI pass. Nothing is applied automatically. A chunk request carries `translated_in_other_games_of_the_series` (at most 10 rows, each with `project`), a single-string request lists them in **TRANSLATION MEMORY** marked `in <project>`; and a bar above the editor says **Translated in <project>: "…"** with **Apply here**. The same bar says **The same text is in N other place(s) of this project** when the current text has other copies, and **Apply to places with the same context** writes the current (or the remembered) translation into every other place of the project where the same text is said under the same speaker and window (the duplicate-fold test) and the text fits the window; the other places are left alone and the status bar counts them. The edits are unsaved and you can undo them. A line of another game is carried across when both games give the same kind to the same control tags in the same order (`get_series_tag_map`; for example a page break or a name the game inserts): its tags are written in this game's syntax. A tag that has no equivalent blocks the carry-over, and the memory bar says why.

**Translation memory across runs.** Every translation Picoripi saves as a backup (`saved_translations.json` in the project folder, keyed by position) is also remembered by its source text in `translation_memory.json` next to it. When a run is about to translate a string whose own position has no saved translation but whose text was translated and saved somewhere else in the project, the *Cached Translation* window offers that translation too — marked *(same text elsewhere)* — after the same layout check as a positional restore. Only exactly the same text is restored. A text that occurs more than once in the project is offered only when the saved line had the same speaker, addressee and context (the duplicate-fold test); a line said by another speaker is translated anew, and a row saved before this rule is not offered for such a text until the line is saved again. The window has one check box per line, checked by default: **OK** fills the checked rows without a request, an unchecked row goes to the model, and **Translate Anew** sends every row to the model. A single-string translation request additionally lists, as `TRANSLATION MEMORY (same source elsewhere)`, up to three saved translations of the same text — including spellings that differ only in tags, case or spacing — so that the model keeps the wording; a request for variations does not get the list. A project saved before this feature builds its memory from the existing saved translations the first time it is needed. **File > Update Translation Memory with Context** gives the rows saved before this rule their context (speaker, addressee and fold key) from the saved translations, so a repeated text is offered again. It runs on a worker thread and can be cancelled; the previous memory is kept as `translation_memory.before_context.json`, and **File > Restore Translation Memory Before the Context Update** puts it back.

**Fixed interface strings.** Put the recurring interface words — *OK*, *Yes*, *No*, *Back* — into the glossary section named **UI**. A game string that is, as a whole, exactly such a term (or one of its aliases; same case, no extra characters) is filled with the glossary translation before the run starts: no request, no question. A row that already has a translation is not touched, a translation that does not fit the row's layout is not forced in, and an entry whose translation is still an unconfirmed AI suggestion fixes nothing. Other sections can be named in the translation config: `"fixed_output_sections": ["UI", "Menu"]`; an empty list switches the feature off.

**Line layout of a reply.** The model writes the words; Picoripi lays them out. Every string has a **layout class** (`core/translation/layout_class.py`): the plugin names it (`layout_class` in `get_translation_context_for_string`, from the window kind) or the engine guesses it from the source: a few short lines without sentence punctuation are **lines** (a menu, a name, a choice, credits), everything else is **prose**. The request says which (`layout_class: "lines"` on the item; prose is the default) and gives a letter budget instead of pixels: `max_chars_per_line`, measured on the Ukrainian alphabet in the game's font (`lines_per_window` × `max_chars_per_line` per page). For prose the model may write each page as running text; when the reply is applied, the words of every page are reflowed by the **typesetter** (`core/typesetter.py`) with the game's font: fill to the target width (`warn_width`), never leave «і», «в», «на» and the other one- and two-letter function words at the end of a line, never leave one word alone on the last line, and go past the target only up to the limit (`max_width`) when those rules need it. The same typesetter breaks a too-wide line in the width autofix. A **lines** string keeps the model's lines as they are. A reply must still keep the blank lines (page breaks) and the trailing newline, or its chunk fails. **Shorten pass:** after the draft (and the review), Picoripi typesets every item; a prose item that then needs more windows than the source, or a lines item with a line wider than the limit, goes back once in the same conversation with `shorten_by_letters` (how many letters, measured) and the reason; a shortened line is taken only when it fits better, otherwise the draft stays. `"shorten_enabled": false` in the translation config turns the pass off. The run summary counts `layout: N did not fit, M shortened`. The two widths of a window kind are its target and its limit; a plugin that knows only one of them gives `width_tolerance_percent` in `config.json` (default 5) and the other follows.

A single-string request also carries an `Addressee:` line when the plugin knows who the line is spoken to — the same information a batch item has.

**Forms of address (ти/ви).** **Tools → Forms of Address...** is a small table saved in the project (`address_forms` in the `.uiproj` metadata, `core/address_forms.py`): **Characters** with free-word traits (`child`, `adult`, `elder`, `royalty`, `deity`, `male`, `female`...; the list starts with the names the Speaker field shows), **Rules** between traits in priority order (the defaults: anyone → royalty, deity or elder formal, then child → adult formal, adult → child informal, child → child informal; `*` is anyone) and **Pairs** (one speaker to one addressee) that beat every rule. For a line whose plugin names the addressee, the first matching pair or rule becomes `address_form: "formal"` or `"informal"` in the batch item and an `Address form:` line in a single-string request; the review pass checks ти/ви against it. No match, no field: the model decides as before. Set it once when the project starts; it works for every run after that.

---

## Turn a provider on

**Settings → AI Translation**

| Field | Values |
|-------|--------|
| Target Language | e.g. Ukrainian, Spanish, German |
| Active Provider | Disabled · OpenAI Compatible · Ollama Chat · Gemini · Perplexity |
| Preset | Save Preset / Delete Preset (saving an existing name overwrites it) |
| Parallel Requests | 1–16, default 6. Concurrent requests during batch/chunked translation |
| Test Provider | One tiny request. Disabled while provider is Disabled |

**OpenAI Compatible** (use this for Web2API):

| Field | Notes |
|-------|--------|
| API Key | Bearer token (password field) |
| API Key Env Var | default name `OPENAI_API_KEY` (also loaded from `.env` via `settings_manager`) |
| Endpoint | placeholder includes `https://api.openai.com/v1` or `http://127.0.0.1:8081/v1` |
| Model | placeholder `gpt-4o-mini` or `gemini-3.7-flash` |
| Temperature | 0.0–2.0, default 0.0 |
| Max Output Tokens | 0 = Provider default |
| Request Timeout | 1–600 s, default 60. Use **180 s** with Web2API |

**Ollama Chat API:** Base URL `http://localhost:11434`, Model `llama3`, timeout default 120 s, Keep Alive.

**Google Gemini API:** Base URL optional (`http://127.0.0.1:8081/v1` or empty for Google API), API Key optional for a local proxy, Model `gemini-3.7-flash`.

**Perplexity API:** Bearer token, Base URL `https://api.perplexity.ai`, model placeholder `sonar-medium-8x7b-chat`.

**Edit Prompts JSON** edits the stored templates. For a one-off tweak, Ctrl-click **AI Translate** or **AI Variation** instead.

**Global → Show prompt editor before AI requests** opens the editor on every request.

In the editor, the system prompt ends with a line `--- REQUEST RULES (added by Picoripi …) ---` followed by the fixed rules for that kind of request (output format, layout, glossary, tags, optional context fields). They are the same for every chunk of a run, which lets providers cache them; you may edit them for one run, but saving the prompt stores only the part above the line. The user message holds the header and the data: for a block, `layout_defaults` once and one line per string with only what is specific to it.

Default config `provider` is `"disabled"` until you pick one.

---

## Translate in the editor

**AI Translate** (above Editable):

- Click: translate the current string. If a translation already exists in the backup database, that one is reused (no new request).
- Ctrl-click: prompt editor, and **ignore** the stored translation (always re-translate).
- Several strings: select lines in **Strings in block**, right-click (Ctrl-click there too for the prompt editor).
- More than 12 items in one job uses **chunked** translation (`translate_specific_strings`).

If a job is already running: dialog **AI Busy**.

Nothing selected (`physical_block_idx == -1`): the button does nothing.

**AI Variation**:

- Click: alternative wording of the **current translation** (`request_type='variation_list'`; temperature override 0.7).
- Select a fragment in Editable first — only that fragment is rewritten.
- Ctrl-click: prompt editor.
- Pick from **AI Translation Variations**; Refresh / Ctrl-click ignores the in-memory cache.

**AI Chat** (toolbar, `Ctrl+Shift+C`): window **AI Chat**. Discuss translations. Ctrl+Enter / Send sends; Enter is a newline. Optional **Web Search**. Features a dedicated **Retry** button (and `Ctrl+Shift+R`) to instantly resend the last message (with new model/settings or after a connection failure) without retyping, a **Stop** button during generation, message queueing with `[In Queue]` badge, and a **Reset Context** action. Chat does **not** write the Editable pane; copy a suggestion yourself or use **AI Translate**.

---

## Batch Translation Pipelines & Modes

Bulk translation can be launched from the main toolbar **AI** button, the blocks tree header, **Tools → AI Batch Translation ➔**, or Step 5 of the [Localization Pipeline](8_Localization_Pipeline.md). This opens the **AI Batch Translation Dialog** (`AIBatchTranslationDialog`).

### Available Modes

1. **Translate Story First (Chronological)**:
   - Uses `core/translation/block_classifier.py` and MemePalace script mappings to isolate primary narrative dialogue.
   - Translates lines chronologically, so the story text is settled before the auxiliary blocks.
2. **Translate Remaining Blocks (Semantic & System)**:
   - Translates remaining UI, menu, inventory, shop, and mini-game blocks.
   - Uses the same glossary and per-line context as any other run. Nothing else is carried over from Phase 1: consistency with the story comes from the glossary and from the neighbouring rows that are already translated.
3. **Run Full Pipeline (Story ➔ Semantic)**:
   - Automatically runs Phase 1 followed immediately by Phase 2 in a single multi-stage run.
4. **Translate All Blocks (Chronological Legacy)**:
   - Flattens all blocks into a single chronological timeline and translates continuously.

### Multi-Agent Translation Consilium

During batch runs, translations are processed through a cooperative multi-agent architecture:
- **Primary Translator**: Generates candidate phrasing respecting layout limits and control codes.
- **Inline Arbiter / Editor**: A supervisor agent that validates terminology against active glossary entries, refines phrasing, and checks tone consistency before text is committed.

## What goes into the prompt

The engine does **not** hard-code game vocabulary. The plugin may attach (`get_translation_context_for_string`):

| Key | Prompt effect |
|-----|----------------|
| `window_type` | `Window Type: <value>` |
| `content_role` | `Content Role: <value>` |
| `role_instruction` | inserted verbatim (plugin teaches the model its own roles) |
| `has_speaker` | `False` skips speaker lookup |
| `glossary_section` | section for a new term from this line |
| `force_glossary` | line must produce a glossary entry |

Plus speaker (after Merge Speakers), glossary hits (then, at lower priority, linked series-glossary rows for terms the project glossary lacks — [8](8_Localization_Pipeline.md)), MemePalace scene if built, optional `get_ai_flow_context_for_string` / `get_ai_flow_overview`.

**How a run is cut into requests.** A request carries at most 12 strings. Strings of one MemePalace scene travel together; within a scene (and among the strings that have none) the lines of one conversation — as the plugin reports it through `get_ai_flow_group_for_string` — are kept in the same request whenever they fit, so a question is not separated from its answers or a choice from its options. A conversation is cut only when it alone is longer than 12 lines. Plugins without that hook get the plain cut by count. A translation that was in progress before this version resumes with the cut it was started with.

### Language-Specific Transcription Directives

System and plugin prompts support language-conditional directive blocks:
`[IF_TARGET_LANG: <Language>]...[/IF_TARGET_LANG]`.
When the target language matches (e.g. `Ukrainian`), the directives unwrap to provide strict rules for transcription and transliteration:
- English plosive `G` is transcribed as Ukrainian `Ґ` (e.g. *Ganon* -> **Ґанон**, *Goron* -> **Ґорон**, *Gengar* -> **Ґенґар**), while aspirate `H` is transcribed as `Г` (e.g. *Hyrule* -> **Гайрул**, *Hogwarts* -> **Гоґвортс**).
- Zelda universe `Hy-` [haɪ] root is consistently unified using `Г` and `ай`: *Hyrule* -> **Гайрул**, *Hylia* -> **Гайлія**, *Hylian* -> **гайлійський / гайлієць** (including all landmarks and creatures: *Lake Hylia* -> **озеро Гайлія**, *Hylian Shield* -> **гайлійський щит**, *Hyrule Bass* -> **гайрульський окунь**, *Hylian Loach* -> **гайлійський в'юн**). Russian calques like «Хайрул» and desynchronized forms like «Гілія / Хілія / гілійці» are strictly prohibited.
- Japanese names and terms follow the academic Kovalenko system (`shi` -> **сі**, `chi` -> **ті**, `tsu` -> **цу**, `ji` -> **дзі**, plosive `g` -> **ґ**), avoiding Russian-style Polivanov adaptations (e.g. *Satoshi* -> **Сатосі**, *Shigeru* -> **Сіґеру**, *Fuji* -> **Фудзі**).
When a non-matching target language is selected (e.g. `Spanish`), these blocks are cleanly stripped, keeping prompts completely free of Cyrillic characters.

### Reference Translations Context

When external reference patches or unpacked multi-language ROMs are loaded, corresponding dialogue lines from all available reference languages are injected under `REFERENCE TRANSLATIONS` (for single strings) or `reference_translations` (for batch requests).

The engine enforces strict translation boundaries:
- **Primary Source**: The model always translates from the original source text (`Input text (Original source):` or the `"text"` field).
- **Context Only**: Reference translations are contextual evidence only, helping disambiguate meaning, speaker tone, and character gender across official or community localizations.
- **Strict Prohibition**: The prompt explicitly forbids translating from any reference language or copying a reference translation as the target result.
- **How many**: A single-string request shows every loaded reference language. A batch request sends every loaded language for every line by default; set `"max_reference_languages"` in the translation settings block to cap the count (the first loaded come first; 0 sends none). Russian, when loaded, always goes last and the prompt marks it as the least trusted reference, so a cap drops it first.

---

## Glossary AI

**Settings → AI Glossary**

| Field | Notes |
|-------|--------|
| Provider | OpenAI Compatible · Ollama · Gemini |
| API Key | |
| Use API key from AI Translation | |
| Model | |
| Text Chunk Size | 1000–32000 characters |
| Parallel Requests | 1–16. Wider than the number of proxy accounts only queues on cooldown |
| Retry Delay | 0–600 s. Server `Retry-After` wins |

Pipeline launch: **Tools → Prepare Glossary…** or wizard step **Prepare and enrich the glossary**. See [8](8_Localization_Pipeline.md).

---

## Parallel Requests

`translation_workers_spin` / `glossary_workers_spin`. Proxies that rotate several accounts (Web2API) can use 4–8. One account: set **1**.

---

## What not to do

- Do not click Translate with Active Provider **Disabled**.
- Do not leave Request Timeout at 60 s on Web2API (proxy retries across accounts).
- Do not assume a reused backup is a fresh model output — Ctrl-click to force.
- Do not start a second Translate while **AI Busy**.
- Do not put API keys or cookies in the wiki, README, or commits. Use Settings or `.env`.
- Do not set Parallel Requests far above Active accounts; extra workers wait on cooldown.
