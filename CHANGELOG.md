All notable changes to the **Picoripi** project will be documented in this file.

## [Unreleased]

- New plugin `paper_mario_nx` — Paper Mario: The Thousand-Year Door (Switch, 2024): the 46 EU English MSBT files (14,885 messages) open with tags named from the game's `msg.msbp` and save byte-exact when unedited; the eight fonts (BFFNT, now also BC5 outline fonts, and `.bfotf`) in the Font Editor; every UI texture in the Textures window (BC1/3/4/5/7 and ASTC 8x8, which now encodes like 12x12); MSBT tag strings start on an even byte and take `s32` arguments. The workspace scripts unpack base + update and pack everything back into a LayeredFS mod; seen in Eden: title text, two fonts and the title logo edited at once.
- Tears of the Kingdom ready for translation: ASTC textures (`core/texture_formats/astc.py`: every LDR block decodes, 4x4 blocks encode) and RGB565 in BNTX, so the English title logos open in the Textures window and an imported PNG saves and builds; the Font Editor saves edited widths and redrawn glyphs of scalable `.bfotf` fonts (CFF code moved to `core/font_formats/cff.py`); SARC rebuild keeps each file's own alignment (an edited layout archive lost its logo in game). Checked in Eden: text, font and logo edits on the title screen.
- Real-data tests and the Twilight Princess dump fallbacks (`zelda_bmg` reference tools, window frames, stage scene data) follow the new workspace layout `E:\Emulators\RomHacking\<Series>\<Game>` (a platform subfolder only when a game has several versions) (shared scripts in `_shared\scripts`).
- Twin Snakes (`mgs_ts`): menu and HUD pictures in the Textures window — `stage.dat` opens as an archive (`plugins/mgs_ts/stage_dat.py`: texture packs read as TPL, only changed folders re-deflated, a stage that still fits stays in place, unedited = the original bytes); `texture_sources.json` lists the text textures of 52 stages (the workspace copies each out as `texture\<stage>.stage`); a texture source's `texture` glob takes `{2,5,7}`; HUD words (`mgso.rel`) take Ukrainian capitals through redrawn ASCII cells of the HUD font (`rel.HUD_LETTERS`). Seen in Dolphin: Ukrainian title menu, difficulty and radar select, options.
- New plugin `zelda_tingle` — The Wind Waker's Tingle Tuner (the GBA text): `res/Gba/msg_LZ*.bin` of the US and European discs (1,086 messages, GBA LZ77, the game's own glyph codes) open with readable codes, a 96 px / 6-line layout and save byte-exact when unedited; an edited text is packed again (own optimal LZ77, `core/containers/lz10.py`) and refused when it outgrows the GBA's buffer. The USA client program `client_u.bin` gives its two own lines and its font: new Font Editor format `gba_tiles` (GBA tiles inside the LZ77-packed multiboot program), Ukrainian letters on free glyph codes and on accent codes pointed at free tiles. Checked in Dolphin with its built-in GBA: Ukrainian text in the Tingle Tuner window.
- New plugin `vagrant_story` — Vagrant Story (PlayStation, USA): events, room scripts, menus, item names and descriptions, Quick Manual, Monster Book, room names and the names in program and zone data (6,018 English strings, plus 119 ASCII HUD words kept ASCII) from the workspace's `source`, with readable control tags, balloon width limits read from the scripts, text growth inside tables and scripts, byte-exact unedited saves, scene names of rooms and the Russian fan translation (Reborn 1.5f) as the reference language; Ukrainian letters through `translation_map.json` (cells English never uses). Font Editor: new format `vagrant` (the 12x12 text font, regular and italic sets, advances included); seen in DuckStation: a Ukrainian line in the game's first balloon.
- New plugin `paper_mario_gc` — Paper Mario: The Thousand-Year Door (GameCube, USA): the 260 message files of `msg/US` (13,018 English messages) open with the game's tags in braces and save byte-exact when unedited (Japanese leftovers kept as they are); speakers of 3,472 messages from the area modules' event scripts (`context.json`, `python -m plugins.paper_mario_gc.context_builder`), Goombella's tattles, scenes by chapter and area, width and lines per window kind, glossary seed (party, items, badges, enemies, places, characters), the `papermarioset_US.bfn` font with the Ukrainian alphabet in unused Latin-1 slots and 188 text textures; seen in Dolphin (opening narration, memory-card prompt).
- New plugin `yokai_watch` — Yo-kai Watch (3DS, USA): the 2005 English Level-5 `cfg.bin` tables (42,702 strings: story events for both heroes, map NPCs, Medallium, items, skills, quests, menus) open with the game's `<...>` codes shown as `{PAGE}`, `{PNAME01}`, `{CG}…{/C}` and real line breaks, and save byte-exact when unedited (growth moves the string table); Japanese leftovers and passwords stay out of the editor; speakers from the game's own tables (99.7 % of event lines, 68 % of map NPC lines), scenes by event / map / chapter, width limits measured on the English text with the game font, a glossary seed (Yo-kai with their Medallium text, people, items, skills, abilities, tribes, places). Font Editor: Level-5 XF fonts (`xf`; new characters, byte-exact unedited); Textures window: Level-5 IMGC textures (`imgc`, also inside XPCK packs, `core/containers/level5.py`); Level-5 compression (LZ10, Huffman, RLE, zlib). Yo-kai Watch 3 (3DS, EUR) uses the same plugin: told apart by its source layout, 5,641 English files (140,904 strings) byte-exact, speakers also from the voice clip a line plays (`<PV#pv_c001000_23>`: character ids are the CRC32 of the model name), its own width limits and width maps.
- New plugin `zelda_fsae` — Zelda: Four Swords Anniversary Edition (DSiWare, Europe): the 220 messages of `eu.kmsg` (KMSG: UTF-8 with aligned `0x7F` control codes) open one block per id range with readable tags (`[speaker:1]`, `[wait:120]`, `[next:90]`, `[close]`, `[icon:N]`, `[color:N]`…), only the English (EU) slot is shown and saved and an unedited file stays byte for byte; speakers from the speaker code and the Great Fairy messages, line widths from the game font, the Russian build and the game's other languages as reference languages. Font Editor: Nintendo DS NFTR fonts (`nftr`): every glyph shown, byte-exact unedited, a letter typed into a spare cell becomes a new glyph with its widths and character code.
- The Wind Waker HD (`zelda_ww`): reference languages — Load Reference Patch with a folder of `permanent_2d_<Region><Language>.pack` files shows the game's French and Spanish and the Russian patch (as `permanent_2d_RuRussian.pack`), Russian first, matched by file and label (all 5,040 messages of the USA game in each).
- Twin Snakes (`mgs_ts`): the HUD words of the game module `mgso.rel` (LIFE, O2, item and weapon box labels, boss names; 80 strings) open as one block and save in place — ASCII only, never longer than the game's slot (seen in Dolphin: a changed LIFE on the life bar); the workspace unpacks it to `common\mgso.rel`.
- Twin Snakes (`mgs_ts`): checked in the game (Dolphin, input movies): codec, options help and Ukrainian letters show; the game wraps a too-wide row mid-word, so the width limit is now the codec box (509 font units, measured) for codec lines and the widest English row of the neighbouring strings (no slack) for menu and item text, instead of the widest row of the whole file + 5 % (item descriptions were allowed twice their window).
- Twilight Princess / Wind Waker layout previews: GX textures are decoded by the shared codecs — IA8, RGB565 and RGB5A3 used 8x4 tiles instead of 4x4, C14X2 was missing, and a BTI's palette format was read from the wrong byte.
- New Textures window (Tools → Textures…) for text drawn into game textures: the plugin's `texture_sources.json` (hook `get_texture_sources`) lists them with thumbnails, original next to translated and a status per texture; Export PNG / Import PNG (or a whole folder) / Revert; the redrawn image is encoded into the game's own format (`core/texture_formats`: BTI and TPL, 3DS BFLIM/BCLIM, CTPK and Grezzo CTXB in ZAR/GAR/LzS archives, Wii U BFLIM, Switch BNTX, Koei G1T, N64 textures in the ROM incl. Majora's Mask `yar` archives; GX, PICA incl. ETC1/ETC1A4, BC1–BC5 and a BC7 encoder) and written into the translation copy with the archives around it repacked; unchanged blocks keep their bytes. Texture lists for WW (151 textures), TP GC/Wii, WW HD, OoT/MM N64, HWDE, CoH, TotK (BC4 masks); 3DS files open directly. SARC moved to `core/containers/sarc.py`.
- New plugin `zelda_sshd` — Zelda: Skyward Sword, HD (Switch) and the Wii original in one plugin (told apart by the source folder): the big-endian MSBT text the workspace unpacks from the U8 `.arc` archives (HD 8,279 English messages, Wii 8,035) opens with tags named from the text itself (`{heroName}`, `{color:Red}`, `{item:11}`, `{icon:41}`, `{wait:15}`, `{choice1:65535}` …) and saves byte-exact when unedited; speakers from the HD's ATR1 speaker byte, Fi's window and one-character files (by file + label, so the Wii gets them too); conversations from the MSBF flows; line limits per window kind measured on the English text of each version (the game breaks an over-long line mid-word); the official Russian and 12 other languages as reference languages, matched by label (96.8 % of the Wii lines from the HD). Font Editor: Wii BRFNT fonts (`brfnt`: GX I4/I8/IA4/IA8 sheets, new characters and sheets), byte-exact unedited; Render Font with baseline alignment now stands rendered letters on the font's own Latin baseline (`font_formats.align_to_latin`). Shared code moved to `plugins/common` (`msbt.py`, `lms_tags.py`, `msbp.py`); U8 archives with folders now open (the folder walk started at the parent index) and an edited archive keeps its original end.
- Twilight Princess on Wii and Wii U (HD) in `zelda_bmg`: their message archives are the GameCube format with the same message ids, so they open with the same speakers, scenes and flow context and save byte-exact (tests on the real Wii disc and the HD archives); the HD-only Wii U control tags (group 7) read as `{U:ZL}`, `{U:L stick}`… and count 24 px. The BFN code (Font Editor, preview, widths) reads the HD fonts: I8 sheets, split maps (several MAP1 blocks, the first holding a code wins) and type-3 maps as the file's (code, glyph) pairs.
- The Wind Waker HD (Wii U) in `zelda_ww`: the 68 MSBT files of `permanent_2d_UsEnglish.pack` (5,040 messages) open with readable tags from the game's `CKing.msbp` (`[Red]…[/C]`, `[Name]`, `[Wait:10]`) and save byte-exact when unedited; speakers, box widths (875 / 812 units by balloon type), conversations (NextNo) and glossary terms come from the messages' own attributes; the Font Editor opens Wii U BFFNT (`bffnt_wiiu`: big-endian, GX2-tiled BC4 sheets), adds characters and blank sheets (`min_sheets`). Kruptar `.txt` projects open as before.
- Hyrule Warriors DE fonts: the advance of each letter is the game's own table in its executable (two f32 tables, `font_eu` and `font_eu_p`), not the atlas ink. The Font Editor shows and edits those widths and Save writes them as IPS32 executable patches `exefs/<build id>.ips` (1.0.0 and the update) in the translation folder, which the workspace build puts into the mod's `exefs_patches`; the width checks read the same widths. Ukrainian letters on narrow cp1252 cells no longer overlap (checked in Eden).
- Ocarina of Time / Majora's Mask: the Ukrainian letter cells (`translation_map.json`) are confirmed against the US ROMs: no English message or credit, no text the code prints, no name entry and no SoH/2Ship message uses them, and every glyph fits its cell (`translation_map.md` in each plugin, and a test that counts the cells in the ROM).
- Startup: opening a Hyrule Warriors DE project took 39 s (frozen window) and takes about 3.5 s. Asking the speaker of each of 106,128 lines parsed the whole 12-language file again for each of its 776 tables and rebuilt every table to check it; now a file is parsed once, files without subtitles or voice lines are told apart by their English tables alone, speakers are kept per table, and the byte-exact rebuild check runs only before a save.
- Zelda: Tears of the Kingdom checked on the real 1.4.0 game: every one of the 47,799 English messages loads and saves byte-exact (an unedited project writes nothing); group 1 tags read `{pause:30}`, `{textSpeed:0.5}`, `{autoAdvance:90}`; speakers for ~69% of the event lines from the game's event flows and cutscene timelines (English names from its character list); the game's other languages (Russian first) as reference languages; line widths from the dialogue font (talk window 1000 px, cutscene subtitles 1290 px); the resource size table follows the game's own rule (text and font archives); the Font Editor opens the scalable `.bfotf` fonts (view, byte-exact) and `plugins/zelda_totk/font_glyphs.py` adds І і Ї ї Є є Ґ ґ to the fonts that lack them.
- New plugin `mgs_ts` — Metal Gear Solid: The Twin Snakes (GameCube, USA): codec calls (`codec.dat`), stage scripts (`*.gcx`: menus, briefing, item descriptions, credits) and cutscene / voice / movie subtitles (`*.subs`) from the workspace's `source\text`; only the English strings of the six languages are shown (found by voice clip or language detection), speakers come from the game data, longer text takes the room of the unused French–Spanish strings, unedited files stay byte for byte. Font Editor: new format `mgs` (the game's 2bpp proportional text font, glyph widths and descender shift editable).
- Startup, every plugin: a disabled spellchecker no longer parses its dictionary (an enabled one parses it after the window is up) — the window is built in 0.2 s instead of 1 s; the text files of each source archive are remembered in `<project>/archive_scan.json` (by file time and size), so an unchanged archive is not read and unpacked at every open — The Wind Waker (GameCube, 1322 archives) opens in 1.2 s instead of 3.6 s.
- Font Editor opens the 3DS Zelda fonts with File → Open: BCFNT / 3DS BFFNT (A Link Between Worlds, Tri Force Heroes; A4/A8/L4/L8/LA4/LA8 sheets), Grezzo QBF (Ocarina of Time 3D) and GZF (Majora's Mask 3D); unedited fonts save byte-exact, and typing a letter into an empty cell adds that real character (CMAP/CWDH blocks, a sorted QBF/GZF table).
- Font Editor: Render System Font takes a TTF/OTF file without installing it (Font File...) and can thicken strokes; Move glyph (arrow buttons, Ctrl+Arrow) shifts glyph pixels with undo in every format; selecting a cell on a non-square sheet (N64, G1T) picks the right glyph; Wind Waker's name-entry (Yaz0 inside `nameres.arc`) and system fonts are listed; Ocarina of Time / Majora's Mask save Ukrainian through a reviewable `translation_map.json` (look-alikes on Latin glyphs, other letters on accented/punctuation slots by width) and The Wind Waker ships one (cp1251 positions, never 0x80–0x9F).
- New plugin `zelda_coh` — Cadence of Hyrule (Switch): the 1,809 strings of `localization.xml`, one block per id range, saved as a LayeredFS mod with only the edited English strings replaced (an unedited file stays byte for byte); speakers and glossary terms from the string keys and id ranges; the six `.bffnt` fonts in the Font Editor.
- Font Editor, Switch BFFNT: a font can get new characters — a `min_sheets` font source opens with spare sheets, a letter typed into an empty cell becomes that real character (as in the 3DS and G1N fonts: one rule, `font_formats.adds_glyphs`), and saving adds the used sheets as texture layers with their widths and character map (`LoveBug.bffnt` of Cadence of Hyrule showed Cyrillic in Eden this way).
- New plugin `zelda_aoc` (Hyrule Warriors: Age of Calamity, Switch): opens the game's text as per-table bundles cut out of `data/LinkData2.bin` (12 or 13 languages, UTF-8, the game's `[tags]` with `[es:1_5_1]` for name-form codes), shows and saves the English table byte-exact when unchanged (battle dialogue also into the second English table), speakers from the battle-dialogue speaker ids, glossary seed from the names/places/items tables, per-table width limits; the Font Editor opens, edits and saves the game's G1N fonts and adds glyphs for characters the font lacks (a new glyph typed as «Ж» gets the code of «Ж»).
- Startup: opening the Twilight Princess project took 17.5 s and takes under 6 s. The reference languages were parsed twice (project settings are read more than once; the same request now reuses the result), each archive was decompressed two or three times (format detection now decompresses four bytes), every string re-scanned the whole alias table and checked `translation_map.json` on disk (now at most once a second); Yaz0 decompression copies runs in blocks and BMG text parsing jumps to the next terminator.
- The review pass is on by default (new key `review_enabled`; `false` turns it off). The old `editor_review_enabled`, saved as `false` in existing settings, belonged to the removed editor review and is no longer read.
- Ocarina of Time / Majora's Mask (N64): line widths take a character's width from the Font Editor's map of the game font (`<project>/font_maps/oot_font.json` / `mm_font.json`) when the project has one, so redrawn or Ukrainian letters are measured; the game's table stays the fallback.
- Player names, per game: Ocarina of Time, Majora's Mask (`{name}`) and Tears of the Kingdom (`{playerName}`) send the hero's tag as the declined name «Лінк» through a `{F:Link}` force alias, like Twilight Princess and The Wind Waker; Hyrule Warriors has no player-named hero.
- Review pass replaces the editor review: a second request per chunk in the translation's own conversation (rules, glossary rows, speakers, addressees, scene) asks the model to fix only real errors in its draft and return the corrected lines with a reason; corrections pass the draft's checks or the draft stays. `review_model` may name another model. The context-blind editor review and its `editor_review` prompt section are gone. Off by default (`editor_review_enabled`); on the proofread Minish Cap its changes were better in 13 of 20 blind comparisons.

- Player names, per game: Minish Cap and The Wind Waker send the hero's tag as the declined name «Лінк» (force alias, as Twilight Princess already did); Minish Cap draws that name green, so it goes out and comes back as `{Color:Green}…{Color:White}` — the new plugin hook `get_force_alias_wrapping`. The tag warning no longer counts those colour tags as extra. Twilight Princess and The Wind Waker do not colour the name (checked on their game text and the Russian translations).

- AI translation refuses a reply that leaves a line in the source language (more than half of four or more source words still there): the model sometimes translated only the glossary term («You bought a шматочок пирога! One bite…»); the chunk is retried with that reason.
- Minish Cap: `{Player}` in a reply no longer turns into `{original}` — restoring tag aliases now skips aliases that are bare words (the plugin maps "player" → "original" for its tag checker, and the case-insensitive restore hit "Player" inside the tag).
- Projects: a file split into blocks the plugin leaves unnamed (Minish Cap's list of lists) loads every block instead of 80 empty "(Missing)" ones; the prompt's neighbouring-rows section no longer raises for a row past the end of its block.

- AI translation accepts a reply that uses more or fewer lines than the source, as long as page breaks and the trailing newline stay; a reflowed reply with a line wider than the window has its page re-wrapped by the game's width rules. The strict line count lost a whole chunk per merged line (four attempts each) on the real model; two Twilight Princess sections now finish 84/87 and 48/48 lines with no error.

- Glossary rows for a request are found in the text the model gets, after force aliases: a line with the hero's tag now brings the `Link → Лінк` row. Without it the model spelled the name after the Russian reference («Линка» in 10 of 48 lines in one live run; 0–2 lines after the fix).

- Reference languages: Russian, when loaded, always goes last and the prompt calls it the least trusted reference (a live run took «Уговори Линка» from it); a `max_reference_languages` cap drops it first.
- Twilight Princess: the hero and the horse keep fixed, declined names — «Лінк» and «Епона» through their force aliases (`docs/DECISIONS.md` D15); a short-lived ordinary `{Epona}` alias and its nominative-only prompt rule were taken back.

- AI traffic log: a chunk reply that comes back but is refused (no JSON, a changed line layout) now gets an error record with its chunk number; it used to appear only in the run's summary, unlinked to any reply. Found in the first live run against the real model (`docs/REVIEW_QUEUE.md`).

- New plugin `zelda_hwde` (Hyrule Warriors: Definitive Edition, Switch): opens the game's 12-language Koei Tecmo XL text tables (`msgdata.bin`, battle `snstr*.bin`, cutscene/movie/narration subtitles, voice lines), shows the English section one block per table with readable `{c:0}`/`{form:1}`/`{btn:H}` tags, writes it back byte-exact when unchanged and mirrors edits into the English-EU section; Cyrillic goes into the cp1251 slots of the cp1252 font grid; speakers from the subtitle name rows and `VoiceInf.bin.gz`, glossary seed from the names table, per-table width limits from the font atlas.
- Nothing is written into `plugins/` at runtime any more (rule 8): widths set in the tag width dialog or Settings go to `~/.picoripi/plugins/<plugin>/font_map.json`, the BFN editor's `translation_map.json` without a project likewise; both win over the plugin's own file. The shared `translation_prompts/` folder and the BFN editor's plugin fonts are found from the code's location, so the application also works when started from another folder.
- Delete Block no longer crashes when the block tree is rebuilt while it asks for confirmation (chapters arriving); the speaker finder no longer looks at a path of the developer's machine; in the Ukrainian interface the provider ids stay English (Disabled was stored as `вимкнено`).
- Review tests: MemPalace builder results, the delete / glossary / autofix confirmations, starting from another folder; the proxy 429 test waits for the proxy's log.
- Font editor for every game: besides `.bfn` it opens, edits and saves the N64 Zelda message font inside the ROM (I4 glyphs + the `code` width table, CRC fixed), Hyrule Warriors G1T atlases (BC3, only edited blocks re-encoded) and Switch BFFNT (BNTX/BC4 sheets, CWDH widths). `core/font_formats/` is the shared model; the new plugin hook `get_font_sources()` (`font_sources.json`) lists a game's fonts in the editor's tree; saving writes the translation copy (archives repacked) and `<project>/font_maps/<map>.json` for the width checks; a text save of a ROM keeps the font edits. The BFN engine now repacks Wind Waker and Twilight Princess fonts byte-exact (chunk order, padding, linear maps). Descriptors for WW, OoT, MM, HWDE (with a cp1251 translation map) and TotK.
- "BFN Font Editor" is now "Font Editor" in the Tools menu, toolbar, window title and messages, since it edits every supported font format.

- `zelda_mm64` offers a reference translation: Load Reference Patch with a folder holding `mm3d_seed.json` (or the file) shows its Ukrainian text, carried over from Majora's Mask 3D and keyed by N64 message id, as the "Ukrainian (MM3D)" reference.
- `zelda_oot64` / `zelda_mm64` read `context.json`, mined offline from the decompilations and the ROMs by `plugins/common/zelda64_context.py`: a speaker for 2,765 of 4,589 MM and 1,100 of 2,115 OoT lines (only when exactly one actor's code shows the message), candidate scenes, item-get and place-name roles, and 270 / 165 glossary seeds (items, places, characters, highlighted terms).
- New plugin `zelda_oot64`: Ocarina of Time (N64) from the US 1.0 ROM, like `zelda_mm64` — all 2,115 messages round-trip byte for byte, colours/buttons/accents as tags, `sFontWidths` (NTSC) for widths. Both plugins now share `plugins/common/z64_text.py` (codec, table, rebuild) and `plugins/common/z64_rules.py` (open, save, relocate, widths).
- New plugin `zelda_mm64`: Majora's Mask (N64) opened straight from the US ROM and saved as a translated ROM — message codec from zeldaret/mm (every code a `{tag}`, a line break after each text-box break), all 4,589 retail messages round-trip byte for byte and an unchanged project saves the identical ROM; line widths from `sNESFontWidths` per textbox type. New `plugins/common/n64_rom.py` (byte order, dmadata, file swap that re-compresses Yaz0 files in place when they fit, header CRC for every CIC). Text that outgrows its range moves to free address space and the four `lui`/`addiu` pairs that load it are retargeted; a message over the game's 1280-byte buffer is refused.
- New plugin `zelda_tww`: The Wind Waker (GameCube) `bmgres.arc` on the Twilight Princess BMG code — a tag catalogue from the zeldaret/tww decompilation (75 control codes, sound/camera/animation groups, `color.bmc` colours, scale), the game's own button icons, INF1 box types with per-box line width and lines per page, item windows as glossary seeds. The escape-tag engine moved to `plugins/common/escape_catalog.py` (TP output unchanged). The BMG writer keeps empty messages on the shared DAT1 null and no longer adds a MID1 section to a file that had none: all 16 retail TP and WW message files now save back byte for byte.

- New plugin `zelda_totk` (Zelda: Tears of the Kingdom): opens `romfs/Mals/*.sarc.zs` (zstd SARC of MSBTs, game dictionary from `Pack/ZsDic.pack.zs`, Python 3.14 `compression.zstd`), shows tags readably (`{color:2}`, `{icon:AButton0}`, raw `{tag:G:T:hex}` otherwise), saves a drop-in mod archive (unchanged input is byte-identical), gives each line its MSBT file and label as context; offline tools for font widths from BFFNT (`font_tool`) and the resource size table (`restbl`).

- Series glossary: a project can link one glossary shared by a game series (`project.metadata["series_glossary"]`, files in `~/.picoripi/series_glossaries/`). **Glossary… → Series Glossary...** creates, links or imports one (a `{"terms": [...]}` multi-source document is converted, keeping per-source variants and status); the Glossary window shows it as a **Series: <name>** tab with the same editing and search, **Copy to Project Glossary** / **Promote to Series Glossary** for the selected terms, and terms the two glossaries translate differently marked red in both. AI prompts add series rows, marked lower priority, only for terms the project glossary does not translate; glossary builds never write the series file.

## [0.3.151-dev] - 2026-10-03

- Review-queue tests: `tests/test_review/` turns the manual checks of `docs/REVIEW_QUEUE.md` into end-to-end tests (fake OpenAI/Ollama/Gemini server, the real Companion server, the WP8 proxy with a stubbed Gemini, golden outputs from the pre-audit code in `tests/fixtures/review_queue/`). Bugs they found are fixed: an uncaught `TypeError` (sometimes an access violation) on the first event-loop turn of every start (`ui/adaptive_scrollbars.py`: the deferred configure timer is owned by the manager, areas Qt destroys meanwhile are dropped through `destroyed`); Cancel now shuts the request's socket down so the Web2API proxy stops instead of trying the next account (`transport.AbortableSession`); the glossary translate progress no longer goes back after a retry pass; preview pre-caching no longer runs after its window is gone; `ScriptSpeakerFinder` read a `project_dir` that `Project` does not have.
- Glossary build: "related" entries ignore common English function words (that, you, there…), which had filled almost every sweep request to its 40-line cap.
- Docs: `docs/REVIEW_QUEUE.md` keeps only owner decisions (with evidence and a recommendation), live runs and environment items; the manual checks it listed are covered by `tests/test_review/`, the remaining test gaps and side findings moved to `docs/OPEN_ITEMS.md`.
- Batch translation: every loaded reference language goes with every line again (WP2 2.5 had cut it to one language and none for lines of one or two words); `max_reference_languages` in the translation config still caps the count, 0 sends none.
- Fixes found by the review tests: the run's request summary shows on the status bar (it went to the already hidden status window); with Parallel Requests = 1 the error names the failed chunk; closing during an AI glossary build opens no message boxes on the closed window, and a finished build no longer shows its popup twice; the spellcheck and search workers stop at exit; the editor no longer re-analyses every 1.5 s after an edit (a rehighlight counted as typing); Paste with an empty clipboard no longer leaves an undo group open that swallowed every later edit; the block tree keeps its scroll position after a rebuild; Pull in the glossary window writes the pulled terms (it looked for a glossary manager MainWindow does not have).
- Pokémon FireRed: a one-block file is saved under its block name, not the file name; the second file of a project is saved with its own keys (each project block of a split file parsed the whole file again, doubling the keys; a source file is now parsed once per load); a project revert keeps every block of a file; a session written by an older build (keys doubled) no longer replaces the keys just loaded.
- Companion: terms pulled from the server no longer revert the next time the glossary window opens (and so are no longer overwritten by the next save): `load_prompts()` took the glossary manager's text as the authority instead of reloading a stale cached copy over it.
- UI session state (expanded nodes, selection, cursor per project) moves from `session_state.json` in the working directory to `~/.picoripi/session_state.json`; the old file is read once. The test suite no longer overwrote that file, truncated `app_debug.txt` (`PICORIPI_LOG_FILE` now overrides the log path), wrote `~/.picoripi/plugins/*/aliases.json`, or let one test read the settings another had saved.
- Licence: GPL-3.0-or-later; `LICENSE` holds the GPL v3 text (PyQt6 is GPL v3 as well). The README said MIT, with no licence file.

## [0.3.150-dev] - 2026-10-02

- wp7 7.6: `tests/test_docs/` checks that backticked repository paths and relative links in the README, AGENTS.md, the wiki, ARCHITECTURE, ENGINEERING, DECISIONS, FEATURES and INDEX exist, that every Ukrainian wiki page has the same section structure as the English one, that the version is not repeated outside `utils/constants.py`, that the entry documents stay within their token budgets and that `docs/PLUGIN_CONTRACT.md` is what the spec generates (it found a moved dialog path in wiki 2, a run-time folder named as a repository path in wiki 12 and a section missing from the Ukrainian wiki 7 — fixed). All 266 modules without a module docstring got a one-line one; `tests/test_architecture/test_module_docstrings.py` fails on a new bare module. New `docs/DECISIONS.md`: fourteen short records of why the code is the way it is.
- wp7 7.4: documents merged and archived — `docs/ENGINEERING.md` (1.5k tokens) replaces the 3.9k `AI_DEVELOPMENT_MANIFESTO`; `FEATURE_REFERENCE` is gone (its content is in `docs/FEATURES.md`); the glossary-pass guide became an appendix of wiki 8, the scene auto-fill plan a section of wiki 9, the ChatMock how-to a section of wiki 5 (EN + UK each; ChatMock is set up as an OpenAI Compatible endpoint — there never was a separate provider); `docs/MEMPALACE_CONTEXT_MANIFESTO.md` is a 2.3k-token contract in English and the 156 KB original with its progress log moved to `docs/history/`; `docs/PIPELINE_ROADMAP.md` opens with a shipped-vs-planned table and marks its outdated sections as history; the Wind Waker glossary copy in `plugins/plain_text/` (read by nothing) is deleted; the `update-wiki` skill owns wiki page 12 and `docs/FEATURES.md`. `docs/INDEX.md` has no `merge` rows left and fits in 1.2k tokens.
- wp7 7.3: `README.md` is now the pitch, install, run, development commands and the documentation map (1.5k tokens instead of 16k); the feature inventory, modifier shortcuts and validation rules moved to `docs/FEATURES.md` together with the "must survive a change" lists of `docs/FEATURE_REFERENCE.md`. Stale claims are gone: "Settings → Preferences" (it is File → Settings…, `Ctrl+P`), the DeepL key (nothing reads it; removed from `.env.example` too), the test count, the directory tree with files that moved, the `gemini/` note, "Python 3.14 or higher" (3.10+), the link to a `LICENSE` file that does not exist. The version is no longer repeated in the README title; `scripts/deploy.py` stops rewriting it, bumps `-dev` versions and inserts a release entry under `[Unreleased]`.
- wp7 7.5: `tasks.py` — one cross-platform entry for the routine commands (`python tasks.py test | test-serial | test-perf | lint | smoke | docs-check | docs-index | graph | bump | new-plugin | run`); it finds the project environment itself (the active one, then `venv`/`.venv`), so `test_all.ps1`, `run_stress_tests.ps1`, `run.bat` and `run.sh` no longer name an interpreter path. `--dry-run` prints the command lines.
- wp7 7.2: `docs/ARCHITECTURE.md` — the data-flow diagram (widgets → MainWindow → handlers → DataStateProcessor → AppDataStore → updaters), a layers table with where to start reading and which tests and wiki page belong to each package, the fourteen compatibility modules that only re-export, and a "where to change what" table.
- wp7 7.1: `docs/INDEX.md` — one line per document (purpose, size in tokens, status, what it owns), generated by `python tools/docs_index.py --write` from a header that every document under `docs/` now carries (`status`, `updated`, `owns`, `tokens`, `purpose`); `--check` and a test keep the index and the token counts in step with the documents.

## [0.3.149-dev] - 2026-10-02

- wp8: the Gemini Web2API proxy, version 1.4.0, on branch `audit/wp8` of its own repository (a separate worktree, `D:\git\dev\gemini-web2api-wp8`; the proxy's working directory is untouched): one implementation instead of two, `429 + Retry-After` / `502` with a stable `error.type`, a 170 s total deadline per request, a concurrency gate, `GET /healthz`, a locked-down dashboard API, an offline test suite. Picoripi itself: wiki page 5 (EN + UK) gets the section "Proxy 1.4.0: what changes for Picoripi"; no code change.

## [0.3.148-dev] - 2026-10-02

- wp4 4.4: fixed interface strings. A game string that is exactly a glossary term of the `UI` section (translation config `fixed_output_sections`) is filled with the glossary translation before a run starts — no request; rows already translated, texts that do not fit the layout and unconfirmed suggestions are left alone. A single-string request now carries the plugin's `Addressee:` like a batch item does.
- wp4 4.3: a request to the model is packed from whole conversations. New plugin hook `get_ai_flow_group_for_string(block, string)` names the conversation of a line; lines that share it stay in one request when they fit (12 strings), and a conversation is cut only when it alone is longer. Twilight Princess reports the flow entry that reaches the message. Plugins without the hook, and translations in progress from an earlier version, keep the plain cut by count.
- wp4 4.2: translation memory across runs. Saved translations are also indexed by source text (`translation_memory.json` next to `saved_translations.json`; built from the existing file on first use). A string whose text was translated elsewhere in the project is offered for restore in the Cached Translation window — marked "(same text elsewhere)", same layout check, no AI request — and a single-string translation request lists up to three saved translations of the same source as `TRANSLATION MEMORY (same source elsewhere)`.
- wp4 4.1: one source, one translation per run. Strings with exactly the same text — and the same speaker, addressee, window and row context — are sent to the model once and share the translation (`"fold_duplicates": false` in the translation config sends every string). A run memory (`core/translation/run_memory.py`) shows later chunks, as `already_translated_in_this_run`, what was chosen for sources that differ only in tags, case or spacing.

## [0.3.147-dev] - 2026-10-02

- wp6: a worker thread can no longer be destroyed while it runs. Every thread class (27) derives from `utils.thread_utils.WorkerThread`, which stays referenced from `start()` until Qt reports it finished; before, a result slot that dropped the last reference (`self.save_worker = None`) could run before `run()` had returned and Qt aborted the process — rarely in the application, and as a random "worker crashed" in the test suite. At exit every thread still running is asked to stop and waited for.
- wp6 6.5: the two longest functions are split with no change of behaviour — `AIWorker.run()` (746 lines) is a dispatcher over one method per kind of task, `populate_blocks` (542 lines) builds the tree from named steps; no method in either module is longer than 80 lines and a test holds them under 120. One fix on the way: the error report of a failed chunk quotes that chunk's reply, not the one left over from the chunk before. `ruff` now enforces unused locals (F841, 72 removed) and silent broad `except` (S110/S112): 166 `except Exception: pass` handlers log what they swallowed at debug level.
- wp6 6.4: product code no longer detects the test runner. The 21 `'pytest' in sys.modules` checks (and one `PYTEST_CURRENT_TEST`) read one explicit switch, `utils.app_mode.headless`, set by `tests/conftest.py`; the twelve compatibility modules no longer replace other modules' globals with late-bound `_ShimName` proxies (in the running application a proxy stood where `Path`, `QMessageBox` or `QTextCursor` was expected); a Companion address that is not a string starts no network thread. The test suite's walk over the whole heap for stray threads is deleted — nothing leaves one behind — and a full run takes about 95 s instead of 130 s. An architecture test keeps the detectors out.
- wp6 6.3: no Companion request runs on the interface thread. Push, Pull and Test Connection (glossary window, Settings) run in the background behind a progress window with Cancel; the merge after resolving conflicts is committed by the sync worker; the sync window on exit gives up after 6 s without an answer, and with a window open there is no blocking fallback any more.
- wp6 6.2: background threads are never killed and never destroyed while running. `safe_shutdown_thread` asks the worker to cancel, waits, and deletes only a thread that stopped; one that did not is kept until it ends (and gets a last wait when the application quits). "Skip" in the Companion sync window returns at once instead of terminating the thread, and a cancelled sync writes nothing afterwards. Opening a project while another is still loading stops the first load; a second save while one runs is refused. Thread classes no longer redefine Qt's own `finished` signal (`finished_with_result` instead).
- wp6 6.1: files that hold a user's work are written atomically (`utils/atomic_io.py`: temporary file in the same folder, flushed to disk, renamed over the target, three tries when the target is briefly locked) — translation files, packed game archives, the project file, project and global settings, the glossary, the session, saved translations, Script Markup projects, font maps, prompt overrides. A crash or a full disk in the middle of a save leaves the previous file intact. Line endings are unchanged.

## [0.3.146-dev] - 2026-10-02

- wp5 5.8: one plugin guide — `docs/wiki/3_Plugin_Developer_Guide.md` (EN + UK) absorbs `docs/PLUGIN_AUTHORING_GUIDE.md` and `plugins/DEVELOPER_GUIDE.md` (both removed); the list of hooks is `docs/PLUGIN_CONTRACT.md`, generated from `plugins/spec.py` (`python -m plugins.spec --write`) and checked by a test. The plain-text plugin is now labelled "Plain Text" (it shared the label "Zelda: The Wind Waker" with the Wind Waker plugin, so only one of the two could be picked).
- tests: the interface language is reset to English around every test — a test that switched it to Ukrainian left later tests on the same worker failing and one of them waiting on a message box for ever (the rare "one F, then the run stalls" hang).
- wp5 5.7: the host imports no game plugin any more — the bitmap-font preview and the Settings table of per-window limits ask the active plugin through hooks on `BaseGameRules` (`get_window_presets`, `get_window_preset_label(s)`, `get_window_style_for_preset`, `get_window_frame`, `get_window_item_icon`, `get_window_text_offset_y`, `get_window_layout_groups`, `get_window_layouts_document`, `save_window_layouts_document`); Twilight Princess implements them. The item-id rule of the item window moved from the preview into the plugin; `core/mempalace/flow_validation.py` moved to `plugins/zelda_bmg/flow_validation.py`.
- wp5 5.6: plugin isolation — `core/plugin_call.py::safe_call` wraps the hooks called on hot paths (editor text, file parsing), so a plugin error is logged and reported instead of reaching the crash handler; switching plugins drops every module of the plugin (by prefix) instead of a fixed list of six; code running without a main window gets `plugins/common/generic_rules.py` instead of silently borrowing the Minish Cap plugin; all 24 CWD-relative `Path("plugins")` sites use `utils.constants.plugins_root()`.
- wp5 5.5: a plugin declares its file formats (`get_file_formats()` → `core.formats.FileFormat`, mode json / text / bytes) and the host loads, saves and imports through `core/formats.py` instead of five extension switches — a game with its own binary table needs no host change (tested end to end with a made-up `.tbl` plugin). The host no longer reads or writes plugin attributes: `original_keys` and `last_loaded_bmg` are replaced by the hooks `export_runtime_state` / `restore_runtime_state` / `reset_runtime_state` / `prepare_save_context`. The BMG parser moved to `plugins/zelda_bmg/bmg_tool.py` (a shim keeps `import bmg_tool` working); `ContainerManager.register()` lets a plugin add an archive format; binary files are written atomically.
- wp5 5.4: `python tools/new_plugin.py <id> "<Display Name>" --prefix XX` creates a working plugin from `plugins/default_plugin` together with `tests/test_plugins/test_<id>/` (three passing checks from the new `plugins/testing.py`); the same checks run for every shipped plugin.
- wp5 5.3: prompt files are merged key by key (application → `plugins/common/defaults` → plugin → project/user override) in `core/translation/prompt_files.py`; a plugin with a `translation`-only `prompts.json` now gets the glossary, MemPalace and editor-review prompts from the common file instead of built-in constants. The editor-review pass (which could never run: its loader imported a module that does not exist) is fixed and has its own switch, `translation_config["editor_review_enabled"]`, off by default.
- wp5 5.2: a plugin declares its parts instead of wiring them — `BaseGameRules` builds the tag manager, problem analyzer and text fixer from class attributes (`problem_prefix`, `problem_definitions`, `tag_manager_class`, `tag_style`, `star_section_mode`, `analyze_whole_string_first`) and answers the pass-through hooks itself; `rules.py` of Minish Cap went from 245 to 81 lines, Wind Waker from 187 to 53. The analyzer no longer guesses the tag style from module names. Pass-through `text_fixer.py` / `problem_analyzer.py` / `tag_manager.py` files are gone from four plugins; plain text uses a neutral `plugins/common/tag_logic.py` instead of a copy of the Wind Waker one; the dead `is_tag_legitimate` / `get_tag_pattern` hooks are removed from `GameRules`. The AI translate actions (Ctrl+Alt+T / L / B) are registered by the application for every game instead of by the Minish Cap plugin.
- wp5 5.1: the plugin contract is data (`plugins/spec.py`: every hook the host calls, the main-window attributes a plugin may use, the `config.json` keys) and `python -m plugins.validate [name]` checks a plugin against it — hooks are called with dummy arguments, signatures and return types are verified, JSON files are checked. All six shipped plugins pass; per-session keys were removed from their `config.json`.
## [0.3.145-dev] - 2026-10-02

- wp3: term families are formed by the rarest shared word instead of by every shared word (which chained a third of the shipped glossary into one "family" and ignored the real big ones), and glossary translation runs in three tiers — one-word terms, two-word terms, longer ones — so a compound name is translated after its head term whatever family it is in.
- wp3 3.7: regression gate `tests/test_core/test_glossary_consistency.py` on the shipped glossary (no entry stored twice, no new spelling variants of an existing term, a merge leaves no collision and loses nothing; diverging families are reported as a warning); wiki 8 describes how the glossary stays consistent (EN + UK).
- wp3 3.6: glossary storage hardening — `GlossaryManager.transaction()` turns many changes into one file write (a build pass writes every 20 results instead of after every term); the file is replaced atomically; every entry has a stable `id`; deletions are recorded (`deleted_at`) so a Companion sync or pull no longer brings a deleted or merged entry back, and a renamed entry is matched by id instead of being duplicated; a re-sweep adds fragments to a translated entry instead of resetting it to "seeded".
- wp3 3.5: reconcile pass for the glossary — "Reconcile related terms afterwards" in the build dialog compares entries that are one term spelled differently or share a word, one request per cluster that looks off, then merges spellings (the other one stays as an alias, its translation as a variant) and aligns translations to a shared root. Confirmed entries are never changed; every change is in the report and in the log; a second run changes nothing (`core/glossary_build/reconcile_driver.py`, `GlossaryBuildCoordinator.run_reconcile`, `GlossaryManager.merge_into`).
- wp3 3.4: cleaner glossary rows in translation prompts — a plural in the text finds the singular entry ("Rupees" → `Rupee`, also through aliases), a term found only inside a longer term is not listed on its own ("Lake Hylia", not "Hylia" + "Lake"), entries without a translation are left out, at most 40 rows ranked by who decided them, and notes are cut to 300 characters in the prompt table (the editor keeps the full note). The pattern cache is built aside and swapped in whole.
- wp3 3.3: glossary build requests are told what is already decided — each sweep chunk and each term translation gets the settled entries that share a word with it (`core/glossary_build/decisions.py`, up to 40 lines, a person's decisions first); translation runs family by family (head term first, siblings see what it got), and the one-shot builder passes both the glossary's decisions and the earlier chunks' terms to every chunk.
- wp3 3.2: a glossary build is reproducible — the pool releases results in item order (bounded look-ahead), sweep terms are merged by canonical key and named by their most common spelling, seeding is sorted by section and key, translation runs family by family with the head term first.
- wp3 3.1: glossary entries are found the same way by every operation (exact, case/spacing, alias, then a canonical key that folds plurals, articles and possessives) — a build no longer creates "Hylian shield" next to "Hylian Shield" or "Rupees" next to "Rupee", and updates no longer miss silently; new `aliases` field; text replace keeps status, variants and notes; forced re-translation leaves confirmed entries alone. Existing look-alike entries are reported, not merged.

## [0.3.144-dev] - 2026-10-02

- wp2 2.1: the request rules are fixed text appended to the system prompt (`prompt_composer/instructions.py`) instead of an `INSTRUCTIONS` block rebuilt into every user message — the system prompt is byte-identical for every chunk (cacheable prefix ~2100 → ~3065 tok) and the user message carries data only; a retry quotes the real error; the prompt editor shows the rules but saves only the user's prompt.
- wp2 2.2: the rows shown before and after a chunk come from the strings' real position — selections and preview runs no longer show rows 0–3 of the first block, project-wide and story-first runs get neighbour rows at all, and a chunk spanning two blocks gets both sets.
- wp2 2.3: starting a block translation no longer composes the prompt for the whole item set (twice) before the first request — only the tag placeholders are collected, and the prompt editor previews one chunk; the worker composes each chunk as before.
- wp2 2.4: removed two things that never ran — the `NarrativeLedger` (nothing ever wrote to it, so no "canon context" was ever injected) and the translation-session path (unreachable behind a duplicated flag); README and wiki 2, 8, 11 no longer describe them. AI Chat sessions are unchanged.
- wp2 2.5: smaller batch payload — shared layout values once in `layout_defaults`, per item only `line_count` and what differs; unresolved speakers omitted; one reference language per line by default (`max_reference_languages`), none for one- or two-word lines; the editor review gets `{id, text, translation}` triples. A 12-item chunk: ~5440 → ~4610 tok.
- wp2 2.6: a chunk's glossary table is built from the chunk's own text plus its speakers and story participants (no 60-line lookahead, no matching against the story-context JSON); batch requests carry compact character cards (role, address and grammar, speech style of the current speaker; 40 words per field) instead of full MemPalace profiles.
- wp2 2.7: translation requests ask for native JSON output where the provider has it — `response_format: json_object` for api.openai.com, `responseMimeType` for native Gemini, `format: json` for Ollama; nothing is added for a Web2API proxy or Perplexity. The tolerant JSON extractor stays as the fallback.
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
