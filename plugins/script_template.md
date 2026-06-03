# Game Translation Script & Context Template

This template defines the standardized Markdown format for preparing game walkthrough scripts. 
By using this format, Picoripi can parse all character profiles, relationships, terminology, 
and chronological dialogues locally, without performing expensive AI character mining.

Save your game script as `<game_plugin_name>_script.md` (e.g. `zelda_mc_script.md`) to be recognized automatically.

---

## 1. Global Plot & Synopsis
Provide a general overview of the story, key conflicts, and settings. This is used as global background context for AI translation prompts.

Example:
```text
The Legend of Zelda: Twilight Princess follows Link as he tries to prevent the land of Hyrule from being engulfed by a corrupted parallel dimension known as the Twilight Realm.
```

---

## 2. Character Cast & Profiles
Use the exact bullet-point format below. The parser will automatically extract their attributes (gender, age_group, address style) and populate the glossary and database.

*Note: The character name in the list item header must match the SPEAKER name used in dialogues.*

- **[CHARACTER_SPEAKER_ID]** (Name in Game: `[Display Name]`)
  - **Translation**: `[Translated Name in Target Language]`
  - **Gender**: `[male/female/unknown]`
  - **Age Group**: `[child/adult/elder/unknown]`
  - **Address Style**: `[e.g., informal, respectful, formal]`
  - **Relationship**: `[Relationship description, e.g. Mentor of Link]`
  - **Description**: `[Detailed backstory, speech quirks, and guidelines for translators]`

Example:
- **RUSL** (Name in Game: `Rusl`)
  - **Translation**: `Руслан`
  - **Gender**: `male`
  - **Age Group**: `adult`
  - **Address Style**: `informal (uses 'ти') to Link, formal (uses 'ви') to Mayor Bo`
  - **Relationship**: `Mentor of Link, husband of Uli, father of Colin`
  - **Description**: `A brave warrior and swordfighter from Ordon Village who asks Link to deliver the Ordon Sword.`

- **MIDNA** (Name in Game: `Midna`)
  - **Translation**: `Мідна`
  - **Gender**: `female`
  - **Age Group**: `adult`
  - **Address Style**: `teasing and informal (uses 'ти')`
  - **Relationship**: `Companion of Link`
  - **Description**: `An imp-like creature from the Twilight Realm who assists Link.`

---

## 3. Terms & Glossary
Define special items, locations, groups, or in-game terminology. These will be added to the Glossary table.

- **[TERM_ID]** (Original: `[Original Term]`)
  - **Translation**: `[Translated Term]`
  - **Description**: `[Notes and contextual meaning of the term]`

Example:
- **ORDON_SHIELD** (Original: `Ordon Shield`)
  - **Translation**: `Ордонський щит`
  - **Description**: `A wooden shield with a goat design, crafted by Rusl for the Hyrule Castle delivery.`

---

## 4. Chronological Dialogue Timeline
Organize dialogues into Chapters, Locations, and Actions. 
- Use Level 1 headers (`#`) or Level 2 headers (`##`) starting with `Chapter` or `Act` to define chapters.
- Use Level 3 headers (`###`) starting with `Location:` to define room/area boundaries.
- Use curly braces `{Action: ...}` to define visual context.
- Use `SPEAKER_ID: Dialogue text` format for dialogues.

# Chapter I: The Forest Encounter
This chapter covers Link's first meeting with Midna in the Faron Woods.

### Location: Ordon Woods - Pathway

{Action: Link is walking along the path when Midna suddenly drops down from a tree branch}

MIDNA: Well, look what we have here!
ZELDA: Midna, please, we must be careful.

{Action: Zelda steps forward, pointing to a strange dark portal appearing in the distance}

ZELDA: Do you see that purple fog ahead?
MIDNA: Yeah, looks like trouble. Link, get your sword ready!
