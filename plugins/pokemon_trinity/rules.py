"""Pokémon Scarlet/Violet (+ The Teal Mask, The Indigo Disk) and Pokémon Legends: Z-A (+ Mega Dimension) (Switch).

Both run on Game Freak's Trinity engine. The workspace's ``1_unpack.bat`` (``_shared/scripts/zt/trinity.py``)
takes from the game's packs (``arc/data.trpfs``) into the source folder, at the game's paths:
the English text ``message/dat/English/{common,script}/*.dat`` (Legends: Z-A: ``ik_message/dat/English/...``),
one project block per file (``gfmsg``: every menu, name, Pokédex entry, battle and story line, DLC included);
the fonts (``.bfotf`` Switch OpenType, ``.bffnt``); the English layout archives (``*_eng.arc``: SARC with BFLYT and
the BNTX text pictures: title logo, menus). ``2_build.bat`` writes changed files into a LayeredFS mod and a
``data.trpfd`` that no longer points the game to the packed originals.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

from core.i18n import tr
from plugins.base_game_rules import BaseGameRules
from plugins.common import gfmsg, message_block
from plugins.common.tag_manager import GenericTagManager

from . import build, unpack
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS


class TagManager(GenericTagManager):
    """Variables and grammar branches as ``{PAGE}``, ``{VAR 0102 0000}``, ``{GENDER 00FF|he|she}``."""

    def get_legitimate_tags(self) -> Set[str]:
        return {gfmsg.TAG_RE.pattern}

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        return isinstance(tag_to_check, str) and gfmsg.TAG_RE.fullmatch(tag_to_check) is not None


class GameRules(BaseGameRules):
    """Pokémon Scarlet/Violet, Pokémon Legends: Z-A (Nintendo Switch)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._loaded: Optional[bytes] = None      # the last message file loaded
        self._base: Optional[bytes] = None        # the message file a save writes over (line flags)
        self._located: Dict[int, Optional[Tuple[str, List[int], List[str]]]] = {}   # block -> its message file

    def get_display_name(self) -> str:
        return "Pokémon Scarlet/Violet, Legends: Z-A (Switch)"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".dat",), "bytes", "Game Freak messages (gfmsg)")]

    # -- wizard: unpack --------------------------------------------------------

    def get_source_roles(self) -> List[Dict[str, str]]:
        return [{"id": "base", "label": tr("Base game")}, {"id": "update", "label": tr("Update")},
                {"id": "other_base", "label": tr("Other version: base game")},
                {"id": "other_update", "label": tr("Other version: update")}]

    def identify_source(self, path: str) -> Optional[Dict[str, Any]]:
        return unpack.identify(path)

    def unpack_key_consoles(self) -> List[str]:
        return ["switch", "oodle"]

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        return unpack.unpack(sources, target_dir, progress, is_cancelled)

    def get_source_subfolder(self) -> Optional[str]:
        return unpack.SOURCE_DIR

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": "switch_layeredfs", "label": tr("Switch: Atmosphere LayeredFS mod (the game of the image)"),
                 "platforms": ["switch"], "kind": "layeredfs"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != "switch_layeredfs":
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        return build.build_switch(source_dir, translation_dir, output_dir, progress, is_cancelled)

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        if not gfmsg.is_gfmsg(raw):
            return [[]], {}
        self._loaded = raw
        return [[gfmsg.to_editor(units) for units, _flags in gfmsg.read(raw)]], {}

    def prepare_save_context(self, context) -> None:
        """The file is written over its newest existing version (the translation, else the source)."""
        self._base = next((raw for raw in context.existing_versions() if gfmsg.is_gfmsg(raw)), None)

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        base = self._base if self._base is not None else self._loaded
        if base is None:
            return super().save_data_to_json_obj(data, block_names)
        old = gfmsg.read(base)
        texts = [text for block in data for text in block]
        if len(texts) != len(old):
            raise ValueError(f"the message file has {len(old)} lines, the project {len(texts)}")
        return gfmsg.write([(gfmsg.from_editor(str(text)), flags) for text, (_units, flags) in zip(texts, old)])

    def reset_runtime_state(self) -> None:
        self._loaded, self._base = None, None
        self._located.clear()

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """The line's label (from the ``.tbl`` beside its file), its index and flags."""
        if block_idx not in self._located:
            self._located[block_idx] = message_block.locate(self.mw, block_idx, PLUGIN_PREFIX)
        located = self._located[block_idx]
        if not located:
            return None
        rel, line_flags, labels = located
        try:
            index = int(string_idx)
            flags = line_flags[index]
        except (IndexError, TypeError, ValueError):
            return None
        attributes: Dict[str, Any] = {"file": rel, "line": index, "flags": flags}
        if index < len(labels):
            attributes["label"] = labels[index]
        return attributes

    def get_tag_tooltip(self, tag: str) -> str:
        return gfmsg.describe(str(tag))

    def get_custom_preview_widget(self, main_window: Any) -> Optional[Any]:
        """The message box drawn from the game's own layout (plugins/common/switch_message_preview.py).

        Scarlet / Violet: the sub-window box. Legends: Z-A: the field dialogue box (msg_body_00.arc, written by the wizard).
        Only the box whose archive the unpacked game has is shown.
        """
        from plugins.common.switch_message_preview import (SCARLET_VIOLET_SUB_BOX, ZA_FIELD_BOX, SwitchMessagePreview,
                                                           sibling_layout_exists)
        project_dir = getattr(getattr(main_window, "project_manager", None), "project_dir", None)
        if not project_dir:
            return None
        for spec in (SCARLET_VIOLET_SUB_BOX, ZA_FIELD_BOX):
            if sibling_layout_exists(str(project_dir), spec):
                return SwitchMessagePreview(main_window, spec)
        return None

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
