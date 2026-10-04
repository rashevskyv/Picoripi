"""Tears of the Kingdom plugin: MSBT texts inside the zstd SARC archives of romfs/Mals."""
import urllib.parse
import weakref
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import utils.utils as width_utils
from core.containers import ContainerManager
from plugins.base_game_rules import BaseGameRules
from utils.constants import SETTINGS_DIR
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import sarc
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .msbt import Msbt
from .tag_manager import TagManager
from .tags import describe, from_editor, to_editor

PLUGIN_DATA_DIR = SETTINGS_DIR / "plugins" / "zelda_totk"


class GameRules(BaseGameRules):
    """Zelda: Tears of the Kingdom.

    A project points at a romfs (or its ``Mals`` folder). Every ``Mals/*.sarc.zs`` opens as an
    archive (``sarc.SarcContainer``), every MSBT inside is one block, every message one string.
    Saving writes the translated archive, compressed with the game's dictionary, to the
    translation folder -- a LayeredFS ``romfs`` for Atmosphere or an emulator mod.
    """

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._msbt: Optional[Msbt] = None      # the file loaded or about to be saved
        self._members: Dict[int, Tuple[Optional[str], Optional[Msbt]]] = {}
        ContainerManager.register(sarc.SarcContainer, (".zs",))
        sarc.dictionary_dirs = _dictionary_dirs(weakref.ref(self))
        if sarc.zstd is None:
            log_warning("zelda_totk: Python 3.14+ is needed to open TotK's .zs archives (compression.zstd)")

    def get_display_name(self) -> str:
        return "Zelda: Tears of the Kingdom"

    def get_file_formats(self) -> list:
        """Loose MSBT files are binary; the archives themselves are found as containers."""
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".msbt",), "bytes", "MSBT"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        msbt = Msbt(json_obj)
        self._msbt = msbt
        return [[to_editor(tokens, msbt.little) for tokens in msbt.messages]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._msbt is None:
            return super().save_data_to_json_obj(data, block_names)
        msbt = self._msbt
        texts = data[0] if data and isinstance(data[0], list) else []
        messages = []
        for index, original in enumerate(msbt.messages):
            text = texts[index] if index < len(texts) else None
            # An untouched message keeps its exact tokens, whatever the editor form would re-encode to.
            if text is None or text == to_editor(original, msbt.little):
                messages.append(original)
            else:
                messages.append(from_editor(str(text), msbt.little))
        return msbt.build(messages)

    def prepare_save_context(self, context) -> None:
        """An MSBT is rebuilt from the existing file (labels, attributes): load the newest that parses."""
        for raw in context.existing_versions():
            try:
                self._msbt = Msbt(raw)
                return
            except (ValueError, IndexError) as error:
                log_warning(f"zelda_totk: cannot read {context.relative_path}: {error}; trying the next version")

    def reset_runtime_state(self) -> None:
        self._msbt = None
        self._members.clear()

    # -- context ---------------------------------------------------------------

    def _member(self, block_idx: int) -> Tuple[Optional[str], Optional[Msbt]]:
        """``(path inside the archive, parsed MSBT)`` of a block; cached until the next project load."""
        if block_idx in self._members:
            return self._members[block_idx]
        found: Tuple[Optional[str], Optional[Msbt]] = (None, None)
        try:
            pm = getattr(self.mw, "project_manager", None)
            project_idx = (getattr(self.mw, "block_to_project_file_map", None) or {}).get(block_idx, block_idx)
            block = pm.project.blocks[project_idx]
            meta = getattr(block, "metadata", {}) or {}
            if meta.get("is_archive_member"):
                inner = meta.get("archive_file_name")
                raw = pm.get_archive_container(meta.get("archive_rel_path"), is_translation=False).read_file(inner)
                found = (inner, Msbt(raw))
            else:
                path = Path(pm.get_absolute_path(block.source_file))
                found = (path.name, Msbt(path.read_bytes()))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"zelda_totk: no MSBT behind block {block_idx}: {error}")
        self._members[block_idx] = found
        return found

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        """The MSBT the line comes from and its label (TotK names files after events and NPCs)."""
        resource, msbt = self._member(block_idx)
        result: Dict[str, Any] = {}
        if resource:
            result["resource"] = resource
        if msbt is not None and string_idx in msbt.labels:
            result["label"] = msbt.labels[string_idx]
        return result

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        context = self.get_scene_context_for_string(block_idx, string_idx)
        if not context.get("resource"):
            return None
        where = f"Message file {context['resource']}"
        return f"{where}, label {context['label']}" if context.get("label") else where

    def get_dynamic_name_tags(self) -> dict:
        return {"{playerName}": "Link"}

    def get_tag_tooltip(self, tag: str) -> str:
        return describe(self.replace_aliases_with_tags(str(tag)))

    def get_external_reference_url(self, term: str) -> Optional[str]:
        if not term or not term.strip():
            return None
        return f"https://zeldawiki.wiki/wiki/Special:Search?search={urllib.parse.quote(term.strip())}"

    def get_capabilities(self) -> Set[str]:
        """No speaker data yet: TotK's event flows are not extracted (see docs/OPEN_ITEMS.md)."""
        return {"external_reference"}

    # -- editor ----------------------------------------------------------------

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        icon_sequences = getattr(self.mw, "icon_sequences", []) if self.mw else []
        mappings = getattr(self.mw, "default_tag_mappings", None) if self.mw else None
        return width_utils.calculate_string_width(
            text,
            font_map or {},
            default_char_width=default_char_width,
            icon_sequences=icon_sequences,
            default_tag_mappings=mappings,
        )

    def process_pasted_segment(
        self,
        segment_to_insert: str,
        original_text_for_tags: str,
        editor_player_tag_const: str,
    ) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE


def _dictionary_dirs(rules_ref):
    """Where to look for ZsDic.pack.zs: the open project's folders, then the plugin's data folder."""
    def dirs():
        rules = rules_ref()
        project = getattr(getattr(getattr(rules, "mw", None), "project_manager", None), "project", None)
        metadata = getattr(project, "metadata", None) or {}
        for key in ("source_path", "translation_path"):
            if metadata.get(key):
                yield Path(metadata[key])
        yield PLUGIN_DATA_DIR
    return dirs
