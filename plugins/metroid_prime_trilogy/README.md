# Metroid Prime Trilogy (`metroid_prime_trilogy`)

Wii, USA (R3ME01): Metroid Prime, Metroid Prime 2: Echoes, Metroid Prime 3: Corruption and the Trilogy menu on one
disc. The workspace scripts (`_shared\scripts\zt\mpt.py`, packages in `zt\retro_gx.py`) unpack the Retro packages
into `source\<game>\` (`MP1`, `MP2`, `MP3`, `Menu`) and write the translation back into a copy of the ISO:

- `text\<package>\<name>.<id>.strg` — every STRG string table once per game (`strg.py`; 5,473 tables, 16,211
  strings). Tags `&name=value;` show as `{name=value}` (`tags.py`).
- `font\<name>.<id>.font` — a FONT followed by its C4 texture (Font Editor format `retro_font_gx`).
- `texture\<package>\<name>.<id>.txtr` — the interface textures, decompressed (Textures window format `txtr_gx`).

A saved table carries the edited strings as every language of the table: one shared copy keeps the table small
enough for its place in the package (the disc has little free room), and the game shows the translation whatever
the console language is.

Prime 1 here is the Trilogy edition; its English text matches Metroid Prime Remastered in most tables, so a
Remastered plugin can take this translation over by the English strings.
