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

from core.containers import ContainerManager
from core.containers.nitro import NarcContainer
from core.i18n import tr
from core.project_library import images
from plugins.base_game_rules import BaseGameRules
from plugins.common import gen4msg, nds_build
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import ds_text, unpack
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

LINES_PER_BOX = 2
BUILD_TARGET = "nds_rom"
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


def _narc_members(data: bytes) -> List[bytes]:
    """The members of a NARC (``[]`` for other files and for NARCs above the picture cap)."""
    if data[:4] != b"NARC" or len(data) > _TEXTURE_NARC_MAX:
        return []
    btaf, gmif = data.find(b"BTAF"), data.find(b"GMIF")
    if btaf < 0 or gmif < 0:
        return []
    count = struct.unpack_from("<I", data, btaf + 8)[0]
    body = gmif + 8
    members = []
    for n in range(count):
        start, end = struct.unpack_from("<II", data, btaf + 12 + 8 * n)
        members.append(bytes(data[body + start:body + end]))
    return members


def _lz10_ncgr(member: bytes) -> bool:
    """A Gen 4 LZ10 member whose stream is an NCGR picture (``RGCN``)."""
    from core.containers import lz10
    if member[:1] != b"\x10":
        return False
    try:
        return lz10.decompress(member)[0][:4] == b"RGCN"
    except ValueError:
        return False


def _glyph_map(charmap_path: str) -> Dict[str, int]:
    """{character: glyph index} of a charmap: a single-character entry of text code c is glyph c - 1."""
    chars, _commands = gen4msg.load_charmap(charmap_path)
    glyphs: Dict[str, int] = {}
    for code, text in sorted(chars.items()):
        if len(text) == 1 and text.strip() and code >= 1:
            glyphs.setdefault(text, code - 1)
    return glyphs


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
        ContainerManager.register(NarcContainer)     # the font and picture NARCs (Font Editor, Textures)
        self._loaded: Optional[str] = None
        self._source: Optional[str] = None
        self._msg_file: Optional[bytes] = None          # the ROM bank a save writes over (raw lines, codec)
        self._bank: Optional[gen4msg.Bank] = None
        self._codec: Optional[gen4msg.Codec] = None

    # Project Manager: the cartridge (USA) is read by core/project_library/images.py; unpack.py picks the files.
    def get_platforms(self) -> list:
        return [{"id": "nds", "label": tr("Nintendo DS")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        return images.base_identity(path, ("ADAE", "APAE", "CPUE", "IPKE", "IPGE"))

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        base = sources.get("base")
        if not base:
            return None
        nds_build.store_base_rom(base, Path(target_dir))
        return unpack.extract(base, target_dir, progress, is_cancelled)

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": BUILD_TARGET, "label": tr("Translated DS ROM"), "platforms": ["nds"], "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != BUILD_TARGET:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        try:
            built = nds_build.build_text_rom(
                source_dir, translation_dir, narc_of_folder=lambda folder: folder.replace("+", "/"),
                is_text=gen4msg_is_bank, progress=progress, is_cancelled=is_cancelled)
        except nds_build.NdsBuildError as error:
            raise ValueError(str(error)) from None
        out = Path(output_dir) / f"{built[0x0C:0x10].decode('ascii', 'replace')}_UA.nds"
        nds_build.write_rom(out, built)
        return str(out)

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

    def _narc_files(self):
        """``(relative path, members)`` of each NARC of the unpacked ``source`` (text banks are skipped)."""
        root = ""
        try:
            root = str(self.mw.project_manager.project.metadata.get("source_path") or "")
        except AttributeError:
            pass
        if not root or not os.path.isdir(root):
            return
        for path in sorted(Path(root).rglob("*")):
            rel = path.relative_to(root).as_posix()
            if not path.is_file() or rel.startswith(("text/", "files/")):
                continue
            try:
                members = _narc_members(path.read_bytes())
            except (OSError, ValueError, struct.error) as error:
                log_debug(f"{_PLUGIN}: cannot read {rel}: {error}")
                continue
            if members:
                yield rel, members

    def get_font_sources(self) -> List[Dict[str, Any]]:
        """The Gen 4 font bins (``core.font_formats.gen4_glyphs``): the members of each font NARC, with the
        glyph map of the game's charmap (glyph index = text code - 1), so the Font Editor shows letters."""
        from core.font_formats import gen4_glyphs
        glyphs = _glyph_map(self._game_charmap())
        sources: List[Dict[str, Any]] = []
        for rel, members in self._narc_files():
            numbers = [n for n, m in enumerate(members) if gen4_glyphs.is_font_bin(m)]
            if numbers:
                sources.append({"label": rel, "kind": "font", "format": "gen4_glyphs", "path": rel,
                                "member": "#{" + ",".join(str(n) for n in numbers) + "}",
                                "params": {"chars": glyphs}})
        return sources

    def _game_charmap(self) -> str:
        """The charmap of the game of the unpacked tree: Platinum has pl_msg banks, HeartGold / SoulSilver a+0+2+7,
        Diamond / Pearl neither."""
        try:
            root = Path(str(self.mw.project_manager.project.metadata.get("source_path") or ""))
        except AttributeError:
            root = Path("")
        if (root / "text" / "msgdata+pl_msg.narc").is_dir():
            return str(_CHARMAPS / "charmap_platinum.txt")
        return str(_CHARMAPS / "charmap_dp_hgss.txt")

    def get_texture_sources(self) -> List[Dict[str, Any]]:
        """The NCGR pictures of the NARCs, one source per kind per NARC: the raw members, and the LZ10 members with
        ``compression: lz10`` (decompressed for reading; written back compressed again, as a valid LZ10 stream)."""
        sources: List[Dict[str, Any]] = []
        for rel, members in self._narc_files():
            raw = [n for n, m in enumerate(members) if m[:4] == b"RGCN"]
            packed = [n for n, m in enumerate(members) if _lz10_ncgr(m)]
            if raw:
                sources.append({"label": rel, "kind": "ui", "format": "tiles", "path": rel,
                                "member": "#{" + ",".join(str(n) for n in raw) + "}"})
            if packed:
                sources.append({"label": f"{rel} (LZ10)", "kind": "ui", "format": "tiles", "path": rel,
                                "member": "#{" + ",".join(str(n) for n in packed) + "}",
                                "params": {"compression": "lz10"}})
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

    def _source_root(self) -> Optional[str]:
        """The unpacked source folder of the project (None before a project is open)."""
        try:
            root = str(self.mw.project_manager.project.metadata.get("source_path") or "")
        except AttributeError:
            return None
        return root if root and os.path.isdir(root) else None

    def _window_facts(self) -> Optional[Tuple[str, Tuple[str, int]]]:
        """(source folder, font location) for the games whose message window is known (Platinum)."""
        from . import message_preview
        root = self._source_root()
        code = message_preview.game_code(root) if root else None
        facts = message_preview.facts_for(code) if code else None
        return (root, facts) if facts else None

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """The message box of the game: its width and lines (pret facts, see ``message_preview``)."""
        if self._window_facts() is None:
            return None
        from . import message_preview
        return {"max_width": message_preview.BOX_PX, "warn_width": message_preview.BOX_PX,
                "lines_per_page": message_preview.LINES_PER_PAGE}

    def get_custom_preview_widget(self, main_window: Any) -> Optional[Any]:
        """The game's message box drawn with the game's own font; None (the BFN preview) without the facts."""
        from . import message_preview
        found = self._window_facts()
        if found is None:
            return None
        root, (narc, member) = found
        font = message_preview.load_font(root, narc, member)
        if font is None:
            return None
        return message_preview.MessageWindowPreview(font, gen4msg.Codec(self._game_charmap()))

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
