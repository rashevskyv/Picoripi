---
status: current
updated: 2026-11-08
owns: tools/bfn_editor/ and ui/texture_window.py
tokens: 2.7k
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
5. To find a glyph in **Glyph Table**, right-click it and press **Show in Glyph Table**. The table opens on the row of this glyph. If the table search hides the glyph, the editor clears the search.

The editor reads all fonts of the project once, right after it opens. Switching between fonts and sheets does not decode a font again. The tree shows all sheets of each font.

The fonts of a project come from the game plugin. The Font Editor can also open a font file that you choose yourself. The editor reads many game font formats. Examples are BFN, BFFNT, NFTR, G1T and TTF.

## Add a Ukrainian letter

A letter needs a glyph. Find a free glyph for it or draw over an unused one.

1. Open the font in the Font Editor. Find the glyph in **Glyph Table**.
2. Draw the letter. Use one of these ways:
   - Right-click the glyph and press **Render Font to Selected Glyph...**. Choose the **Font File...**, the **Font Size (px):** and the style. The editor draws the letter from a system font.
   - Double-click the glyph. It opens in your external image editor (see below). Draw and save there (`Ctrl+S`).
   - Right-click the glyph and press **Export Selected Glyph PNG...**. Draw in an image editor. Then press **Import Selected Glyph PNG...**. The PNG must have the same size as the glyph. Otherwise the editor refuses it.
3. Press **Auto-detect Width** to set the width of the letter.
4. Press **Save Changes** (`Ctrl+S`).

After saving, the editor writes `translation_map.json` into the project folder. Picoripi also reloads the font widths. It checks the text again by itself.

## Edit in an external image editor

Press **External Editors...** under the sheet list. Add one or more editors: a name, the program and its arguments. `{file}` in the arguments is the image path. The first editor is the default one. When YY-CHR is found, it is the first entry.

- Double-click a glyph: the editor opens this one glyph cell.
- Double-click the sheet background or a sheet in the list: the editor opens the whole sheet.
- Right-click a sheet in the list and press **Send to External Editor**. Choose the editor.

The editor gets a BMP file. It is 8-bit indexed when the sheet has 256 colours or fewer, so tile editors such as YY-CHR can open it. Otherwise it is 24-bit. A BMP has no transparency: each colour is shown as it looks over black, and Picoripi maps it back to the exact colour of the font.

Save in the external editor (`Ctrl+S`). Picoripi takes the change at once. It is one step of **Undo**. A file of another size is not applied; the status bar says so. Then press **Save Changes** in the Font Editor as usual. The BMP files are deleted when the font closes.

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

### Redraw a texture with an image AI

1. Set the image model in **Settings → Image AI** (see [Configuration](4_Configuration_Guide.md#image-ai)).
2. Right-click a texture in the list and press **Send to Image AI...**.
3. Check the prompt. It comes from the settings; you can change it for this request.
4. Press **Send**. The answer appears next to the original. Each request costs money at the provider. When the key or the agent command is missing, **Set up Image AI** opens: enter the OpenAI key (it is saved as the AI Translation OpenAI key) or pick a local agent, then press **OK**. An error opens a message box.
5. Press **Accept** to write the answer into the texture. Picoripi writes it the same way as **Import PNG...**: it keeps the texture's size and format. Press **Send** again for another try, or **Cancel**.
6. Press **Revert** to put the game's original back.

A local agent gets the texture at its own size and must write a PNG of the same size. Image models answer on a few fixed canvases (square, wide, tall). Picoripi puts the texture on the closest canvas and scales the answer back to the texture's size. **Cancel** drops an answer that is still on its way; the request itself ends at the latest after the timeout.

## Fonts folders and the default font

| Setting | Where | What it does |
|---|---|---|
| Original Fonts Directory Path (original font) | **Settings → Project → File Paths** | A folder with the original fonts. Optional |
| Fonts Directory Path (translated font) | **Settings → Project → File Paths** | A folder with your own fonts. Optional |
| Default Font for Project | **Settings → Project → Display** | The font the project uses. The first item is **None** |

The list of default fonts holds the fonts of the game plugin. It also holds the fonts of your fonts folder. The program restarts after you change the default font.

## How plugins declare fonts and textures

Translators do not write this part. The plugin author lists the fonts in `font_sources.json` and the textures in `texture_sources.json`. The author can also return the lists from code. Each entry gives a file, a format and a label. If a game has no entry, the Font Editor and the Textures window show nothing for it. The author's details are in the [Plugin Developer Guide](3_Plugin_Developer_Guide.md).

## Edit a font from the command line

An agent or a script can export a plugin font as PNG sheets and import them back. Run this from the Picoripi folder:

```
python -m core.font_formats.sheet_io project-export <project.uiproj> "<label>" <folder>
python -m core.font_formats.sheet_io project-import <project.uiproj> "<label>" <folder>
```

`<label>` is the font's label in `font_sources.json`, or a unique start of it. The export reads the translation copy if it exists, else the game's file. The import writes the translation copy in the same way as the Font Editor, and keeps the old copy as `<file>.bak_<time>`. It uses the font's own game constants, so a texture grid keeps its cell size and characters.

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
