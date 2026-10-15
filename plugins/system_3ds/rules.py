"""Nintendo 3DS system titles (HOME Menu, System Settings, applets): the owner's 3ds-ua string files, edited in place.

The project's source and translation are the same files of the owner's repo (its Makefile stays the build):
``src/strings/<part>/*.json`` (MSBT label -> {"en", "ua", "ru"?}) and ``src/layouts/<part>.json`` (archive -> layout
-> pane -> [{"en", "ru", "ua"}], text baked into a layout pane). One file is one block; a string is one object with
``en`` and ``ua``, its id the label or the pane path ("up_LZ.bin/./blyt/StartTopEU_U_00.bclyt/TextBoxTitle_00#0").
The original is ``en``, the translation ``ua``; ``ru`` is a read-only reference column. ``_all_langs.json`` is not a
block: it holds build overrides per language slot (slot -> file -> label -> text), not en/ua pairs.

Saving writes only the ``ua`` literals that changed into the file as it is on disk; every other byte stays, so a file
saved without a change is the same bytes, whatever its layout (indented, one entry per line, CRLF).

Widths: the glyph advances are the 3DS system font table of plugins/manual_3ds (widths.json: the owner's
assets/font_widths.json plus the letters the patched font adds, and the build's homoglyphs). A string is measured as
the owner's tools/validate.py measures it: the widest line, {t:1.0:XXXX} / {t:1.1:XXXX} scale the glyphs, other tags
draw nothing. A string whose pane box is known (boxes.json) is checked against the box; the others show their width.
"""
import hashlib
import json
import os
import re
from json.decoder import scanstring
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.manual_3ds import layout as manual_layout

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS

_DATA_DIR = os.path.dirname(os.path.abspath(__file__))
_WIDTHS_FILE = os.path.join(os.path.dirname(_DATA_DIR), "manual_3ds", "widths.json")
# The owner's MSBT tag (tools/msbt.py TOKEN_RE): {t:group.type:args} and {/t:group.type}.
_TAG = re.compile(r"\{(/?)t:(\d+)\.(\d+)(?::([0-9a-fA-F]*))?\}")
_SCALE_100 = 0x6400  # a scale tag's argument for 100 %
_SPACE = re.compile(r"[ \t\r\n]*")
_DECODER = json.JSONDecoder()
_SKIPPED_FILE = "_all_langs.json"


class Entry(NamedTuple):
    """One {"en", "ua"} object of a file."""

    key: str
    en: str
    ru: str
    ua: str
    span: Tuple[int, int]  # where the "ua" value's literal is in the file text


def read_entries(text: str) -> List[Entry]:
    """Every object with string ``en`` and ``ua`` in a string or layout file, in file order. ValueError: not JSON."""
    out: List[Entry] = []
    start = 1 if text.startswith("﻿") else 0
    end = _value(text, _SPACE.match(text, start).end(), [], out)
    if _SPACE.match(text, end).end() != len(text):
        raise ValueError(f"extra data at {end}")
    return sorted(out, key=lambda entry: entry.span)


def patch_ua(text: str, entries: List[Entry], texts: List[str]) -> str:
    """``text`` with the ``ua`` literal of each entry whose text changed replaced; the rest is kept as it is."""
    parts: List[str] = []
    last = 0
    for entry, value in zip(entries, texts):
        if value != entry.ua:
            parts += [text[last:entry.span[0]], json.dumps(value, ensure_ascii=False)]
            last = entry.span[1]
    return "".join(parts) + text[last:]


def _value(text: str, pos: int, path: List[Any], out: List[Entry]) -> int:
    """Read the JSON value at ``pos``; return where it ends. Objects with en/ua are added to ``out``."""
    if text.startswith("{", pos):
        return _object(text, pos, path, out)
    if text.startswith("[", pos):
        pos = _SPACE.match(text, pos + 1).end()
        index = 0
        while not text.startswith("]", pos):
            pos = _SPACE.match(text, _value(text, pos, path + [index], out)).end()
            pos = _SPACE.match(text, _after(text, pos, ",", "]")).end()
            index += 1
        return pos + 1
    return _DECODER.raw_decode(text, pos)[1]


def _object(text: str, pos: int, path: List[Any], out: List[Entry]) -> int:
    fields: Dict[str, Tuple[Any, int, int]] = {}
    pos = _SPACE.match(text, pos + 1).end()
    while not text.startswith("}", pos):
        if not text.startswith('"', pos):
            raise ValueError(f"expected a key at {pos}")
        name, pos = scanstring(text, pos + 1)
        pos = _SPACE.match(text, pos).end()
        if not text.startswith(":", pos):
            raise ValueError(f"expected ':' at {pos}")
        start = _SPACE.match(text, pos + 1).end()
        if text.startswith(("{", "["), start):
            pos = _value(text, start, path + [name], out)
        else:
            value, pos = _DECODER.raw_decode(text, start)
            fields[name] = (value, start, pos)
        pos = _SPACE.match(text, _after(text, _SPACE.match(text, pos).end(), ",", "}")).end()
    en, ua, ru = fields.get("en"), fields.get("ua"), fields.get("ru")
    # "en": null is a label with no English (23 in nnid/message__EU.json): an empty original.
    if en and ua and isinstance(en[0], (str, type(None))) and isinstance(ua[0], str):
        out.append(Entry(_key(path), en[0] or "", ru[0] if ru and isinstance(ru[0], str) else "", ua[0],
                         (ua[1], ua[2])))
    return pos + 1


def _after(text: str, pos: int, separator: str, closing: str) -> int:
    """Past a separator at ``pos``, or still at ``pos`` when the container closes there."""
    if text.startswith(separator, pos):
        return pos + 1
    if text.startswith(closing, pos):
        return pos
    raise ValueError(f"expected '{separator}' or '{closing}' at {pos}")


def _key(path: List[Any]) -> str:
    """["up_LZ.bin", "./blyt/x.bclyt", "Pane", 0] -> "up_LZ.bin/./blyt/x.bclyt/Pane#0"; ["label"] -> "label"."""
    key = ""
    for part in path:
        key += f"#{part}" if isinstance(part, int) else (f"/{part}" if key else part)
    return key


def _text(raw: Any) -> str:
    return bytes(raw).decode("utf-8")


def _fingerprint(entries: List[Entry]) -> str:
    """Which file a block is: its ids and English (two hud files with the same content are the same file here)."""
    return hashlib.sha1("\0".join(f"{e.key}\0{e.en}" for e in entries).encode("utf-8")).hexdigest()


def line_widths(text: str, widths: manual_layout.Widths) -> List[float]:
    """Painted width of each line in font pixels, as the owner's tools/validate.py line_widths measures it."""
    text = widths.apply_homoglyphs(text)
    scales = {"0": 1.0, "1": 1.0}  # {t:1.0} and {t:1.1} can be open at once: the size is their product
    lines = [0.0]
    index = 0
    while index < len(text):
        tag = _TAG.match(text, index)
        if tag:
            if tag.group(2) == "1" and tag.group(3) in scales:
                value = tag.group(4)
                scales[tag.group(3)] = int(value, 16) / _SCALE_100 if value and not tag.group(1) else 1.0
            index = tag.end()
            continue
        char = text[index]
        index += 1
        if char == "\n":
            lines.append(0.0)
        else:
            lines[-1] += widths.glyph(char) * scales["0"] * scales["1"]
    return lines


class GameRules(BaseGameRules):
    """Nintendo 3DS system menus and applets (Ukrainian), from the 3ds-ua repo's JSON files."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_style = "curly"
    data_dir = _DATA_DIR

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._blocks: List[Dict[str, Any]] = []  # per data block, in load order: {"keys": [...], "fp": "..."}
        self._sources_read = False
        self._save_text: Optional[str] = None
        self._widths: Optional[manual_layout.Widths] = None
        self._boxes: Optional[Dict[str, Any]] = None

    def get_display_name(self) -> str:
        return "Nintendo 3DS system (Ukrainian)"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        # Bytes in and out: the save patches the file's own text, so nothing reformats it.
        return [FileFormat((".json",), "bytes", "3DS system text (3ds-ua JSON)")]

    def includes_source_file(self, rel_path: str) -> bool:
        """``strings/<part>/<file>.json`` (not ``_all_langs.json``) and ``layouts/<part>.json`` of the repo's src."""
        parts = rel_path.split("/")
        if parts[0] == "strings":
            return len(parts) == 3 and parts[2].endswith(".json") and parts[2] != _SKIPPED_FILE
        return parts[0] == "layouts" and len(parts) == 2 and parts[1].endswith(".json")

    # -- loading and saving ---------------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return [], {}  # the project sync hands parsed JSON only to name blocks: one file is one block
        entries = read_entries(_text(json_obj))
        if self._sources_read:
            return [[entry.ua for entry in entries]], {}
        self._blocks.append({"keys": [entry.key for entry in entries], "fp": _fingerprint(entries)})
        return [[entry.en for entry in entries]], {}

    def export_runtime_state(self) -> Any:
        # The source and the translation are the same file. The load worker parses every source, exports this state,
        # then parses the translations (BaseGameRules.export_runtime_state); every later parse (a save, a revert)
        # is a translation too. So a parse before the first export since a reset is a source (en), after it ua.
        # ponytail: an autosave export while a project load still parses sources would flip it early; the loads
        # clear the editor first, so nothing is dirty then. Upgrade: a host hook naming the pass.
        self._sources_read = True
        return {"blocks": [dict(block) for block in self._blocks]}

    def restore_runtime_state(self, state: Any) -> None:
        blocks = state.get("blocks") if isinstance(state, dict) else None
        if isinstance(blocks, list):
            self._blocks = [dict(block) for block in blocks if isinstance(block, dict)]
        self._sources_read = True

    def reset_runtime_state(self) -> None:
        self._blocks = []
        self._sources_read = False
        self._save_text = None

    def prepare_save_context(self, context: Any) -> None:
        """The file is patched as it is on disk now (the translation copy is the source file itself)."""
        self._save_text = None
        for version in context.existing_versions():
            try:
                text = _text(version)
                read_entries(text)
            except (ValueError, UnicodeDecodeError):
                continue
            self._save_text = text
            return

    def save_data_to_json_obj(self, data: list, block_names: Optional[dict] = None) -> Any:
        text, self._save_text = self._save_text, None
        if text is None:
            raise ValueError("3DS system: the file to save into is not on disk")
        entries = read_entries(text)
        texts = [str(value) for value in (data[0] if data else [])]
        if len(texts) != len(entries):
            raise ValueError(f"3DS system: the file on disk has {len(entries)} strings and the editor {len(texts)}; "
                             "it changed outside Picoripi. Reopen the project before saving.")
        return patch_ua(text, entries, texts).encode("utf-8")

    # -- strings --------------------------------------------------------------------------

    def string_key(self, block_idx: int, string_idx: int) -> Optional[str]:
        """The label or pane path of a string, or None."""
        blocks = self._blocks
        keys = blocks[block_idx].get("keys", []) if 0 <= block_idx < len(blocks) else []
        return keys[string_idx] if 0 <= string_idx < len(keys) else None

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        key = self.string_key(block_idx, string_idx)
        return {"resource": key} if key else {}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        key = self.string_key(block_idx, string_idx)
        if key is None:
            return {}
        return {"content_role": "3DS system menu text",
                "role_instruction": (f"Nintendo 3DS system menu string {key}. Keep every {{t:...}} tag, %-format "
                                     "and line break; the console's buttons and panes have no spare room.")}

    # -- reference (Russian, read-only) ---------------------------------------------------

    def supports_reference_patch(self) -> bool:
        return True

    def get_reference_language_label(self) -> str:
        return "Russian (RU)"

    def load_reference_patch(self, patch_path: str, block_names: Any = None) -> Dict[Tuple[int, int], str]:
        """The ``ru`` of the files under ``patch_path`` (the repo's src folder, or one file), matched by content."""
        wanted: Dict[str, List[int]] = {}
        for block, info in enumerate(self._blocks):
            wanted.setdefault(str(info.get("fp")), []).append(block)
        root = Path(patch_path)
        paths = [root] if root.is_file() else [path for path in sorted(root.rglob("*.json"))
                                                if self.includes_source_file(path.relative_to(root).as_posix())]
        out: Dict[Tuple[int, int], str] = {}
        for path in paths:
            try:
                entries = read_entries(_text(path.read_bytes()))
            except (OSError, ValueError, UnicodeDecodeError):
                continue
            for block in wanted.get(_fingerprint(entries), []):
                out.update({(block, index): entry.ru for index, entry in enumerate(entries) if entry.ru})
        return out

    # -- widths ---------------------------------------------------------------------------

    def _widths_table(self) -> manual_layout.Widths:
        if self._widths is None:
            with open(_WIDTHS_FILE, encoding="utf-8") as handle:
                self._widths = manual_layout.Widths(json.load(handle))
        return self._widths

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        """Font pixels of the widest line (the unit of the owner's budgets and of ``get_string_layout``)."""
        return round(max(line_widths(text, self._widths_table())))

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """The pane box of a layout-bound string, in font pixels; None when the string's box is not known."""
        key = self.string_key(block_idx, string_idx)
        if key is None:
            return None
        if self._boxes is None:
            with open(os.path.join(_DATA_DIR, "boxes.json"), encoding="utf-8") as handle:
                self._boxes = json.load(handle)
        box = self._boxes.get(key.split("#", 1)[0])
        if not isinstance(box, dict):
            return None
        limit = int(float(box["width"]) * manual_layout.FONT_WIDTH / float(box["font_size"]))
        return {"max_width": limit, "warn_width": limit}
