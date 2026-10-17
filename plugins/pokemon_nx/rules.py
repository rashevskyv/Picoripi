"""Pokémon Sword/Shield and Legends: Arceus (Switch) plugin: Game Freak ``.dat`` message tables, one block per file."""
import json
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.i18n import tr
from plugins.base_game_rules import BaseGameRules
from plugins.common import gfmsg, message_block, name_seeds
from plugins.common.name_seeds import TABLE_ROLES
from plugins.common.block_loader import ReadThrough, rescan_block
from utils.constants import user_plugin_file_or_shipped
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import build, unpack
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager
from plugins.common.gfmsg import SERIES_TAG_MAP

_PLUGIN = "pokemon_nx"
# script file prefix -> part of the story
_STORY = (("rigel1", "The Isle of Armor (DLC)"), ("rigel2", "The Crown Tundra (DLC)"),
          ("main_event", "Main story"), ("sub_event", "Side story"), ("demo", "Cutscene"))


def _stem(rel: str) -> str:
    return Path(str(rel).replace("\\", "/")).stem


class GameRules(BaseGameRules):
    """Pokémon Sword/Shield (with both DLC) and Pokémon Legends: Arceus.

    A project points at the workspace ``source`` folder made by ``1_unpack.bat``: ``bin/message/English``
    (``common/*.dat`` menus, names and descriptions; ``script/*.dat`` dialogue), the fonts in ``bin/font``
    and the English layout archives (``bin/appli/**/*_eng.arc``, textures with words). Each ``.dat`` is
    one block; the ``.tbl`` next to it names its lines. Saving rebuilds the ``.dat`` (unchanged files stay
    byte-exact); ``2_build.bat`` copies the changed files into a LayeredFS mod.

    The text fonts lack Ґ Є І Ї ґ є і ї: ``translation_map.json`` writes І і Ї ї as the look-alike Latin
    letters and Є є Ґ ґ as Э э Ъ ъ, whose glyphs a person redraws in the Font Editor.
    """

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def get_series_tag_map(self):
        """The control tags of this game, with a kind each, for the series reuse (plugins/common/series_tags.py)."""
        return SERIES_TAG_MAP

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._file: Optional[bytes] = None        # the message file a save writes over (line flags)
        self._located = ReadThrough(f"{_PLUGIN} message", lambda block_idx: rescan_block(self.mw, block_idx))
        self._map_stamp: Optional[tuple] = None
        self.translation_map: Dict[str, str] = {}
        self.reverse_translation_map: Dict[str, str] = {}

    def get_display_name(self) -> str:
        return "Pokémon Sword/Shield + Legends: Arceus (Switch)"

    def get_source_roles(self) -> List[Dict[str, str]]:
        """The base game and its update: the English text is in the update's patched RomFS."""
        return [{"id": "base", "label": tr("Base game")}, {"id": "update", "label": tr("Update")}]

    def identify_source(self, path: str) -> Optional[Dict[str, Any]]:
        """The base game or the update of Sword, Shield or Legends: Arceus, with the library its unpack needs."""
        return unpack.identify(path)

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        """Sword / Shield / Legends: Arceus: the base game with its update applied (``unpack.py``)."""
        return unpack.unpack(sources, target_dir, progress, is_cancelled)

    def unpack_key_consoles(self) -> List[str]:
        return ["switch", "oodle"]

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": "switch", "label": tr("Nintendo Switch")}]

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": "switch_layeredfs", "label": tr("Switch: Atmosphere LayeredFS mod"),
                 "platforms": ["switch"], "kind": "layeredfs"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != "switch_layeredfs":
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        return build.build_switch(source_dir, translation_dir, output_dir, progress, is_cancelled)

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".dat",), "bytes", "Pokémon (Switch) message tables"), *DEFAULT_FORMATS]

    # -- translation map ---------------------------------------------------------

    def load_translation_map(self) -> None:
        """``translation_map.json`` of the project, else the user's or the plugin's: letter -> font slot.
        Look-alike Latin slots are never turned back into Ukrainian letters when the game's text is read."""
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        project_dir = getattr(pm, "project_dir", None)
        path = os.path.join(project_dir, "translation_map.json") if project_dir else ""
        if not path or not os.path.isfile(path):
            path = str(user_plugin_file_or_shipped(_PLUGIN, "translation_map.json"))
        try:
            stamp = (path, os.path.getmtime(path))
        except OSError:
            stamp = (path, 0.0)
        if stamp == self._map_stamp:
            return
        self._map_stamp = stamp
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            log_warning(f"{_PLUGIN}: cannot read {path}: {error}")
            raw = {}
        self.translation_map = {k: v for k, v in raw.items() if isinstance(v, str) and len(k) == 1 and len(v) == 1}
        self.reverse_translation_map = {v: k for k, v in self.translation_map.items()
                                        if not v.isascii() and not "À" <= v <= "ÿ"}

    # -- load and save -----------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        raw = bytes(json_obj)
        if not gfmsg.is_gfmsg(raw):
            log_debug(f"{_PLUGIN}: not a message file")
            self._file = None
            return [[]], {}
        self._file = raw
        self.load_translation_map()
        back = str.maketrans(self.reverse_translation_map) if self.reverse_translation_map else None
        texts = [gfmsg.to_editor(units) for units, _flags in gfmsg.read(raw)]
        return [[text.translate(back) if back else text for text in texts]], {"0": "Text"}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._file is None:
            return super().save_data_to_json_obj(data, block_names)
        self.load_translation_map()
        table = str.maketrans(self.translation_map) if self.translation_map else None
        old = gfmsg.read(self._file)
        texts = [str(text).translate(table) if table else str(text) for text in (data or [[]])[0]]
        if len(texts) != len(old):
            raise ValueError(f"{len(texts)} lines for a file of {len(old)}")
        return gfmsg.write([(gfmsg.from_editor(text), flags) for text, (_units, flags) in zip(texts, old)])

    def prepare_save_context(self, context) -> None:
        """The file is rebuilt from its current version (translation first): the newest that parses."""
        self._file = next((raw for raw in context.existing_versions() if gfmsg.is_gfmsg(raw)), self._file)

    def reset_runtime_state(self) -> None:
        self._file = None
        self._located.clear()

    # -- where a block comes from ------------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[str, List[int], List[str]]]:
        """``(relative path, line flags, line labels)`` of a data block, from memory (read off the UI thread)."""
        return message_block.cached(self._located, self.mw, block_idx)

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """The line's label (from the ``.tbl``), its index and flags."""
        located = self._locate(block_idx)
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

    # -- AI and story context ----------------------------------------------------

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        located = self._locate(block_idx)
        if not located:
            return {}
        rel, _message, labels = located
        stem = _stem(rel)
        context: Dict[str, Any] = {}
        for pattern, role, instruction, section in TABLE_ROLES:
            if re.fullmatch(pattern, stem):
                context.update(content_role=role, role_instruction=instruction)
                if section:
                    context["glossary_section"] = section
                break
        else:
            if "/script/" in f"/{rel}":
                context["content_role"] = "Dialogue"
        try:
            context["label"] = labels[int(string_idx)]
        except (IndexError, TypeError, ValueError):
            pass
        return context

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        located = self._locate(block_idx)
        if not located:
            return {}
        rel = located[0]
        context = {"resource": rel, "label": _stem(rel)}
        story = next((part for prefix, part in _STORY if _stem(rel).startswith(prefix)), "")
        if story and "/script/" in f"/{rel}":
            context["story_part"] = story
        return context

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        context = self.get_scene_context_for_string(block_idx, string_idx)
        if not context:
            return None
        part = f" ({context['story_part']})" if "story_part" in context else ""
        return f"File {context['resource']}{part}"

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Pokémon, moves, items, Abilities, places, trainer names and types from the game's own name tables."""
        return name_seeds.gfmsg_seed_entries(getattr(self.mw, "project_manager", None) if self.mw else None, _PLUGIN)

    def get_capabilities(self) -> Set[str]:
        return {"glossary_seed"}

    # -- editor ------------------------------------------------------------------

    def get_tag_tooltip(self, tag: str) -> str:
        return gfmsg.describe(str(tag))

    def get_external_reference_url(self, term: str) -> Optional[str]:
        if not term or not term.strip():
            return None
        return f"https://bulbapedia.bulbagarden.net/w/index.php?search={urllib.parse.quote(term.strip())}"

    def process_pasted_segment(
        self,
        segment_to_insert: str,
        original_text_for_tags: str,
        editor_player_tag_const: str,
    ) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    def get_custom_preview_widget(self, main_window: Any) -> Optional[Any]:
        """The dialogue box drawn from the game's own layout and font (plugins/common/switch_message_preview.py).

        Only the games with that layout (Sword / Shield) get it; the others keep the BFN preview.
        """
        from plugins.common.switch_message_preview import (ARCEUS_BATTLE_BOX, ARCEUS_FIELD_BOX, SWORD_SHIELD_BOX,
                                                          SwitchMessagePreview, sibling_layout_exists)
        project_dir = getattr(getattr(main_window, "project_manager", None), "project_dir", None)
        if not project_dir:
            return None
        # Arceus first: its msg_00.arc is the same file name as Sword's, and only Arceus has the archive folder.
        for spec in (ARCEUS_FIELD_BOX, SWORD_SHIELD_BOX, ARCEUS_BATTLE_BOX):
            if sibling_layout_exists(str(project_dir), spec):
                return SwitchMessagePreview(main_window, spec)
        return None
