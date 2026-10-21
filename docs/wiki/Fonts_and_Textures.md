---
status: current
updated: 2026-10-21
owns: tools/bfn_editor/ and ui/texture_window.py
tokens: 1.8k
purpose: Edit game fonts and textures, add Ukrainian letters, and set the fonts folders and default font of a project
---
# Fonts and textures

**Language:** English · [Українська](uk/Fonts_and_Textures.md)

Many games draw text with bitmap fonts and with pictures. This page shows how to change them. Use the Font Editor for letters. Use the Textures window for pictures that hold text.

The interface in the screenshots is Ukrainian. The labels below are the English ones.

## Terms

| Term | Meaning |
|---|---|
| Font | A set of letter pictures that the game draws |
| Glyph | One letter picture in a font. Glyphs have numbers |
| Font Editor | The window that opens and edits game fonts |
| Texture | A picture in the game, for example a title logo or a menu label |
| Translation map | `translation_map.json` in the project folder. It sets which glyph shows which letter |
| Font Map | The table of letter widths, in **Settings → Project → Font Map** |

## Open the Font Editor

1. Press **Tools → Font Editor...**. Or press the **A** button on the toolbar.
2. A file dialog opens. Choose a font file. The dialog lists the formats `.bfn`, `.bffnt`, `.bcfnt`, `.qbf`, `.gzf`, `.g1t`, `.g1n` and `.gz`.
3. To open a folder instead, press **Cancel**. Choose a folder with `data.json` and `sheet_*.png` files.
4. The glyphs appear as a grid. Click a glyph to see its values.

The fonts of a project come from the game plugin. The Font Editor can also open a font file that you choose yourself. The editor reads many game font formats. Examples are BFN, BFFNT, NFTR, G1T and TTF.

## Add a Ukrainian letter

A letter needs a glyph. Find a free glyph for it or draw over an unused one.

1. Open the font in the Font Editor. Find the glyph in **Glyph Table**.
2. Draw the letter. Use one of these ways:
   - Right-click the glyph and press **Render Font to Selected Glyph...**. Choose the **Font File...**, the **Font Size (px):** and the style. The editor draws the letter from a system font.
   - Right-click the glyph and press **Export Selected Glyph PNG...**. Draw in an image editor. Then press **Import Selected Glyph PNG...**. The PNG must have the same size as the glyph. Otherwise the editor refuses it.
3. Press **Auto-detect Width** to set the width of the letter.
4. Press **Save Changes** (`Ctrl+S`).

After saving, the editor writes `translation_map.json` into the project folder. Picoripi also reloads the font widths. It checks the text again by itself.

## What is saved and where

- The editor writes the font into the **translation** folder of the project. It never changes the original file.
- A font that a plugin lists is read from the translation copy when that copy exists. Otherwise it is read from the original.
- `translation_map.json` goes into the project folder.
- The letter widths go into the `font_maps` folder of the project.
- Changes stay unsaved until you press **Save Changes**. When you close the editor with unsaved changes, it asks what to do.

## Textures window

1. Press **Tools → Textures...**.
2. The list shows the columns **Texture**, **Game file**, **Format**, **Size** and **Status**. The two previews show **Original** and **Translated**.
3. Select a texture.
4. Press **Export PNG...** (`Ctrl+E`) and choose a folder. The PNG goes there.
5. Redraw the PNG in an image editor. Keep its size.
6. Press **Import PNG...** (`Ctrl+I`) and choose the PNG. Picoripi converts it to the game's format. It writes the translation copy.
7. Set **Status** to **Redrawn**. After you see the texture in the game, set it to **Checked in game**.

The other buttons:

| Button | What it does |
|---|---|
| **Export All...** | Saves every texture as a PNG file in a folder |
| **Import Folder...** | Imports each PNG whose name matches a texture. A PNG of another size is resized |
| **Revert** | Puts the game's original back into the selected textures. It asks you first |
| **Open Folder** | Shows the folder of the translated game file |

**File → Reload Project Textures** (`F5`) reloads the list. The statuses are kept in the file `textures/status.json` in the project folder.

To edit one texture file without a plugin, press **File → Open Texture File...**. Picoripi then changes that file in place. Make a copy of it first.

## Fonts folders and the default font

| Setting | Where | What it does |
|---|---|---|
| Original Fonts Directory Path (original font) | **Settings → Project → File Paths** | A folder with the original fonts. Optional |
| Fonts Directory Path (translated font) | **Settings → Project → File Paths** | A folder with your own fonts. Optional |
| Default Font for Project | **Settings → Project → Display** | The font the project uses. The first item is **None** |

The list of default fonts holds the fonts of the game plugin. It also holds the fonts of your fonts folder. The program restarts after you change the default font.

## How plugins declare fonts and textures

Translators do not write this part. The plugin author lists the fonts in `font_sources.json` and the textures in `texture_sources.json`. The author can also return the lists from code. Each entry gives a file, a format and a label. If a game has no entry, the Font Editor and the Textures window show nothing for it. The author's details are in the [Plugin Developer Guide](3_Plugin_Developer_Guide.md).

## Common situations

- **Letters show as squares.** The font has no glyph for that letter. Add the letter as shown above. Check that **Default Font for Project** is the right font.
- **Text is too wide after a font change.** The widths changed. Press **Auto-detect Width** in the Font Editor and save. Then press `Ctrl+Shift+R` to count the widths again.
- **My game needs a new font.** Some games have no Ukrainian letters in their font. You must draw them in the Font Editor. Picoripi does not add them by itself.
- **My font is not in the list.** The plugin does not list it. Open the font file yourself with the Font Editor's file dialog.
- **I drew a wrong glyph.** Do not save. Close the Font Editor. When it asks about unsaved changes, answer that you do not want to save.
- **I replaced a texture by mistake.** Select the texture and press **Revert**. It asks you to confirm.
- **The picture is wrong in the game.** Set **Status** to **Redrawn** again. Redraw the picture and import it.
- **The Textures list is empty.** The plugin lists no textures for this game. Use **File → Open Texture File...** for one file.

## Related pages

- [Build and test](Build_and_Test.md)
- [Width, fonts and tags](Width_Fonts_Tags.md)
- [Configuration](4_Configuration_Guide.md)
- [Troubleshooting](Troubleshooting.md)

<!-- wiki-nav -->
---

**Previous:** [Gemini Web2API (WebTOP)](5_Gemini_Web2API.md) · [Back to the wiki index](README.md) · **Next:** [Building a mod and testing it in the game](Build_and_Test.md)
