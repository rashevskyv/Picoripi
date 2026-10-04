# Paper Mario: The Thousand-Year Door: where the Ukrainian letters live (`translation_map.json`)

Status: **checked 2026-10-04** against the US disc (G8ME01): `msg/US/*.txt`, `sys/main.dol`, `rel/*.rel` and
the text font `f/papermarioset_US.bfn` (161 glyphs, one 512×256 I4 sheet, Latin-1 codes).

Rule (as in the other single-byte fonts): Latin and Cyrillic both stay usable. A Cyrillic letter that looks like
a Latin one shares its glyph (А В Е І К М Н О Р С Т Х а е і о р с у х → the ASCII letter; Ї ї → Ï ï; ’ → ’).
The other 44 letters take a Latin-1 slot of the font that no English text draws; their glyphs are drawn into
those cells (workspace `tools\draw_ukrainian_font.py`, Balsamiq Sans Bold through the Font Editor's Render Font
with `align_to_latin`; widths from the ink).

| Check | Evidence | Result |
|---|---|---|
| English messages | all 13,018 English messages of the 260 files of `msg/US` (Japanese UTF-16 leftovers excluded: the game never shows them) | 0 uses of any taken slot |
| What English does use above 0x7F | é è ë í ú ö (credits), and the symbol slots A4 ○, B2 ↑, B3 ↓, D0 ♡, D7 ×, D8 ♪, DE ☆ | none taken |
| Strings in the code | every string of the data sections of `main.dol` and the 29 area modules that holds a taken byte: Japanese Shift-JIS debug text, the European disc-cover / 60 Hz messages (DE, FR, ES, IT) and "Münze(n)", "Français", "Español" (only for other languages) | none drawn by the US game |
| Name entry | the file-name keyboard shows the accented Latin-1 letters | those keys now show Ukrainian letters: a player can type a Ukrainian name (harmless) |
| Glyph cells | every slot has a glyph cell in the font's maps (test `test_every_slot_is_in_the_font_and_the_font_round_trips`) | all mapped |

Taken slots (letter → slot): Б À, Г Á, Ґ Â, Д Ä, Є Ç, Ж È, З É, И Ê, Й Ë, Л Ì, П Í, У Î, Ф Ñ, Ц Ò, Ч Ó, Ш Ô,
Щ Ö, Ь Ù, Ю Ú, Я Û; б à, в á, г â, ґ ä, д ç, є ê, ж ì, з î, и ñ, й ò, к ó, л ô, м ù, н û, п ü, т ß, ф Œ, ц œ,
ч ¡, ш ª, щ º, ь ¼, ю ½, я ¾. Free for later: Ü ¿ ‚ „. Kept for Ukrainian punctuation: « » “ ” ’.

The census is the test `test_no_english_message_uses_a_slot_a_ukrainian_letter_takes`
(`tests/test_plugins/test_paper_mario_gc/test_rules.py`, runs where the disc is unpacked).
