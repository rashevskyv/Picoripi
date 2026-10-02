All notable changes to the **Picoripi** project will be documented in this file.

## [Unreleased]

- wp2 2.1: the request rules are fixed text appended to the system prompt (`prompt_composer/instructions.py`) instead of an `INSTRUCTIONS` block rebuilt into every user message — the system prompt is byte-identical for every chunk (cacheable prefix ~2100 → ~3065 tok) and the user message carries data only; a retry quotes the real error; the prompt editor shows the rules but saves only the user's prompt.
- wp2 2.2: the rows shown before and after a chunk come from the strings' real position — selections and preview runs no longer show rows 0–3 of the first block, project-wide and story-first runs get neighbour rows at all, and a chunk spanning two blocks gets both sets.
- wp2 2.3: starting a block translation no longer composes the prompt for the whole item set (twice) before the first request — only the tag placeholders are collected, and the prompt editor previews one chunk; the worker composes each chunk as before.
- wp2 2.4: removed two things that never ran — the `NarrativeLedger` (nothing ever wrote to it, so no "canon context" was ever injected) and the translation-session path (unreachable behind a duplicated flag); README and wiki 2, 8, 11 no longer describe them. AI Chat sessions are unchanged.
- wp2 2.5: smaller batch payload — shared layout values once in `layout_defaults`, per item only `line_count` and what differs; unresolved speakers omitted; one reference language per line by default (`max_reference_languages`), none for one- or two-word lines; the editor review gets `{id, text, translation}` triples. A 12-item chunk: ~5440 → ~4610 tok.
- wp2 2.6: a chunk's glossary table is built from the chunk's own text plus its speakers and story participants (no 60-line lookahead, no matching against the story-context JSON); batch requests carry compact character cards (role, address and grammar, speech style of the current speaker; 40 words per field) instead of full MemPalace profiles.
- wp2 2.0: `tools/measure_prompts.py` measures the single and batch translation prompts against a fixed fake project; baseline in `docs/audit/2026-10-01/measure_prompts_before.json` (single ~3010 tok, 12-item chunk ~5520 tok).

## [0.3.143-dev] - 2026-10-02

- wp1 1.1: `core/translation/transport.py` — `ErrorKind`, `TransportError`, `classify`, `TransportPolicy` (backoff + jitter, honours `Retry-After`, total deadline, cancellable waits), per-endpoint circuit breaker and concurrency gate; dead `core/glossary_build/retry.py` and `concurrency.py` removed.
- wp1 1.2: every provider request runs under `TransportPolicy` — classified errors, `Retry-After` carried to the retry dialog (which now waits that long), one automatic retry for quick failures in the translation worker (never for a request that timed out), a per-provider circuit breaker; an empty or non-JSON reply is an error instead of a silent empty success; the Gemini custom-URL route shares the OpenAI path (gets `think`); API keys are masked in error text; block timeout is `max(180 s, user setting)`.
- wp1 1.3: `utils/json_extract.py` replaces the three JSON cleaners — string-aware extraction, repairs (trailing commas, curly quotes, raw newlines), cut-off replies detected; an unreadable reply raises `ParseError` instead of becoming `[]`/`""` (legacy glossary build stops on a bad chunk; the pipeline counts it as a failed unit).
- wp1 1.4: parallel block translation uses a rolling pool — one failed chunk no longer discards the block (finished chunks are kept, failed ones are listed, a retry sends only those), a fatal error or a cancel stops further requests; a reply with reordered or foreign ids is rejected instead of being written to the wrong rows.
- wp1 1.5: provider profile — a self-hosted OpenAI-style endpoint is treated as a Web2API proxy (gets `think`, timeout raised to 180 s, parallel requests capped by the Active accounts its `/healthz` reports), hosted APIs never receive `think`; `"profile"` in the provider settings overrides the guess; one `MAX_CONSECUTIVE_FAILURES = 3` for translation and the glossary pipeline (was 3 and 5).
- wp1 1.6: applying an AI reply is guarded — a reply that is not `{translated_strings: [...]}` is rejected before anything is written, any failure while applying ends as an AI error instead of an unhandled exception, and the undo group is always closed; the legacy glossary build reports a non-list reply instead of "no new terms".
- wp1 1.7: `ai_traffic.log` is JSON Lines in the settings folder — request, response and error records share a `request_id` and carry chunk, attempt, sizes, duration, error kind and status; written under a lock (no interleaving from parallel requests); rolled over at 8 MB instead of truncated at start-up and at every task; a per-run summary (requests, p50/p95, failures by kind) goes to the log and the status dialog.
- wp1 1.8: cancelling a translation no longer waits for the request in flight — the worker walks away from it within a fraction of a second and the run ends as cancelled, not as an error; streaming and Ollama requests share the timeouts, error classification and circuit breaker.
- Qt pins follow the environment the app is developed and tested on: `PyQt6==6.11.0`, `PyQt6-Qt6==6.11.1`, `PyQt6-sip>=13.11` (the 6.6.1 pin was never installed locally).

## [0.3.142-dev] - 2026-10-01

- wp0 0.1: `.gitattributes` (LF everywhere, CRLF for .bat/.ps1, binaries marked); BOM stripped from 52 .py files.
- wp0 0.2: pinned `PyQt6-Qt6==6.6.1`, `PyQt6-sip`, dev tools; `requires-python = ">=3.10"`.
- wp0 0.3: user aliases → `~/.picoripi/plugins/<name>/aliases.json` (shipped file stays as read-only defaults); prompt edits → `<project>/plugin_overrides/<name>/prompts.json` (or the settings dir without a project); `eval` → `ast.literal_eval` for `string_metadata` keys.
- wp0 0.4: test hygiene — Windows-only tests skipped elsewhere, delegate paint test uses `initStyleOption`, `fastapi` importorskip, ruff test runs from repo root without `gemini/`, autouse fixture keeps settings/`app_debug.txt`/`ai_traffic.log` out of `~/.picoripi` and the repo; glossary dialog no longer defaults to a CWD-relative `settings.json`.
- wp0 0.6: `AGENTS.md` is the single agent entry (rules, commands, checklist); `CLAUDE.md` and `GEMINI.md` are stubs; duplicate `.agents/workflows/` removed (release-notes rules merged into the deploy skill).
- wp0 0.7: process logs archived under `docs/history/` (changelog split by month, old walkthrough/plan/task/audit, refactor specs); root `plan.md`/`task.md`/`walkthrough.md` hold the current iteration only; `docs/OPEN_ITEMS.md` added; `scripts/deploy.py` rolls the walkthrough into the archive on release.
- wp0 0.5: xdist crash roots fixed (deferred callbacks bound to their widgets, stable occurrence keys, QAction ownership, highlighter editor reference, DeferredDelete flush in conftest); UI/tools lanes pass 5 consecutive `-n 2` runs.
- wp0 0.8: `.graphifyignore` keeps tests, locales, archives and markdown out of the graph (15.9k → 9.5k nodes); README documents the free `graphify update .` path only.
- wp0 0.9: `dummy.json` and `.grok/skills` untracked (the session-state test now writes to `tmp_path`); `scripts/bump_version.py` keeps the `-dev` suffix.

## [0.3.141-dev] - 2026-09-29

### 🚀 Added & Architectural Changes
- **Smart Glossary Synchronization on Application Shutdown & Project Close**:
  - Implemented automatic diff-based synchronization when closing the application (`MainWindow.closeEvent` / `File → Exit`) and when closing a project (`File → Close Project`).
  - Automatically pushes any pending in-memory and local glossary modifications made by the user on their PC to the remote Companion cloud/server before shutdown, guaranteeing zero data loss between mobile and desktop devices.
  - Displays the dedicated `CompanionSyncDialog` in exit mode (`is_closing=True`) with a customized header ("Closing Picoripi — Synchronizing Glossary…"), real-time progress indicators ("Pushing local updates to Companion server…"), and rapid completion auto-close (800ms).
  - Ergonomic exit controls: offers a 1-click `"Skip & Close"` button to bypass synchronization immediately if the user is in a hurry, as well as a `"Close Anyway"` option if the server is offline or unreachable.
  - Guaranteed local persistence: automatically flushes pending glossary entries to disk via `save_to_disk()` and directly passes the merged entry payload to the sync client.
  - Seamless background synchronization: upgraded `GlossaryDialog` dismissal (`closeEvent`/`reject`) to run `smart_sync_in_background`.
  - Added localized strings in `locales/en.json` and `locales/uk.json`.

## [0.3.140-dev] - 2026-09-29

### 🚀 Added & Architectural Changes
- **Smart Bidirectional Diff & Merge Synchronization for Companion Server**:
  - Implemented smart diff-based two-way synchronization engine (`merge_glossaries`, `apply_conflict_resolutions`, `CompanionSyncClient.sync_project`) that intelligently merges local and remote glossary entries based on per-entry timestamps (`updated_at`) and file/server modification times.
  - Automatically identifies newer reviewed terms from the mobile Companion app (downloading and updating local `glossary.json` with `.bak` backup protection) and newer edits or newly added terms from the desktop application (uploading merged changes to the server).
  - Added timestamp tracking (`updated_at` in ISO 8601 UTC) across `GlossaryEntry`, serialization in `notes.py`, parsing in `parse_mixin.py`, mutation tracking in `mutation_mixin.py`, and Companion server storage in `storage.py` and `models.py`.
- **Visual Synchronization Progress Dialog (`CompanionSyncDialog`)**:
  - Automatically triggered upon opening the Glossary dialog (`Ctrl+G` / `Tools → Open Glossary...`) when Companion auto-sync is enabled.
  - Displays a dedicated modern progress window ("Йдеться синхронізація") showing connection status, real-time diff analysis, and merge progress with an animated progress bar.
  - Includes a non-blocking "Skip & Work Offline" action to ensure the user can immediately continue working offline without waiting or hanging if the remote server is unreachable.
  - Features smooth auto-dismiss upon successful synchronization with status bar feedback.
- **Interactive Collision & Conflict Resolver (`CompanionConflictDialog`)**:
  - Automatically detects collisions when the same term has been edited with differing values locally and remotely within close succession.
  - Presents an interactive side-by-side card view comparing local (PC) and remote (Companion) translations, statuses, notes, and modification timestamps.
  - Provides ergonomic individual radio selections and bulk actions ("Keep All Local" / "Keep All Remote") with safe application into the merged glossary.
- **Glossary Dialog Integration**:
  - Added `"🔄 Smart Sync with Companion..."` as the top action in the `[☁ Companion Sync...]` button menu in `GlossaryDialog` for on-demand synchronization with instant hot-reloading of the glossary table.
  - Upgraded background auto-sync on application startup and project opening (`smart_sync_in_background`) to use the bidirectional diff engine, preventing accidental overwrites of local edits.
  - Localized all dialogs, buttons, and status strings into English and Ukrainian (`locales/en.json`, `locales/uk.json`).

### 🚀 Added & Architectural Changes
- **Collapsible Detail Panes & Responsive Splitter Sizing in Glossary Dialog**:
  - Implemented comprehensive collapse/expand lifecycle management in `GlossaryDialog` (`_set_section_collapsed` and `_rebalance_lower_splitter`) for the three lower detail sections: **Description**, **AI Notes & Unresolved Choices**, and **Occurrences**.
  - Enabled `setChildrenCollapsible(False)` on `_lower_detail_splitter` so Qt never automatically crushes detail panes into illegible slits.
  - Dynamically redistributes available vertical height when collapsing or expanding sections:
    - Collapsing a section shrinks it cleanly to a compact 32px header bar with `"▶"` indicator, hides the content editor/list, and distributes the freed height among the remaining expanded panes.
    - Expanding a section back actively allocates comfortable, readable height (at least 90-140px, never stuck at 34px), and dynamically borrows space from an over-expanded `_variants_pane` in `_detail_splitter` if total space in the lower detail splitter is constrained.
  - Added full persistent storage and restoration of `notes_collapsed`, `ai_notes_collapsed`, and `occurrences_collapsed` in `settings.json`.
  - Added automatic backward-compatibility migration for older `settings.json` files: sections previously saved with heights `<= 34` are seamlessly recognized as collapsed rather than shown as flattened slits with visible text.
  - Added pointing hand cursors (`Qt.CursorShape.PointingHandCursor`) on collapse toggle buttons and localized dynamic tooltips (`Collapse section` / `Expand section`) in English and Ukrainian.
  - Isolated test settings paths in `test_glossary_review_ui.py` to prevent workspace pollution and parallel test interference.

## [0.3.137] - 2026-09-27

### 🚀 Added & Architectural Changes
- **Reference & ROM Configuration Moved to Settings**:
  - Moved reference translations and multi-language ROM / `.iso` path configuration out of the `File` menu into **Settings → Project → File Paths** (`Reference Translation / ROM Path`).
  - Added interactive popup menu for browsing either a patch/unpacked ROM folder or a game `.iso` disc image, with a clear path option.
  - Added global **Wiimms ISO Tool (`wit.exe`) Path** setting in **Settings → Global** to allow custom executable configuration for automatic GameCube/Wii ISO message extraction, prioritized ahead of system `PATH` and fallback locations.
  - Dynamically clears or loads multi-language reference tabs (`Original`, `RU`, `DE`, `FR`, `IT`, `ES`) in real time when Settings are saved.
- **Picoripi Companion PWA & Background Desktop Synchronization**:
  - Standalone mobile PWA companion (FastAPI + HTML5/CSS/JS) with Docker and systemd deployment workflows.
  - Non-blocking automatic desktop synchronization on application startup and project open/close with diff-based change detection, local backups (`.bak`), and hot in-memory reloading.
  - Touch-optimized mobile interface with 44px touch targets, natural inertial scrolling, and strict exclusion of confirmed terms from review filters.
- **AI Batch Translation Pipelines**:
  - Introduced `AIBatchTranslationDialog` and Tools menu commands for `Story First`, `Remaining Blocks`, and `All Pipeline` modes.
  - Integrated `NarrativeLedger` for character voice consistency and an Arbiter/Editor consensus workflow.
- **Compact 2-Row Editor Header & Vertical Alignment**:
  - Streamlined story, speaker, window, font, and width controls into a compact 2-row layout.
  - Added `HeaderSyncFilter` for exact vertical baseline Y-alignment between source tabs and editable panels across DPI scales.
- **Full Wiki & Documentation Twin Parity**:
  - Added `docs/wiki/12_Picoripi_Companion.md` and `docs/wiki/uk/12_Picoripi_Companion.md`.
  - Fully synchronized User Guide, Configuration Guide, and Pipeline documentation across English and Ukrainian catalogs.

### 🛠️ Fixed
- **Status Bar Resilience in Background Workers**: Guarded `statusBar()` calls in background workers to safely handle both method and object references in test environments.
- **Companion Settings Persistence**: Fixed serialization of Companion server endpoint parameters in `GlobalSettings.save`.

## [0.3.136-dev] - 2026-09-26

### 🛠️ Fixed & Improved
- **Companion Mobile Editor Natural Scrolling & Accordion Squashing Fix**:
  - Fixed a critical layout bug where accordion elements (`.accordion-item`) at the bottom of the term editor were squashed down to flat 2px lines due to default flex-shrink behavior on elements with `overflow: hidden`.
  - Added `flex-shrink: 0` to all direct children of `.editor-scroll-body` and `.terms-list`, ensuring field cards, proposed variants, and accordions always maintain their full intrinsic heights.
  - Set explicit `min-height: 44px` on `.accordion-header` for consistent touch ergonomics and tap accessibility.
  - Replaced `height: 100%` with `min-height: 0` on `.view` containers to prevent viewport overflow caused by header stacking.
  - Enabled smooth native mobile momentum scrolling with `-webkit-overflow-scrolling: touch` and comfortable bottom padding `padding-bottom: max(32px, env(safe-area-inset-bottom))`.

## [0.3.135-dev] - 2026-09-26

### 🚀 Added & 🛠️ Improved
- **Mobile Companion PWA Header & Navigation Ergonomics**:
  - Replaced the bulky `● Connected` text badge in the header with a compact glowing green indicator dot (`.status-dot`), saving ~75px of horizontal space and allowing the full project title dropdown to fit without truncation or cramming.
  - Enlarged the back/forward term navigation buttons (`[◀]` and `[▶]`) to minimum 44×38px touch targets (`.nav-arrow-btn`) with 1.15rem arrow glyphs and interactive tap feedback (`transform: scale(0.95)`), adhering to mobile touch guidelines.
  - Aligned the `← Back` button (`.btn-back`) to 38px height and enhanced the active term counter typography for improved readability.

### Fixed
- **Companion Review Filter Excludes Confirmed Terms**: Fixed `is_unconfirmed` condition in `companion/server/api.py`, `storage.py`, and `glossary_view.js` to ensure confirmed terms (`status="confirmed"`) are strictly excluded from the "Needs review" filter, even when they retain multiple historical candidate variants (`translation_variants`).

## [0.3.134-dev] - 2026-09-26

### 🚀 Added & 🛠️ Improved
- **Automatic Background Companion Sync on Startup**:
  - Implemented non-blocking background auto-sync triggered 600ms after startup UI readiness (`finish_startup_loading()`) and on project load.
  - Granular remote vs local glossary diffing in `CompanionSyncClient.pull_project()`; skips file backups and disk I/O when glossaries are identical (`changed_count = 0`).
  - Hot in-memory reloading on change via `glossary_mgr.refresh_from_disk()`, instant editor syntax highlighting re-initialization, and auto-refreshing open `GlossaryDialog` views.
  - Automatic push fallback: if the Companion server has no terms for the current project while the local project has terms, automatically pushes the initial glossary to make terms immediately available for mobile review.
  - Built-in debouncing (3-second window) and running-worker detection (`existing_worker.isRunning()`) to prevent overlapping pull requests.
  - Localized status bar feedback (`Companion: auto-synced {count} updated terms from server.` and `Companion: glossary is in sync with server.`).

### Fixed
- **Companion Server Settings Persistence**: Added `companion_server_url`, `companion_api_token`, and `companion_auto_sync` serialization to `GlobalSettings.save` so configured Companion server endpoints persist to `settings.json`.
- **Centralized Settings State Synchronization**: Updated `MainWindowSettingsActionsMixin.open_settings_dialog` to synchronize modified settings with `SettingsManager.set(key, value)`.
- **Open Settings Delegation**: Added `open_settings_dialog()` delegator method on `MainWindow` to allow child and modeless dialogs to reliably invoke application settings.
- **Glossary Companion Sync Prompt**: Resolved server URL lookup in `GlossaryDialog` and connected the "Yes" confirmation prompt to automatically open the Settings dialog and re-check server configuration upon closing.

## [0.3.133-dev] - 2026-09-26

### Improved
- Glossary occurrence cards show the complete source message and corresponding Russian reference entry, with a vertical scrollbar for long cards.
- Preview zoom and panning keep the background, frame, and text aligned; warning tooltips show colored status markers.
- Reference translations remain contextual evidence for AI translation, while the original text is the translation source.

## [0.3.132-dev] - 2026-09-23

### 🚀 Added & 🛠️ Improved
- **Authentic BLO Font Scaling & Layout Line Spacing**:
  - **Restored Authentic BLO Metrics**: Reinstated game layout line spacing and character advance based on BLO `text_metrics` (`layout_line_spacing = game_line_space * cell_h / game_font_y - leading`, `layout_char_spacing = game_char_space * cell_h / game_font_y`) and native font ratio `scale_factor = (game_font_y / cell_h) * fit` from commit `d0fc666c`.
  - **Original Vertical Centering (`do_heightcenter`)**: Restored `textbox_height_center` algorithm matching the console engine `jmessage_tRenderingProcessor::do_heightcenter`, providing exact vertical margin symmetry inside dialogue frames.
  - **Lockstep 1:1 Bidirectional Scaling**: Fully preserved bidirectional proportional scaling with window dimensions and background image zoom (`Ctrl+Wheel`).
  - **Robust Type Coercion**: Maintained numeric/boolean type sanitization across preview widget properties to prevent `MagicMock` poisoning in headless/test environments.
  - **Comprehensive Unit Testing**: All 40 preview unit tests in `tests/test_ui/test_bfn_preview_widget.py` pass cleanly.

## [0.3.131-dev] - 2026-09-23

### 🚀 Added & 🛠️ Improved
- **Bidirectional Proportional Preview Scaling & Aspect Ratio Lock**:
  - **1:1 Scaling with Background**: Re-engineered font rendering scale calculation in `ui/components/bfn_preview/paint_mixin.py` to strictly couple with frame transformation `fit` (`scale_factor = (game_font_y / cell_h) * fit` or `fixed_font_scale * (fit / base_fit)`). Text and background frame now scale in lockstep bidirectionally (both when expanding and shrinking) preserving the exact 100% visual proportion without one-sided scale clamping or overflowing.
  - **Custom Background Geometry Locking**: Preset frame bounds and fit calculations now dynamically bind to custom background image transformation properties (`bg_scale / 100.0`, `bg_offset_x`, `bg_offset_y`) when a background image is active, keeping frame boundaries and text positions aligned with the custom backdrop.
  - **Anti-Clipping Offscreen Buffer Expansion**: Expanded offscreen QImage rendering buffer bounds (`img_w = max(1, abs_rect.width(), int(round(total_width * scale_factor + 40)))`, `img_h = max(1, abs_rect.height(), int(round(total_height * scale_factor + 40)))`), preventing edge text, shadows, and glyph descenders from being cut off during high-zoom rendering.
  - **Dynamic Preview Sidebar Button Scaling**: Implemented height-responsive button resizing in `BfnPreviewSideBar` (`resizeEvent`), dynamically scaling icon buttons from 28px down to 24px and 20px when preview panel height decreases below 215px and 165px. Prevents button overlapping at compact splitter heights without enforcing rigid min-height window locks.
  - **Mouse Wheel Zoom & Reset Shortcut**: Added Ctrl+Wheel wheel event handler for smooth background zooming (±5% steps) and a "Reset Scale (100%)" action to the preview context menu (localized in English and Ukrainian).
- **Multi-Language ROM Discovery & Automatic ISO Extraction**:
  - **Automatic Wii/GC ISO Extraction via `wit`**: Integrated `_try_extract_iso_messages()` in `plugins/zelda_bmg/reference.py`, allowing users to select an `.iso` file directly. Picoripi automatically locates `wit.exe` and extracts message files (`+*Msg*`) seamlessly into an extracted folder.
  - **Deep Recursive Directory Scanning**: Enhanced folder scanning using recursive patterns (`**/Msg*` and `**/msg*`) to locate deeply nested PAL message folders (`Msgde`, `Msgfr`, `Msgit`, `Msgsp`, `Msguk`) without requiring precise navigation down to the `res/` directory.
  - **PAL Russian (`Msguk`) Priority Mapping**: When official PAL languages (`Msgde`, `Msgfr`, etc.) are detected alongside `Msguk`, `Msguk` is accurately prioritized and mapped as `Russian (RU)` with `cp1251` single-byte encoding (since European PAL Russian fan localizations replace UK English).
  - **Direct ISO Selection Prompt**: Enhanced the reference selection prompt (`_prompt_load_multi_reference_rom`) in `MainWindowEventHandler` to allow selecting `.iso` GameCube/Wii images in addition to unpacked directories.


## [0.3.130-dev] - 2026-09-23

### 🚀 Added & 🛠️ Improved
- **Multi-Language ROM Discovery & Cyrillic Encoding Fix**:
  - **Direct BMG Decoding Without Mojibake**: Added `override_encoding` support to `BMGFile.load(data, override_encoding=...)` in `bmg_tool.py`, allowing BMG files with Cyrillic cp1251 characters to be parsed directly into unicode strings without lossy intermediate cp1252 re-encoding.
  - **Accurate Language Identification**: Mapped `Msg`, `Msg_RU`, `Msg_US`, `Msg_UK`, `Msg_EN`, etc. to `Russian (RU)` with `cp1251` encoding in `plugins/zelda_bmg/reference.py`, eliminating the previous `Reference ()` fallback tab label.
  - **Smart Sibling & Recursive Directory Scanning**: When selecting a specific language directory (such as `.../res/Msg`), `load_zelda_bmg_multi_reference` now automatically traverses parent and sibling directories, discovering all localized PAL folders (`Msgde`, `Msgfr`, `Msgit`, `Msgsp`, `Msgjp`) simultaneously.
- **Editor Height Alignment & Vertical Space Optimization**:
  - **Compact 2-Row Header Layout**: Re-engineered `header_grid` in `_build_edited_panel()` into a sleek 2-row layout (Row 0: `Window` + `Chapter` on left, Navigation/AI/Fix actions on right; Row 1: `Speaker` on left, Font/Max-width/Apply on right).
  - **Raised Editors**: Raised both text editors by over 35 pixels, eliminating excessive top padding and blank vertical space.
  - **Clean Left Header**: Removed the redundant `Original / Reference` title above the multi-language tabs and removed top stretch padding.
  - **Dynamic Level Alignment (`HeaderSyncFilter`)**: Updated `HeaderSyncFilter` to dynamically compute `left_header.height = right_header.height - tab_bar.height`, ensuring the top edge of text editing areas across left and right panels starts at the exact same vertical Y level across all screen resolutions and DPI scaling.
  - **Aligned Middle Panel Buttons**: Adjusted spacing in `_build_middle_panel()` so the revert string button aligns directly with Line 1 of both text editors.

## [0.3.129-dev] - 2026-09-23

### 🚀 Added & 🛠️ Improved
- **Automatic Background Synchronization for Picoripi Companion**:
  - **Automatic Pull on Project Open**: When opening any project or recent project, Picoripi automatically pulls the latest reviewed glossary terms from the remote Companion server in the background, updates local `glossary.json` (with automatic `.bak` backup), hot-reloads the glossary manager and open review dialogs, and notifies the user via statusbar.
  - **Automatic Push on Save & Exit**: Whenever changes are saved, a project is closed, the glossary review window is closed, or the application exits, Picoripi pushes current terms, context occurrences, and reference translations to the Companion server so mobile devices immediately receive the freshest data.
  - **Non-Blocking Architecture**: Integrated `CompanionPullWorker` and `CompanionPushWorker` via `QThread`, preventing UI freezes and safely tolerating network unavailability or offline servers without disruptive pop-up errors.
  - **Configurable Auto-Sync Toggle**: Added `companion_auto_sync` option and a dedicated checkbox *"Automatically sync on project open and close"* in **Settings ➔ Companion**.
  - **Unit Testing**: Added lifecycle unit tests in `tests/test_companion/test_companion_sync_client.py` for background pull/push workers and offline/online scenarios.

## [0.3.128-dev] - 2026-09-23

### 🚀 Added & 🛠️ Improved
- **Picoripi Companion: Mobile Web PWA & Synchronization Server**:
  - **Companion Server (`companion/server/`)**:
    - Lightweight, high-performance FastAPI service running natively on Ubuntu Linux (systemd) or Docker (`docker-compose.yml`).
    - Project storage manager (`StorageManager`) with automated `.bak` backups before every modification, project metadata, and atomic JSON persistence.
    - RESTful API supporting PIN/token authentication (`/api/auth/login`), project listing (`/api/projects`), full-fidelity glossary sync (`/api/sync/push`, `/api/sync/pull`), category filtering, "Needs review" querying, in-game occurrence lookups, and term update endpoints.
  - **Mobile Web App PWA (`companion/web/`)**:
    - Mobile-first, responsive Single Page Application optimized for touch targets (48px) and safe areas on iOS Safari and Android Chrome.
    - Full PWA support: web app manifest, maskable SVG icon, and "Add to Home Screen" standalone app mode.
    - **Glossary List View**: Horizontal scrolling category pills (`All`, `Characters`, `Locations`, `Items`, etc.) with counts, live debounced search, "Needs review" filter toggle, and responsive term cards with status and variant count badges.
    - **Term Review & Editor Screen**:
      - Previous/Next navigation with progress counters.
      - Original term card (`О:`) with one-tap clipboard copy.
      - Large translation input (`П:`).
      - Primary action: **"✓ Confirm & Next"** button to confirm status, save, and immediately advance to the next unreviewed term.
      - Candidate Variants: interactive cards displaying proposed AI translations and rationales; tapping applies the variant to the translation field immediately.
      - Context & Lore: collapsible sections for dynamic lore description with real-time `{{TERM}}` substitution, AI and editable user notes, and in-game occurrences with English quotes and Russian reference translation blocks.
  - **Desktop Integration (`core/companion_sync.py`)**:
    - Built-in `CompanionSyncClient` with push/pull operations, server health tests, and automatic `.bak` backup protection.
    - Added **`[☁ Companion Sync...]`** action button to `GlossaryDialog` for 1-click push and pull with instant view hot-reloading.
    - Added **Companion** tab to Application Settings (`SettingsCompanionMixin`) for configuring server URL, API token, and testing connection.
  - **Testing**:
    - Added unit test suite in `tests/test_companion/test_companion_server.py` covering storage, backup creation, authentication, filters, and sync endpoints.
    - Added unit test suite in `tests/test_companion/test_companion_sync_client.py` covering push, pull, backups, and error handling.
    - Added UI test `TestGlossaryCompanionSyncButton` in `tests/test_components/test_glossary_review_ui.py`.
- **Unpacked Multi-Language ROM Reference Loading (PAL Multi-5 Support)**:
  - **Multi-Language Detection & Extraction**: Added `load_zelda_bmg_multi_reference` to `plugins/zelda_bmg/reference.py` and `BaseGameRules.load_multi_reference` to automatically discover localized message folders in unpacked ROMs (`root/res/`, `files/res/`, `res/`).
  - **Smart Region & Language Mapping**:
    - English directories (`Msguk`, `Msgus`, `Msgen`, `Msge`) where Russian translation replaced English are decoded as single-byte `cp1251` and labeled `Russian (RU)`.
    - Native European multi-language folders (`Msgde`, `Msgfr`, `Msgit`, `Msgsp`, `Msgjp`) are loaded with `cp1252` (and Shift-JIS for Japanese) as `German (DE)`, `French (FR)`, `Italian (IT)`, `Spanish (ES)`.
    - Single patch directory fallback: if no multi-language folders are found, the folder is loaded as a single reference patch.
  - **Dynamic Multi-Language Tabs in Editor**:
    - Enhanced `source_tab_widget` (`ui/updaters/text_views_mixin.py`) to dynamically generate read-only comparison tabs for every detected reference language (`Original (EN)`, `Russian (RU)`, `German (DE)`, `French (FR)`, `Spanish (ES)`, `Italian (IT)`).
    - Synchronized line navigation across all language editors while preserving scroll, cursor, and active tab index.
  - **Multi-Language Context for AI Translation Prompts**:
    - Injected `reference_translations` into batch translation payloads (`handlers/translation/prompt_composer/batch_mixin.py`).
    - Added structured `REFERENCE TRANSLATIONS (from other official releases / reference patch for context)` block into single string translation and variations prompts (`handlers/translation/prompt_composer/messages_mixin.py`).
    - Provides LLMs with crucial multi-lingual context on honorifics/politeness (German "du/Sie", French "tu/vous") and grammatical gender/number.
  - **UI Menu & Event Integration**:
    - Added **"Load Unpacked ROM (Multi-Language Reference)..."** action (`load_multi_reference_rom_action`) to the **File** menu.
    - Persisted unpacked ROM path in `project_settings.json` (`reference_patch_path`) and automatically reloaded all reference languages on project open.
    - Updated UI localization in `locales/en.json` and `locales/uk.json`.
  - **Testing**:
    - Added comprehensive unit tests in `tests/test_core/test_multi_reference.py` covering multi-language extraction, `cp1251`/`cp1252` encodings, and delegation.
    - Added `test_update_text_views_populates_multi_reference` in `tests/test_ui/test_source_tab_widget.py`.
    - Added prompt reference translation verification in `tests/test_handlers/test_ai_prompt_composer.py`.

## [0.3.127-dev] - 2026-09-22

### 🚀 Added & 🛠️ Improved
- **Glossary Reference Translation Variant & AI Notes Isolation**:
  - **Reference Variant Isolation**: External patch reference variants (such as `Желе зелёного чу — RU патч v2.0`) in `GlossaryDialog` (`_variants_list`) are visually isolated with distinctive styling (cyan/blue text `#0284c7` / `#38bdf8`, italic font, distinct tooltip).
  - **Context-Only Protection**: Disabled double-click application and the "Apply selected variant" button for reference variants, guaranteeing that reference text cannot accidentally overwrite the translation editor or trigger early settlement.
  - **AI Notes Categorization**: Reference variants in `_ai_notes_for_entry` are separated from target translation options into an explicit `Russian reference translation (for context):` section instead of being mixed into `Defensible translation choices:`.
  - **Mention Counterpart Auto-Fallback**: If no explicit Russian variant exists in the glossary entry, the system automatically checks `_reference_data` for the first dialogue mention string and supplies `Russian reference context (from mention string):\n"{line}"` to ensure full context.
- **Preview Proportional Scaling & Overlap Prevention**:
  - **Sidebar Height Constraints**: Enforced `MIN_HEIGHT = 230px` on `BfnPreviewSideBar` and `BfnPreviewWidget`, plus minimum height on the preview column splitter (`260px`), preventing vertical button overlap when the preview column is resized.
  - **Proportional Text Scaling**: Ensured text scales down proportionally with dialog frame `fit` even when `fix_font_scale` is enabled (`scale_factor = self.fixed_font_scale * fit`), keeping dialogue text neatly inside the frame box on window resize rather than overflowing.
- **Testing**:
  - Added `TestGlossaryReferenceVariantsAndNotes` in `tests/test_components/test_glossary_review_ui.py` covering:
    - Reference variant styling, italic font, and disabled apply/double-click operations.
    - Separation of reference variants in AI notes.
    - Fallback to reference context from mention strings when no variant exists.
  - Added tests in `tests/test_ui/test_bfn_preview_widget.py` for sidebar minimum height and proportional scaling.

## [0.3.126-dev] - 2026-09-22

### 🚀 Added & 🛠️ Improved
- **Reference Translation Counterpart in Glossary Occurrences**:
  - Threaded loaded reference patch data (`AppDataStore.reference_data`) into `GlossaryDialog` and `TableMixin.reload_data(...)`.
  - For every dialogue occurrence in the glossary list (`_occurrence_list`), displayed the corresponding translation phrase from the reference patch (e.g. Russian patch v2.0) in an eye-catching colored badge container (`RU:` with soft sky blue background).
  - Implemented smart term highlighting (`_highlight_russian_term`): if a 100% confident direct match for the glossary term is found in the Russian text (via exact word-boundary match or Slavic noun/adjective inflection), the term is highlighted with an underlined amber style.
  - Full context preservation: if no direct term match is found with 100% certainty, the complete Russian phrase is displayed without truncation or premature elision, ensuring the translator has the entire dialogue context.
  - Removed the artificial 120-character preview truncation on occurrences to prevent cutting off essential narrative context.
  - Enhanced English occurrence preview to highlight the target term directly in `EN:` lines for mention occurrences.
- **Robust Mock-Free UI Tab Counting**:
  - Hardened `_do_update_text_views` in `ui/updaters/text_views_mixin.py` to safely verify tab count without raising type comparison errors against mock objects in test suites.
- **Testing**:
  - Added `TestGlossaryReferenceOccurrences` in `tests/test_components/test_glossary_review_ui.py` covering:
    - Rendering of the `RU:` block when reference data is present.
    - Direct term highlighting within the Russian text.
    - Full phrase context display without truncation when direct match is absent.
    - Clean omission of `RU:` block when reference data is not loaded.
    - Hot-reloading of reference data in an open dialog.

## [0.3.125-dev] - 2026-09-22

### 🚀 Added & 🛠️ Improved
- **Plugin-Driven Reference Translation Architecture**:
  - Decoupled game-specific reference patch loading from `core/reference_manager.py` to adhere strictly to Picoripi's plugin architecture ("the mechanism is general, but the concrete implementation is in the plugin").
  - Added reference patch lifecycle hooks to `BaseGameRules` in `plugins/base_game_rules.py`:
    - `supports_reference_patch() -> bool`: whether the plugin supports loading external reference translation patches (default: `False`).
    - `get_reference_language_label() -> str`: display label for the reference tab (e.g. `'Russian (RU)'`, `'German (DE)'`; default: `'Reference (RU)'`).
    - `load_reference_patch(patch_path, block_names) -> Dict[Tuple[int, int], str]`: parses and maps patch texts to project blocks (default: `{}`).
  - Created `plugins/zelda_bmg/reference.py` encapsulating all Nintendo GameCube/Wii Zelda BMG specific logic:
    - RARC archive extraction (`bmgres*.arc` / `Msg/*.arc`).
    - Binary BMG decoding with `windows-1251` (`cp1251`) single-byte encoding.
    - Escape tag conversion (`{escape:...}`).
    - Dynamic mapping between `zel_XX` resource names and project block indices.
  - Implemented `supports_reference_patch`, `get_reference_language_label`, and `load_reference_patch` in `plugins/zelda_bmg/rules.py`.
  - Refactored `ReferenceManager` (`core/reference_manager.py`) into a clean, game-agnostic coordinator that delegates loading and labeling to the active plugin.
  - Updated `ui/builders/layout_builder.py` and `ui/updaters/text_views_mixin.py` to dynamically synchronize the reference tab title with the active plugin's language label.
  - Updated `tools/extract_ru_glossary_variants.py` to instantiate the active plugin and use `ReferenceManager.load_reference`.
- **Capability Documentation & Propagation (Mandatory)**:
  - Updated `docs/PIPELINE_ROADMAP.md` section 2.2 with the new reference patch hooks.
  - Updated `docs/PLUGIN_AUTHORING_GUIDE.md` section 4 with `supports_reference_patch`, `get_reference_language_label`, and `load_reference_patch`.
  - Updated `plugins/default_plugin/AI_PLUGIN_ASSISTANT_PROMPT.md` question 8 to prompt new plugin authors about existing translation patches.
- **Testing**:
  - Updated `tests/test_core/test_reference_manager.py` with tests for delegation to `BaseGameRules`, `ZeldaBmgRules` declarations, and `_extract_bmg_messages`.
  - Updated `tests/test_ui/test_source_tab_widget.py` for flexible reference tab labels.

## [0.3.124-dev] - 2026-09-22

### 🚀 Added & 🛠️ Improved
- **Reference Translation Tab (Russian / RU) in Editor**:
  - Replaced the single `original_text_edit` in the translation editor layout with a tabbed container (`self.mw.source_tab_widget`, `QTabWidget`) containing **"Original (EN)"** (`original_text_edit`) and **"Russian (RU)"** (`reference_text_edit`).
  - Added full line width/font metrics synchronization and event filters to `reference_text_edit`, including support for tag hiding (`Ctrl+Q`), line numbering, and soft shading.
  - Implemented smart text copying: clicking the revert/copy button (`→`, `revert_string_button`) now contextually copies the active reference text into `edited_text_edit` when the **Russian (RU)** tab is selected, or original English text when the **Original (EN)** tab is selected.
- **Reference Manager & External Patch Integration**:
  - Created `core/reference_manager.py` with `ReferenceManager` to load external reference patches (such as GameCube/Wii Russian translation patches containing `bmgres*.arc` files).
  - Implemented in-memory RARC archive extraction and BMG binary decoding using `windows-1251` (`cp1251`) encoding, converting raw BMG escape sequences to Picoripi tag format (`{escape:...}`).
  - Mapped reference BMG blocks directly to project blocks (`AppDataStore.reference_data` keyed by `(block_idx, string_idx)`).
  - Added project setting `reference_patch_path` in `core/settings/plugin_settings.py` for persistent configuration per project.
  - Added **"Load Reference Translation Patch..."** menu action under the **File** menu (`load_reference_patch_action`) with file picker dialog.
- **Multi-Pass Russian Glossary Variant Extractor**:
  - Implemented `tools/extract_ru_glossary_variants.py` to extract corresponding Russian translations and populate `translation_variants` in `glossary.json` with `rationale="RU патч v2.0"`.
  - Uses 4 extraction strategies: exact standalone matching, tagged/colored span extraction (`{escape:255:...}`), character name frequency analysis across speaker lines, and clean multi-word phrase matching.
  - Successfully extracted **692 Russian terminology variants** into the Twilight Princess project glossary with automatic backup creation (`glossary.json.bak`).
- **UI Localization (i18n)**:
  - Added English and Ukrainian translations in `locales/en.json` and `locales/uk.json` for all new UI strings:
    - `"Original (EN)"` / `"Оригінал (EN)"`
    - `"Russian (RU)"` / `"Російська (RU)"`
    - `"Load Reference Translation Patch..."` / `"Завантажити референсний переклад..."`
    - `"Select Reference Translation Patch Directory"` / `"Оберіть папку референсного перекладу"`
    - `"Loaded {count} reference strings from patch."` / `"Завантажено {count} референсних рядків із патчу."`
    - `"Reference Translation"` / `"Референсний переклад"`
    - `"No reference translation found in selected folder."` / `"У вибраній папці не знайдено референсного перекладу."`
- **Testing**:
  - Added `tests/test_core/test_reference_manager.py` for testing archive discovery, BMG parsing, `cp1251` decoding, and block mapping.
  - Added `tests/test_ui/test_source_tab_widget.py` for testing tab switching, UI text updating, and contextual copying (`→` button).
  - Added `tests/test_core/test_glossary_ru_variants.py` for testing multi-pass extraction and variant merging.
  - Verified with full test suite passing across UI and Core test lanes.

Older entries: `docs/history/changelog/<YYYY-MM>.md` (archive — grep only).
