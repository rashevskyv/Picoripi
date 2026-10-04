# Ocarina of Time: where the Ukrainian letters live (`translation_map.json`)

Status: **confirmed 2026-10-04** against the US 1.0 ROM (`CZLE` v0), the oot decomp and Ship of Harkinian 9.2.3.

Rule (owner's decision): Latin and Cyrillic both stay fully usable. A Cyrillic letter that looks like a Latin
one shares its glyph (А→A, В→B, Е→E, І→I, К→K, М→M, Н→H, О→O, Р→P, С→C, Т→T, Х→X, а е і о р с у х, ’→',
Ї→Ï, ї→ï); every other letter takes the cell of a character the game never draws, and its glyph fits the
cell's advance (Ship of Harkinian draws with the game's width table).

| Check | Evidence | Result |
|---|---|---|
| English messages | all 2,115 messages of `nes_message_data_static` (code table at 0xFD9EC), control codes skipped | 0 uses of any taken cell |
| Credits | all 48 messages of `staff_message_data_static` (the table after the English one) | 0 uses |
| Characters the code prints | `z_message.c` (NES path): the player name converts only `A–Z a–z 0–9 space . -`; times and scores add digits, `"` and `:` | none taken |
| File select / name entry | NTSC loads the file-select font from the Japanese kanji font (`Font_LoadOrderedFont`, message 0xFFFC of the Japanese table), not from the message font | not affected |
| Ship of Harkinian | its file-select font is message 0xFFFC `0–9 A–Z a–z space - .`; its own English messages (103 colour-coded strings in `soh.exe`) use only letters and `. , ! ? ' - ( ) : "`; `& ^ @ % | #` there are format codes, never drawn | none taken |
| Glyph width | every redrawn glyph's ink fits its cell's advance in the game's (unchanged) width table | all fit |

Taken cells (letter → cell): Б ö, Г $, Ґ #, Д Ü, Є ~, Ж Ö, З è, И Ç, Й &, Л \, П Ù, У ô, Ф Ä, Ц À, Ч û, Ш Ô,
Щ %, Ь ë, Ю @, Я ù, б â, в à, г *, ґ Ë, д ê, є É, ж Û, з [, и <, й >, к Ê, л +, м ü, н _, п ç, т ], ф ^, ц ß,
ч ä, ш î, щ Â, ь È, ю =, я á, « `, » |.

Characters the English text does use: `space ! " ' ( ) , - . / 0–9 : ; ? A–Z a–z é` — none of them is taken.

The census is the test `test_no_english_message_or_credit_uses_a_cell_a_ukrainian_letter_takes`
(`tests/test_plugins/test_zelda64_translation_map.py`, runs where the ROM is on disk).
