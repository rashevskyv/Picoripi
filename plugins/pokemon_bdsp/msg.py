"""Pokémon Brilliant Diamond / Shining Pearl message tables (ILCA ``MsbtData`` MonoBehaviours) as editor text.

``1_unpack.bat`` (``_shared/scripts/zt/bdsp_unity.py``) writes each English table as the MonoBehaviour's type
tree in JSON (``json.dumps(..., ensure_ascii=False, indent=1)`` + newline). A table is a list of labels; a
label's text is a list of *words*:

- ``patternID`` 0: plain text; 2, 3, 4: a TextMeshPro rich-text tag (``<color=…>``, ``<size=…>``, ``<pos=…>``);
  5: a game tag (a name, a number, a grammar form), its data in the label's ``tagDataArray[tagIndex]``;
  7: an event word, the text before the event.
- ``eventID`` after the word's text: 0 none, 1 new line, 2 wait ``tagValue`` seconds, 3 scroll (wait for the
  button, scroll one line), 4 clear (wait, new window), 5 an event with a number, 7 end of the message.
- ``strWidth``: the width of the text in font units (sum of the glyph advances at 32 pt); -1 for tags and
  waits. ``2_build.bat`` measures the words of every edited label again with the game's font.

Editor text: words joined; ``\\n`` for a new line; ``{scroll}`` / ``{clear}`` followed by ``\\n``;
``{wait:0.2}``; ``{event:5:3}``; ``{tag:G:T}`` for a game tag (``{tag:G:T:P}`` with its parameter,
``{tag:19:0:255|he|she}`` with its word forms, ``:art=1`` / ``:grm=2`` for the rare flags). Rich-text tags stay
as they are. An unedited label keeps its words byte for byte (``save_table``).
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

EVENT_NEWLINE, EVENT_WAIT, EVENT_SCROLL, EVENT_CLEAR, EVENT_END = 1, 2, 3, 4, 7
_PATTERN_OF_GROUP = {1: 0, 2: 1, 19: 5}
_RICH = {"color": 2, "size": 3, "pos": 4, "line-indent": 4}
TOKEN_RE = re.compile(r"\{scroll\}\n?|\{clear\}\n?|\{wait:[^{}]*\}|\{event:[^{}]*\}|\{tag:[^{}]*\}"
                      r"|</?(?:color|size|pos|line-indent)(?:=[^<>]*)?>|\n")
TAG_RE = re.compile(r"\{(?:scroll|clear|wait:[^{}]*|event:[^{}]*|tag:[^{}]*)\}|</?(?:color|size|pos|line-indent)(?:=[^<>]*)?>")


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _tag_text(tag: Dict[str, Any]) -> str:
    parts = [str(tag["tagIndex"]), str(tag["groupID"]), str(tag["tagID"])]
    if tag["tagParameter"] or tag["tagWordArray"]:
        parts.append(str(tag["tagParameter"]))
    if tag["tagPatternID"] != _PATTERN_OF_GROUP.get(tag["groupID"], 0):
        parts.append(f"pat={tag['tagPatternID']}")
    if tag["forceArticle"]:
        parts.append(f"art={tag['forceArticle']}")
    if tag["forceGrmID"]:
        parts.append(f"grm={tag['forceGrmID']}")
    return "{tag:" + ":".join(parts) + "".join("|" + word for word in tag["tagWordArray"]) + "}"


def parse_tag(text: str) -> Dict[str, Any]:
    """``{tag:S:G:T…}`` -> a ``tagDataArray`` entry; ValueError when malformed."""
    match = re.fullmatch(r"\{tag:([^{}|]*)((?:\|[^{}|]*)*)\}", text)
    if not match:
        raise ValueError(f"Not a game tag: {text}")
    fields = match.group(1).split(":")
    positional = [f for f in fields if "=" not in f]
    named = dict(f.split("=", 1) for f in fields if "=" in f)
    if len(positional) not in (3, 4) or not all(re.fullmatch(r"-?\d+", f) for f in positional):
        raise ValueError(f"A game tag needs argument:group:tag[:parameter]: {text}")
    slot, group, tag_id = (int(f) for f in positional[:3])
    words = match.group(2).split("|")[1:] if match.group(2) else []
    return {"tagIndex": slot, "groupID": group, "tagID": tag_id,
            "tagPatternID": int(named.get("pat", _PATTERN_OF_GROUP.get(group, 0))),
            "forceArticle": int(named.get("art", 0)),
            "tagParameter": int(positional[3]) if len(positional) == 4 else 0,
            "tagWordArray": words, "forceGrmID": int(named.get("grm", 0))}


def label_text(label: Dict[str, Any]) -> str:
    """Editor text of one label."""
    out = []
    tags = label["tagDataArray"]
    for word in label["wordDataArray"]:
        pattern, event = word["patternID"], word["eventID"]
        if pattern == 5:
            out.append(_tag_text(tags[word["tagIndex"]]))
        else:
            out.append(word["str"])
        if event == EVENT_NEWLINE:
            out.append("\n")
        elif event == EVENT_SCROLL:
            out.append("{scroll}\n")
        elif event == EVENT_CLEAR:
            out.append("{clear}\n")
        elif event == EVENT_WAIT:
            out.append("{wait:" + _number(word["tagValue"]) + "}")
        elif event not in (0, EVENT_END):
            out.append(f"{{event:{event}:{_number(word['tagValue'])}}}")
    return "".join(out)


def _word(pattern: int, event: int, text: str = "", tag_index: int = -1, value: float = 0.0) -> Dict[str, Any]:
    measured = pattern == 0 or (pattern == 7 and event in (EVENT_NEWLINE, EVENT_SCROLL, EVENT_CLEAR))
    return {"patternID": pattern, "eventID": event, "tagIndex": tag_index, "tagValue": value,
            "str": text, "strWidth": 0.0 if measured else -1.0}


def text_words(text: str, end_pattern: int = 0) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """``(wordDataArray, tagDataArray)`` of editor text; widths are 0.0 until ``2_build`` measures them.

    ``end_pattern``: the pattern of a closing text word (the game's tables use both 0 and 7 there; an edited
    label keeps the one its original had)."""
    words: List[Dict[str, Any]] = []
    tags: List[Dict[str, Any]] = []
    buffer = ""
    at = 0

    def flush() -> None:
        nonlocal buffer
        if buffer:
            words.append(_word(0, 0, buffer))
            buffer = ""

    def event(kind: int, value: float = 0.0) -> None:
        nonlocal buffer
        words.append(_word(7, kind, buffer, value=value))
        buffer = ""

    for match in TOKEN_RE.finditer(text):
        buffer += text[at:match.start()]
        at = match.end()
        token = match.group(0)
        if token == "\n":
            event(EVENT_NEWLINE)
        elif token.startswith("{scroll}"):
            event(EVENT_SCROLL)
        elif token.startswith("{clear}"):
            event(EVENT_CLEAR)
        elif token.startswith("{wait:"):
            event(EVENT_WAIT, float(token[6:-1]))
        elif token.startswith("{event:"):
            kind, _, value = token[7:-1].partition(":")
            event(int(kind), float(value or 0))
        elif token.startswith("{tag:"):
            flush()
            tags.append(parse_tag(token))
            words.append(_word(5, 0, tag_index=len(tags) - 1))
        else:
            flush()
            words.append(_word(_RICH[re.match(r"</?([\w-]+)", token).group(1)], 0, token))
    buffer += text[at:]
    if buffer:
        words.append(_word(end_pattern, EVENT_END, buffer))
        if end_pattern:
            words[-1]["strWidth"] = 0.0
    elif words and words[-1]["eventID"] == 0:
        words[-1]["eventID"] = EVENT_END
    else:
        words.append(_word(7, EVENT_END))
    return words, tags


def end_pattern(label: Dict[str, Any]) -> int:
    """7 when the label closes with an event word that carries text, else 0."""
    words = label["wordDataArray"]
    last = words[-1] if words else None
    return 7 if last and last["patternID"] == 7 and last["eventID"] == EVENT_END and last["str"] else 0


def load_table(raw: bytes) -> Tuple[Dict[str, Any], List[int], List[str]]:
    """``(type tree, indices of the real labels, their texts)``; padding labels (no name) are left out."""
    table = json.loads(bytes(raw).decode("utf-8"))
    indices = [i for i, label in enumerate(table["labelDataArray"]) if label["labelName"]]
    return table, indices, [label_text(table["labelDataArray"][i]) for i in indices]


def dump_table(table: Dict[str, Any]) -> bytes:
    """The file bytes, formatted as ``1_unpack.bat`` writes them."""
    return (json.dumps(table, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


def save_table(table: Dict[str, Any], indices: List[int], texts: List[str]) -> bytes:
    """The table with the edited texts; a label whose text did not change keeps its words and tags."""
    labels = table["labelDataArray"]
    for index, text in zip(indices, texts):
        label = labels[index]
        if text is None or text == label_text(label):
            continue
        label["wordDataArray"], label["tagDataArray"] = text_words(str(text), end_pattern(label))
    return dump_table(table)
