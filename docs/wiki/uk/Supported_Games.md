---
status: current
updated: 2026-10-21
owns: plugins/
tokens: 8.3k
---
# Підтримувані ігри

**Мова:** [English](../Supported_Games.md) · Українська

Ця сторінка перелічує всі ігрові плагіни Picoripi: платформи, файли, які просить майстер нового проєкту, і цілі збірки. Кожну гру читає її власний плагін у теці plugins. Перевірте таблицю, щоб дізнатися, чи підтримується ваша гра.

Технічні нотатки однієї гри (теки джерел, формати файлів, теги, перегляд, збірка) шукайте на сторінці [Нотатки по іграх](Game_Notes.md).

## Як знайти свою гру

1. Відкрийте **Файл → Новий проєкт…** (`Ctrl+N`).
2. У полі **Гра** введіть частину назви гри. Список звужується під час введення.
3. Виберіть гру. Порівняйте її **Платформу** з вашою копією.
4. Прочитайте **Що потрібно майстру** і додайте названі файли.

## Якщо вашої гри немає в списку

Якщо вашої гри немає в таблиці, Picoripi поки не може її прочитати. Скопіюйте теку `default_plugin` у `plugins`, перейменуйте її і дотримуйтесь [Посібника розробника плагінів](3_Plugin_Developer_Guide.md).

Назвіть нову теку малими літерами, наприклад `my_game`.

## Ігри за платформою

### Nintendo Switch

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Ace Attorney Trilogy | Nintendo 3DS, Nintendo Switch | Файли гри (тека або образ) | Немає | Версії для 3DS і Switch. |
| Animal Crossing: New Horizons (Switch) | Nintendo Switch | Файли гри (тека або образ) | Немає | Switch, 2020. |
| Atomic Bomberman | ПК, Nintendo Switch | Файли гри (тека або образ) | Atomic Bomberman: мовний файл для порту на ПК; Atomic Bomberman: тека експорту для Switch (sdmc:/switch/atomic-bomberman/lang) | PC і Switch. Мовний файл і тека експорту для Switch. |
| Black & White (openBlack Switch port) | Nintendo Switch | Base game (PC data folder or Switch port SD folder) | **openBlack SD card: switch/openblack/game/Scripts/InfoScript2.txt** | Порт openBlack для Switch. Порт ще не показує текст гри. |
| Castlevania: Belmont's Curse | Nintendo Switch | Base game, Update; Файл ключів, якщо файл зашифровано (Switch) | **Switch: LayeredFS mod (Atmosphere)** | Switch 1.1.0 (v65536). |
| Code of Princess | Nintendo 3DS, Nintendo Switch | Файли гри (тека або образ) | Немає | 3DS і Switch EX. Текст всередині виконуваного файлу. |
| Corpse Party | Nintendo 3DS, Nintendo Switch | Файли гри (тека або образ) | Немає | 3DS і Switch 2021. Текст не може перевищити свій слот повідомлення. |
| Donkey Kong Country: Tropical Freeze | Nintendo Switch | Файли гри (тека або образ) | Немає | Switch, оновлення v131072. Шрифти і текстури ще не відкриваються. |
| Dragon Quest Builders 1 + 2 (Switch) | Nintendo Switch | Файли гри (тека або образ) | Немає | Switch. Builders 1 і 2 в одному плагіні. |
| Jak and Daxter | PlayStation 2, Nintendo Switch | Файли гри (тека або образ) | Немає | Порт OpenGOAL для Switch. Jak 1, Jak II і Jak 3 в одному плагіні. |
| Layton Brothers: Mystery Room | Nintendo Switch, **Android** | Файли гри (тека або образ) | Немає |  |
| Link's Awakening (Switch) | Nintendo Switch | Файли гри (тека або образ); Файл ключів, якщо файл зашифровано (Switch) | **LAS Recomp (romfs.bin)** | Лише базова гра v1.0.0. Потрібен prod.keys один раз. |
| Mario vs. Donkey Kong (Switch) | Nintendo Switch | Файли гри (тека або образ) | Немає |  |
| Metal Gear Solid (Master Collection) | ПК, Nintendo Switch | Файли гри (тека або образ) | Немає | PC Steam і Switch. Гра США. |
| Metal Gear Solid 2 / 3 (Master Collection) | Nintendo Switch, ПК | Файли гри (тека або образ) | Немає | Switch. PC поки немає. |
| Metal Gear Solid 4 (Master Collection) | Nintendo Switch, ПК | Файли гри (тека або образ) | Немає | Switch і PC, Master Collection. |
| Metal Gear Solid Master Collection Bonus Content | Nintendo Switch | Файли гри (тека або образ) | Немає | Switch, бонусний вміст, томи 1 і 2. |
| Metal Gear Solid: Peace Walker (Master Collection) | Nintendo Switch, ПК | Файли гри (тека або образ) | Немає | Switch і PC, Master Collection. |
| Metroid Prime 4: Beyond | Nintendo Switch | Файли гри (тека або образ) | Немає | Switch, оновлення 1.1.0. Гліфи редагуються на місці, нові не додаються. |
| Metroid Prime Remastered | Nintendo Switch | Файли гри (тека або образ) | Немає | Switch, базова гра. Такі самі формати, як у Metroid Prime 4. |
| Miitopia (Switch) | Nintendo Switch | Файли гри (тека або образ) | Немає | Switch 1.0.0 з оновленням 1.1.0. |
| Monster Hunter Stories (Switch) | Nintendo Switch | Файли гри (тека або образ) | Немає | Switch, англійський архів повідомлень. |
| Okami HD (Switch) | Nintendo Switch | Файли гри (тека або образ); Файл ключів, якщо файл зашифровано (Switch) | Switch: мод LayeredFS для Atmosphere | Switch. Мод LayeredFS для Atmosphere. |
| One Piece: Unlimited World Red (3DS) / Deluxe (Switch) | Nintendo 3DS, Nintendo Switch | Файли гри (тека або образ) | Немає | 3DS, Європа. |
| Paper Mario: The Origami King (Switch) | Nintendo Switch | Файли гри (тека або образ) | Немає | Switch, 2020. |
| Paper Mario: The Thousand-Year Door (Switch) | Nintendo Switch | Файли гри (тека або образ) | Немає | Switch, 2024. |
| Pokémon Brilliant Diamond / Shining Pearl | Nintendo Switch | Base game, Update; Файл ключів, якщо файл зашифровано (Switch) | Switch: мод LayeredFS для Atmosphere (обидві гри) | Switch. Один проєкт для обох ігор. |
| Pokémon Scarlet/Violet, Legends: Z-A (Switch) | Nintendo Switch | Base game, Update, Other version: base game, Other version: update; Файл ключів, якщо файл зашифровано (Switch, бібліотека Oodle) | Switch: мод LayeredFS для Atmosphere (гра з образу) | Switch. Scarlet/Violet з DLC і Legends: Z-A. |
| Pokémon Sword/Shield + Legends: Arceus (Switch) | Nintendo Switch | Base game, Update; Файл ключів, якщо файл зашифровано (Switch, бібліотека Oodle) | Switch: мод LayeredFS для Atmosphere | Switch. Обидва DLC включено. |
| Rune Factory 4 (3DS) / Special (Switch) | Nintendo 3DS, Nintendo Switch | Файли гри (тека або образ) | Немає | 3DS США. Switch Special в тому ж плагіні. |
| Silent Hill (Switch, PAL) | Nintendo Switch | Файли гри (тека або образ) | Немає |  |
| Silent Hill 2 (PC, Switch data) | ПК, Nintendo Switch | Файли гри (тека або образ) | Немає |  |
| Sly Cooper and the Thievius Raccoonus | ПК, Nintendo Switch | Файли гри (тека або образ) | Немає | Порт ProjectCane. Зараз записується лише текст ASCII. |
| Super Mario Galaxy | Wii, Nintendo Switch | Wii disc (USA), Switch game, Another Wii disc (reference languages); Файл ключів, якщо файл зашифровано (Switch, Wii) | Wii: патч Riivolution і запуск у Dolphin; Nebula (ПК): маніфест мода диска; Switch: мод LayeredFS для Atmosphere | Wii, Switch і Nebula (PC) в одному проєкті. Galaxy 1 і 2. |
| Xenoblade Chronicles 2 (Switch) | Nintendo Switch | Файли гри (тека або образ) | Немає | Switch, оновлення 2.1.0. Torna та інші DLC включено. |
| Xenoblade Chronicles 3 (Switch) | Nintendo Switch | Файли гри (тека або образ) | Немає | Switch. Базова гра з хвилями DLC. |
| Xenoblade Chronicles X: Definitive Edition (Switch) | Nintendo Switch | Файли гри (тека або образ) | Немає | Switch, оновлення 1.0.2. |
| Xenoblade Chronicles: Definitive Edition (Switch) | Nintendo Switch | Файли гри (тека або образ) | Немає | Switch 1.1.1. |
| Yo-kai Watch | Nintendo 3DS, Nintendo Switch | Base game, Update; Файл ключів, якщо файл зашифровано (3DS, Switch) | Немає | 3DS і Switch. США. |
| Zelda: Cadence of Hyrule | Nintendo Switch | Файли гри (тека або образ) | Немає | Джерело — тека з localization.xml. |
| Zelda: Hyrule Warriors Age of Calamity | Nintendo Switch | Файли гри (тека або образ) | Немає | Switch. |
| Zelda: Hyrule Warriors Definitive Edition | Nintendo Switch | Файли гри (тека або образ) | Немає |  |
| Zelda: Skyward Sword | Nintendo Switch | Файли гри (тека або образ) | SkyRecomp (порт для Windows, тека моду) | Switch HD і оригінал для Wii в одному плагіні. |
| Zelda: Tears of the Kingdom | Nintendo Switch | Файли гри (тека або образ) | Немає | Перевірено на 1.4.0. Джерело — розпаковане romfs. |

### Nintendo 3DS

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Animal Crossing: New Leaf / Happy Home Designer (3DS) | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS: Welcome amiibo і Happy Home Designer. |
| Attack on Titan: Humanity in Chains | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, США. |
| Bravely Default / Bravely Second | Nintendo 3DS | Файли гри (тека або образ) | Немає | Європа. Також відкриває Bravely Second (США) в тому ж плагіні. |
| Castlevania: Mirror of Fate | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа, англійська. |
| Code Name: S.T.E.A.M. | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа. |
| Digimon World: Re:Digitize Decode | Nintendo 3DS | Файли гри (тека або образ) | Немає | Японський випуск з англійським фан-перекладом. |
| Dragon Ball Fusions | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа. |
| Dragon Quest Monsters: Joker 3 (3DS) | Nintendo 3DS | Файли гри (тека або образ) | Немає | Японський 3DS-випуск з англійським фан-патчем 1.02. |
| Dragon Quest VII (3DS) | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа, англійський слот EN. |
| Dragon Quest VIII (3DS) | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа, англійський слот eng. |
| Ever Oasis | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа. |
| Fantasy Life | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа. |
| Final Fantasy Explorers | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа, англійська. |
| Fire Emblem Awakening | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа, англійський слот. |
| Gravity Falls: Legend of the Gnome Gemulets | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа. Рушій UbiArt. |
| Harvest Moon 3D / Story of Seasons (3DS) | Nintendo 3DS | Файли гри (тека або образ) | Немає | Чотири назви в одному плагіні, усі Європа. |
| Kid Icarus: Uprising | Nintendo 3DS | Файли гри (тека або образ) | Немає | Європа, англійський набір eu. |
| Kingdom Hearts 3D: Dream Drop Distance | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа, англійська. |
| Luigi's Mansion: Dark Moon (3DS) | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа. |
| Metal Gear Solid: Snake Eater 3D | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа. |
| Monster Hunter (3DS: 3 Ultimate, 4 Ultimate, Stories) | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS: Monster Hunter 3 Ultimate, 4 Ultimate і Stories. |
| Paper Mario: Sticker Star | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа, англійський набір. |
| Pokémon Mystery Dungeon (3DS) | Nintendo 3DS | Файли гри (тека або образ); Файл ключів, якщо файл зашифровано (3DS) | Мод 3DS (LayeredFS) | 3DS: Gates to Infinity і Super Mystery Dungeon. |
| Pokémon Sun/Moon + Ultra Sun/Ultra Moon (3DS) | Nintendo 3DS | Base game, Update v1.2 (Ultra Sun / Ultra Moon); Файл ключів, якщо файл зашифровано (3DS) | Мод 3DS (LayeredFS) | Sun/Moon і Ultra Sun/Ultra Moon. Оновлення v1.2 — це роль. |
| Pokémon X/Y + Omega Ruby/Alpha Sapphire (3DS) | Nintendo 3DS | Файли гри (тека або образ); Файл ключів, якщо файл зашифровано (3DS) | Мод 3DS (LayeredFS) | X/Y і Omega Ruby/Alpha Sapphire. Один проєкт на пару. |
| Professor Layton (3DS) | Nintendo 3DS | Файли гри (тека або образ) | Немає | Кілька назв 3DS в одному плагіні. |
| Rhythm Paradise Megamix | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа. |
| Senran Kagura Burst | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа. |
| Shin Megami Tensei IV | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа. Shin Megami Tensei IV і Apocalypse. |
| Silent Hill 2 (Switch, Ukrainian) | Nintendo 3DS | Файли гри (тека або образ) | Порт sh23ds (3DS): українські повідомлення та шрифт |  |
| Stella Glow | Nintendo 3DS | Файли гри (тека або образ) | Немає | 3DS, Європа. |
| Tomodachi Life / Miitopia (3DS) | Nintendo 3DS | Файли гри (тека або образ) | Немає | Європа. Tomodachi Life і Miitopia. |
| Xenoblade Chronicles (Wii / 3DS) | Wii, Nintendo 3DS | Файли гри (тека або образ) | Немає | Wii США і 3DS (New 3DS, EUR) в одному плагіні. |
| Zelda: A Link Between Worlds | Nintendo 3DS | Файли гри (тека або образ) | Немає | Європа. |
| Zelda: Majora's Mask 3D | Nintendo 3DS | Файли гри (тека або образ) | Немає | Європа. З оновленням v1040 або без нього. |
| Zelda: Ocarina of Time 3D | Nintendo 3DS | Файли гри (тека або образ) | Немає | Європа. |
| Zelda: Tri Force Heroes | Nintendo 3DS | Файли гри (тека або образ) | Немає | Європа. Використовує теги A Link Between Worlds. |

### Wii

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Fragile Dreams: Farewell Ruins of the Moon | Wii | Файли гри (тека або образ) | Немає | Wii, Європа. |
| Ikenie no Yoru | Wii | Файли гри (тека або образ) | Немає | Японський диск Wii з англійським фан-патчем, який застосовується під час розпакування. |
| MadWorld | Wii | Файли гри (тека або образ); Файл ключів, якщо файл зашифровано (Wii) | **Wii disc image (ISO)** | Wii, Європа. |
| Metroid Prime Trilogy | Wii, GameCube | Файли гри (тека або образ) | Немає | Wii, США. Prime 1, 2, 3 і меню трилогії. |
| Metroid: Other M | Wii | Файли гри (тека або образ) | Немає | Wii, США. Файл повідомлень зберігає ще сім мов. |
| No More Heroes | Wii | Файли гри (тека або образ); Файл ключів, якщо файл зашифровано (Wii) | Образ диска Wii (ISO, англійська) | Wii, Європа. Образ диска: ISO або RVZ. |
| Okami (Wii) | Wii | Файли гри (тека або образ); Файл ключів, якщо файл зашифровано (Wii) | **Wii disc image (ISO, English messages)**; Wii: змінені записи повідомлень (файли) | Образ диска Wii, англійські повідомлення. |
| Raving Rabbids: Party Collection | Wii | Файли гри (тека або образ) | Немає | Wii, Європа. Меню і три гри на одному диску. |
| Spore Hero | Wii | Файли гри (тека або образ) | Немає | Wii, Європа. Літера без байта символу отримує новий байт. |
| Wario Land: Shake It! (Wii) | Wii | Wii disc (USA); Файл ключів, якщо файл зашифровано (Wii) | Образ диска Wii (ISO, англійська) | Wii, США, RWLE01 rev 0. |
| Zelda: Twilight Princess | GameCube, Wii, Wii U | Файли гри (тека або образ); Файл ключів, якщо файл зашифровано (Wii) | Образ диска GameCube (ISO); Мод для Dusklight (.dusk, потрібен оригінальний диск); Графічний пакет Wii U і тека SDCafiine (HD) | Тека шрифтів: res/Fontus (HD: Fonteu). Диск Wii поки без цілі збірки. |

### Wii U

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Paper Mario: Color Splash | Wii U | Файли гри (тека або образ) | Немає | Wii U, Європа. |
| Zelda: The Wind Waker | Wii U | Файли гри (тека або образ) | **Cemu graphic pack** | Wii U HD. Додайте розпаковану теку гри кнопкою Додати папку... |

### GameCube

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Eternal Darkness: Sanity's Requiem | GameCube | Файли гри (тека або образ) | Немає | GameCube, США. |
| Metal Gear Solid: The Twin Snakes | GameCube | Disc 1, Disc 2 | Немає | GameCube, США. Диск 1 і Диск 2 — це ролі. |
| Paper Mario: The Thousand-Year Door | GameCube | Файли гри (тека або образ) | Немає | GameCube, США. |
| Skies of Arcadia Legends (GameCube, USA) | GameCube | Файли гри (тека або образ) | Образ диска GameCube (ISO) | GameCube, США. Ліміт байтів на скрипт: змінений текст не може збільшитися загалом. |
| Super Mario Sunshine | GameCube | Файли гри (тека або образ) | Образ диска GameCube (ISO); Пакет для портів PC і Switch (mods/uk) | GameCube, США, GMSE01 rev 0. Європейський диск — як еталон. |
| Super Paper Mario | GameCube | Файли гри (тека або образ) | Немає | Wii PAL, англійська (Британія). |
| Zelda: The Wind Waker (GameCube BMG) | GameCube, BlueWake | Файли гри (тека або образ) | Образ диска (ISO); Диск для BlueWake (оригінальний main.dol) | Збірка BlueWake потребує оригінального main.dol (перевірка SHA-1). |
| Zelda: The Wind Waker (Tingle Tuner, GBA) | GameCube | Файли гри (тека або образ) | Немає | Текст GBA-програми на диску GameCube. |

### PlayStation 2

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Okami (PlayStation 2) | PlayStation 2 | Файли гри (тека або образ) | PlayStation 2: образ диска (ISO) | Образ диска PlayStation 2. |

### PlayStation

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Castlevania: Symphony of the Night (PlayStation) | PlayStation | Файли гри (тека або образ) | Немає | PlayStation, США. Також PC-порт. |
| Grandia II (Dreamcast, USA) | Dreamcast, PlayStation | Файли гри (тека або образ) | Перекладений набір диска (cue і доріжки) |  |
| Lunar 2: Eternal Blue Complete | PlayStation | Файли гри (тека або образ) | Немає | PlayStation, США, три диски. |
| Lunar: Silver Star Story Complete | PlayStation | Файли гри (тека або образ) | Немає | PlayStation, США, два диски. |
| Metal Gear Solid (PlayStation) | PlayStation | Файли гри (тека або образ) | Немає | PlayStation, США, обидва диски. |
| Policenauts | PlayStation, **PSP** | Файли гри (тека або образ) | Немає | Японські диски з англійським фан-патчем. |
| Silent Hill (PlayStation) | PlayStation | Файли гри (тека або образ) | Немає |  |
| Vagrant Story | PlayStation | Файли гри (тека або образ) | Немає |  |

### **PSP**

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Castlevania: The Dracula X Chronicles (PSP) | **PSP** | Файли гри (тека або образ) | Немає | PSP. Рядки Symphony of the Night є в оверлеях PSP. |
| Lunar: Silver Star Harmony (PSP) | **PSP** | Файли гри (тека або образ) | Немає | PSP, США. Збірка записує кириличний шрифт на диск. |
| Monster Hunter Portable 3rd HD (PSP, Yakumo) | **PSP** | Файли гри (тека або образ) | Немає | Образ PSP і PC-порт Yakumo. Потрібен en_source.json з робочого скрипта власника. |

### ПК

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Hard Corps: Uprising | ПК | Файли гри (тека або образ) | Немає | Проєкт з текстур. Блоків тексту немає. |
| Link's Awakening DX HD | ПК | Файли гри (тека або образ) | Немає | PC-ремейк-фанатів v1.0.0. Жоден шрифт ще не має українських літер. |
| Silent Hill 3 (PC) | ПК | Файли гри (тека або образ) | Немає |  |
| Super Metroid (PC port) | ПК | Файли гри (тека або образ) | Немає | ROM SNES, США, через PC-порт sm_rewrite. Лише великі літери. |
| Zelda: A Link to the Past (PC port) | ПК | Файли гри (тека або образ) | Немає | ROM SNES США через PC-порт snesrev/zelda3. |

### Nintendo DS

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Castlevania DS: Dawn of Sorrow / Portrait of Ruin / Order of Ecclesia | Nintendo DS | Файли гри (тека або образ) | Немає | DS: Dawn of Sorrow, Portrait of Ruin і Order of Ecclesia. |
| Dragon Quest IX: Sentinels of the Starry Skies | Nintendo DS | Файли гри (тека або образ) | Немає | DS, Європа. |
| Final Fantasy Tactics A2 | Nintendo DS | Файли гри (тека або образ) | Немає | DS, Європа. |
| Final Fantasy XII: Revenant Wings | Nintendo DS | Файли гри (тека або образ) | Немає | DS, Європа. |
| Infinite Space | Nintendo DS | Файли гри (тека або образ) | Немає | DS, Європа. |
| Pokémon Black / White and Black 2 / White 2 (DS) | Nintendo DS | Файли гри (тека або образ) | Перекладений ROM DS | DS: Black/White і Black 2/White 2. |
| Pokémon Diamond, Pearl, Platinum, HeartGold and SoulSilver (DS) | Nintendo DS | Файли гри (тека або образ) | Перекладений ROM DS | ROM DS, США. |
| Professor Layton (DS) | Nintendo DS | Файли гри (тека або образ) | Немає | Кілька назв DS в одному плагіні. |
| The World Ends with You | Nintendo DS | Файли гри (тека або образ) | Немає | DS, Європа. |
| Zelda: Four Swords Anniversary Edition | Nintendo DS | Файли гри (тека або образ) | Немає | DSiWare, Європа. |
| Zelda: Phantom Hourglass / Spirit Tracks (DS) | Nintendo DS | Файли гри (тека або образ) | Немає | США. Phantom Hourglass і Spirit Tracks. |

### Game Boy Advance

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Castlevania: Circle of the Moon (GBA) | Game Boy Advance | Файли гри (тека або образ) | Немає | GBA, США. |
| Castlevania: Harmony of Dissonance / Aria of Sorrow (GBA) | Game Boy Advance | Файли гри (тека або образ) | Немає | GBA: Harmony of Dissonance (Європа) і Aria of Sorrow (США). |
| Donkey Kong Country 3 (GBA) | Game Boy Advance | Файли гри (тека або образ) | Немає | GBA, Європа. Простий текст ASCII. |
| Final Fantasy Tactics Advance (GBA) | Game Boy Advance | Файли гри (тека або образ) | Перекладений ROM GBA | GBA, США. |
| Mario vs. Donkey Kong (GBA) | Game Boy Advance | Файли гри (тека або образ) | Немає |  |
| Pokemon FireRed/LeafGreen | Game Boy Advance | Game ROM (Game Boy Advance) | **Patched ROM**; Пакет рекомпіляції (EmeraldRecomp, FireRedLeafGreenRecomp) | GBA. Також JSON-дампи тексту ROM і файли вихідного коду pret. |
| The Legend of Zelda: The Minish Cap | Game Boy Advance | Файли гри (тека або образ) | Немає | GBA. |

### **Game Boy Color**

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Pokémon Gold, Silver and Crystal (pret) | **Game Boy Color** | Game ROM (Game Boy Color) | **Patched ROM**; Пакет рекомпіляції (Gen2Recomp: Gold, Silver, Crystal) | Gold, Silver і Crystal через декомпіляції pret. Також режим Game ROM. |
| Zelda: Link's Awakening DX (Game Boy Color) | **Game Boy Color** | Файли гри (тека або образ) | Немає | Англійський ROM v1.0. |
| Zelda: Oracle of Ages / Seasons (Game Boy Color) | **Game Boy Color** | Файли гри (тека або образ) | Немає | Game Boy Color. |

### **Game Boy**

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Pokémon Red / Blue / Yellow (Game Boy) | **Game Boy** | Game ROM (Game Boy) | **Patched ROM** | Red, Blue і Yellow. Режим Game ROM читає файл .gb, make не потрібен. |

### Nintendo 64

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Conker's Bad Fur Day (N64) | Nintendo 64 | N64 ROM (USA) | Пропатчений ROM (US); BPS-патч (від US ROM до перекладу) | N64, США 1.0. Плагін у розробці. |
| Paper Mario (N64) | Nintendo 64 | Файли гри (тека або образ) | Немає | N64, США 1.0, у PC-порту PaperBoat 1.0.2. |
| Zelda: Majora's Mask (N64) | Nintendo 64 | Файли гри (тека або образ) | Немає | ROM США. Українські літери використовують карту шрифту. |
| Zelda: Ocarina of Time (N64) | Nintendo 64 | Файли гри (тека або образ) | Немає | ROM США 1.0. |

### Super Nintendo

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Donkey Kong Country (SNES) | Super Nintendo | Файли гри (тека або образ) | Немає | ROM SNES, США v1.0, через PC-порти для Switch. |
| Rock N' Roll Racing (SNES) | Super Nintendo | USA ROM | Перекладений ROM і патч IPS | SNES, США. |

### **Sega Saturn**

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Castlevania: Symphony of the Night (Saturn) | **Sega Saturn** | Файли гри (тека або образ) | Немає | Випуск для Sega Saturn. |

### Dreamcast

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Skies of Arcadia (Dreamcast, USA) | Dreamcast | Файли гри (тека або образ) | Перекладений набір диска (cue і доріжки) | Dreamcast, США. Такий самий ліміт байтів, як у версії для GameCube. |

### Допоміжні та загальні плагіни

| Гра | Платформа | Що потрібно майстру | Цілі збірки | Примітки |
|---|---|---|---|---|
| Electronic manuals (3DS, Ukrainian) | Nintendo 3DS | Файли гри (тека або образ) | Немає | Електронні посібники 3DS (допоміжний). |
| Nintendo 3DS system (Ukrainian) | Nintendo 3DS | Файли гри (тека або образ) | Мод 3DS поверх російського слота (dist/); Мод 3DS поверх англійського слота (dist_en/) | Системні меню 3DS українського моду (допоміжний). |
| Plain Text | Інше | Файли гри (тека або образ) | **Translated files** | Загальні файли JSON і TXT, без гри (допоміжний). |
| Wii System Font | Wii | Файли гри (тека або образ) | Немає | Системні растрові шрифти Wii wbf1 і wbf2 (допоміжний). |

## Типові ситуації

**Моя гра працює на двох платформах.**

- Колонка **Платформа** показує всі платформи плагіна.
- Майстер визначає платформу з ваших файлів. Перевірте колонку **Платформа** у списку файлів.

**Майстер просить файл ключів.**

- Ваш файл зашифровано. Натисніть **Додати файл ключів для ...**.
- Picoripi запам’ятовує шлях до ключа для кожної консолі.

**Майстер пише: Не читається: додайте папку.**

- Ця гра не може прочитати цей файл сама.
- Приберіть файл і додайте розпаковану теку гри кнопкою **Додати папку...**.

**Майстер просить оновлення або DLC.**

- Додайте файл оновлення або DLC. Встановіть його роль: **Update** або **DLC**.
- Повторюватися може лише DLC. Кожному іншому файлу дайте окрему роль.

**Кнопки Зібрати, Експорт і Запустити вимкнені.**

- Плагін не оголошує цілі збірки. У таблиці стоїть **Немає**.
- Гру можна все одно збирати робочим скриптом. Див. [Збірка і тестування](Build_and_Test.md).

**Дві версії однієї гри мають один плагін.**

- Деякі рядки охоплюють кілька версій, наприклад Wii і Switch.
- Прочитайте колонку **Примітки** перед вибором версії.

<!-- wiki-nav -->
---

**Назад:** [Налаштування](4_Configuration_Guide.md) · [До змісту вікі](README.md) · **Далі:** [Нотатки по іграх](Game_Notes.md)
