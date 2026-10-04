# Majora's Mask: where the Ukrainian letters live (`translation_map.json`)

Status: **confirmed 2026-10-04** against the US ROM (`NZSE` v0), the mm decomp and 2 Ship 2 Harkinian 5.0.1.

Rule (owner's decision): Latin and Cyrillic both stay fully usable. A Cyrillic letter that looks like a Latin
one shares its glyph (А→A, В→B, Е→E, І→I, К→K, М→M, Н→H, О→O, Р→P, С→C, Т→T, Х→X, а е і о р с у х, ’→',
Ї→Ï, ї→ï); every other letter takes the cell of a character the game never draws, and its glyph fits the
cell's advance (2 Ship 2 Harkinian draws with the game's width table).

| Check | Evidence | Result |
|---|---|---|
| English messages | all 4,589 messages of `message_data_static` (code table at 0x1210D8), control codes skipped | 0 uses of any taken cell |
| Credits | all 45 messages of `staff_message_data_static` (the table after the English one; OoT control codes) | 0 uses |
| Characters the code prints | `z_message_nes.c`: player and Deku Playground names convert only `A–Z a–z 0–9 space . -`; owl-warp places, `Fast`/`Slow`, `RED`/`BLUE`/`YELLOW`/`GREEN`, `Rupees`; digits, `" ' : 1 R e p` | none taken |
| File select / name entry, title | `Font_LoadOrderedFont` copies message-font cells for the keyboard (`0–9 A–Z a–z space - . :`; the accented cells it also copies are never typed: the keyboard is `z_file_nameset_data.c` rows A–Z, a–z, 1–0 . - space) and for "PRESS START" | not affected |
| 2 Ship 2 Harkinian | its own English messages (75 colour-coded strings in `2ship.exe`) use only letters and `. , ! ? ' - ( ) :` | none taken |
| Glyph width | every redrawn glyph's ink fits its cell's advance in the game's (unchanged) width table | all fit |

Taken cells (letter → cell): Б ê, Г ç, Ґ ä, Д Û, Є Ñ, Ж Ô, З ¡, И Ç, Й ¿, Л ô, П Ù, У é, Ф Ä, Ц À, Ч ò, Ш Ó,
Щ Ö, Ь è, Ю Ò, Я ë, б à, в Ê, г Ì, ґ º, д ß, є È, ж Ú, з Í, и ù, й ú, к É, л ñ, м ó, н û, п â, т Î, ф ö, ц ü,
ч á, ш Á, щ Â, ь ª, ю Ü, я Ë.

Characters the English text does use: `space ! " & ' ( ) , - . / 0–9 : ; ? A–W Y Z a–z ~` — none of them is
taken (`&` and `~` stay Latin; `X` is unused but shares Х).

The census is the test `test_no_english_message_or_credit_uses_a_cell_a_ukrainian_letter_takes`
(`tests/test_plugins/test_zelda64_translation_map.py`, runs where the ROM is on disk).
