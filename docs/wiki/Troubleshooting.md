---
status: current
updated: 2026-10-21
owns: handlers/ and ui/ (messages and dialogs)
tokens: 2.6k
purpose: Symptom, cause and fix tables for the problems a new user meets, plus how to read the log and report a bug.
---
# Troubleshooting

**Language:** English · [Українська](uk/Troubleshooting.md)

This page lists common problems. Find your stage in the list, then find the symptom. Each row gives the cause and the fix.
Messages are quoted as Picoripi shows them in English.

## Install

| Symptom | Cause | What to do |
|---|---|---|
| `setup.bat` stops with `Microsoft Visual C++ 14.0 or greater is required`. | A package must compile, and the C++ compiler is missing. | Install Microsoft C++ Build Tools with **Desktop development with C++**. Run `setup.bat` again. |
| `setup.bat` fails on the Python step. | Picoripi needs Python 3.10 or newer. | Install a newer Python. Run `setup.bat` again. |
| `run.bat` shows no window for a long time. | The first start is slow. | Wait about 15 seconds. Do not start it twice. |
| The start stops with `DLL load failed while importing QtCore`. | The Visual C++ Redistributable is missing, or another program has its own Qt. | Install the Microsoft Visual C++ Redistributable 2015-2022 (x64). Run `setup.bat` again. |

## First start

| Symptom | Cause | What to do |
|---|---|---|
| Picoripi asks where to keep its data. | No data folder is chosen yet. | Choose an empty folder you can write to. Settings and the project list go there. |
| The interface is not in Ukrainian. | The interface language is not set. | Open the **Language** menu and choose Ukrainian. |

## Wizard (New project)

| Symptom | Cause | What to do |
|---|---|---|
| The file status shows **Needs the key file**. | The file is encrypted. | Click **Add the key file for ...**. Choose the key file for that console. |
| The status shows **Cannot read: add its folder**. | The game plugin cannot read this file type. | Remove the file. Add the unpacked game folder with **Add folder...**. |
| The status shows **Not recognised by this game**. | The file is not from this game, or it is a format the plugin does not read. | Remove the file. Or set its **Role** and **Platform** by hand. |
| `Give every file a role.` | At least one file has no role. | Choose a role for each file. Press **Apply**. |
| `Two files have the role ...` | Two files share one role. Only DLC can repeat. | Give the other file its own role. |
| `Not enough free space on ...` | The drive is too full to unpack the game. | Free space on that drive, or choose a project folder on another drive. |
| `Choose the game.` / `Give the project a name.` / `Add at least one file.` | A required field is empty. | Fill in the field. Press **Create project** again. |
| `No key file was chosen. Nothing was created.` | You closed the key file dialog. | Start again and choose the key file. |
| Your game is not in the **Game** list. | Picoripi has no plugin for it. | See [Supported games](Supported_Games.md). |

## Opening a project

| Symptom | Cause | What to do |
|---|---|---|
| `Project Load Failed` with `Failed to load project from: ...`. | The project file cannot be read, or the load stops with a reason. | Read the reason under the path. If the project file is damaged, restore a copy. |
| `Project Not Found` with `Project file not found: ...`. | The project folder was moved or deleted. Picoripi also removes it from the recent list. | Find the folder. Open it with **File → Open Project…** (`Ctrl+O`). |
| The row shows **Plugin missing**. | The game plugin folder is not in `plugins`. | Put the missing folder back in `plugins`. Open the project again. |
| The row shows **Needs attention**. | A path or a file of the project is wrong. The detail panel names the problem. | Read the text under the list. For example, `The original files path does not exist.` Fix that path. |
| The row shows **Missing** or **Unreadable**. | The project file is gone, or it cannot be read. | Restore the project file from a copy. |
| `N blocks have no translation file yet.` | The project is new, or some blocks are not saved yet. | This is normal for a new project. Translate the blocks and save. |

## Editor

| Symptom | Cause | What to do |
|---|---|---|
| The string list is empty. | **Show Unsaved Only** is on and nothing has changed. | Turn off **Show Unsaved Only**. It is off after a restart. |
| Your last edit is missing after a restart. | The edit was not saved. | Press `Ctrl+S` before you close. Check the **Restore unsaved session on startup** setting. |
| `Discard Unsaved Changes?` appears. | You reload or close with unsaved edits. | Press **Cancel**, then save. |
| The list shows **Tag Error**. | A tag in your text does not match the original. | Fix the tag. See [Width, fonts and tags](Width_Fonts_Tags.md). |
| The list shows **Width Exceeded**. | The line is wider than the game's limit. | Shorten the line. See [Width, fonts and tags](Width_Fonts_Tags.md). |
| Saving stops with `... changed outside Picoripi. Reopen the project before saving.` | The file changed on disk after Picoripi read it. The text on screen is old. | Reopen the project. Then edit and save again. |
| The editor reacts slowly. | A large project is loading, or a background task is running. | Wait until the progress stops. If it stays slow, send the log (see below). |

## AI translation

| Symptom | Cause | What to do |
|---|---|---|
| `AI provider is disabled. Configure it in AI Translation settings first.` | The AI provider is set to **Disabled**. | Open **Settings → AI Translation**. Choose a provider. |
| **Test Provider** shows `Connection failed!`. | The proxy or endpoint is not running, or the address is wrong. | Start the proxy. For Gemini Web2API, check the address `http://127.0.0.1:8081/v1`. Test again. |
| Batch translation is very slow, or requests fail. | **Parallel Requests** is higher than the number of proxy accounts. | Set **Parallel Requests** to the number of accounts. Extra requests wait on a cooldown. See [AI translation](11_AI_Translation.md). |

## Build

| Symptom | Cause | What to do |
|---|---|---|
| **Build**, **Export** and **Run** are disabled. | The game plugin declares no build target. | Check [Supported games](Supported_Games.md) for the game's build targets. Some games need a workspace script. See [Build and test](Build_and_Test.md). |
| `No build target yet. Add a project with a build target first.` | The emulator dialog has no build target for the open project. | Open a project that has a build target. Then run it. |
| `The folder is not empty: ...` | The output folder already has files. | Choose an empty folder for the build. |
| The build stops with an error. | A source file or a translation file is wrong. | Read the message. It names the file. Fix that file and build again. |

## Emulator

| Symptom | Cause | What to do |
|---|---|---|
| The emulator does not start. | The platform command is missing or its path is wrong. | Check the platform command in **Settings**. Check the emulator path. |
| The built mod does not load in the emulator. | The mod was not installed. A LayeredFS or Luma folder is not loaded by itself. | Install the built folder in the emulator. Some games need an install step in the command. |

## Data folder and settings

| Symptom | Cause | What to do |
|---|---|---|
| Settings or projects seem to be gone. | Picoripi uses another data folder. | Check **File → Settings (`Ctrl+P`) → Global → Data location…**. Choose the folder that holds your settings. |
| Picoripi asks for the data folder again. | No data folder choice is saved. | Choose the same folder. Keep the pointer file `picoripi_home.json` next to the program. |

## Sharing

| Symptom | Cause | What to do |
|---|---|---|
| `This file is not a shared Picoripi project.` | You opened a different file. | Choose the `.zip` that **Share project...** created. |
| `This shared project was made by a newer Picoripi. Update Picoripi to import it.` | The other person has a newer version. | Update Picoripi. Then import again. |
| `The folder is not empty: ...` | The import folder already has files. | Choose an empty folder. |

## Logs

Picoripi writes a log file named `app_debug.txt`. The default place is the program folder.

1. Open **File → Settings (`Ctrl+P`)**. Open the **Logging** tab.
2. Turn on **Enable File Logging**. Turn on **Enable Console Logging** if you want the log in the console.
3. In the log file path field, leave the text empty for the default `app_debug.txt`. Or type a folder and file name.
4. Repeat the problem. Then open `app_debug.txt`.

## Report a bug

1. Open the issue page: <https://github.com/rashevskyv/Picoripi/issues>. Search for the same problem first.
2. Write what you did, step by step. Write what you expected and what happened.
3. Copy the full message text from the window.
4. Attach `app_debug.txt` from the time of the problem.
5. Name your Picoripi version, your Python version and your Windows version.

**Do not attach** game files, copyrighted dumps or your translation text. Remove personal paths from the log before you upload it.

## Common situations

**Everything fails after an update.**
- Run `setup.bat` again. It updates the packages in `.venv`.
- If it still fails, send the log with the report.

**I made a mistake and saved it.**
- Picoripi does not undo a saved file. Use the copy of the project folder you made before.
- Keep a copy of the project folder before large changes.

**The program is slow only with one project.**
- Note the project name and the stage (editor, build or AI).
- Send the log. Name the project in the report, but not its text.

**A problem is not in this list.**
- Read [Getting started](0_Getting_Started.md) for the first steps.
- Then report it as described above.

<!-- wiki-nav -->
---

**Previous:** [Script Markup Studio](9_Script_Markup.md) · [Back to the wiki index](README.md) · **Next:** [Plugin Developer Guide](3_Plugin_Developer_Guide.md)
