"""Final Fantasy Tactics Advance (GBA, USA ``AFXE``): the text, the font and the translated ROM.

The wizard unpacks the ROM (``unpack_sources``) into ``rom/`` (a copy the build starts from), ``text/*.fftatext``
(``rom_text.extract``: every string as its ROM bytes, one block per table) and ``fonts/font.bin`` (the 16x16 font
and its width table, the ``cells`` font format). The editor shows a string through ``codec``; an unedited string
keeps its bytes. The build target ``gba_rom`` writes the ROM with the edited strings and font (``rom_text.build``).
Ukrainian letters have kana codes (``codec.UA_CODES``); a character with no code is refused by name.
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.i18n import tr
from plugins.base_game_rules import BaseGameRules
from utils.atomic_io import atomic_write_bytes
from utils.logging_utils import log_warning
from utils.utils import clean_spaces

from . import codec, rom_text
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

FONT_FILE = "ffta_text.json"
FONT_PATH = "fonts/font.bin"
TEXT_DIR, ROM_DIR = "text", "rom"
OUTPUT_NAME = "Final Fantasy Tactics Advance (UA).gba"
TARGET_ID = "gba_rom"


def font_descriptors() -> List[Dict[str, Any]]:
    """The game's one font: 3175 cells, code ``8000 + cell``."""
    chars = "".join(codec.CHARS.get(0x8000 + cell, "\0") for cell in range(rom_text.FONT_GLYPHS))
    return [{"label": "Text font 16x16", "format": "cells", "path": FONT_PATH, "font_map": FONT_FILE,
             "params": {"offset": 0, "count": rom_text.FONT_GLYPHS, "cell": [16, 16], "bpp": 4, "tiles": "columns",
                        "columns": 16, "widths": rom_text.FONT_GLYPHS * 128, "chars": chars}}]


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(str(path), data)


def _text_of(kind: str, raw: bytes) -> str:
    return rom_text.tbl_text(raw) if kind == "offsets" else rom_text.abs_text(raw)


class GameRules(BaseGameRules):
    """Final Fantasy Tactics Advance (Game Boy Advance, USA)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._bank: Optional[Dict[str, Any]] = None

    def get_display_name(self) -> str:
        return "Final Fantasy Tactics Advance (GBA)"

    def get_capabilities(self) -> Set[str]:
        return set()

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".fftatext",), "json", "Final Fantasy Tactics Advance text (text/*.fftatext)"),
                *DEFAULT_FORMATS]

    def get_font_sources(self) -> List[Dict[str, Any]]:
        return font_descriptors()

    # -- Project Manager ---------------------------------------------------------------------------------

    def get_platforms(self) -> list:
        return [{"id": "gba", "label": tr("Game Boy Advance")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        try:
            with open(path, "rb") as stream:
                head = stream.read(0xC0)
        except OSError:
            return None
        return {"role": "base", "platform": "gba"} if head[0xAC:0xB0] == rom_text.GAME_CODE else None

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        base = sources.get("base")
        if not base:
            return None
        data = Path(base).read_bytes()
        if not rom_text.is_ffta(data):
            raise ValueError(tr("{0} is not Final Fantasy Tactics Advance (USA, AFXE).", base))
        root = Path(target_dir)
        progress(10, tr("Reading the text..."))
        banks = rom_text.extract(data)
        if is_cancelled():
            return None
        _write(root / ROM_DIR / Path(base).name, data)
        for key, bank in banks.items():
            _write(root / TEXT_DIR / f"{key}.fftatext",
                   json.dumps(bank, ensure_ascii=False, indent=1).encode("utf-8"))
        _write(root / FONT_PATH, data[rom_text.FONT_START:rom_text.FONT_END])
        progress(100, "")
        return str(root)

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": TARGET_ID, "label": tr("Translated GBA ROM"), "platforms": ["gba"], "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != TARGET_ID:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        source, translation = Path(source_dir), Path(translation_dir)
        roms = sorted((source / ROM_DIR).glob("*.gba"))
        if not roms:
            raise ValueError(tr("The unpacked folder has no ROM in {0}.", str(source / ROM_DIR)))
        banks = []
        for path in sorted((source / TEXT_DIR).glob("*.fftatext")):
            edited = translation / TEXT_DIR / path.name
            banks.append(json.loads((edited if edited.is_file() else path).read_text(encoding="utf-8")))
        font = translation / FONT_PATH
        progress(20, tr("Writing the ROM..."))
        try:
            data = rom_text.build(roms[0].read_bytes(), banks, font.read_bytes() if font.is_file() else None)
        except rom_text.BuildError as error:
            raise ValueError(str(error)) from None
        out = Path(output_dir) / OUTPUT_NAME
        atomic_write_bytes(str(out), data)
        progress(100, "")
        return str(out)

    # -- load and save -----------------------------------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not (isinstance(json_obj, dict) and json_obj.get("format") == rom_text.TEXT_FORMAT):
            self._bank = None
            return self._load_plain(json_obj)
        self._bank = json_obj
        blocks, names = [], {}
        for n, block in enumerate(json_obj.get("blocks") or []):
            blocks.append([_text_of(block.get("kind", ""), bytes.fromhex(s["raw"])) for s in block.get("strings") or []])
            names[str(n)] = block.get("name") or block.get("id") or f"Block {n + 1}"
        return blocks, names

    @staticmethod
    def _load_plain(json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        """A list of string lists (samples and tests) or plain text split by blank lines."""
        if isinstance(json_obj, list) and all(isinstance(block, list) for block in json_obj):
            blocks = json_obj
        elif isinstance(json_obj, str):
            blocks = [[line for line in raw.splitlines() if line.strip()] for raw in re.split(r"\n\s*\n", json_obj.strip())]
            blocks = [block for block in blocks if block] or [[]]
        else:
            blocks = [[]]
        return blocks, {str(i): f"Block {i + 1}" for i in range(len(blocks))}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._bank is None:
            return data
        blocks, data = [], list(data or [])
        for n, block in enumerate(self._bank.get("blocks") or []):
            texts = data[n] if n < len(data) else None
            kind, strings = block.get("kind", ""), []
            for k, string in enumerate(block.get("strings") or []):
                raw = bytes.fromhex(string["raw"])
                text = texts[k] if texts and k < len(texts) else None
                if text is not None and text != _text_of(kind, raw):    # an untouched text keeps its exact bytes
                    try:
                        raw = rom_text.tbl_encode(text, raw) if kind == "offsets" else rom_text.abs_encode(text, raw)
                    except codec.EncodeError as error:
                        raise ValueError(tr("String {0}: {1}", string["id"], str(error))) from None
                strings.append({**string, "raw": raw.hex()})
            blocks.append({**block, "strings": strings})
        return {**self._bank, "blocks": blocks}

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): load the newest that parses."""
        for raw in context.existing_versions():
            try:
                bank = json.loads(bytes(raw).decode("utf-8-sig"))
            except ValueError as error:
                log_warning(f"ffta_gba: cannot read {context.relative_path}: {error}; trying the next version")
                continue
            if isinstance(bank, dict) and bank.get("format") == rom_text.TEXT_FORMAT:
                self._bank = bank
                return

    def reset_runtime_state(self) -> None:
        self._bank = None

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        try:
            return {"id": self._bank["blocks"][int(block_idx)]["strings"][int(string_idx)]["id"]}
        except (TypeError, KeyError, IndexError, ValueError):
            return None

    # -- editor ------------------------------------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        return {"font_file": FONT_FILE}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        return codec.line_width(text, font_map or {}, default_char_width)

    def get_tag_tooltip(self, tag: str) -> str:
        return codec.describe(str(tag))

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
