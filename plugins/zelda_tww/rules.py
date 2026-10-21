"""The Wind Waker (GameCube) plugin: zel_00.bmg in res/Msg/bmgres.arc, the Hylian lines (zel_01.bmg in
bmgresh.arc), the disc-error messages inside sys/main.dol (``dol``) and the disc banner (``plugins/common/gc_banner``).

Wind Waker and Twilight Princess share the JSystem BMG format, so this class reuses
the Twilight Princess rules for reading, saving, aliases, preview and checks, and
replaces only what is game data: the escape-tag catalogue, the color table, the
INF1 attributes and the per-window line width.  Sources: zeldaret/tww
(``include/f_op/f_op_msg_mng.h``, ``src/f_op/f_op_msg_mng.cpp``, ``src/d/d_msg.cpp``).
"""
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.containers import ContainerManager
from core.i18n import tr
from core.project_library import images
from plugins.common import gc_banner as banner
from plugins.common.msbt import MAGIC as MSBT_MAGIC, Msbt
from plugins.zelda_ww.tags import TAG_RE as HD_TAG_RE, from_editor, to_editor
from plugins.zelda_bmg.rules import GameRules as TwilightPrincessRules

from . import disc
from .dol import DolResources
from .tag_catalog import COLOR_NAMES, COLOR_TABLE, WW_CATALOG

plugin_dir = os.path.dirname(os.path.abspath(__file__))

DISC_TARGET = "iso"
BLUEWAKE_TARGET = "bluewake"
DISC_NAME = "The Wind Waker (UA).iso"
BLUEWAKE_NAME = "GZLE01.iso"
# main.dol of GZLE01 USA revision 0. BlueWake checks its SHA-1 before it reads the disc (disc_import.c).
BLUEWAKE_DOL_SHA1 = "8d28bab68bb5078c38e43f29206f0bd01f7e7a67"

# INF1 textbox type (byte 0x0C of the entry) -> what the player sees (d_msg.cpp, d_message.cpp).
TEXTBOX_TYPES = {
    0: "Talk", 1: "Item-style notice", 2: "Sign", 5: "Prologue caption",
    6: "Board or tablet", 7: "Letter", 8: "Talk (closes by itself)", 9: "Item get",
    10: "Talk (fixed position)", 11: "Item name", 12: "Hylian text",
    13: "Picto Box notice", 14: "Wind Waker conducting",
}

# Boxes whose every source line is one output line (names, Hylian glyph text, conducting cues).
LINE_KINDS = frozenset({11, 12, 14})

# Widths in font units (cell 24; the game draws the font at 23 px, so units = px x 24/23).
# The game wraps mid-word once a line reaches 503 px (419 px in an item-get box with its
# icon), so the longest allowed line is one pixel less.  The warning sits at the centring
# width, 486 / 402 px, which English text keeps to with few exceptions.
TALK_WIDTH = 523
TALK_WARN_WIDTH = 507
ITEM_GET_WIDTH = 436
ITEM_GET_WARN_WIDTH = 419
_ITEM_GET = 9


def decode_ww_attributes(info: bytes) -> Optional[Dict[str, int]]:
    """The 20 INF1 bytes after the DAT1 offset (JMSMesgEntry_c), or None if too short."""
    if len(info) < 20:
        return None
    return {
        "message_id": int.from_bytes(info[0:2], "big"),
        "item_price": int.from_bytes(info[2:4], "big", signed=True),
        "next_message_id": int.from_bytes(info[4:6], "big"),
        "textbox_type": info[8],
        "draw_type": info[9],
        "textbox_position": info[10],
        "item_image": info[11],
        "alignment": info[12],
        "initial_sound": info[13],
        "initial_camera": info[14],
        "initial_animation": info[15],
        "lines_per_page": info[18],
    }


def _require_bluewake_dol(path: Path) -> None:
    """BlueWake refuses any other main.dol, so a BlueWake disc is not built from one."""
    digest = hashlib.sha1()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    if digest.hexdigest() != BLUEWAKE_DOL_SHA1:
        raise ValueError(tr("The source main.dol is not USA revision 0 (GZLE01), so BlueWake would refuse the disc."))


class GameRules(TwilightPrincessRules):
    """Zelda: The Wind Waker (GameCube)."""

    escape_catalog = WW_CATALOG
    color_table = COLOR_TABLE
    color_names = {name: index for index, name in COLOR_NAMES.items()} | {"default": 0, "gray": 7}
    data_dir = plugin_dir

    # Kind sets the inherited speaker/glossary code reads, in Wind Waker textbox types.
    _NAME_CARD_KINDS = {11: "Items"}
    _ITEM_WINDOW_KIND = _ITEM_GET
    _NON_CONVERSATIONAL_KINDS = {1, 2, 5, 6, 7, 9, 11, 13, 14}
    _SYSTEM_VOICE_KINDS = {2, 6, 9, 11, 13, 14}
    _WINDOW_SPEAKERS: Dict[int, str] = {}

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._banner: Optional[bytes] = None          # the banner file being saved (None: a BMG)
        self._banner_loaded: Optional[bytes] = None
        self._msbt: Optional[Msbt] = None             # an HD MSBT file loaded for a family project (None: a BMG)
        self._msbt_save: Optional[Msbt] = None        # the MSBT the save in progress writes over
        ContainerManager.register(DolResources, (".dol",))   # disc-error messages and font in main.dol

    # Project Manager: the GameCube disc (USA) is extracted whole into sys\ and files\, as zt/gc.py does.
    def get_platforms(self) -> list:
        return [{"id": "gc", "label": tr("GameCube")}, {"id": "bluewake", "label": tr("BlueWake (PC port)")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        return images.base_identity(path, ("GZLE01",))

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        base = sources.get("base")
        return images.extract(base, target_dir, progress, is_cancelled) if base else None

    def get_source_subfolder(self) -> Optional[str]:
        """The whole disc is the source (the Twilight Princess base class names a subfolder)."""
        return None

    def unpack_key_consoles(self) -> List[str]:
        return []   # a GameCube disc only; the Twilight Princess base class reads the Wii key

    def get_build_targets(self) -> List[Dict[str, Any]]:
        """The Dolphin disc (translated main.dol) and the BlueWake disc (original main.dol: BlueWake checks its SHA-1).

        BlueWake run (3_run_bluewake.bat): from the BlueWake folder (pushd), ``BlueWake.exe --disc <GZLE01.iso>``. Set the
        BlueWake platform command to ``"<BlueWake folder>\\BlueWake.exe" --disc {path}``; Run starts it in that folder.
        """
        return [{"id": DISC_TARGET, "label": tr("Disc image (ISO)"), "platforms": ["gc"], "kind": "patch"},
                {"id": BLUEWAKE_TARGET, "label": tr("BlueWake disc (original main.dol)"),
                 "platforms": ["bluewake"], "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id not in (DISC_TARGET, BLUEWAKE_TARGET):
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        if target_id == BLUEWAKE_TARGET:
            _require_bluewake_dol(Path(source_dir) / "sys" / "main.dol")
        name = DISC_NAME if target_id == DISC_TARGET else BLUEWAKE_NAME
        out = Path(output_dir) / name
        disc.build_disc(Path(source_dir), Path(translation_dir), out, target_id == DISC_TARGET,
                        progress, is_cancelled)
        return str(out)

    def get_display_name(self) -> str:
        """Get the display name."""
        return "Zelda: The Wind Waker (GameCube BMG)"

    def get_file_formats(self) -> list:
        """Message files and the disc banner; the fonts (.bfn) open in Tools -> Font Editor, not as text."""
        from core.formats import FileFormat
        return [FileFormat((".bnr",), "bytes", "Disc banner"),
                FileFormat((".msbt",), "bytes", "MSBT (Wind Waker HD)"),
                *(item for item in super().get_file_formats() if ".bfn" not in item.extensions)]

    def load_data_from_json_obj(self, json_obj: Any):
        """A BMG, the disc banner's five texts, or an HD MSBT (the family project's HD-only messages)."""
        if isinstance(json_obj, bytes) and banner.is_banner(json_obj):
            self._banner_loaded = json_obj
            return [banner.read(json_obj)], {"0": "Disc banner"}
        if isinstance(json_obj, (bytes, bytearray)) and bytes(json_obj[:8]) == MSBT_MAGIC:
            self._msbt = Msbt(bytes(json_obj))
            return [[to_editor(tokens) for tokens in self._msbt.messages]], {}
        return super().load_data_from_json_obj(json_obj)

    def _load_bmg_cached(self, cache_key, read_bytes):
        """An MSBT block has no BMG behind it: the message-context code reads none."""
        data = read_bytes()
        if bytes(data[:8]) == MSBT_MAGIC:
            return None
        return super()._load_bmg_cached(cache_key, lambda: data)

    def family_plan(self, sources: list, project_dir: Optional[str] = None) -> Any:
        """Wind Waker family: GameCube (base) and HD message folders (see plugins/zelda_ww/family.py)."""
        from plugins.zelda_ww.family import plan_for_sources
        return plan_for_sources(sources, project_dir)

    def prepare_save_context(self, context) -> None:
        """The banner is written over its current file; an MSBT over the one loaded; a BMG as the Twilight Princess rules do it."""
        self._banner = None
        self._msbt_save = None
        name = str(context.relative_path).lower()
        if name.endswith(".bnr"):
            self._banner = next(iter(context.existing_versions()), None) or self._banner_loaded
            return
        if name.endswith(".msbt"):
            self._msbt_save = self._msbt
            return
        super().prepare_save_context(context)

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._banner is not None:
            return banner.write(self._banner, data[0])
        if self._msbt_save is not None:
            return self._save_msbt(self._msbt_save, data[0] if data and isinstance(data[0], list) else [])
        return super().save_data_to_json_obj(data, block_names)

    @staticmethod
    def _save_msbt(msbt: Msbt, texts: list) -> bytes:
        """The MSBT with the edited messages re-encoded in HD tags; unedited messages keep their tokens."""
        new_tokens = []
        for index, tokens in enumerate(msbt.messages):
            current = to_editor(tokens)
            text = texts[index] if index < len(texts) else current
            new_tokens.append(tokens if text == current else from_editor(text))
        return msbt.build(new_tokens)

    def get_syntax_highlighting_rules(self):
        """The GameCube curly tags, plus the HD tags and icon characters of an MSBT block (see prepare/load).

        GameCube text never holds square brackets or the icon characters (U+E000..U+F8FF), so the HD patterns
        cannot match a BMG block; both syntaxes are highlighted in every block.
        """
        rules = super().get_syntax_highlighting_rules()
        manager = getattr(self, "tag_manager", None)
        if manager is None:
            return rules
        return [*rules, (HD_TAG_RE.pattern, manager.tag_format), (r"[-]", manager.tag_format)]

    def check_msbt_text(self, text: str) -> list:
        """Problem checks of one HD (MSBT) block text: unparsed, unknown, unmatched, size, colour and icon issues.

        Called for MSBT blocks only; GameCube text is checked by the curly-tag rules. See plugins/zelda_ww/msbt_checks.py.
        """
        from plugins.zelda_ww.msbt_checks import check_text
        return check_text(text)

    def get_capabilities(self):
        """Lore from the wiki and terms from item windows; no speakers or window chrome yet."""
        return {"glossary_seed", "external_lore", "external_reference"}

    def get_dynamic_name_tags(self) -> dict:
        """The player name is the only name the game inserts at runtime."""
        return {"{PLAYER}": "Link", "{escape:0:0000}": "Link"}

    def replace_runtime_names_for_ai(self, text: str) -> str:
        """Show the language model Link instead of the player-name escape."""
        result = str(text or "")
        for tag in ("{PLAYER}", "{F:Link}", "{f:Link}", "{escape:0:0000}"):
            result = result.replace(tag, "Link")
        return result

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, int]]:
        """Decoded INF1 attributes, with the textbox type also under the key the
        inherited kind-based code reads (``fuki_kind``)."""
        try:
            string_idx = int(string_idx)
        except (TypeError, ValueError):
            return None
        bmg, _, _ = self._get_bmg_for_block(block_idx)
        messages = getattr(bmg, "messages", None) or []
        if not (0 <= string_idx < len(messages)):
            return None
        attrs = decode_ww_attributes(getattr(messages[string_idx], "info", b""))
        if attrs is not None:
            attrs["fuki_kind"] = attrs["textbox_type"]
        return attrs

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        """Tell the translator which kind of box the text sits in."""
        attrs = self.get_message_attributes(block_idx, string_idx)
        if not attrs:
            return {}
        kind = attrs["textbox_type"]
        context = {"window_type": TEXTBOX_TYPES.get(kind, f"Textbox type {kind}")}
        if kind in LINE_KINDS:
            context["layout_class"] = "lines"
        return context

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Line width and lines per page from the message's own INF1 entry."""
        attrs = self.get_message_attributes(block_idx, string_idx)
        if not attrs:
            return None
        item_get = attrs["textbox_type"] == _ITEM_GET
        layout: Dict[str, Any] = {
            "max_width": ITEM_GET_WIDTH if item_get else TALK_WIDTH,
            "warn_width": ITEM_GET_WARN_WIDTH if item_get else TALK_WARN_WIDTH,
        }
        if attrs["lines_per_page"]:
            layout["lines_per_page"] = attrs["lines_per_page"]
        return layout

    def get_preview_window_style(self, block_idx: Optional[int] = None,
                                 string_idx: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Box name and lines per page only: no geometry, so the generic preview
        draws the text (Wind Waker window frames are not drawn yet)."""
        attrs = self.get_message_attributes(block_idx, string_idx) if block_idx is not None else None
        if not attrs:
            return None
        kind = attrs["textbox_type"]
        style: Dict[str, Any] = {"kind_name": TEXTBOX_TYPES.get(kind, f"Textbox type {kind}")}
        if attrs["lines_per_page"]:
            style["lines_per_page"] = attrs["lines_per_page"]
        return style
