---
status: current
updated: 2026-10-21
owns: handlers/issue_scan_handler.py
tokens: 2.0k
purpose: Problem lines, warning colours, navigation, Detection and Auto-fix settings, Fix All Strings, rescans and the spell checker.
---
# Warnings and auto-fix

**Language:** English · [Українська](uk/Warnings_and_Autofix.md)

This page explains the warnings that Picoripi shows for each line. It shows how to find problem lines and how to fix them. Read it when a line has a coloured strip, or when you want to fix many lines at once.

![Main window](img/getting_started/07_editor_uk.jpg)

*The screenshot shows the Ukrainian interface. The labels on this page are English.*

## What a problem line is

Picoripi checks every line by itself. A line with a problem has at least one problem type. Each problem type has a name, a colour and a check.

The list of types depends on the game plugin. The standard types are:

| Name | What it means |
|---|---|
| **Tag Warning** | The tag count does not match, or a tag is not valid |
| **Subline Width Exceeded** | A subline is wider than the hard limit |
| **Empty Odd Display Subline** | A displayed odd-numbered subline is empty or shows `0` |
| **Empty First Line of Page** | The first line of a page is empty, but later lines are not |
| **Short Subline** | A subline has no end punctuation and room for the next word |
| **Single Word Subline** | A subline has one word only |
| **Single Word Subline (Non-Start)** | A subline has one word only, and it is not the first line of a window |
| **Bad Spacing** | Two spaces in a row, or a line that starts with a space |
| **Missing Tag Spacing** | No space around a visible tag, or between words split by zero-width tags |
| **Broken Icon-Hyphen Wrap** | A tag, a hyphen and a word are split by a line break |

Hold the mouse over a type in **Settings → Project → Detection** to read its description.

## Coloured strips

- In **Strings in block**, a coloured strip sits beside the line number. Each problem type has its own colour.
- In the **Blocks** tree, the strips at the right show the problem types in that block.
- The colour of a type is the same in the lists under **Detection** and **Auto-fix**.

## Find the next problem

| Action | Keys |
|---|---|
| Next line with a problem | `Ctrl+↓` or the arrow above **Editable** |
| Previous line with a problem | `Ctrl+↑` or the arrow above **Editable** |
| Next line, with or without a problem | `Alt+↓` |
| Next block | `Alt+Shift+↓` |

The search stays in the current block. At the end of the block, it starts again from the top of the block. If the block has no problem line, the selection does not move.

## Show only problem lines

1. Turn on **Show Warnings Only** in the filter bar above **Strings in block**.
2. Click **Warnings: X / Y** and choose the types to show.

The first number is the count of chosen types. The second number is the count of types that are on in **Detection**. A type that is off in **Detection** does not count.

## Detection and Auto-fix settings

Go to **File → Settings (`Ctrl+P`) → Project**.

- **Detection** has one box for each problem type. A box that is off turns that check off.
- **Auto-fix** has two general boxes:
  - **Align sentences to original page layout**
  - **Prevent adding empty padding lines during pagination**
- Below them, **Auto-fix** has one box for each problem type. These boxes choose which types the fix may change.

By default, every detection box is on. Every auto-fix box is on, except three: **Tag Warning**, **Single Word Subline** and **Single Word Subline (Non-Start)**. The two general boxes are off. A plugin can set other defaults.

## The Auto-fix button

The **Auto-fix** button is above **Editable**. It fixes the current line.

| Action | Result |
|---|---|
| Click | Fixes the line with every enabled type |
| `Ctrl`+click | Opens a list. You choose the types to fix |
| `Shift`+click | Fixes each page on its own. Text does not move across a page break |
| `Ctrl`+`Shift`+click | Opens the list, and then fixes each page on its own |
| `Ctrl+Shift+A` | Fixes the line with every enabled type. It never opens the list |

The modifiers work on the button only. The keyboard shortcut always runs the plain fix.

## Fix all strings

Go to **Tools → Fix All Strings...**.

1. The dialog lists the problem types. It starts with the choices from **Auto-fix** in Settings.
2. Tick the types you want. If you tick none, the program stops and shows a message.
3. Press **OK**. The program fixes all strings in the background.

Save your work with `Ctrl+S` before you start.

## Rescan

- **Rescan All** (`Ctrl+Shift+R`) rebuilds the widths and the warnings for the whole project. The toolbar button does the same.
- Right-click one block in the **Blocks** tree to rescan only that block.
- A large project takes time on the first scan. The program shows a progress window.

Use **Rescan All** after you change fonts, tags or width limits. Use it also when the strips look wrong.

## Spelling

The spell checker is separate from the problem types.

- Go to **Settings → Spelling**. Choose the **Dictionary Language:**.
- Press **Manage Dictionaries...** to download or remove dictionaries. The same window lists the words you added.
- Use **Add to Dictionary** from the spellcheck menu to add a word.
- The **Misspelled words** list shows the words the checker finds. Click a word to review it. The main editor jumps to its line.

See also [Settings](4_Configuration_Guide.md) for the other settings tabs.

## Plugins with their own problem types

A plugin lists its problem types in its `config.py` file. It uses the shared checks from `plugins/common/problem_rules/`. A plugin can add its own types, change their names and colours, and set its own default settings. A plugin can also leave out a shared type that its game does not use. The mechanism and the steps are in the [Plugin developer guide](3_Plugin_Developer_Guide.md).

## Common situations

**The warning stays after I fixed the line.**
- Press **Rescan All** (`Ctrl+Shift+R`).
- Check that the line is saved with `Ctrl+S`.

**A problem type that I need is not in the list.**
- The plugin does not use that check.
- Plugins define their own types. See the [Plugin developer guide](3_Plugin_Developer_Guide.md).

**Auto-fix changed more than I wanted.**
- Press `Ctrl+Z` to undo the last change.
- Next time, use `Ctrl`+click and tick only the types you need.

**Auto-fix moved text across a page break.**
- Use `Shift`+click on the **Auto-fix** button. Each page is fixed on its own.

**Auto-fix does nothing for a type.**
- Check **Auto-fix** in **Settings → Project**. A type with its box off is not fixed.
- Check **Detection** too. A type that is not detected is not fixed.

**The list of warnings is too long.**
- Turn on **Show Warnings Only**.
- Click **Warnings: X / Y** and choose one or two types.

**Fix All Strings did not change a line I expected.**
- Check that the type was ticked in the dialog.
- Check that the type is on in **Detection**.

**Fix All Strings changed too many lines.**
- See [Saving, undo and recovery](Saving_and_Recovery.md) to restore earlier work.

**A word is marked as a spelling error, but it is correct.**
- Click **Add to Dictionary** for that word.
- Check that the **Dictionary Language:** is the one you write in.

**The first scan is slow.**
- Wait for the progress window to finish.
- A large project takes longer than a small one.

## Related pages

- [Getting Started](0_Getting_Started.md)
- [Editor basics](Editor_Basics.md)
- [Line width, fonts and tags](Width_Fonts_Tags.md)
- [Saving, undo and recovery](Saving_and_Recovery.md)
- [Troubleshooting](Troubleshooting.md)

<!-- wiki-nav -->
---

**Previous:** [Line width, fonts and tags](Width_Fonts_Tags.md) · [Back to the wiki index](README.md) · **Next:** [Find, replace and bookmarks](Search_Bookmarks.md)
