---
status: current
updated: 2026-10-21
owns: ui/project_manager/window.py, core/project_library/
tokens: 2.1k
purpose: The Project Manager window: list, folders, flags, import, share, storage and reopen at start
---
# Project Manager

**Language:** English · [Українська](uk/Project_Manager.md)

The Project Manager lists every game project you added. Use it to open, group, search, rename, move and share
projects. To create a project, read [Creating a project: every kind of game](New_Project_Scenarios.md).

![Project Manager with an expanded row](img/getting_started/11_manager_row_uk.png)

*The screenshot shows the Ukrainian interface.*
Press **File → Project Manager...** or `Ctrl+Shift+M` to open the window. It also opens at start. See [Reopen at start](#reopen-at-start).

## The toolbar

| Button | What it does |
|---|---|
| **+ Add project** | Menu: **New project...**, **Add existing project...**, **Import projects from a folder...**, **Import shared project...** |
| **New folder...** | Makes a folder in the list. Nothing is made on disk |
| **Group glossary...** | Sets the shared glossary of a folder. See [Group glossary](#group-glossary) |
| **Emulator...** | Sets the emulator command for each platform. **Run in emulator** needs it |
| **Search projects** | Filters by name, series, platform, plugin, folder or path. `Ctrl+F` focuses it, `Esc` clears it |
| **List** / **Grid** | Switches the view. The grid shows large icons |
| **Group** | Sets the sections. See below |
| **Sort**, **Descending** | Orders the projects inside each section |

## Grouping and sorting

| Group | Sections |
|---|---|
| **By folder** | Each folder. Projects with no folder go to **No folder** |
| **By platform** | Each platform. Missing platform goes to **No platform** |
| **By readiness** | **Not started** (0 %), **In progress**, **Done** (100 %), **Unknown** |
| **By text amount** | **Small** (up to 1,000 lines), **Medium** (up to 10,000), **Large**, **Unknown** |
| **No grouping** | One section: **All projects** |

**Sort** uses **Project name**, **Lines**, **Platform**, **Readiness** or **Modified**. **Last opened** is always the
first section.

## Folders

Folders exist only in the Manager. Right-click a folder to **Rename folder...** or **Delete folder...**. Right-click a
project to **Move to folder...**. **Delete folder** moves its projects to the top level. No project file is deleted.

## Columns and status

List view columns: **Project name**, **Platform**, **Series**, **Plugin**, **Progress**, **Last opened**, **Status**.

The **Status** column can show these words, separated by commas:

| Status | Meaning |
|---|---|
| **Opens** | The project file is readable |
| **Missing** | The project file is not on disk |
| **Unreadable** | The project file cannot be read |
| **Plugin missing** | The game plugin is not installed |
| **Needs attention** | Another problem. The expanded row lists it |
| **refreshing...** | The row is being scanned again |
| **Built**, **Verified in game** | Your own flags. See [Built and Verified](#built-and-verified) |

## The expanded row

Click the arrow at the left of a row. It shows the path, platform, plugin and game files with their roles, the
series glossary, the line count, translated percent and dates, a resource table (**Text files**, **Font files**,
**Texture files**, **Other files**), the **Built** and **Verified in game** boxes, and these buttons: **Open**,
**Show in folder**, **Remove from manager**, **Change icon...**, **Share project...**, **Build mod**, **Export mod**,
**Run in emulator**.

## Icons

Picoripi reads the game icon at creation for 3DS and GameCube only. **Change icon...** saves your image as
`icon.png` (256 pixels) in the project's `picoripi` folder. **Clear icon** deletes that file, not the game files.

## Rename, move, remove

| Action | What it changes |
|---|---|
| **Rename...** | The name shown in the Manager only. The project file keeps its name |
| **Move to folder...** | The folder in the Manager. It also changes the group glossary stored in the project file |
| **Remove from manager** | Removes the project from the list. Files stay on disk. Picoripi cannot delete a project from disk |
| **Show in folder** | Opens the project folder in Explorer |

To delete a project from disk, delete its folder in Explorer. **Remove from manager** asks for confirmation. When
the project is not open, it also clears the group glossary in the project file.

## Importing projects

**Add existing project...** adds a `project.uiproj` file that is already on disk.

**Import projects from a folder...** searches the folder for `picoripi\project.uiproj` files. Backup and tool folders
are skipped. Tick the projects, then press **Import**. Projects already listed show **Already in the manager**. A
series folder is created when it is missing.

**Import shared project...** opens a `.zip` file. See below.

### Sharing a project

**Share project...** packs the project into one `.zip` file. It holds the project folder, the translation files and
the linked series glossaries. It does **not** hold the original game files. Save unsaved editor changes first, because
they are not in the package.

When you import a shared project, Picoripi asks for your own original game files. The sender's file name is shown.

**Export mod** asks for a folder. **Run in emulator** needs the command set with **Emulator...**. Both run in the background.

## Group glossary

A group glossary is one glossary shared by all projects of a folder.

1. Select a folder or group.
2. Press **Group glossary...**, then **New shared glossary...**, **Link shared glossary...** or **Change shared glossary...**.
3. Press **Unlink shared glossary** to remove it. The glossary file is not deleted.

Each project stores the link in its project file. Moving a project into or out of the folder updates that link.

## Built and Verified

**Built** and **Verified in game** are your own flags. Only you set them, in the expanded row. They are saved in the project file.

## Where data is stored

| File | Where | What it holds |
|---|---|---|
| `project_manager.json` | Data folder | The list, folders, view choices, folder glossaries |
| `project_index.json` | Data folder | Cache of each project's card and line counts |
| `project.uiproj` | Project folder | The project, including the Built and Verified flags |
| `icon.png` | `picoripi` folder of the project | Your icon, if you set one |

The data folder is set in **File → Settings (Ctrl+P) → Global → Data location...**. Original game files are not copied.

## Scan and cache

The window scans every project when it opens. The scan runs in a separate process and counts the lines. A project is
read again only when its file, its plugin or its source files change.

- **Cancel scan** stops the scan. Saved results stay.
- **Hide** hides the progress strip. The scan keeps running.
- Closing the window stops the scan at once.

## Reopen at start

Picoripi opens the project you had open last, if its file still exists. Otherwise the Manager opens. Closing the
Manager with no project open quits the program.

## Common situations

**The list is empty.**
- You have no projects yet. Press **+ Add project → New project...**.

**A project shows Missing.**
- Its `project.uiproj` moved or was deleted. Move it back, or remove the project from the Manager.

**A project shows Plugin missing.**
- The game plugin is not installed in this copy of Picoripi. Install or update Picoripi.

**I removed a project by mistake.**
- Nothing was deleted from disk. Press **Add existing project...** and choose its `project.uiproj`.

**The scan is slow or stuck.**
- Press **Cancel scan**. Open the window again. The scan continues from the cache.

See also: [Creating a project](New_Project_Scenarios.md), [Getting Started](0_Getting_Started.md),
[Troubleshooting](Troubleshooting.md).

<!-- wiki-nav -->
---

**Previous:** [Getting Started](0_Getting_Started.md) · [Back to the wiki index](README.md) · **Next:** [Creating a project: every kind of game](New_Project_Scenarios.md)
