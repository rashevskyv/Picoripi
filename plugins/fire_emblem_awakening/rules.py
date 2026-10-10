"""Fire Emblem Awakening (3DS, EUR) plugin: the English message archives, the bfnt fonts, CTPK / CGFX text images.

The project's source folder is the workspace's ``source`` folder (``1_unpack.bat``): ``romfs/m/U/*.bin`` are the
message archives decompressed (story, supports, unit / class / item / skill names and descriptions, menus,
tutorials, DLC chapter text), ``romfs/fonts/*.bfnt`` the fonts (``font_sources.json``) and the English textures
(``texture_sources.json``). Saving writes the same files into the translation folder; ``2_build.bat`` compresses
them again. Control codes stay in the text (``$k`` wait, ``$Wm<name>|<n>`` speaker window, ``$E<face>,|``
expression, ``$Sv<voice>|``, ``$t<n>``, ``$w<n>|``, ``$Ws<name>|``, ``$Wa``, ``$Fo`` / ``$Fi`` fade); the label of a
message (``MID_...``) is its id, the Japanese speaker of ``$Wm`` / ``$Ws`` is named in English from ``GameData.bin``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from .archive import Archive, FormatError
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager

_SPEAKER = re.compile(r"\$W[ms]([^$|]*)\|")
_ROLES = {
    "GameData": ("Name or description", "Unit, class, item, skill or place name as menus show it; short."),
    "E": ("Dialogue", "A line of a downloadable chapter's story or battle conversation."),
    "X": ("Dialogue", "A line of a paralogue (side chapter) conversation."),
    "digits": ("Dialogue", "A line of a main chapter's story or battle conversation."),
    "support": ("Support conversation", "A support conversation line between two units: casual, in character."),
    "other": ("Menu or system text", "A menu label, help text, tutorial or system message."),
}


def category(stem: str) -> str:
    if stem == "GameData":
        return "GameData"
    if stem[:1] in ("E", "X") and stem[1:].isdigit():
        return stem[:1]
    if stem.isdigit():
        return "digits"
    if "_" in stem and not stem[:1].isascii():
        return "support"
    return "other"


class GameRules(BaseGameRules):
    """Fire Emblem Awakening (3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._located: Dict[int, Optional[Tuple[str, Archive]]] = {}
        self._names: Optional[Dict[str, str]] = None

    def get_display_name(self) -> str:
        return "Fire Emblem Awakening"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin",), "bytes", "Message archive (m/U/*.bin)"), *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution"}

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            return [Archive(self._last_loaded).texts], {}
        except (FormatError, ValueError) as error:
            log_debug(f"fire_emblem_awakening: not a message archive ({error})")
            return [[]], {}

    def prepare_save_context(self, context) -> None:
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        return Archive(source).build([str(s) for s in (data[0] if data else [])])

    def reset_runtime_state(self) -> None:
        self._located.clear()
        self._names = None
        self._save_source = self._last_loaded = None

    # -- where a string comes from ---------------------------------------------

    def _project(self):
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        return pm, getattr(pm, "project", None)

    def _locate(self, block_idx: int) -> Optional[Tuple[str, Archive]]:
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm, project = self._project()
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = project.blocks[block_map.get(block_idx, block_idx)]
            path = Path(pm.get_absolute_path(block.source_file))
            found = (str(block.source_file).replace("\\", "/"), Archive(path.read_bytes()))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"fire_emblem_awakening: no archive behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def _message(self, block_idx: int, string_idx: int):
        located = self._locate(block_idx)
        if not located:
            return None
        rel, archive = located
        try:
            return rel, archive.labels[int(string_idx)], archive.texts[int(string_idx)]
        except (IndexError, TypeError, ValueError):
            return None

    def _source_root(self) -> Optional[Path]:
        _pm, project = self._project()
        source = (getattr(project, "metadata", None) or {}).get("source_path") if project else None
        return Path(source) if source and Path(source).is_dir() else None

    def _english_names(self) -> Dict[str, str]:
        """Japanese speaker name (as ``$Wm`` writes it) -> English name, from ``GameData.bin``'s ``MPID_`` labels."""
        if self._names is None:
            self._names = {}
            root = self._source_root()
            path = root / "romfs" / "m" / "U" / "GameData.bin" if root else None
            if path and path.is_file():
                try:
                    archive = Archive(path.read_bytes())
                    self._names = {label[5:]: text for label, text in zip(archive.labels, archive.texts)
                                   if label.startswith("MPID_") and text}
                except (OSError, FormatError, ValueError):
                    pass
        return self._names

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._message(block_idx, string_idx)
        if not found:
            return None
        rel, label, _text = found
        return {"file": rel, "label": label, "category": category(Path(rel).stem)}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._message(block_idx, string_idx)
        if not found:
            return {}
        role, instruction = _ROLES[category(Path(found[0]).stem)]
        return {"content_role": role, "role_instruction": instruction}

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._message(block_idx, string_idx)
        if not found:
            return None
        match = _SPEAKER.search(found[2])
        if not match:
            return None
        name = match.group(1)
        return self._english_names().get(name, name) or None

    def is_placeholder_speaker(self, name: str) -> bool:
        return name in ("username", "プレイヤー")

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._message(block_idx, string_idx)
        return f"{found[0]}#{found[1].rsplit('_', 1)[0]}" if found else None

    # -- editor ----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return TAG_RE.pattern

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    def get_default_script_name(self) -> Optional[str]:
        return "fire_emblem_awakening_script.md"
