"""Atomic Bomberman plugin: the interface texts of the port (data/lang/<code>.json, one JSON object).

Each entry maps an English text (the key, also the source) to its translation. Placeholders {0},
{1}, ... are shown as tags ([0], [1]) in the editor and are checked against the English text.
The bottom hint row of a menu is measured with the free set's font (8 px a glyph, 6 px a space).
The Options row "Language: <name>" is measured the same way, with each language name of the table.
"""
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from core.formats import FileFormat
from core.i18n import tr
from plugins.base_game_rules import BaseGameRules

from .config import PROBLEM_DEFINITIONS, PROBLEM_HINT_ROW_WIDTH, PROBLEM_OPTIONS_ROW_WIDTH, PROBLEM_PLACEHOLDER

PLACEHOLDER = re.compile(r"\{(\d+)\}")
ALIAS = re.compile(r"\[(\d+)\]")  # the editor's form of {0}, {1}, ... (default_tag_mappings in config.json)
# The bottom hint row of a free-set menu starts at x = 60 on a 640 px screen (rendered by free_art / main).
HINT_ROW_LIMIT_PX = 580
HINT_ROW_PREFIX = "Up/Down:"
# The Options row "Language: <name>" starts at x = 55 and must end before x = 635 (options_layout.hpp).
OPTIONS_ROW_LIMIT_PX = 580
OPTIONS_ROW_PREFIX = "Language: "
LANGUAGE_NAME_KEY = "_language_name"  # the language's own name in its table (lang.cpp listLanguages)
ENGLISH_NAME = "English"  # built into the program: always offered in the Options menu
GLYPH_PX = 8  # the free font: 7 px glyph + 1 px spacing
SPACE_PX = 6  # the free font: 5 px space + 1 px spacing
BLOCK_NAME = "Interface texts"
BUILD_LANG_PC = "lang_pc"
BUILD_SWITCH = "switch_sdmc"
SWITCH_EXPORT = os.path.join("switch", "atomic-bomberman", "lang")  # sdmc:/switch/atomic-bomberman/lang


def text_width_px(text: str) -> int:
    """Width of a line in the free set's font."""
    return sum(SPACE_PX if ch == " " else GLYPH_PX for ch in text)


def placeholders(text: str) -> List[str]:
    return sorted(PLACEHOLDER.findall(text))


class GameRules(BaseGameRules):
    """The Atomic Bomberman interface texts: one block, one string per English text."""

    problem_prefix = "ABM"
    problem_definitions = PROBLEM_DEFINITIONS

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._keys: List[str] = []
        self._loaded: Dict[str, str] = {}  # the file's values as loaded: the Options row check reads them

    def get_display_name(self) -> str:
        return "Atomic Bomberman"

    def get_file_formats(self) -> List[Any]:
        return [FileFormat((".json",), "json", "Atomic Bomberman texts")]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in json_obj.items()):
            self._keys = []
            self._loaded = {}
            return [[]], {"0": BLOCK_NAME}
        self._keys = list(json_obj.keys())
        self._loaded = dict(json_obj)
        return [list(json_obj.values())], {"0": BLOCK_NAME}

    def save_data_to_json_obj(self, data: list, block_names: Optional[Dict[str, str]] = None) -> Any:
        values = data[0] if data and isinstance(data[0], list) else []
        return {key: (str(values[i]) if i < len(values) and values[i] is not None else "")
                for i, key in enumerate(self._keys)}

    def reset_runtime_state(self) -> None:
        self._keys = []
        self._loaded = {}

    def get_default_tag_mappings(self) -> Dict[str, str]:
        return {"{0}": "[0]", "{1}": "[1]", "{2}": "[2]", "{3}": "[3]"}

    def get_text_fit_problems_for_string(self, block_idx: int, string_idx: int, text: str) -> List[str]:
        """Checked when a translation is written to its place: placeholders and the hint row width."""
        if block_idx != 0 or not 0 <= string_idx < len(self._keys):
            return []
        key = self._keys[string_idx]
        plain = ALIAS.sub(r"{\1}", self.replace_aliases_with_tags(text))  # [0] in the editor is {0} in the file
        problems = []
        if placeholders(key) != placeholders(plain):
            problems.append(PROBLEM_PLACEHOLDER)
        if key.startswith(HINT_ROW_PREFIX) and text_width_px(PLACEHOLDER.sub("0", plain)) > HINT_ROW_LIMIT_PX:
            problems.append(PROBLEM_HINT_ROW_WIDTH)
        if key in (OPTIONS_ROW_PREFIX, LANGUAGE_NAME_KEY) and self._options_row_too_wide(key, plain):
            problems.append(PROBLEM_OPTIONS_ROW_WIDTH)
        return problems

    def _options_row_too_wide(self, key: str, text: str) -> bool:
        """The Options row is the label and one language name. Each name of the table and the program's
        English must fit beside the label. The other half is the value loaded from the file (a text
        changed in the editor is measured when it is written, the other half as it was loaded)."""
        if key == OPTIONS_ROW_PREFIX:
            label, names = text, [ENGLISH_NAME, self._loaded.get(LANGUAGE_NAME_KEY, "")]
        else:
            label, names = self._loaded.get(OPTIONS_ROW_PREFIX, ""), [ENGLISH_NAME, text]
        return any(text_width_px(label + name) > OPTIONS_ROW_LIMIT_PX for name in names if name)

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": "pc", "label": tr("PC")}, {"id": "switch", "label": tr("Nintendo Switch")}]

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [
            {"id": BUILD_LANG_PC, "label": tr("Atomic Bomberman: language file for the PC port"), "platforms": ["pc"], "kind": "files"},
            {"id": BUILD_SWITCH, "label": tr("Atomic Bomberman: export folder for Switch (sdmc:/switch/atomic-bomberman/lang)"),
             "platforms": ["switch"], "kind": "files"},
        ]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        """Copy the translated table(s) into the folder the port reads: lang/ next to its settings file."""
        if target_id not in (BUILD_LANG_PC, BUILD_SWITCH):
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        import shutil
        from pathlib import Path
        root = Path(translation_dir)
        files = [root] if root.is_file() else sorted(path for path in root.rglob("*.json") if path.is_file())
        folder = Path(output_dir) / (SWITCH_EXPORT if target_id == BUILD_SWITCH else "lang")
        folder.mkdir(parents=True, exist_ok=True)
        for position, path in enumerate(files, start=1):
            if is_cancelled():
                break
            shutil.copy2(path, folder / path.name)
            progress(100 * position // max(1, len(files)), path.name)
        return str(folder)
