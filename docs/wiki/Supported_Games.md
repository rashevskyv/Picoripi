---
status: current
updated: 2026-10-21
owns: plugins/
tokens: 6.6k
purpose: Table of every game plugin with platforms, wizard needs and build targets.
---
# Supported games

**Language:** English · [Українська](uk/Supported_Games.md)

This page lists every game plugin in Picoripi, with its platforms, the files the New Project wizard asks for, and the build targets. Each game is read by its own plugin in the plugins folder. Use the table to check that your game is supported before you start.

For the technical notes of one game (source folders, file formats, tags, previews, builds), see [Game notes](Game_Notes.md).

## How to find your game

1. Open **File → New Project…** (`Ctrl+N`).
2. In the **Game** box, type a part of the game's name. The list narrows as you type.
3. Select the game. Compare its **Platform** with your copy.
4. Read **What the wizard needs** and add the files it names.

## If your game is not listed

If your game is not in the table, Picoripi cannot read it yet. Copy the `default_plugin` folder in `plugins`, rename it and follow the [Plugin Developer Guide](3_Plugin_Developer_Guide.md).

Name the new folder in lowercase, for example `my_game`.

## Games by platform

### Nintendo Switch

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Ace Attorney Trilogy | Nintendo 3DS, Nintendo Switch | Game files (folder or image) | None | 3DS and Switch versions. |
| Animal Crossing: New Horizons (Switch) | Nintendo Switch | Game files (folder or image) | None | Switch, 2020. |
| Atomic Bomberman | PC, Nintendo Switch | Game files (folder or image) | Atomic Bomberman: language file for the PC port; Atomic Bomberman: export folder for Switch (sdmc:/switch/atomic-bomberman/lang) | PC and Switch. Language file and Switch export folder. |
| Black & White (openBlack Switch port) | Nintendo Switch | Base game (PC data folder or Switch port SD folder) | openBlack SD card: switch/openblack/game/Scripts/InfoScript2.txt | openBlack Switch port. The port does not show game text yet. |
| Castlevania: Belmont's Curse | Nintendo Switch | Base game, Update; Key file if encrypted (Switch) | Switch: LayeredFS mod (Atmosphere) | Switch 1.1.0 (v65536). |
| Code of Princess | Nintendo 3DS, Nintendo Switch | Game files (folder or image) | None | 3DS, and Switch EX. Text is inside the executable. |
| Corpse Party | Nintendo 3DS, Nintendo Switch | Game files (folder or image) | None | 3DS and Switch 2021. A text may not outgrow its message slot. |
| Donkey Kong Country: Tropical Freeze | Nintendo Switch | Game files (folder or image) | None | Switch update v131072. Fonts and textures not opened yet. |
| Dragon Quest Builders 1 + 2 (Switch) | Nintendo Switch | Game files (folder or image) | None | Switch. Builders 1 and 2 in one plugin. |
| Jak and Daxter | PlayStation 2, Nintendo Switch | Game files (folder or image) | None | Switch OpenGOAL port. Jak 1, Jak II and Jak 3 in one plugin. |
| Layton Brothers: Mystery Room | Nintendo Switch, Android | Game files (folder or image) | None |  |
| Link's Awakening (Switch) | Nintendo Switch | Game files (folder or image); Key file if encrypted (Switch) | LAS Recomp (romfs.bin) | Base game v1.0.0 only. Needs prod.keys once. |
| Mario vs. Donkey Kong (Switch) | Nintendo Switch | Game files (folder or image) | None |  |
| Metal Gear Solid (Master Collection) | PC, Nintendo Switch | Game files (folder or image) | None | PC Steam and Switch. USA game. |
| Metal Gear Solid 2 / 3 (Master Collection) | Nintendo Switch, PC | Game files (folder or image) | None | Switch. PC not yet. |
| Metal Gear Solid 4 (Master Collection) | Nintendo Switch, PC | Game files (folder or image) | None | Switch and PC, Master Collection. |
| Metal Gear Solid Master Collection Bonus Content | Nintendo Switch | Game files (folder or image) | None | Switch bonus content, volumes 1 and 2. |
| Metal Gear Solid: Peace Walker (Master Collection) | Nintendo Switch, PC | Game files (folder or image) | None | Switch and PC, Master Collection. |
| Metroid Prime 4: Beyond | Nintendo Switch | Game files (folder or image) | None | Switch update 1.1.0. Glyphs are edited in place, none added. |
| Metroid Prime Remastered | Nintendo Switch | Game files (folder or image) | None | Switch base game. Same formats as Metroid Prime 4. |
| Miitopia (Switch) | Nintendo Switch | Game files (folder or image) | None | Switch 1.0.0 with update 1.1.0. |
| Monster Hunter Stories (Switch) | Nintendo Switch | Game files (folder or image) | None | Switch English message archive. |
| Okami HD (Switch) | Nintendo Switch | Game files (folder or image); Key file if encrypted (Switch) | Switch: Atmosphere LayeredFS mod | Switch. Atmosphere LayeredFS mod. |
| One Piece: Unlimited World Red (3DS) / Deluxe (Switch) | Nintendo 3DS, Nintendo Switch | Game files (folder or image) | None | 3DS Europe. |
| Paper Mario: The Origami King (Switch) | Nintendo Switch | Game files (folder or image) | None | Switch, 2020. |
| Paper Mario: The Thousand-Year Door (Switch) | Nintendo Switch | Game files (folder or image) | None | Switch, 2024. |
| Pokémon Brilliant Diamond / Shining Pearl | Nintendo Switch | Base game, Update; Key file if encrypted (Switch) | Switch: Atmosphere LayeredFS mod (both games) | Switch. One project for both games. |
| Pokémon Scarlet/Violet, Legends: Z-A (Switch) | Nintendo Switch | Base game, Update, Other version: base game, Other version: update; Key file if encrypted (Switch, Oodle library) | Switch: Atmosphere LayeredFS mod (the game of the image) | Switch. Scarlet/Violet with DLC and Legends: Z-A. |
| Pokémon Sword/Shield + Legends: Arceus (Switch) | Nintendo Switch | Base game, Update; Key file if encrypted (Switch, Oodle library) | Switch: Atmosphere LayeredFS mod | Switch. Both DLC included. |
| Rune Factory 4 (3DS) / Special (Switch) | Nintendo 3DS, Nintendo Switch | Game files (folder or image) | None | 3DS USA. Switch Special in the same plugin. |
| Silent Hill (Switch, PAL) | Nintendo Switch | Game files (folder or image) | None |  |
| Silent Hill 2 (PC, Switch data) | PC, Nintendo Switch | Game files (folder or image) | None |  |
| Sly Cooper and the Thievius Raccoonus | PC, Nintendo Switch | Game files (folder or image) | None | ProjectCane port. Only ASCII text is written now. |
| Super Mario Galaxy | Wii, Nintendo Switch | Wii disc (USA), Switch game, Another Wii disc (reference languages); Key file if encrypted (Switch, Wii) | Wii: Riivolution patch and Dolphin launcher; Nebula (PC): disc mod manifest; Switch: Atmosphere LayeredFS mod | Wii, Switch and Nebula (PC) in one project. Galaxy 1 and 2. |
| Xenoblade Chronicles 2 (Switch) | Nintendo Switch | Game files (folder or image) | None | Switch update 2.1.0. Torna and other DLC included. |
| Xenoblade Chronicles 3 (Switch) | Nintendo Switch | Game files (folder or image) | None | Switch. Base game with the DLC waves. |
| Xenoblade Chronicles X: Definitive Edition (Switch) | Nintendo Switch | Game files (folder or image) | None | Switch update 1.0.2. |
| Xenoblade Chronicles: Definitive Edition (Switch) | Nintendo Switch | Game files (folder or image) | None | Switch 1.1.1. |
| Yo-kai Watch | Nintendo 3DS, Nintendo Switch | Base game, Update; Key file if encrypted (3DS, Switch) | None | 3DS and Switch. USA. |
| Zelda: Cadence of Hyrule | Nintendo Switch | Game files (folder or image) | None | Source is a folder with localization.xml. |
| Zelda: Hyrule Warriors Age of Calamity | Nintendo Switch | Game files (folder or image) | None | Switch. |
| Zelda: Hyrule Warriors Definitive Edition | Nintendo Switch | Game files (folder or image) | None |  |
| Zelda: Skyward Sword | Nintendo Switch | Game files (folder or image) | SkyRecomp (Windows port, mod folder) | Switch HD and the Wii original in one plugin. |
| Zelda: Tears of the Kingdom | Nintendo Switch | Game files (folder or image) | None | Checked on 1.4.0. Source is the dumped romfs. |

### Nintendo 3DS

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Animal Crossing: New Leaf / Happy Home Designer (3DS) | Nintendo 3DS | Game files (folder or image) | None | 3DS: Welcome amiibo and Happy Home Designer. |
| Attack on Titan: Humanity in Chains | Nintendo 3DS | Game files (folder or image) | None | 3DS USA. |
| Bravely Default / Bravely Second | Nintendo 3DS | Game files (folder or image) | None | Europe. Also opens Bravely Second (USA) in the same plugin. |
| Castlevania: Mirror of Fate | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe, English. |
| Code Name: S.T.E.A.M. | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe. |
| Digimon World: Re:Digitize Decode | Nintendo 3DS | Game files (folder or image) | None | Japanese release with the English fan translation. |
| Dragon Ball Fusions | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe. |
| Dragon Quest Monsters: Joker 3 (3DS) | Nintendo 3DS | Game files (folder or image) | None | Japanese 3DS release with the English fan patch 1.02. |
| Dragon Quest VII (3DS) | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe, English slot EN. |
| Dragon Quest VIII (3DS) | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe, English slot eng. |
| Ever Oasis | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe. |
| Fantasy Life | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe. |
| Final Fantasy Explorers | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe, English. |
| Fire Emblem Awakening | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe, English slot. |
| Gravity Falls: Legend of the Gnome Gemulets | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe. UbiArt engine. |
| Harvest Moon 3D / Story of Seasons (3DS) | Nintendo 3DS | Game files (folder or image) | None | Four titles in one plugin, all Europe. |
| Kid Icarus: Uprising | Nintendo 3DS | Game files (folder or image) | None | Europe, English set eu. |
| Kingdom Hearts 3D: Dream Drop Distance | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe, English. |
| Luigi's Mansion: Dark Moon (3DS) | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe. |
| Metal Gear Solid: Snake Eater 3D | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe. |
| Monster Hunter (3DS: 3 Ultimate, 4 Ultimate, Stories) | Nintendo 3DS | Game files (folder or image) | None | 3DS: Monster Hunter 3 Ultimate, 4 Ultimate and Stories. |
| Paper Mario: Sticker Star | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe, English set. |
| Pokémon Mystery Dungeon (3DS) | Nintendo 3DS | Game files (folder or image); Key file if encrypted (3DS) | 3DS mod (LayeredFS) | 3DS: Gates to Infinity and Super Mystery Dungeon. |
| Pokémon Sun/Moon + Ultra Sun/Ultra Moon (3DS) | Nintendo 3DS | Base game, Update v1.2 (Ultra Sun / Ultra Moon); Key file if encrypted (3DS) | 3DS mod (LayeredFS) | Sun/Moon and Ultra Sun/Ultra Moon. Update v1.2 is a role. |
| Pokémon X/Y + Omega Ruby/Alpha Sapphire (3DS) | Nintendo 3DS | Game files (folder or image); Key file if encrypted (3DS) | 3DS mod (LayeredFS) | X/Y and Omega Ruby/Alpha Sapphire. One project per pair. |
| Professor Layton (3DS) | Nintendo 3DS | Game files (folder or image) | None | Several 3DS titles in one plugin. |
| Rhythm Paradise Megamix | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe. |
| Senran Kagura Burst | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe. |
| Shin Megami Tensei IV | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe. Shin Megami Tensei IV and Apocalypse. |
| Silent Hill 2 (Switch, Ukrainian) | Nintendo 3DS | Game files (folder or image) | sh23ds 3DS port: Ukrainian messages and font |  |
| Stella Glow | Nintendo 3DS | Game files (folder or image) | None | 3DS Europe. |
| Tomodachi Life / Miitopia (3DS) | Nintendo 3DS | Game files (folder or image) | None | Europe. Tomodachi Life and Miitopia. |
| Xenoblade Chronicles (Wii / 3DS) | Wii, Nintendo 3DS | Game files (folder or image) | None | Wii USA and 3DS (New 3DS, EUR) in one plugin. |
| Zelda: A Link Between Worlds | Nintendo 3DS | Game files (folder or image) | None | Europe. |
| Zelda: Majora's Mask 3D | Nintendo 3DS | Game files (folder or image) | None | Europe. With or without the v1040 update. |
| Zelda: Ocarina of Time 3D | Nintendo 3DS | Game files (folder or image) | None | Europe. |
| Zelda: Tri Force Heroes | Nintendo 3DS | Game files (folder or image) | None | Europe. Uses the A Link Between Worlds tags. |

### Wii

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Fragile Dreams: Farewell Ruins of the Moon | Wii | Game files (folder or image) | None | Wii Europe. |
| Ikenie no Yoru | Wii | Game files (folder or image) | None | Japanese Wii disc with the English fan patch applied at unpack. |
| MadWorld | Wii | Game files (folder or image); Key file if encrypted (Wii) | Wii disc image (ISO) | Wii Europe. |
| Metroid Prime Trilogy | Wii, GameCube | Game files (folder or image) | None | Wii USA. Prime 1, 2, 3 and the trilogy menu. |
| Metroid: Other M | Wii | Game files (folder or image) | None | Wii USA. The message file keeps seven other languages. |
| No More Heroes | Wii | Game files (folder or image); Key file if encrypted (Wii) | Wii disc image (ISO, English) | Wii Europe. The disc image is ISO or RVZ. |
| Okami (Wii) | Wii | Game files (folder or image); Key file if encrypted (Wii) | Wii disc image (ISO, English messages); Wii: changed message entries (files) | Wii disc image, English messages. |
| Raving Rabbids: Party Collection | Wii | Game files (folder or image) | None | Wii Europe. Menu and three games on one disc. |
| Spore Hero | Wii | Game files (folder or image) | None | Wii Europe. A letter with no character byte gets a new byte. |
| Wario Land: Shake It! (Wii) | Wii | Wii disc (USA); Key file if encrypted (Wii) | Wii disc image (ISO, English) | Wii USA, RWLE01 rev 0. |
| Zelda: Twilight Princess | GameCube, Wii, Wii U | Game files (folder or image); Key file if encrypted (Wii) | GameCube disc image (ISO); Dusklight mod (.dusk, needs the original disc); Wii U graphic pack and SDCafiine folder (HD) | Fonts folder: res/Fontus (HD: Fonteu). The Wii disc has no build target yet. |

### Wii U

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Paper Mario: Color Splash | Wii U | Game files (folder or image) | None | Wii U, Europe. |
| Zelda: The Wind Waker | Wii U | Game files (folder or image) | Cemu graphic pack | Wii U HD. Add the unpacked title folder with Add folder... |

### GameCube

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Eternal Darkness: Sanity's Requiem | GameCube | Game files (folder or image) | None | GameCube USA. |
| Metal Gear Solid: The Twin Snakes | GameCube | Disc 1, Disc 2 | None | GameCube USA. Disc 1 and Disc 2 are roles. |
| Paper Mario: The Thousand-Year Door | GameCube | Game files (folder or image) | None | GameCube USA. |
| Skies of Arcadia Legends (GameCube, USA) | GameCube | Game files (folder or image) | GameCube disc image (ISO) | GameCube USA. Byte budget per script: changed text may not grow in total. |
| Super Mario Sunshine | GameCube | Game files (folder or image) | GameCube disc image (ISO); PC and Switch port pack (mods/uk) | GameCube USA GMSE01 rev 0. The European disc is a reference. |
| Super Paper Mario | GameCube | Game files (folder or image) | None | Wii PAL, English UK. |
| Zelda: The Wind Waker (GameCube BMG) | GameCube, BlueWake | Game files (folder or image) | Disc image (ISO); BlueWake disc (original main.dol) | A BlueWake build needs the original main.dol (SHA-1 check). |
| Zelda: The Wind Waker (Tingle Tuner, GBA) | GameCube | Game files (folder or image) | None | GBA program text in the GameCube disc. |

### PlayStation 2

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Okami (PlayStation 2) | PlayStation 2 | Game files (folder or image) | PlayStation 2: disc image (ISO) | PlayStation 2 disc image. |

### PlayStation

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Castlevania: Symphony of the Night (PlayStation) | PlayStation | Game files (folder or image) | None | PlayStation USA. Also the PC port. |
| Grandia II (Dreamcast, USA) | Dreamcast, PlayStation | Game files (folder or image) | Translated disc set (cue and tracks) |  |
| Lunar 2: Eternal Blue Complete | PlayStation | Game files (folder or image) | None | PlayStation USA, three discs. |
| Lunar: Silver Star Story Complete | PlayStation | Game files (folder or image) | None | PlayStation USA, two discs. |
| Metal Gear Solid (PlayStation) | PlayStation | Game files (folder or image) | None | PlayStation USA, both discs. |
| Policenauts | PlayStation, PSP | Game files (folder or image) | None | Japanese discs with the English fan patch. |
| Silent Hill (PlayStation) | PlayStation | Game files (folder or image) | None |  |
| Vagrant Story | PlayStation | Game files (folder or image) | None |  |

### PSP

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Castlevania: The Dracula X Chronicles (PSP) | PSP | Game files (folder or image) | None | PSP. The Symphony of the Night strings are in the PSP overlays. |
| Lunar: Silver Star Harmony (PSP) | PSP | Game files (folder or image) | None | PSP USA. The build puts a Cyrillic font on the disc. |
| Monster Hunter Portable 3rd HD (PSP, Yakumo) | PSP | Game files (folder or image) | None | PSP image and Yakumo PC port. Needs en_source.json from the owner's workspace script. |

### PC

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Hard Corps: Uprising | PC | Game files (folder or image) | None | Texture-first project. No text blocks. |
| Link's Awakening DX HD | PC | Game files (folder or image) | None | PC fan remake v1.0.0. No font has Ukrainian letters yet. |
| Silent Hill 3 (PC) | PC | Game files (folder or image) | None |  |
| Super Metroid (PC port) | PC | Game files (folder or image) | None | SNES USA ROM through the PC port sm_rewrite. Capitals only. |
| Zelda: A Link to the Past (PC port) | PC | Game files (folder or image) | None | SNES USA ROM through the PC port snesrev/zelda3. |

### Nintendo DS

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Castlevania DS: Dawn of Sorrow / Portrait of Ruin / Order of Ecclesia | Nintendo DS | Game files (folder or image) | None | DS: Dawn of Sorrow, Portrait of Ruin and Order of Ecclesia. |
| Dragon Quest IX: Sentinels of the Starry Skies | Nintendo DS | Game files (folder or image) | None | DS Europe. |
| Final Fantasy Tactics A2 | Nintendo DS | Game files (folder or image) | None | DS Europe. |
| Final Fantasy XII: Revenant Wings | Nintendo DS | Game files (folder or image) | None | DS Europe. |
| Infinite Space | Nintendo DS | Game files (folder or image) | None | DS Europe. |
| Pokémon Black / White and Black 2 / White 2 (DS) | Nintendo DS | Game files (folder or image) | Translated DS ROM | DS: Black/White and Black 2/White 2. |
| Pokémon Diamond, Pearl, Platinum, HeartGold and SoulSilver (DS) | Nintendo DS | Game files (folder or image) | Translated DS ROM | DS USA ROM. |
| Professor Layton (DS) | Nintendo DS | Game files (folder or image) | None | Several DS titles in one plugin. |
| The World Ends with You | Nintendo DS | Game files (folder or image) | None | DS Europe. |
| Zelda: Four Swords Anniversary Edition | Nintendo DS | Game files (folder or image) | None | DSiWare, Europe. |
| Zelda: Phantom Hourglass / Spirit Tracks (DS) | Nintendo DS | Game files (folder or image) | None | USA. Phantom Hourglass and Spirit Tracks. |

### Game Boy Advance

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Castlevania: Circle of the Moon (GBA) | Game Boy Advance | Game files (folder or image) | None | GBA USA. |
| Castlevania: Harmony of Dissonance / Aria of Sorrow (GBA) | Game Boy Advance | Game files (folder or image) | None | GBA: Harmony of Dissonance (Europe) and Aria of Sorrow (USA). |
| Donkey Kong Country 3 (GBA) | Game Boy Advance | Game files (folder or image) | None | GBA Europe. Plain ASCII text. |
| Final Fantasy Tactics Advance (GBA) | Game Boy Advance | Game files (folder or image) | Translated GBA ROM | GBA USA. |
| Mario vs. Donkey Kong (GBA) | Game Boy Advance | Game files (folder or image) | None |  |
| Pokemon FireRed/LeafGreen | Game Boy Advance | Game ROM (Game Boy Advance) | Patched ROM; Recomp package (EmeraldRecomp, FireRedLeafGreenRecomp) | GBA. Also JSON dumps of the ROM text and pret source files. |
| The Legend of Zelda: The Minish Cap | Game Boy Advance | Game files (folder or image) | None | GBA. |

### Game Boy Color

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Pokémon Gold, Silver and Crystal (pret) | Game Boy Color | Game ROM (Game Boy Color) | Patched ROM; Recomp package (Gen2Recomp: Gold, Silver, Crystal) | Gold, Silver and Crystal through the pret decompilations. Also Game ROM mode. |
| Zelda: Link's Awakening DX (Game Boy Color) | Game Boy Color | Game files (folder or image) | None | English v1.0 ROM. |
| Zelda: Oracle of Ages / Seasons (Game Boy Color) | Game Boy Color | Game files (folder or image) | None | Game Boy Color. |

### Game Boy

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Pokémon Red / Blue / Yellow (Game Boy) | Game Boy | Game ROM (Game Boy) | Patched ROM | Red, Blue and Yellow. Game ROM mode reads a .gb file, no make needed. |

### Nintendo 64

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Conker's Bad Fur Day (N64) | Nintendo 64 | N64 ROM (USA) | Patched ROM (US); BPS patch (US ROM to translation) | N64 USA 1.0. Plugin in progress. |
| Paper Mario (N64) | Nintendo 64 | Game files (folder or image) | None | N64 USA 1.0 in the PC port PaperBoat 1.0.2. |
| Zelda: Majora's Mask (N64) | Nintendo 64 | Game files (folder or image) | None | US ROM. Ukrainian letters use the font map. |
| Zelda: Ocarina of Time (N64) | Nintendo 64 | Game files (folder or image) | None | US 1.0 ROM. |

### Super Nintendo

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Donkey Kong Country (SNES) | Super Nintendo | Game files (folder or image) | None | SNES USA v1.0 ROM through the Switch PC ports. |
| Rock N' Roll Racing (SNES) | Super Nintendo | USA ROM | Translated ROM and IPS patch | SNES USA. |

### Sega Saturn

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Castlevania: Symphony of the Night (Saturn) | Sega Saturn | Game files (folder or image) | None | Sega Saturn release. |

### Dreamcast

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Skies of Arcadia (Dreamcast, USA) | Dreamcast | Game files (folder or image) | Translated disc set (cue and tracks) | Dreamcast USA. Same byte budget as the GameCube game. |

### Helper and generic plugins

| Game | Platform | What the wizard needs | Build targets | Notes |
|---|---|---|---|---|
| Electronic manuals (3DS, Ukrainian) | Nintendo 3DS | Game files (folder or image) | None | 3DS electronic manuals (helper). |
| Nintendo 3DS system (Ukrainian) | Nintendo 3DS | Game files (folder or image) | 3DS mod over the Russian slot (dist/); 3DS mod over the English slot (dist_en/) | 3DS system menus of the Ukrainian mod (helper). |
| Plain Text | Other | Game files (folder or image) | Translated files | Generic JSON and TXT files, no game (helper). |
| Wii System Font | Wii | Game files (folder or image) | None | Wii system bitmap fonts wbf1 and wbf2 (helper). |

## Common situations

**My game is on two platforms.**

- The Platform column lists every platform of the plugin.
- The wizard finds the platform from your files. Check the **Platform** column in the file list.

**The wizard asks for a key file.**

- Your file is encrypted. Click **Add the key file for ...**.
- Picoripi remembers the key path for each console.

**The wizard says Cannot read: add its folder.**

- This game cannot read that file itself.
- Remove the file and add the unpacked game folder with **Add folder...**.

**The wizard asks for an update or DLC.**

- Add the update or DLC file. Set its role to **Update** or **DLC**.
- Only DLC can repeat. Give every other file its own role.

**Build, Export and Run are disabled.**

- The plugin declares no build target. The table shows **None**.
- The game may still build with a workspace script. See [Build and Test](Build_and_Test.md).

**Two versions of one game share a plugin.**

- Some rows cover several versions, for example Wii and Switch.
- Read the **Notes** column before you choose a version.

<!-- wiki-nav -->
---

**Previous:** [Configuration](4_Configuration_Guide.md) · [Back to the wiki index](README.md) · **Next:** [Game notes](Game_Notes.md)
