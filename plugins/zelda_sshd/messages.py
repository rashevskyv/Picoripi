"""Skyward Sword message attributes (MSBT ATR1), speakers and places.

ATR1 (HD and Wii): 3 bytes per message in the story files -- byte 0 the window kind (1 talk, 2 Fi and
spirit windows, 5 / 10 / 11 item get, 12 / 13 tutorial captions, 14 hints, 20 area title cards, ...),
byte 2 on HD the speaker: an index into ``0-Common/009-SpeakerName.msbt`` plus 2 (0 = not named). The
Wii version has no speaker byte and no SpeakerName file, so both versions read the speakers from
``speakers.json``, made from the HD files by ``python -m plugins.zelda_sshd.messages <HD romfs>``:
``names`` (SpeakerName, in order), ``files`` ({msbt stem: {label: speaker}} from the speaker byte).
Measured on HD 1.0.1: 828 English messages name their speaker (Fi 182, Zelda 126, Groose 112, Gorko 92 ...).

Where the speaker byte is 0: window 2 is Fi's (all 182 window-2 messages that name a speaker name Fi,
no other speaker ever uses it; its 1,553 others are Fi's notes, reports and "Master..." lines), else a
file that one character owns names its speaker (``OWNERS``): the file names are the developers' own
(``105-Terry`` -- Beedle is "Terry" in Japanese; ``121-AkumaKun`` -- Batreaux).
"""
from __future__ import annotations

import json
import struct
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

SPEAKER_BASE = 2
TALK, SPIRIT, ITEM_GET, TITLE_CARD = 1, 2, 5, 20

# Message files of one character.
OWNERS = {"102-Zelda": "Zelda", "103-DaiShinkan": "Gaepora", "105-Terry": "Beedle", "111-FortuneTeller": "Sparrot",
          "113-RemodelStore": "Gondo", "119-Captain": "Eagus", "121-AkumaKun": "Batreaux", "503-Goron": "Gorko"}
FI = "Fi"

# Message files that are not spoken: (content role, glossary section).
NOT_DIALOGUE = {
    "001-Action": ("Action prompt on the button guide", None),
    "002-System": ("System message (saving, files, errors)", None),
    "003-ItemGet": ("Item get message, item name or item description", "Items"),
    "005-Tutorial": ("Tutorial caption or help text", None),
    "007-MapText": ("Map label: place, bird statue or boss name", "Places"),
    "009-SpeakerName": ("Character name", "Characters"),
    "010-ControllPanel": ("Controller tutorial caption", None),
    "word": ("Counted word (singular / plural forms)", None),
}

# The archive a story file comes from -> the part of the world it belongs to.
AREAS = {"0-Common": "Common (system, items, Fi)", "1-Town": "Skyloft and the Sky", "2-Forest": "Faron Province",
         "3-Mountain": "Eldin Province", "4-Desert": "Lanayru Province", "5-CenterField": "Sealed Grounds"}


def attributes(atr1: bytes, index: int) -> Optional[Dict[str, int]]:
    """``{"box", "speaker_byte"}`` of message ``index`` from an ATR1 body; None when it has none."""
    if len(atr1) < 8:
        return None
    count, size = struct.unpack_from(">II", atr1, 0)
    if size < 1 or not 0 <= index < count:
        return None
    raw = atr1[8 + index * size:8 + (index + 1) * size]
    return {"box": raw[0], "speaker_byte": raw[2] if size >= 3 else 0}


@lru_cache(maxsize=1)
def table() -> Dict[str, Any]:
    """``speakers.json``, read once."""
    path = Path(__file__).with_name("speakers.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"names": [], "files": {}}
    return {"names": data.get("names", []), "files": data.get("files", {})}


def speaker(stem: str, label: str, box: Optional[int] = None) -> Optional[str]:
    """Who says message ``label`` of message file ``stem``: the game's speaker byte, Fi's window, the file's owner."""
    found = table()["files"].get(stem, {}).get(label)
    if found:
        return found
    if box == SPIRIT:
        return FI
    return OWNERS.get(stem)


def build_table(romfs: Path) -> Dict[str, Any]:
    """The speaker table from an HD romfs (``US/Object/en_US/*.arc``)."""
    from core.containers.u8_container import U8Container
    from plugins.common.msbt import Msbt
    folder = romfs / "US" / "Object" / "en_US"
    common = U8Container((folder / "0-Common.arc").read_bytes())
    names_file = Msbt(common.read_file("0-Common/009-SpeakerName.msbt"))
    names = ["".join(t for t in tokens if isinstance(t, str)).strip() for tokens in names_file.messages]
    files: Dict[str, Dict[str, str]] = {}
    for arc in sorted(folder.glob("*.arc")):
        container = U8Container(arc.read_bytes())
        for member in container.list_files():
            if not member.endswith(".msbt"):
                continue
            msbt = Msbt(container.read_file(member))
            atr1 = msbt.section(b"ATR1")
            for index in range(len(msbt.messages)):
                found = attributes(atr1, index)
                number = (found or {}).get("speaker_byte", 0) - SPEAKER_BASE
                if found and 0 <= number < len(names) and index in msbt.labels:
                    files.setdefault(Path(member).stem, {})[msbt.labels[index]] = names[number]
    return {"source": "Skyward Sword HD 1.0.1 (US/Object/en_US), ATR1 byte 2 - 2 = SpeakerName index",
            "names": names, "files": files}


if __name__ == "__main__":
    built = build_table(Path(sys.argv[1]))
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).with_name("speakers.json")
    target.write_text(json.dumps(built, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{sum(len(v) for v in built['files'].values())} messages with a speaker -> {target}")
