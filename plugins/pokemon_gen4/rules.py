"""Pokémon Diamond / Pearl, Platinum, HeartGold / SoulSilver (Nintendo DS), two modes.

ROM mode (``.msg``, made by ``zt\\pkgen4.py`` from the clean USA ROM): one project block is one message bank of the
ROM. ``plugins/common/gen4msg`` decodes its lines with the charmap of the game (``charmaps/``); a save writes the
bank back, and unchanged lines keep their raw units.

pret mode (``.gmm`` / ``.json``): the English messages of the decompilations pokediamond, pokeplatinum and
pokeheartgold. ``ds_text`` finds them and writes them back in place. A save is always built from the source file.
"""
import os
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common import gen4msg
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import ds_text
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

LINES_PER_BOX = 2
_PLUGIN = "pokemon_gen4"
_CHARMAPS = Path(__file__).resolve().parent / "charmaps"
_CODECS: List[gen4msg.Codec] = []


def _codecs() -> List[gen4msg.Codec]:
    """The charmaps the ROM banks may use: Diamond / Pearl / HeartGold / SoulSilver first, Platinum second."""
    if not _CODECS:
        _CODECS.append(gen4msg.Codec(str(_CHARMAPS / "charmap_dp_hgss.txt")))
        _CODECS.append(gen4msg.Codec(str(_CHARMAPS / "charmap_platinum.txt")))
    return _CODECS


_TEXTURE_NARC_MAX = 6_500_000        # the same cap as Gen 5: the sprite packs are bigger


def _ncgr_members(data: bytes) -> List[int]:
    """Indices of the members of a NARC that are uncompressed NCGR pictures (``RGCN``); [] for other files."""
    if data[:4] != b"NARC" or len(data) > _TEXTURE_NARC_MAX:
        return []
    btaf = data.find(b"BTAF")
    gmif = data.find(b"GMIF")
    if btaf < 0 or gmif < 0:
        return []
    count = struct.unpack_from("<I", data, btaf + 8)[0]
    body = gmif + 8
    numbers = []
    for n in range(count):
        start, end = struct.unpack_from("<II", data, btaf + 12 + 8 * n)
        if data[body + start:body + start + 4] == b"RGCN":
            numbers.append(n)
    return numbers


def gen4msg_is_bank(data: bytes) -> bool:
    try:
        gen4msg.decode_bank(data)
    except (gen4msg.BankError, ValueError):
        return False
    return True


class GameRules(BaseGameRules):
    """Pokémon generation IV, pret decompilation text."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._loaded: Optional[str] = None
        self._source: Optional[str] = None
        self._msg_file: Optional[bytes] = None          # the ROM bank a save writes over (raw lines, codec)
        self._bank: Optional[gen4msg.Bank] = None
        self._codec: Optional[gen4msg.Codec] = None

    def get_display_name(self) -> str:
        return "Pokémon Diamond, Pearl, Platinum, HeartGold and SoulSilver (DS)"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".msg",), "bytes", "Pokémon generation IV message banks (from the ROM)"),
                FileFormat((".gmm", ".json"), "text", "Pokémon (pret) message files")]

    # -- loading and saving ---------------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if isinstance(json_obj, (bytes, bytearray)) and gen4msg_is_bank(bytes(json_obj)):
            raw = bytes(json_obj)
            try:
                self._codec, self._bank = gen4msg.open_bank(raw, _codecs())
            except gen4msg.BankError as error:
                log_debug(f"{_PLUGIN}: no charmap reads this bank: {error}")
                self._msg_file = None
                return [[]], {}
            self._msg_file = raw
            return [gen4msg.decode_all(self._bank, self._codec)], {"0": "Text"}
        if isinstance(json_obj, (bytes, bytearray)):
            json_obj = bytes(json_obj).decode("utf-8")
        if not isinstance(json_obj, str):
            return super().load_data_from_json_obj(json_obj)
        self._loaded = json_obj
        return [ds_text.load(json_obj)], {"0": "Text"}

    def prepare_save_context(self, context: Any) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        raw_banks = [bytes(v) for v in versions if isinstance(v, (bytes, bytearray)) and gen4msg_is_bank(bytes(v))]
        if raw_banks:
            try:
                self._codec, self._bank = gen4msg.open_bank(raw_banks[-1], _codecs())
                self._msg_file = raw_banks[-1]
            except gen4msg.BankError as error:
                log_debug(f"{_PLUGIN}: newest bank unreadable: {error}")
            return
        self._source = versions[-1].decode("utf-8") if versions else None

    def save_data_to_json_obj(self, data: list, block_names: Optional[dict] = None) -> Any:
        texts = [str(text) for text in (data[0] if data else [])]
        if self._msg_file is not None and self._bank is not None:
            if len(texts) != len(self._bank.lines):
                raise ValueError(f"{len(texts)} lines for a bank of {len(self._bank.lines)}")
            if texts == gen4msg.decode_all(self._bank, self._codec):
                return self._msg_file
            return gen4msg.encode_bank(gen4msg.encode_all(texts, self._codec, base=self._bank))
        source = self._source if self._source is not None else self._loaded
        if source is None:
            return "\n".join(texts)
        return ds_text.write(source, texts)

    def reset_runtime_state(self) -> None:
        self._loaded = None
        self._source = None
        self._msg_file = None
        self._bank = None
        self._codec = None

    # -- pictures (ROM mode) ---------------------------------------------------------------------

    def get_texture_sources(self) -> List[Dict[str, Any]]:
        """Each NARC of the unpacked ``source`` with uncompressed NCGR members (LZ10 members are not listed)."""
        root = ""
        try:
            root = str(self.mw.project_manager.project.metadata.get("source_path") or "")
        except AttributeError:
            pass
        if not root or not os.path.isdir(root):
            return []
        sources: List[Dict[str, Any]] = []
        for path in sorted(Path(root).rglob("*")):
            rel = path.relative_to(root).as_posix()
            if not path.is_file() or rel.startswith(("text/", "files/")):
                continue
            try:
                numbers = _ncgr_members(path.read_bytes())
            except (OSError, ValueError, struct.error) as error:
                log_debug(f"{_PLUGIN}: cannot read {rel}: {error}")
                continue
            if numbers:
                sources.append({"label": rel, "kind": "ui", "format": "tiles", "path": rel,
                                "member": "#{" + ",".join(str(n) for n in numbers) + "}"})
        return sources

    # -- context -----------------------------------------------------------------------------

    def _block_path(self, block_idx: int) -> str:
        try:
            pm = getattr(self.mw, "project_manager", None)
            block_map = getattr(self.mw, "block_to_project_file_map", {}) or {}
            index = block_map.get(block_idx, block_idx)
            return str(pm.project.blocks[index].source_file).replace("\\", "/")
        except (AttributeError, IndexError, KeyError, TypeError) as error:
            log_debug(f"pokemon_gen4: no file for block {block_idx}: {error}")
            return ""

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        rel = self._block_path(block_idx)
        return {"resource": rel, "label": os.path.splitext(os.path.basename(rel))[0]} if rel else {}

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        rel = self._block_path(block_idx)
        return f"File {rel}" if rel else None

    # -- editing -----------------------------------------------------------------------------

    def get_editor_page_size(self) -> int:
        return LINES_PER_BOX

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_capabilities(self) -> Set[str]:
        return set()
