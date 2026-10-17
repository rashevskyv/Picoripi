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
draw nothing. The limits are the owner's own budgets (budgets.json, built by scripts/build_system_3ds_budgets.py from
the decrypted titles): per MSBT label the widest official localisation, per layout pane the widest line of the other
languages. A string wider than its budget is a width problem, the same rule as the owner's validate.py; a string with
no budget (no dump, or a part the owner checks another way) shows its width only.
"""
import json
import os
import re
from json.decoder import scanstring
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple

from core.i18n import tr
from plugins.base_game_rules import BaseGameRules
from plugins.common.problem_analyzer import GenericProblemAnalyzer
from plugins.manual_3ds import layout as manual_layout

from . import build_mod
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS, WIDTH_PROBLEM

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


class SystemProblemAnalyzer(GenericProblemAnalyzer):
    """The owner's width rule for the string being scanned; the generic dialog rules do not apply to menu text."""

    def analyze_data_string(self, data_string, font_map, threshold, logical_hard_limit=None):
        block, string = self._current_scan_block_idx, self._current_scan_string_idx
        if block is None or string is None:
            return [set()]
        return [self.game_rules.width_problems(block, string, data_string)]


class GameRules(BaseGameRules):
    """Nintendo 3DS system menus and applets (Ukrainian), from the 3ds-ua repo's JSON files."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    problem_analyzer_class = SystemProblemAnalyzer
    tag_style = "curly"
    data_dir = _DATA_DIR

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._blocks: List[Dict[str, Any]] = []  # per data block, in load order: {"keys": [string ids]}
        self._load_role = "source"
        self._save_text: Optional[str] = None
        self._widths: Optional[manual_layout.Widths] = None
        self._budgets: Optional[Dict[str, Any]] = None
        self._details: Dict[Tuple[int, int], str] = {}  # (block, string) -> "N px, budget M px" of the last check

    def get_display_name(self) -> str:
        return "Nintendo 3DS system (Ukrainian)"

    def get_platforms(self) -> list:
        return [{"id": "3ds", "label": tr("Nintendo 3DS")}]

    def get_build_targets(self) -> list:
        return [
            {"id": "build-ru", "label": tr("3DS mod over the Russian slot (dist/)"), "platforms": ["3ds"],
             "kind": "layeredfs"},
            {"id": "build-en", "label": tr("3DS mod over the English slot (dist_en/)"), "platforms": ["3ds"],
             "kind": "layeredfs"},
        ]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        """The owner's Makefile runs on a staged copy (plugins/system_3ds/build_mod.py)."""
        if target_id not in build_mod.TARGET_DIRS:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        return str(build_mod.build(source_dir, translation_dir, target_id, output_dir, progress, is_cancelled))

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
        # The source and the translation are the same file: the host's load role says which column a parse fills.
        if self._load_role == "translation":
            return [[entry.ua for entry in entries]], {}
        self._blocks.append({"keys": [entry.key for entry in entries]})
        return [[entry.en for entry in entries]], {}

    def set_load_role(self, role: str) -> None:
        self._load_role = role

    def export_runtime_state(self) -> Any:
        return {"blocks": [dict(block) for block in self._blocks]}

    def restore_runtime_state(self, state: Any) -> None:
        blocks = state.get("blocks") if isinstance(state, dict) else None
        if isinstance(blocks, list):
            self._blocks = [dict(block) for block in blocks if isinstance(block, dict)]

    def reset_runtime_state(self) -> None:
        self._blocks = []
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
        """The ``ru`` of each block's own file under ``patch_path`` (the repo's src folder).

        The files come from the open project, not from what the load has parsed so far: the host reads the reference
        while the project's files are still loading."""
        out: Dict[Tuple[int, int], str] = {}
        for block, path in enumerate(self._project_files()):
            try:
                entries = read_entries(_text((Path(patch_path) / path).read_bytes()))
            except (OSError, ValueError, UnicodeDecodeError):
                continue
            out.update({(block, index): entry.ru for index, entry in enumerate(entries) if entry.ru})
        return out

    # -- widths ---------------------------------------------------------------------------

    def _widths_table(self) -> manual_layout.Widths:
        if self._widths is None:
            with open(_WIDTHS_FILE, encoding="utf-8") as handle:
                self._widths = manual_layout.Widths(json.load(handle))
        return self._widths

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        """Font pixels of the widest line (the owner's pixel_width, the unit of the budgets)."""
        return round(max(line_widths(text, self._widths_table())))

    def _project_blocks(self) -> list:
        """The open project's blocks, [] without one. Each file is one data block, read in project order, so a data
        block's index is its project block's index."""
        try:
            return list(self.mw.project_manager.project.blocks)
        except (AttributeError, TypeError):
            return []

    def _project_files(self) -> List[str]:
        return [str(block.source_file).replace("\\", "/") for block in self._project_blocks()]

    def _budget_table(self) -> Dict[str, Any]:
        if self._budgets is None:
            with open(os.path.join(_DATA_DIR, "budgets.json"), encoding="utf-8") as handle:
                self._budgets = json.load(handle)
        return self._budgets

    def _budget_place(self, block_idx: int, string_idx: int) -> Optional[Tuple[str, str, str]]:
        """(table, part, key) where budgets.json holds the string's width budget: "labels" for a label of a strings
        file (validate.py skips the "_" files), "panes" for a pane of a layout spec. None otherwise."""
        key = self.string_key(block_idx, string_idx)
        blocks = self._project_blocks()
        if key is None or not 0 <= block_idx < len(blocks):
            return None
        parts = str(blocks[block_idx].source_file).replace("\\", "/").split("/")
        if len(parts) == 3 and parts[0] == "strings" and not parts[2].startswith("_"):
            return "labels", parts[1], key
        if len(parts) == 2 and parts[0] == "layouts":
            return "panes", Path(parts[1]).stem, key.split("#", 1)[0]
        return None

    def budget(self, block_idx: int, string_idx: int) -> Optional[int]:
        """The owner's width budget of a string in font pixels (budgets.json), or None when it has none."""
        place = self._budget_place(block_idx, string_idx)
        if place is None:
            return None
        table, part, key = place
        value = self._budget_table()[table].get(part, {}).get(key)
        return int(value) if value else None

    def line_budget(self, block_idx: int, string_idx: int) -> Optional[int]:
        """The most lines any official localisation of the string has (budgets.json "lines"), or None."""
        place = self._budget_place(block_idx, string_idx)
        if place is None or place[0] != "labels":
            return None
        _, part, key = place
        value = self._budget_table().get("lines", {}).get(part, {}).get(key)
        return int(value) if value else None

    def part_of(self, block_idx: int) -> str:
        """The part of a block: the folder of strings/<part>/... or the stem of layouts/<part>.json; "" otherwise."""
        blocks = self._project_blocks()
        if not 0 <= block_idx < len(blocks):
            return ""
        parts = str(blocks[block_idx].source_file).replace("\\", "/").split("/")
        if len(parts) == 3 and parts[0] == "strings":
            return parts[1]
        if len(parts) == 2 and parts[0] == "layouts":
            return Path(parts[1]).stem
        return ""

    def line_widths_of(self, text: str) -> List[float]:
        """The painted width of each line in font pixels (the owner's measure; reads widths.json once)."""
        return line_widths(text, self._widths_table())

    def get_custom_preview_widget(self, main_window: Any) -> Optional[Any]:
        """The budget box of the selected string (plugins/system_3ds/preview_panel.py)."""
        from .preview_panel import SystemPreviewPanel
        return SystemPreviewPanel(main_window, self)

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """The budget as the string's width limit (the editor's guide line); None when the string has none."""
        limit = self.budget(block_idx, string_idx)
        return {"max_width": limit, "warn_width": limit} if limit else None

    def width_problems(self, block_idx: int, string_idx: int, text: str) -> Set[str]:
        """{WIDTH_PROBLEM} when the widest line is wider than the budget (the owner's check_entry), else empty."""
        limit = self.budget(block_idx, string_idx)
        if not limit:
            return set()
        width = self.calculate_string_width_override(text, {})
        self._details[(block_idx, string_idx)] = f"{width} px, budget {limit} px"
        return {WIDTH_PROBLEM} if width > limit else set()

    def get_problem_detail(self, block_idx: int, string_idx: int, problem_id: str) -> str:
        return self._details.get((block_idx, string_idx), "") if problem_id == WIDTH_PROBLEM else ""
