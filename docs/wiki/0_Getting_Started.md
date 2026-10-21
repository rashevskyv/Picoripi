---
status: current
updated: 2026-10-21
owns: ui/project_manager/wizard.py
tokens: 1.4k
purpose: First start to the first saved line: install, first start, new project, first translation, where to read next
---
# Getting Started

**Language:** English · [Українська](uk/0_Getting_Started.md)

This page takes you from GitHub to your first saved line of translation. It has five steps. A separate page covers
each topic in depth, and the links are at the end. The screenshots come from real windows. They show the Ukrainian
interface; pick English in the first dialog to see the English labels used below.

```mermaid
flowchart LR
  A[Install] --> B[First start]
  B --> C[New project]
  C --> D[First line]
  D --> E[Save]
  E --> F[What next]
```

## 1. Install

You need Windows and Python 3.10 or newer (3.14 is the tested one). Windows also needs the Microsoft C++ Build Tools
once, because one package is built on your computer (see the [README](../../README.md)).

1. Download the program: `git clone https://github.com/rashevskyv/Picoripi.git`, or press **Code → Download ZIP** on
   GitHub and unpack the archive.
2. Open the program folder and double-click **`setup.bat`**. It makes a `.venv` folder and installs the packages. This
   takes one to three minutes and ends with "Setup completed successfully".
3. Double-click **`run.bat`**. The first window can take about 15 seconds to appear. Do not start it twice.

To update, run `git pull` and run `setup.bat` again.

## 2. First start

The first window asks where Picoripi keeps your data and lets you choose the interface language. The language starts as
the language of Windows when Picoripi has it. Change it in the list at the top and the window changes at once.

![First start dialog](img/getting_started/01_first_start.png)

The default is **Next to the program, in the data folder**. Press **Use this folder**. Nothing is deleted. For the
other choices, and for changing the folder later, see [Configuration](4_Configuration_Guide.md).

The Project Manager opens next. It is empty for now.

![Empty Project Manager](img/getting_started/02_project_manager.png)

## 3. Create a project

Press **+ Add project → New project...**. The wizard has three steps.

1. **Game.** Type a part of the game's name and pick it from the list. **Project name** fills in by itself.

   ![Step 1: the game](img/getting_started/03_wizard_game.png)

2. **Files.** Press **Add files...** and choose the game files: the game, its update and its DLC. If the game is
   already unpacked, press **Add folder...**. Picoripi sets the role and platform of each file itself. If a key file
   is needed, it says so in the error row.

   ![Step 2: the files](img/getting_started/04_wizard_files.png)

3. **Project folder.** Accept the suggested `Documents\Picoripi\<project name>` or choose another. Press **Create
   project**.

   ![Step 3: the project folder](img/getting_started/06_wizard_location.png)

A big game takes a few minutes to unpack. Then the Manager closes and the project opens in the editor.

Every case (Switch with update and DLC, 3DS, Wii, an unpacked folder, key files) is on the page [Creating a project:
every kind of game](New_Project_Scenarios.md). The Manager itself is on [Project Manager](Project_Manager.md).

## 4. Translate your first line

![Main window](img/getting_started/07_editor_uk.jpg)

1. In the **Blocks** tree on the left, pick a block with text, for example `zel_00.bmg`.
2. At the top, in **Strings in block**, click a line.
3. Below it, **Original** (read only) is on the left and **Editable** on the right. Click in **Editable** and type
   your translation.
4. The number left of a line in **Editable** is its width in game pixels. If a line is too wide, Picoripi warns you.

![Translating in the editor](img/getting_started/08_translation_uk.jpg)

Leave tags such as `{boxatleast:30}` where they are: the game reads them.

## 5. Save

Press `Ctrl+S`. Picoripi writes the translation into the `translation` folder of your project. It never changes the
original files. For backups and recovery see [Saving and recovery](Saving_and_Recovery.md).

## 6. What next

| I want to... | Page |
|---|---|
| Understand the editor window and the keys | [Translating in the editor](Editor_Basics.md), [Keyboard shortcuts](Hotkeys.md) |
| Set line width, fonts and tags | [Line width, fonts and tags](Width_Fonts_Tags.md) |
| Fix problems in my translation | [Warnings and auto-fix](Warnings_and_Autofix.md) |
| Find and replace a word in the whole game | [Find, replace and bookmarks](Search_Bookmarks.md) |
| Translate with AI | [AI Translation](11_AI_Translation.md), [Localization Pipeline](8_Localization_Pipeline.md) |
| Build a mod and test it in the game | [Building a mod and testing it](Build_and_Test.md) |
| Work together with others | [Working Together](13_Working_Together.md) |
| A quick answer to "how do I..." | [Recipes](Recipes.md) |
| Find the cause of an error | [Troubleshooting](Troubleshooting.md) |
| See which games are supported | [Supported games](Supported_Games.md) |

## What a few well-known games need

| Game | Files to add | Key file |
|---|---|---|
| Yo-kai Watch, Switch | the game `.nsz` or `.nsp` and its update | Switch `prod.keys` |
| Yo-kai Watch, 3DS | the `.3ds` | 3DS keys, only when the file is encrypted |
| Twilight Princess, GameCube | the `.iso` | none |
| Twilight Princess, Wii | the Wii `.iso` | Wii `keys.bin` |
| Twilight Princess HD, Wii U | the unpacked game folder (Picoripi cannot read `.wux` yet) | none |

<!-- wiki-nav -->
---

[Back to the wiki index](README.md) · **Next:** [Project Manager](Project_Manager.md)
