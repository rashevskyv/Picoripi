# Script Preparation Guideline for Picoripi

To achieve chronological storyline alignment and enable rich visual/action context in your AI translations via MemePalace context builders, you must properly structure your flat game scripts. 

Picoripi's default script parser (`BaseGameRules`) recognizes a standardized syntax defining **Chapters**, **Locations/Rooms**, **Action/Visual Contexts**, and **Dialogue Speakers**.

Follow this syntax guideline to format any script file (`.txt`) for perfect import:

---

## 1. Chapters & Locations

Chapters and locations partition the script into logical chunks ("Rooms" in SQLite timeline database). A room context is applied to all subsequent dialogue lines until a new chapter or location is declared.

### Syntax:
Use square brackets `[...]` on a separate line with a prefix of either `Chapter:` or `Location:`:

```text
[Chapter: Act I - The Princess in Distress]
[Location: Hyrule Castle - Throne Room]
```

*Note: The parser automatically sanitizes these tags, replacing special characters and converting spaces to underscores for timeline indexing.*

---

## 2. Action & Visual Context

Action descriptions explain what is happening on screen (e.g. character animations, facial expressions, camera directions, environmental events). This context is injected directly into the AI's translation prompt to ensure proper style, formal/informal tone, and pronoun genders (he/she/it).

### Syntax:
Use curly braces `{...}` on a separate line with an `Action:` prefix:

```text
{Action: Zelda looks out the stained glass window, sighing deeply with a worried expression}
```

*Note: An action context is bound to all subsequent dialogue cues until the next action context or room change occurs.*

---

## 3. Speakers and Dialogue Cues

The parser supports two formats for defining the active speaker and their corresponding spoken dialogue:

### Format A: Classical Inline Speaker (Recommended)
Prefix the dialogue line with the speaker's name in UPPERCASE followed by a colon `:` and a space:

```text
ZELDA: I must find the hero of time.
LINK: ...Hyah!
```

### Format B: Uppercase Gutter Line (GameFAQ style)
Put the speaker's name on its own line in UPPERCASE (minimum 2 characters), followed by their dialogue lines immediately below it:

```text
MIDNA
Hey! Listen up! We don't have all day!
```

---

## 4. Complete Example

Below is a complete, well-structured example of a prepared script:

```text
[Chapter: Prologue - The Forest Encounter]
[Location: Ordon Woods - Pathway]

{Action: Link is walking along the path when Midna suddenly drops down from a tree branch}

MIDNA: Well, look what we have here!
ZELDA: Midna, please, we must be careful.

{Action: Zelda steps forward, pointing to a strange dark portal appearing in the distance}

ZELDA: Do you see that purple fog ahead?
MIDNA
Yeah, looks like trouble. Link, get your sword ready!
```

---

## 5. Technical details for Plugin Developers

The default text parser is implemented in `BaseGameRules.parse_walkthrough_transcript()`. 
If your specific retro game requires a custom script structure (e.g. binary symbols, specific offset addresses, or hexadecimal separators like `[0x123]`), you can easily override `parse_walkthrough_transcript` in your plugin (inheriting from `BaseGameRules`) and extend these regular expressions.
