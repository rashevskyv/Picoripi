r"""PC-port menu keys that the disc does not carry, as ordinary project text.

The PC port (SlickAmogus port, pc_port) draws 390 menu and quick-menu strings under the keys ``MENU.<text>`` and
``QUICK.<text>``. The English of each key is the key's text, and the port's own English data
(``pc_port\localization\SilentHill_EN_raw.json``) holds it. Keys that the disc already supplies (see menu_slots.py)
are left out here. The rest become one document, ``source\pc_keys.json``:

    {"format": "silent_hill_pc_keys", "entries": [{"key": "MENU.PC_Options", "text": "PC_Options"}, ...]}

Translation folder: the same document with the translated ``text`` values. The build writes them into the pack
(``gamedata\lang\en_ua.lang``), one line per key. A key without a translated value keeps the port's English.
"""
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

FORMAT = "silent_hill_pc_keys"
PREFIXES = ("MENU.", "QUICK.")


def from_port_english(raw: Dict[str, Any], disc_keys: Iterable[str] = ()) -> Dict[str, Any]:
    """The document for the keys of the port's English data, minus the keys the disc already carries."""
    skip = set(disc_keys)
    entries = []
    for key, text in raw.items():
        if not key.startswith(PREFIXES) or not isinstance(text, str) or key in skip:
            continue
        entries.append({"key": key, "text": text})
    return {"format": FORMAT, "entries": entries}


def is_document(obj: Any) -> bool:
    return isinstance(obj, dict) and obj.get("format") == FORMAT and isinstance(obj.get("entries"), list)


def blocks(doc: Dict[str, Any]) -> Tuple[List[List[str]], Dict[str, str]]:
    """One block of texts, one text per entry."""
    return [[e["text"] for e in doc["entries"]]], {"0": "PC port menu (not on the disc)"}


def with_texts(doc: Dict[str, Any], data: Sequence[Sequence[str]]) -> Dict[str, Any]:
    """The document with the texts of the first block (a missing text keeps the English)."""
    texts = list(data[0]) if data else []
    entries = []
    for i, entry in enumerate(doc["entries"]):
        text = texts[i] if i < len(texts) and texts[i] is not None else entry["text"]
        entries.append({"key": entry["key"], "text": text})
    return {"format": FORMAT, "entries": entries}


def pack_pairs(source: Dict[str, Any], translation: Optional[Dict[str, Any]] = None) -> List[Tuple[str, str]]:
    """(pack key, value) per source entry: the translated text when the translation has the key, else the English.
    '=' in a key is written as '-' (the pack format); a line break in a value becomes a space."""
    tr = {e["key"]: e["text"] for e in translation["entries"]} if translation else {}
    out = []
    for entry in source["entries"]:
        value = tr.get(entry["key"], entry["text"])
        out.append((entry["key"].replace("=", "-"), str(value).replace("\n", " ")))
    return out
