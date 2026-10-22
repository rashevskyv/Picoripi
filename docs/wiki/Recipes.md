---
status: current
updated: 2026-10-21
owns: docs/wiki
tokens: 2.9k
purpose: Short task recipes: what to press, in order, for each common goal, with a link to the full page
---
# Recipes: I want to ...

**Language:** English · [Українська](uk/Recipes.md)

This page lists common goals. Each recipe has a few numbered steps and a link to the page that explains more. Pick the goal in the list, follow the steps, and open the link if you need detail.


## Start and set up

### Install and run Picoripi for the first time
1. Open the program folder and double-click **`setup.bat`**. Wait for "Setup completed successfully".
2. Double-click **`run.bat`**. The first window can take about 15 seconds.
3. In the first dialog, choose the language and the data folder. Press **Use this folder**.

Read more: [Getting Started](0_Getting_Started.md)

### Move the data folder to another disk
1. Press `Ctrl+P` to open **Settings**.
2. Go to **Global** and press **Data location…**.
3. Choose the new folder and press **Copy and use this folder**.
4. Close and start Picoripi again. The old folder stays unchanged.

Read more: [Configuration, the data folder](4_Configuration_Guide.md#the-data-folder)

### Change the interface language
1. Open the **Language** menu. Pick the language. A message says a restart is needed.
2. Press **Restart Now**, or **Restart Later** and restart by hand.

Read more: [Getting Started](0_Getting_Started.md)

### Update Picoripi to a new version
1. Close Picoripi.
2. In the program folder, run `git pull`.
3. Double-click **`setup.bat`** again, then **`run.bat`**.

Read more: [Getting Started](0_Getting_Started.md)


## Add a game

### Add a Switch game with its update and DLC
1. Open the Project Manager with `Ctrl+Shift+M`. Press **+ Add project → New project...**.
2. Step 1: type the game name in **Game** and pick it from the list.
3. Step 2: press **Add files...** and choose the game, its update and its DLC. Check the **Role** of each file.
4. If a row says **Needs the key file**, see the next recipe. Then press **Next**.
5. Step 3: check the project folder and press **Create project**.

Read more: [Creating a project: every kind of game](New_Project_Scenarios.md)

### Add a game that is already unpacked
1. Open the wizard with **+ Add project → New project...**.
2. Step 1: pick the game.
3. Step 2: press **Add folder...** and choose the unpacked game folder.
4. Press **Next**, then **Create project**.

Read more: [New Project Scenarios](New_Project_Scenarios.md)

### Add a game that needs a key file
1. In wizard step 2, the file shows **Needs the key file**.
2. Press **Get keys from the default source**, confirm the dialog and wait. Or press **Add the key file for ...** and choose your own file.
3. Check that the status shows **Ready**.

Read more: [Console keys](4_Configuration_Guide.md#console-keys)


## Share projects

### Continue a project a friend sent me
1. Open the Project Manager (`Ctrl+Shift+M`). Press **+ Add project → Import shared project...**.
2. Choose the `.zip` file.
3. Choose an empty folder for the project.
4. Add your own copy of the game files when Picoripi asks.

Read more: [Project Manager](Project_Manager.md)

### Share my project, or move it to another PC
1. Press `Ctrl+S` to save all changes first.
2. In the Project Manager, expand the project row and press **Share project...**.
3. Save the `.zip` file. It holds the project, the translation and the glossaries. It does not hold the game originals or unsaved text.
4. On the other PC, use **Import shared project...** and add the game files there.

Read more: [Project Manager](Project_Manager.md)


## Translate

### Translate the first line
1. In the **Blocks** tree on the left, click a block, for example `zel_00.bmg`.
2. In **Strings in block**, click a line. Click in **Editable** and type your translation.
3. Press `Ctrl+S` to save.

Read more: [Translating in the editor](Editor_Basics.md)

### Translate with the original text as help
1. Select a line. The source text shows in **Original** on the left. You cannot type there.
2. Press the `→` arrow in the narrow column. It copies the original into **Editable**.
3. Change the copied text into your translation and press `Ctrl+S`.

Read more: [User Guide, Original and Editable](1_User_Guide_and_Workflow_Pipeline.md#13-original-reference-tabs-and-editable)

### Use a reference translation or another language
1. Press `Ctrl+P`, then go to **Project → File Paths**.
2. In **Reference Translation / ROM Path**, type the path or press **...**. Choose a folder, or a game disc image.
3. Press **OK**. The reference text shows next to your translation.

Read more: [Configuration, File Paths](4_Configuration_Guide.md#file-paths)

### Mark a place and come back to it
1. Go to the line and press `Ctrl+B` (**Add Bookmark...**).
2. Type a name and press **OK**.
3. To return, open the **Bookmarks** menu and click the name.

Read more: [Find, replace and bookmarks](Search_Bookmarks.md)

### Find a word everywhere and replace it
1. Press `Ctrl+H` to open **Advanced search**.
2. Type the word in **Find** and the new word in **Replace with**.
3. Press **Find** to see the matches. Click a match to jump to it.
4. Press **Replace All**, or **Replace** for one match. Close the window and press `Ctrl+S`.

Read more: [Find, replace and bookmarks](Search_Bookmarks.md)

### Undo a mistake or restore my last translation
1. To undo a typing mistake, press `Ctrl+Z`. Press `Ctrl+Y` to redo.
2. To bring back a saved translation, press `Ctrl+Shift+T` (**Restore Translated**).
3. To save a line's translation as a backup, press `Ctrl+T` (**Save Translated**).

Read more: [Saving, undo, backups and recovery](Saving_and_Recovery.md)


## Width and tags

### Change the width limit for one line or the whole game
1. **One line:** select the line. In the field **Max-width:** above **Editable**, type the pixels and press **Apply**. Zero means the plugin default.
2. **One line, back to default:** right-click **Max-width:** and choose **Reset to Plugin Default**.
3. **Whole game:** press `Ctrl+P`, go to **Project → Rules**, and change **Game Dialog Max Width (px)** (default 300).
4. Press **OK**. Picoripi rescans all lines.

Read more: [Line width, fonts and tags](Width_Fonts_Tags.md) · [Configuration, Rules](4_Configuration_Guide.md#rules)

### Fix all width problems at once
1. Press `Ctrl+P`, go to **Project → Auto-fix**, and tick the problem types to fix. Press **OK**.
2. Go to **Tools → Fix All Strings...** and confirm.
3. Turn on **Show Warnings Only** to check what is left.

Read more: [Warnings and Auto-fix](Warnings_and_Autofix.md)

### Add a tag with the right-click menu, or hide tags
1. Right-click in **Editable**. With no selection, the menu inserts one tag. With selected text, the tag wraps the text.
2. To change the list, press `Ctrl+P` and go to **Project → Context Tags**.
3. To hide tags, press `Ctrl+Q` or choose **View → Hide Tags**. The stored text does not change.

Read more: [Line width, fonts and tags](Width_Fonts_Tags.md) · [Width, Fonts and Tags](Width_Fonts_Tags.md)


## AI and glossary

### Set up an AI provider
1. Press `Ctrl+P` and open **AI Translation**.
2. In **Active Provider**, pick **OpenAI Compatible**, **Ollama Chat**, **Gemini** or **Perplexity**.
3. Fill the key, endpoint and model fields for that provider.
4. Press **Test Provider**, then **OK**.

Read more: [AI Translation](11_AI_Translation.md) · [Gemini Web2API](5_Gemini_Web2API.md)

### Translate one line, one block or the whole game with AI
1. **One line:** select the line and press **AI Translate** above **Editable**.
2. **Several lines:** select them, right-click, and choose **AI Translate**.
3. **One block:** right-click the block and choose **AI: Translate Block**.
4. **Whole game:** go to **Tools → AI Batch Translation**. Try one block first, because it uses a paid service.

Read more: [AI Translation](11_AI_Translation.md)

### Build a glossary
1. Press `Ctrl+G` or the **Glossary…** button under the **Blocks** tree.
2. Pick a term, type the translation on the right, and press **Confirm translation**.
3. For terms from the game text, go to **Tools → Prepare Glossary...**.

Read more: [Localization Pipeline](8_Localization_Pipeline.md) · [Localization Pipeline](8_Localization_Pipeline.md)


## Build and test

### Build a mod and test it in an emulator
1. Save all changes with `Ctrl+S`.
2. In the Project Manager (`Ctrl+Shift+M`), expand the project row and press **Build mod**. Choose a target.
3. Wait for the status line "Built: <path>". If it says "Failed", read the reason.
4. Press **Emulator...** once. Type the emulator command and put `{path}` where the mod goes, for example `"C:\Emu\emu.exe" {path}`.
5. Press **Run in emulator** and choose the target.

Read more: [Building a mod and testing it in the game](Build_and_Test.md) · [Build and Test](Build_and_Test.md)

### Export the mod for a friend
1. Save all changes with `Ctrl+S`.
2. In the Project Manager, expand the project row and press **Export mod**.
3. Choose a target, then an empty folder. Picoripi does not use a folder that has files.
4. Send the folder to your friend.

Read more: [Building a mod and testing it in the game](Build_and_Test.md)

### Add Ukrainian letters to a font
1. Open **Tools → Font Editor...** (or the **A** button on the toolbar).
2. Check that **Fonts Directory Path** in **Settings → Project → File Paths** points to your fonts folder.
3. Set the width of each new letter in **Settings → Project → Font Map**. Press **OK** and check the warnings.

Read more: [Fonts and Textures](Fonts_and_Textures.md) · [Line width, fonts and tags](Width_Fonts_Tags.md)


## Team and safety

### Work together with a teammate in real time
1. Open **Tools → Work Together...**.
2. One person starts a room.
3. The other people join the same room.

Read more: [Working Together](13_Working_Together.md)

### Review the translation on a phone
1. Set up a Companion server on your PC or on a server.
2. Press `Ctrl+P`, open **Companion**, type the **Server URL** and **API Token / PIN**, and press **Test Connection**.
3. Open the Companion address in the phone browser and review the glossary terms.

Read more: [Picoripi Companion](12_Picoripi_Companion.md) · [Configuration, Companion](4_Configuration_Guide.md#companion)

### Recover after a crash
1. Start Picoripi again and open the same project. Picoripi restores the unsaved text that was saved two seconds after your last change.
2. Check the restored lines, then press `Ctrl+S`.

Read more: [Saving, undo, backups and recovery](Saving_and_Recovery.md) · [Saving and Recovery](Saving_and_Recovery.md)

### Report a bug
1. Write down the steps that cause the problem, and what you expected.
2. Open **Settings → Logging** and find the **Log File Path**. Empty means `app_debug.txt` next to the program.
3. Send the steps and the log file on the project's GitHub page: `https://github.com/rashevskyv/Picoripi`.
4. Before you send the log, check it. It can contain part of your text. Never send an API key.

Read more: [Troubleshooting](Troubleshooting.md)

<!-- wiki-nav -->
---

**Previous:** [Picoripi Companion (Mobile PWA & Sync)](12_Picoripi_Companion.md) · [Back to the wiki index](README.md) · **Next:** [User Guide: Interface](1_User_Guide_and_Workflow_Pipeline.md)
