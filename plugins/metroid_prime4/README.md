# Metroid Prime 4: Beyond (`metroid_prime4`)

Switch, update 1.1.0 (v131072). The workspace scripts (`_shared\scripts\zt\mp4.py`) unpack the game's Retro
packages into `source\`, and pack the translation back into a LayeredFS mod:

- `text\<table>.msbt` — the English (USEN) messages of each MSBT table; the build writes USEN and EUEN.
- `font\FONT_*.rfont` — a FONT form followed by its texture pages (Font Editor format `retro_font`).
- `texture\<package>\*.txtr` — the interface textures, decompressed (Textures window format `txtr`).

Formats: `core/containers/retro_pak.py` (packages, compression modes 1–3 and 12–14, texture buffers),
`core/font_formats/retro_font.py`, `core/texture_formats/txtr.py`, `core/texture_formats/astc.py`.

## Credits

The package layout (60-byte directory entries), the priority of `Patch\*.pak.patch`, the font page layout and
the starting Ukrainian translation (text and fonts with Ukrainian letters) come from **BakAI**'s
Ukrainian translation 1.1.0 and the notes they shared. The code here is a separate implementation; the
compression modes 12–14 are decoded in Python from the game's own tables instead of running the executable.
