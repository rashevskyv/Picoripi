"""Pokémon Mystery Dungeon: Gates to Infinity and Super Mystery Dungeon (3DS, EUR) plugin: SIR0 message files.

One plugin, two games. The project's source folder is the workspace's ``source`` folder (``1_unpack.bat``,
``_shared/scripts/zt/pmd3ds.py``): the English message files (Gates to Infinity: ``romfs/message/*.bin``; Super
Mystery Dungeon: the members of the ``message_en.bin`` pack, unpacked as ``romfs/message_en.bin/*.bin``), a block
per file, a string per message in file order (``message.py``: control codes as ``[name...]`` tags, ``codes.py``);
the ``.dic`` + ``.img`` fonts (``font_sources.json``, ``core.font_formats.pmd_font``) and the ``.img`` pictures of
the menus and the title (``texture_sources.json``, ``core.texture_formats.pmd_img``). Saving writes the rebuilt
message file into the translation folder; ``2_build.bat`` packs the Luma mod (and the FARC pack of Super Mystery
Dungeon) from it. The game is told from the project's file paths (``message_en.bin`` = Super Mystery Dungeon): the
two games' code tables differ in the icon codes.
"""
from __future__ import annotations

from pathlib import Path
import os
from struct import error as struct_error
from typing import Any, Dict, List, Optional, Set, Tuple

from core.i18n import tr
from core.project_library import images
from plugins.base_game_rules import BaseGameRules
from plugins.common import message_window
from plugins.common.block_loader import ReadThrough, rescan_block, source_of
from utils.logging_utils import log_debug
from utils.utils import clean_spaces

from . import build as build_mod
from . import lua_text, message, unpack
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

_CONFIG = Path(__file__).resolve().parent / "config.json"
PSMD_MARKER = "message_en.bin"
BUILD_TARGET = "layeredfs"


class GameRules(BaseGameRules):
    """Pokémon Mystery Dungeon: Gates to Infinity / Super Mystery Dungeon (3DS, European English)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "square"
    analyze_whole_string_first = True
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self.game_override: Optional[str] = None       # "gti" / "psmd"; tests and tools set it
        self._game_name: Optional[str] = None
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._attributes = ReadThrough(f"{PLUGIN_PREFIX} message", lambda block_idx: rescan_block(self.mw, block_idx))
        self._window_fonts = message_window.WindowFonts()

    def get_display_name(self) -> str:
        return "Pokémon Mystery Dungeon (3DS)"

    def get_custom_preview_widget(self, main_window: Any) -> Optional[Any]:
        """The dialogue box drawn with the game's own font and box (the window of the game in the project)."""
        try:
            root = str(self.mw.project_manager.project.metadata.get("source_path") or "")
        except AttributeError:
            return None
        if not root or not os.path.isdir(root):
            return None
        window = "dialogue_psmd" if self.game() == "psmd" else "dialogue_gti"
        try:
            facts = message_window.BoxFacts.load(_CONFIG, window)
        except KeyError:                       # the window is not measured yet
            return None
        return self._window_fonts.widget(root, facts)

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin", ".dbin"), "bytes", "Mystery Dungeon message file (SIR0)"),
                FileFormat((".lua",), "bytes", "Mystery Dungeon script (Lua 5.1 bytecode, its text)"),
                *DEFAULT_FORMATS]

    def get_capabilities(self) -> Set[str]:
        return {"glossary_seed"}

    # -- the wizard: the image in, the source folder and the mod out -----------------

    def get_platforms(self) -> list:
        return [{"id": "3ds", "label": tr("Nintendo 3DS")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        found = images.identify(path)
        if found is None or found["kind"] != "3ds" or unpack.game_of(found["title_id"]) is None:
            return None
        return {"role": "base", "platform": "3ds"}

    def unpack_key_consoles(self) -> list:
        return ["3ds"]

    def unpack_sources(self, sources: Dict[str, str], target_dir: str, progress, is_cancelled) -> Optional[str]:
        base = sources.get("base")
        if not base:
            return None
        return unpack.extract(base, target_dir, progress, is_cancelled)

    def get_build_targets(self) -> list:
        return [{"id": BUILD_TARGET, "label": tr("3DS mod (LayeredFS)"), "platforms": ["3ds"], "kind": "layeredfs"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id != BUILD_TARGET:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        try:
            result = build_mod.build(Path(source_dir), Path(translation_dir), Path(output_dir), progress, is_cancelled)
        except build_mod.ModError as error:
            raise ValueError(str(error)) from None
        return str(result)

    # -- which game -------------------------------------------------------------

    def game(self) -> str:
        """``psmd`` when the project holds the ``message_en.bin`` pack's members, else ``gti``."""
        if self.game_override:
            return self.game_override
        if self._game_name is None:
            paths = ""
            try:
                blocks = self.mw.project_manager.project.blocks if self.mw else []
                paths = " ".join(str(getattr(block, "source_file", "")) for block in blocks)
            except AttributeError:
                blocks = []
            self._game_name = "psmd" if PSMD_MARKER in paths else "gti"
            if not blocks:
                self._game_name = None      # no project yet: decide again next time
                return "gti"
        return self._game_name

    # -- load and save ----------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            if self._last_loaded.startswith(lua_text.HEADER):
                return [lua_text.texts(self._last_loaded)], {}
            return [message.File(self._last_loaded).texts(self.game())], {}
        except (message.FormatError, lua_text.LuaError, ValueError, struct_error) as error:
            log_debug(f"pokemon_md_3ds: not a message file ({error})")
            return [[]], {}

    def prepare_save_context(self, context) -> None:
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = [str(s) for s in (data[0] if data else [])]
        if source.startswith(lua_text.HEADER):
            return lua_text.rebuild(source, texts)
        return message.File(source).rebuild(texts, self.game())

    def reset_runtime_state(self) -> None:
        self._attributes.clear()
        self._game_name = None
        self._save_source = self._last_loaded = None

    # -- context ----------------------------------------------------------------

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """The line's attributes, from memory: the message file is read off the UI thread (block_loader)."""
        source = source_of(self.mw, block_idx)
        if source is None:
            return None
        path = source[1]
        found = self._attributes.get(block_idx, lambda: message.attributes(path.read_bytes()))
        if not found or int(string_idx) >= len(found):
            return None
        return dict(found[int(string_idx)])

    def get_glossary_seed_entries(self) -> List[Dict[str, Any]]:
        """Names from the ``common`` message file (Pokémon, moves, items, Abilities, dungeons, types): its short
        one-line strings with no tags and no sentence ending, in the game's own English wording."""
        entries, seen = [], set()
        try:
            pm = self.mw.project_manager
            for block in [b for b in pm.project.blocks if Path(str(b.source_file)).name == "common.bin"]:
                texts = message.File(Path(pm.get_absolute_path(block.source_file)).read_bytes()).texts(self.game())
                for row, term in enumerate(texts):
                    term = term.strip()
                    if (term and term not in seen and term[0].isupper() and len(term) <= 24 and "\n" not in term
                            and "[" not in term and term[-1] not in ".!?:," and len(term.split()) <= 3):
                        seen.add(term)
                        entries.append({"term": term, "section": "Names", "description": "common.bin",
                                        "source_ref": f"{block.source_file} line {row}"})
        except (AttributeError, OSError, TypeError, ValueError, struct_error) as error:
            log_debug(f"pokemon_md_3ds: no glossary terms: {error}")
        return entries

    # -- editor -----------------------------------------------------------------

    def get_spellcheck_ignore_pattern(self) -> str:
        return message.TAG_RE.pattern

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE

    def get_default_script_name(self) -> Optional[str]:
        return "pokemon_md_3ds_script.md"
