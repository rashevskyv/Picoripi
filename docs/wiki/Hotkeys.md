---
status: current
updated: 2026-10-21
owns: ui/builders/menu_builder.py
tokens: 2.2k
purpose: Every keyboard shortcut and modifier click of the main window and its separate windows, grouped by task, with menu paths
---
# Keyboard shortcuts

**Language:** English · [Українська](uk/Hotkeys.md)

This page lists the keys of Picoripi by task. Each row shows the menu path, so you can find the same action with the mouse. Keys that work only in a separate window are in section 9.

- `Ctrl+Shift+S` means: hold `Ctrl` and `Shift`, then press `S`.
- **No menu item** means the action has a key or a button only.
- The **Shortcuts Help** dialog (`F1`) shows a shorter list. See the end of this page.

## 1. Project and file

| Action | Shortcut | Menu path |
|---|---|---|
| New Project... | `Ctrl+N` | File → New Project... |
| Open Project... | `Ctrl+O` | File → Open Project... |
| Project Manager... | `Ctrl+Shift+M` | File → Project Manager... |
| Save Changes | `Ctrl+S` | File → Save Changes |
| Settings... | `Ctrl+P` | File → Settings... |
| Shortcuts Help | `F1` | Help (top right) → Shortcuts Help |

## 2. Editing text

| Action | Shortcut | Menu path |
|---|---|---|
| Undo Typing | `Ctrl+Z` | Edit → Undo Typing |
| Redo Typing | `Ctrl+Y` or `Ctrl+Shift+Z` | Edit → Redo Typing |
| Save Translated | `Ctrl+T` | Edit → Save Translated |
| Restore Translated | `Ctrl+Shift+T` | Edit → Restore Translated |
| Paste Block Text | `Ctrl+Shift+V` | Edit → Paste Block Text |
| Auto-fix Current String | `Ctrl+Shift+A` | Edit → Auto-fix Current String |
| Hide Tags | `Ctrl+Q` | View → Hide Tags |

In **Editable**, `Enter` starts a new line. In some games, `Shift+Enter` and `Ctrl+Enter` insert a character that the game rules define.

## 3. Find

| Action | Shortcut | Menu path |
|---|---|---|
| Find (show or hide the search bar) | `Ctrl+F` | Edit → Find... |
| Find next | `F3` | No menu item. Search bar **Next** |
| Find previous | `Shift+F3` | No menu item. Search bar **Prev** |
| Advanced Search | `Ctrl+H` | Edit → Advanced Search... |

In the search bar, `Enter` runs **Next**. `F3` and `Shift+F3` work only while the main window is active.

## 4. Problems and rescan

| Action | Shortcut | Menu path |
|---|---|---|
| Next line with a problem | `Ctrl+Down` | No menu item. Arrow above **Editable** |
| Previous line with a problem | `Ctrl+Up` | No menu item. Arrow above **Editable** |
| Rescan All | `Ctrl+Shift+R` | Edit → Rescan All |

## 5. Moving through lines, blocks and folders

| Action | Shortcut | Menu path |
|---|---|---|
| Next line (any) | `Alt+Down` | No menu item |
| Previous line (any) | `Alt+Up` | No menu item |
| Next or previous line in **Strings in block** | `Down` or `Up` alone | No menu item. Not used when several lines are selected |
| Next block | `Alt+Shift+Down` or `Ctrl+Page Down` | Navigation → Next Block Nav |
| Previous block | `Alt+Shift+Up` or `Ctrl+Page Up` | Navigation → Previous Block Nav |
| Next folder | `Alt+Shift+Right` | Navigation → Next Folder Nav |
| Previous folder | `Alt+Shift+Left` | Navigation → Previous Folder Nav |

Picoripi also registers the four `Alt+Shift` arrow keys with Windows. They work even when Windows would take them first.

## 6. View and bookmarks

| Action | Shortcut | Menu path |
|---|---|---|
| Preview | `Ctrl+Shift+P` | View → Preview |
| Add Bookmark... | `Ctrl+B` | Bookmarks → Add Bookmark... |
| Clear All Bookmarks | none | Bookmarks → Clear All Bookmarks |

## 7. Glossary, AI and story tools

| Action | Shortcut | Menu path |
|---|---|---|
| Open Glossary... | `Ctrl+G` | Tools → Open Glossary... (also the **Glossary…** button) |
| Open AI Chat | `Ctrl+Shift+C` | Toolbar button Open AI Chat |
| AI Translate Current String | `Ctrl+Alt+T` | Tools → AI Translate Current String |
| AI Translate Selected Lines | `Ctrl+Alt+L` | Tools → AI Translate Selected Lines |
| AI Translate Entire Block | `Ctrl+Alt+B` | Tools → AI Translate Entire Block |
| AI Reset Translation Session | none | Tools → AI Reset Translation Session |
| Inspect Story Context... | `Ctrl+I` | Tools → Inspect Story Context... |
| MemePalace Context Builder... | `Ctrl+M` | Tools → MemePalace Context Builder... |
| MemePalace Database Viewer... | `Ctrl+Shift+I` | Tools → MemePalace Database Viewer... |

Tools items with no key: **Localization Pipeline**, **Font Editor**, **Textures**, **Script Markup Studio**, **Prepare Glossary**, **Work Together**, **Progress**.

## 8. Mouse with a modifier key

| Click | On | What it does |
|---|---|---|
| `Ctrl`+click | A glossary term in **Original** | Opens that glossary entry for editing |
| `Ctrl`+click | **AI Translate** or **AI Variation** | Opens the prompt editor first |
| `Ctrl`+click | **Auto-fix** | Lets you pick the rules to apply |
| `Shift`+click | **Auto-fix** | Page-local fix. Text does not move across pages |
| `Ctrl`+mouse wheel | Blocks tree | Changes the tree font size |
| Right-click | **Editable** | Inserts a tag. With a selection, the tag wraps the text |

## 9. Separate windows

These keys work only when their window has focus.

| Window | Key | Action |
|---|---|---|
| Glossary | `Ctrl+S` | Saves the glossary |
| Glossary | `Esc` | Closes the window |
| Glossary, term edit dialog | `Enter` | Confirms the entry |
| Project Manager | `Ctrl+F` | Moves the cursor to the search box |
| Project Manager | `Esc` | Clears the search text. The next `Esc` closes the window |
| Script Markup Studio | `Ctrl+F` | Moves the cursor to the search box |
| Script Markup Studio | `Ctrl+M`, `Ctrl+S`, `Ctrl+P`, `Ctrl+T`, `Ctrl+B`, `Ctrl+I` | Mark, Structure, Speaker, Text, Breaker, Ignore |
| Script Markup Studio | `Ctrl+Z` / `Ctrl+Y` | Undo / Redo |
| Script Markup Studio | `Ctrl+Shift+Up` / `Ctrl+Shift+Down` | Changes the outline depth of the selected items |
| Script Markup Studio | `F2` | Renames the outline item |
| Font Editor | `Ctrl+S` | Saves |
| Font Editor | Arrow keys / `Ctrl`+arrow keys | Move between glyphs / move the glyph pixels |
| Font Editor | `Ctrl+C` / `Ctrl+V` | Copies / pastes glyph values in the table |
| Font Editor | `Esc` | Ends a cell edit first. Otherwise closes the window |
| Textures | `Ctrl+O`, `F5` | Open, Reload |
| Textures | `Ctrl+E`, `Ctrl+I` | Export PNG, Import PNG |
| AI Chat | `Ctrl+Enter` / `Enter` | Sends the message / new line |
| AI Chat | `Ctrl+Shift+R` | Presses the **Retry** button |

## 10. Keys used in more than one place

Only the window with focus reacts. No key is set twice in the main window menus.

| Key | Main window | Other window |
|---|---|---|
| `Ctrl+P` | Settings | Speaker (Studio) |
| `Ctrl+S` | Save Changes | Save (Glossary, Font Editor), Structure (Studio) |
| `Ctrl+T` | Save Translated | Text (Studio) |
| `Ctrl+B` | Add Bookmark | Breaker (Studio) |
| `Ctrl+M` | MemePalace Context Builder | Mark (Studio) |
| `Ctrl+I` | Inspect Story Context | Ignore (Studio), Import PNG (Textures) |
| `Ctrl+Shift+R` | Rescan All | Retry (AI Chat) |
| `Ctrl+Enter` | Inserts a game character in **Editable**, in some games | Sends (AI Chat) |

`Ctrl+Alt+T`, `Ctrl+Alt+L` and `Ctrl+Alt+B` are AI shortcuts. On keyboards that use AltGr, `Ctrl+Alt` can type a symbol instead. This was not tested. Plugins can add their own shortcuts. This page does not check each plugin.

## The Help dialog

**Help → Shortcuts Help** (`F1`) lists 22 shortcuts in three groups: General (6), Editor (8) and Navigation (8). Every key in that list matches the code. The dialog does not list:

- `Ctrl+N`, `Ctrl+O`, `Ctrl+Shift+M`, `Ctrl+T`, `Ctrl+Shift+T`, `Ctrl+B`, `Ctrl+Shift+P`, `Ctrl+Shift+R`
- `Ctrl+M`, `Ctrl+I`, `Ctrl+Shift+I`, `Ctrl+Alt+T`, `Ctrl+Alt+L`, `Ctrl+Alt+B`
- `Ctrl+Page Up` and `Ctrl+Page Down`
- The keys of the separate windows (section 9)

## Common situations

- **A key does nothing.** Make the window that should react active. Studio keys do not work in the main window.
- **Ctrl+S saved only the glossary.** The Glossary window had focus. Click the main window and press `Ctrl+S` again.
- **Ctrl+Down skips lines I expect.** It goes only to lines with a problem. Use `Alt+Down` for every line.
- **Ctrl+Shift+R in AI Chat does not rescan.** In the chat window it presses **Retry**. Use **Edit → Rescan All** in the main window.
- **F3 does nothing.** Make the main window active. `F3` does not work in other windows.
- **I want the key for a button.** Hover over the button. Many tooltips show the key in parentheses.
- **Ctrl+Alt shows a symbol.** Your keyboard may use AltGr. Use the menu item instead.

<!-- wiki-nav -->
---

**Previous:** [User Guide: Interface](1_User_Guide_and_Workflow_Pipeline.md) · [Back to the wiki index](README.md) · **Next:** [Configuration](4_Configuration_Guide.md)
