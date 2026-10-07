# Metroid Prime Remastered (`metroid_prime_remastered`)

Switch, base game v0 (010012101468C000). The rules are those of `metroid_prime4` (same Retro formats). The
workspace scripts (`_shared\scripts\zt\mpr.py`) unpack the game's Retro packages into `source\` and pack the
translation back into a LayeredFS mod:

- `text\TEXT_*.msbt` — the English (USEN) messages of the 27 MSBT tables; the build writes USEN and EUEN.
  Table and label names are the Metroid Prime 1 ones (`TEXT_ScansChozoRuins`, ...), so a Prime 1
  translation can later be matched by label.
- `font\FONT_*.rfont` — FONT_Geneva, FONT_Deface (game) and FONT_Deface_PreloadFrontEndMPT (title
  screen and menus): a FONT form followed by its texture pages (Font Editor format `retro_font`).
- `texture\<package>\*.txtr` — every texture of the interface packages, decompressed (format `txtr`).

Differences from Prime 4 handled in shared code: TOC v3 with 52-byte entries, LZSS modes 1–3 only
(no executable needed), texture metadata version 5 (`core/containers/retro_pak.py`), a tile-mode field in
the TXTR header (`core/texture_formats/txtr.py`), FONT fields 4 bytes later and 48-byte glyph records with
kerning pairs (`core/font_formats/retro_font.py`).
