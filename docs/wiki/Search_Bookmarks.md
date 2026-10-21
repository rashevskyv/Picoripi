---
status: current
updated: 2026-10-21
owns: components/search_panel.py, handlers/search_handler.py, dialogs/search_review/, handlers/bookmark_handler.py
tokens: 1.9k
purpose: Quick find, Advanced Search & Replace, search history and bookmarks.
---
# Find, replace and bookmarks

**Language:** English · [Українська](uk/Search_Bookmarks.md)

This page explains how to find text, replace text and mark lines. Use it when you look for a line, change a word in many lines, or return to a line later.

## Quick find

Press `Ctrl+F` (**Edit → Find...**). A search bar opens above the editor. Press `Ctrl+F` again to hide it.

1. Type text in the **Find...** box.
2. Press `Enter` or click **Next**. The editor jumps to the next match.
3. Press `F3` for the next match. Press `Shift+F3`, or click **Prev**, for the previous match.
4. Read the status label. It shows `Found: B<block number>, S<string number>`.

The boxes next to the search text:

| Box | Meaning |
|---|---|
| **Aa** | Match upper and lower case. |
| **Fuzzy** | Find similar words. Endings may differ. |
| **Original** | Search the original text, not the translation. |
| **No Tags** | Ignore tags, line breaks and extra spaces. On by default. |

Rules for quick find:

- The search covers all blocks in the project.
- The search does not wrap around. At the end it shows `Not found (end)`. Press **Next** again to start from the top.
- Changing the text or a box starts the search from the top.
- Quick find only moves the cursor. It does not change any text.
- If the box is empty, the status label asks for a query.

Click **Advance** to open Advanced Search with the same text and boxes.

## Advanced Search & Replace

Press `Ctrl+H`, or choose **Edit → Advanced Search...**. The window lists all matches on the left.

1. Type the search text in **Find:**.
2. Type the new text in **Replace with:**.
3. Tick the boxes you need. They work as in quick find.
4. Click **Find**. The list fills and the status shows `Match 1 of <total> | Block: ... | String: ...`.
5. Click a match. The main editor jumps to that line.
6. Click **Replace**, **Skip** or **Replace All**. See the table below.
7. Close the window. Your replacements become unsaved changes.
8. Press `Ctrl+S` in the main window to write them to disk.

| Button | What it does |
|---|---|
| **Find** | Searches again with the current text and boxes. Rebuilds the list. |
| **Replace** | Changes the current match only. Moves to the next match. |
| **Replace All** | Changes every match in the list. |
| **Skip** | Leaves the current match unchanged. Moves to the next match. |
| **← Previous** / **Next →** | Moves between matches. Changes no text. |

**Match case on replace** keeps capital letters. `Word` becomes `Replacement`. `WORD` becomes `REPLACEMENT`. If your replacement starts with a capital letter, Picoripi uses it as you typed it. With the box off, Picoripi uses your text as typed.

Select several matches with `Ctrl`-click or `Shift`-click. Selecting does not jump to a line. Right-click the selection for actions such as AI translate, spellcheck, revert and restore.

### How replacements reach the project

- Replacements stay in the window until you click **Find** or close the window.
- Then they become unsaved changes. The window title shows the unsaved mark.
- They reach the translation files only after `Ctrl+S`.
- `Ctrl+Z` does not undo replacements made in this window. The code does not record them in the undo history. Test this on a copy before you rely on it.

## Search history

- The drop-down list under the search box keeps your recent searches. It keeps up to 20.
- Click an item to search for it again.
- The history stays after you restart the program.

## Bookmarks

A bookmark marks one line. Add a bookmark to return to a line later.

1. Click a line.
2. Press `Ctrl+B`, or choose **Bookmarks → Add Bookmark...**.
3. Change the name if you want. The default name is `Line <number>: <start of the text>`.
4. Click **OK**. The bookmark appears in the **Bookmarks** menu.

You need an open project and a selected line to add a bookmark.

| Item | What it does |
|---|---|
| **Add Bookmark...** | Adds the current line. |
| Bookmark list | Click a bookmark to jump to its line. Each item shows name, block and line. |
| **Delete Bookmark** | Opens a list. Pick one bookmark. Confirm the question. |
| **Clear All Bookmarks** | Deletes all bookmarks of the project. Confirm the question. |

Limits:

- A bookmark stores a block position and a line number. It does not store an ID. If you move or reorder blocks, a bookmark can point to another line. Delete and add it again.
- A bookmark belongs to one project. If another project is open, the program shows a warning and does not jump.
- If the program cannot find the block in the Blocks tree, the jump does nothing.
- The program sets no limit on the number of bookmarks.

## Navigation menu

The **Navigation** menu moves between blocks and folders. See [Virtual Navigation and Preview](6_Virtual_Navigation_and_Preview.md).

| Item | Shortcut |
|---|---|
| Next Block Nav | `Alt+Shift+Down` |
| Previous Block Nav | `Alt+Shift+Up` |
| Next Folder Nav | `Alt+Shift+Right` |
| Previous Folder Nav | `Alt+Shift+Left` |

## Finding with filters

The strings list has filters that also help you find lines. Examples: **Show Unsaved Only**, **Show Overrides Only**, **Hide translated**, **Show Warnings Only**. Use them with search. See [Editor Basics](Editor_Basics.md).

## Common situations

- **Rename a character everywhere.** Open Advanced Search. Type the old name in **Find:** and the new name in **Replace with:**. Tick **Aa** if case matters. Click **Find** and check the list. Click **Replace All**. Close the window and press `Ctrl+S`.
- **Make a backup first.** Replace All cannot be undone with `Ctrl+Z` after you close the window. Copy the project folder before a large replacement.
- **Find untranslated lines.** Quick find does not search for empty translations. Use the **Hide translated** filter in the strings list.
- **Find a line by its original English.** Tick **Original**. Type a word from the English text. Click **Next**. Untick **Original** before you edit the line.
- **Do not use Replace with Original ticked.** This case is not verified. Replacement text may not go into the translation as you expect. Untick **Original** before you click **Replace** or **Replace All**.
- **Search finds nothing.** Try **Fuzzy** for a similar word. If the text has tags, such as `{name}`, untick **No Tags**.
- **Quick find says `Not found (end)`.** No more matches exist below the cursor. Press **Next** again to search from the top.
- **Too many matches.** Use Advanced Search. Click the matches you need, and use **Replace** for each one. Use **Skip** for the others.
- **A bookmark jumps to the wrong line.** You moved or reordered blocks after you added it. Delete the bookmark and add it again.
- **A bookmark shows a warning about another project.** Open the project that owns the bookmark.

## Related pages

- [Editor Basics](Editor_Basics.md) for the strings list and filters.
- [Saving, undo, backups and recovery](Saving_and_Recovery.md) for undo, backups and the session file.
- [Hotkeys](Hotkeys.md) for all shortcuts.

<!-- wiki-nav -->
---

**Previous:** [Warnings and auto-fix](Warnings_and_Autofix.md) · [Back to the wiki index](README.md) · **Next:** [Saving, undo, backups and recovery](Saving_and_Recovery.md)
