"""Skyward Sword MSBT control tags: the catalogue and the readable ``{tags}`` the editor shows.

The game's own project file (``0-Common/main.msbp``) holds only the colour palette (CLR1), no tag names,
so the catalogue below is measured from the text itself (HD 1.0.1 and Wii USA, every language): the
group/type numbers and parameter sizes are what the files hold, the names come from where the tags
stand. Tags whose effect could not be told from the text keep a neutral name (``{ctl7:21}``) with the
evidence in their description; they still round-trip byte for byte.

  ``{heroName}``               the player's name (2:0) -- 626 of 631 English uses stand in no colour
  ``{color:Red}`` ... ``{color:Default}``   a CLR1 palette colour (0:3); Default (65535) ends it
  ``{item:11}``                an item name by id (2:1), ``{word:3}`` a word.msbt word whose form
                               follows the count before it (``{count:0:0}``, 2:3)
  ``{icon:41}``                a picture-font button icon (2:4)
  ``{wait:15}`` ``{speed:-5}`` ``{textSize:1}`` ``{face:0:0:0:1}`` ``{choice1:65535}`` ...
The codec (``plugins.common.lms_tags``) shows a tag by name only when its readable form encodes back to
the same bytes; anything else stays ``{tag:G:T:hex}``. Arguments with an odd byte length end in 0xCD.
"""
from __future__ import annotations

from typing import Dict, Tuple

from plugins.common.lms_tags import TAG_RE, TagCodec  # noqa: F401 - TAG_RE is this module's API

# CLR1 of main.msbp (identical in every language, HD and Wii), named after the colour it holds.
COLORS = {0: "Red", 1: "LightRed", 2: "Gold", 3: "Blue", 4: "Green", 5: "Orange", 6: "Purple", 7: "DarkGreen",
          8: "Teal", 9: "Crimson", 10: "Grey", 11: "Yellow", 12: "Olive", 13: "White", 65535: "Default"}
COLOR_HEX = {0: "#ff5050", 1: "#ff7878", 2: "#e6a000", 3: "#469beb", 4: "#50dc41", 5: "#ff6400", 6: "#8c468c",
             7: "#1eb91e", 8: "#009ba5", 9: "#f50a32", 10: "#919ba0", 11: "#efef00", 12: "#5f9669", 13: "#ffffff"}

VALUE_NAMES: Dict[Tuple[str, int], Dict[int, str]] = {("color", 0): COLORS}

_UNKNOWN = "Control tag whose effect is not identified"
# (group, type) -> (name, argument types, description)
TAGS: Dict[Tuple[int, int], Tuple[str, Tuple[str, ...], str]] = {
    (0, 0): ("ruby", ("u16", "str"), "Ruby text drawn above the next N bytes of text"),
    (0, 1): ("font", ("str",), "Font face"),
    (0, 2): ("size", ("u16",), "Text size in percent"),
    (0, 3): ("color", ("u16",), "Text colour from the palette; Default ends the colour"),
    (0, 4): ("pageBreak", (), "Starts a new text box page"),
    (1, 0): ("choice1", ("u16",), "First answer of a choice follows (the last lines of the message)"),
    (1, 1): ("choice2", ("u16",), "Second answer of a choice follows"),
    (1, 2): ("choice3", ("u16",), "Third answer of a choice follows"),
    (1, 3): ("choice4", ("u16",), "Fourth answer of a choice follows"),
    (1, 4): ("wait", ("u16",), "Pause in frames before the rest is typed (after sentences: 5-60)"),
    (1, 5): ("endWait", ("u16", "u16"), "Stands at the end of a message: frames before it goes on (10-220)"),
    (1, 6): ("speed", ("s8",), "Typing speed from here on: negative is slower (around '...'), 0 is normal"),
    (1, 7): ("ctl7", ("u32",), _UNKNOWN + " (start or end of shop and NPC messages)"),
    (1, 8): ("textSize", ("s8",), "Text size from here on: 1 large, 2 larger, -1 small, -2 smaller, 0 normal"),
    (1, 9): ("face", ("u8", "u8", "u8", "u8"), "Speaker's expression and gesture for the following text"),
    (1, 10): ("ctl10", ("u16", "u8"), _UNKNOWN + " (before a shouted line, with ctl13)"),
    (1, 11): ("ctl11", ("u32",), _UNKNOWN + " (before names and key words, mostly 4)"),
    (1, 12): ("ctl12", ("u16", "u16"), _UNKNOWN + " (end of Fi's area notes: 6 and a number)"),
    (1, 13): ("ctl13", ("u8", "u8"), _UNKNOWN + " (before a shouted line, with ctl10)"),
    (1, 15): ("ctl15", (), _UNKNOWN + " (wraps a whole door notice; closed by {/ctl15})"),
    (1, 16): ("ctl16", ("u32", "u32"), _UNKNOWN + " (start of the staff roll)"),
    (1, 17): ("ctl17", ("u8",), _UNKNOWN + " (end of item and button tutorials)"),
    (1, 18): ("ctl18", ("u32",), _UNKNOWN + " (in Fi's reports, before 'Master')"),
    (1, 19): ("ctl19", (), _UNKNOWN),
    (2, 0): ("heroName", (), "The player's name (Link)"),
    (2, 1): ("item", ("u16",), "Name of the item with this id"),
    (2, 2): ("number", ("u32",), "Inserted number (by slot)"),
    (2, 3): ("count", ("u32", "u8"), "Inserted count; the {word} after it takes the matching form"),
    (2, 4): ("icon", ("u8",), "Button or symbol icon of the picture font"),
    (2, 5): ("icon2", ("u8",), "Motion icon (aim, swing...) of the picture font"),
    (3, 0): ("sup", (), "Raised text (ordinal endings: 1st, 2nd); closed by {/sup}"),
    (3, 1): ("capitalize", (), "Upper-case the first letter of the next inserted word"),
    (3, 2): ("particle", ("u8",), "Korean particle chosen by the last syllable before it (ko_KR only)"),
    (3, 3): ("counter", ("u8",), "Japanese counter word for the count before it (ja_JP only)"),
    (3, 4): ("word", ("u8",), "Word from word.msbt (lang:word:NNN) in the form the count before it needs"),
}

CODEC = TagCodec(TAGS, VALUE_NAMES)
render_tag = CODEC.render_tag
to_editor = CODEC.to_editor
from_editor = CODEC.from_editor
describe = CODEC.describe
parse_tag = CODEC.parse_tag
