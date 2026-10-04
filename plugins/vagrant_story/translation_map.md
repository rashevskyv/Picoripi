# Vagrant Story: where the Ukrainian letters live (`translation_map.json`)

Status: **draft 2026-10-04**, checked against the USA disc (SLUS-01040). The letters' glyphs in
`FONT/VSFONT.FNT` are a rough draft (rendered from Arimo) for the owner to polish in the Font Editor.

The game draws one byte as one 12x12 cell of `BATTLE/SYSTEM.DAT` (cell = code; 189 regular cells for
menus, the same 189 in italic small capitals for dialog balloons) and advances by the code's entry in
the width table of `BATTLE/BATTLE.PRG`. A Cyrillic letter that looks like a Latin one shares its code
(А→A, В→B, Е→E, І→I, К→K, М→M, Н→H, О→O, Р→P, С→C, Т→T, Х→X, а→a, е→e, і→i, о→o, р→p, с→c, у→y,
х→x; Ї→Ï, ї→ï); every other letter takes a cell the English text never uses.

| Check | Evidence | Result |
|---|---|---|
| English text | every line the plugin shows: 6,018 strings of events, rooms, menus, items, help, bestiary, room names, program and zone data | 0 uses of a taken cell |
| Accented letters English does use | `á` (Leá Monde, 45), `é` (1), `ü` (Müllenkamp, 30) | kept |
| Name entry keyboard | `MENU/MENU8.PRG` table string 13: letters, digits, punctuation, no accented letter | not affected |
| Japanese leftovers | debug events 0501-0511, 0025, 0059 and the 72 empty bestiary slots use font pages (0xEC-0xF7) | not shown, not affected |

Taken cells (letter → cell): Б À, Г Á, Ґ Â, Д Ä, Є Ç, Ж È, З É, И Ê, Й Ë, Л Ì, П Í, У Î, Ф Ò, Ц Ó, Ч Ô,
Ш Ö, Щ Ù, Ь Ú, Ю Û, Я Ü, б ß, в œ, г à, ґ â, д ä, є ç, ж è, з ê, и ë, й ì, к í, л î, м ò, н ó, п ô,
т ö, ф ù, ц ú, ч û, ш Œ; щ ь ю я take the empty cells 0x6B-0x6E (named Å å Ø ø by the codec).
Punctuation: ’→', «»→", …→⋯, –→-.

Free for later: 0x6F-0x85 (23 empty cells).

The census is the test `test_real_text_uses_no_code_the_translation_map_takes`
(`tests/test_plugins/test_vagrant_story/test_rules.py`, runs where the workspace is unpacked).
