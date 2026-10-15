"""Super Mario Galaxy 1 and 2 (Wii, Switch, the Nebula recompilation): one project for every version.

The project edits one ``MessageData/<archive>.smgmsg`` per message archive (``messages.py``): one row per message
label over the Wii and Switch English files, so one translation goes to every version by label. Super Mario Galaxy
has ``Message`` (and ``System`` on the Switch); Super Mario Galaxy 2 has one archive per zone. ``unpack.py`` writes the project from the game files,
``build.py`` writes each version's files, ``import_mod.py`` reads an existing translation mod in. Fonts are the
``Font.arc`` members (BRFNT); the Wii ones open in the font editor (``font_sources.json``). Reference columns are
the other languages and versions (``references.smgref``, written at unpack).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.formats import FileFormat
from core.i18n import tr
from plugins.base_game_rules import BaseGameRules
from plugins.common.problem_analyzer import GenericProblemAnalyzer
from utils.logging_utils import log_debug, log_warning

from . import build, messages, unpack
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS, VERSION_WORDING

# Tag groups (Petari, CC0: CustomTagProcessor.cpp): what each tag does in the game.
TAG_GROUPS = {
    1: "Display: 0 = wait N frames, 1 = next page, 2 = vertical offset, 3 = centre",
    2: "Sound effect (its name follows)",
    3: "Picture from PictureFont (button, coin, star...)",
    4: "Font size: 0 = small, 1 = normal, 2 = large",
    5: "Player name (Mario or Luigi, its form)",
    6: "Number argument",
    7: "Text argument",
    9: "Race time",
    10: "NumberFont text",
    255: "Colour: 0 = default; 1-11 the game's colours; 2 = ruby (Japanese)",
}
_TAG_RE = re.compile(r"\{escape:(\d+):([0-9a-fA-F]*)\}")


class GalaxyProblemAnalyzer(GenericProblemAnalyzer):
    """The shared checks, plus ``SMG_VERSION_WORDING`` on each row of a label the versions word differently."""

    def analyze_data_string(self, data_string, font_map, threshold, logical_hard_limit=None):
        found = super().analyze_data_string(data_string, font_map, threshold, logical_hard_limit)
        rules = getattr(self, "game_rules", None)
        block, string = self._current_scan_block_idx, self._current_scan_string_idx
        if rules is not None and block is not None and string is not None and rules.is_split(block, string):
            if not found:
                found = [set()]
            found[0].add(VERSION_WORDING)
        return found


class GameRules(BaseGameRules):
    """Super Mario Galaxy and Super Mario Galaxy 2."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    problem_analyzer_class = GalaxyProblemAnalyzer
    tag_style = "curly"
    analyze_whole_string_first = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._rows: Optional[List[Dict[str, Any]]] = None   # the document loaded or about to be saved
        self._split: Dict[int, Dict[int, str]] = {}         # block -> {row: the version it is the wording of}

    def get_display_name(self) -> str:
        return "Super Mario Galaxy"

    def get_file_formats(self) -> list:
        return [FileFormat((".smgmsg",), "bytes", "Super Mario Galaxy messages")]

    # -- load and save -------------------------------------------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        found = messages.read_document(json_obj) if isinstance(json_obj, (bytes, bytearray)) else None
        if found is None:
            return super().load_data_from_json_obj(json_obj)
        self._rows = found
        return [[str(row.get("text", "")) for row in found]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._rows is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = data[0] if data and isinstance(data[0], list) else []
        rows = [dict(row, text=str(texts[index])) if index < len(texts) else dict(row)
                for index, row in enumerate(self._rows)]
        return messages.make_document(rows)

    def prepare_save_context(self, context) -> None:
        """The labels come from the document on disk: load the newest version that parses."""
        for raw in context.existing_versions():
            found = messages.read_document(raw)
            if found is not None:
                self._rows = found
                return
        log_warning(f"super_mario_galaxy: no message document behind {context.relative_path}")

    def reset_runtime_state(self) -> None:
        self._rows = None
        self._split.clear()

    # -- context ---------------------------------------------------------------------------------------------------

    def _row(self, string_idx: int) -> Optional[Dict[str, Any]]:
        rows = self._rows or []
        return rows[string_idx] if 0 <= string_idx < len(rows) else None

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        row = self._row(string_idx)
        if row is None:
            return {}
        return {"label": row["label"], "versions": list(row.get("in") or [])}

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        row = self._row(string_idx)
        return f"Message label {row['label']}" if row else None

    def is_split(self, block_idx: int, string_idx: int) -> bool:
        """True for a row of a label the Wii and the Switch word differently (``messages.union_rows``)."""
        if block_idx not in self._split:
            _stem, rows = self._block_rows(block_idx)
            self._split[block_idx] = {index: ",".join(row.get("in") or []) for index, row in enumerate(rows)
                                      if row.get("split")}
        return string_idx in self._split[block_idx]

    def get_problem_detail(self, block_idx: int, string_idx: int, problem_id: str) -> str:
        if problem_id != VERSION_WORDING or not self.is_split(block_idx, string_idx):
            return ""
        version = self._split[block_idx][string_idx]
        return (tr("The Wii row of this label: translate it for the Wii wording.") if version == unpack.WII
                else tr("The {0} row of this label; the Wii row has its own English.", version))

    def get_tag_tooltip(self, tag: str) -> str:
        match = _TAG_RE.fullmatch(self.replace_aliases_with_tags(str(tag)))
        if not match:
            return ""
        group, data = int(match.group(1)), match.group(2)
        return f"{TAG_GROUPS.get(group, tr('Tag group {0}', str(group)))} ({data})"

    # -- reference languages ---------------------------------------------------------------------------------------

    def supports_reference_patch(self) -> bool:
        return True

    def get_reference_language_label(self) -> str:
        return "UsFrench (wii)"

    def load_reference_patch(self, patch_path: str, block_names=None) -> Dict[Tuple[int, int], str]:
        found = self.load_multi_reference(patch_path, block_names)
        return found.get(self.get_reference_language_label()) or next(iter(found.values()), {})

    def load_multi_reference(self, patch_path: str, block_names=None) -> Dict[str, Dict[Tuple[int, int], str]]:
        """Every column of ``references.smgref`` (in ``patch_path``, the project's unpacked folder), by label."""
        path = Path(patch_path or "")
        if path.is_dir():
            path = path / unpack.REFERENCES
        if not path.is_file():
            return {}
        try:
            columns = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            log_debug(f"super_mario_galaxy: references not read from {path}: {error}")
            return {}
        result: Dict[str, Dict[Tuple[int, int], str]] = {}
        for block in sorted(int(key) for key in (block_names or {0: ""})):
            stem, rows = self._block_rows(block)
            for column, by_archive in columns.items():
                texts = by_archive.get(stem) or {}
                for index, row in enumerate(rows):
                    if row["label"] in texts:
                        result.setdefault(column, {})[(block, index)] = texts[row["label"]]
        return result

    def _block_rows(self, block: int) -> Tuple[str, List[Dict[str, Any]]]:
        """``(archive stem, rows)`` of a block's source document, read from disk; without a project, the loaded
        document as ``Message``."""
        try:
            manager = self.mw.project_manager
            source = manager.project.blocks[self.mw.block_to_project_file_map.get(block, block)].source_file
            path = Path(manager.get_absolute_path(source))
            found = messages.read_document(path.read_bytes())
            if found is not None:
                return path.name[:-len(unpack.DOCUMENT_SUFFIX)], found
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"super_mario_galaxy: block {block} has no document on disk: {error}")
        return "Message", list(self._rows or [])

    # -- Project Manager -------------------------------------------------------------------------------------------

    def get_source_roles(self) -> list:
        return [{"id": unpack.WII, "label": tr("Wii disc (USA)")},
                {"id": unpack.SWITCH, "label": tr("Switch game")},
                {"id": "wii_reference", "label": tr("Another Wii disc (reference languages)")}]

    def get_platforms(self) -> list:
        return [{"id": unpack.WII, "label": tr("Wii")}, {"id": unpack.SWITCH, "label": tr("Nintendo Switch")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        found = unpack.identify(path)
        return {"role": found["role"], "platform": found["platform"]} if found else None

    def unpack_key_consoles(self) -> List[str]:
        return ["switch", "wii"]

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        return unpack.unpack(sources, target_dir, progress, is_cancelled)

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [
            {"id": "wii_riivolution", "label": tr("Wii: Riivolution patch and Dolphin launcher"), "platforms": ["wii"],
             "kind": "layeredfs"},
            {"id": "nebula", "label": tr("Nebula (PC): disc mod manifest"), "platforms": ["wii"], "kind": "patch"},
            {"id": "switch_layeredfs", "label": tr("Switch: Atmosphere LayeredFS mod"), "platforms": ["switch"],
             "kind": "layeredfs"},
        ]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        builders = {"wii_riivolution": build.build_wii_riivolution, "nebula": build.build_nebula,
                    "switch_layeredfs": build.build_switch}
        if target_id not in builders:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        return builders[target_id](source_dir, translation_dir, output_dir, progress, is_cancelled)
