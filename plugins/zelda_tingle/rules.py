"""Tingle Tuner (The Wind Waker, GameCube): the GBA-side text in ``res/Gba/msg_LZ*.bin``."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.font_formats import gba_tiles
from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_warning
from utils.utils import clean_spaces

from . import tuner
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

_PLUGIN_DIR = Path(__file__).resolve().parent

_ROLE = ("Tingle Tuner (Game Boy Advance)",
         "Shown on a second player's Game Boy Advance linked to the GameCube: Tingle (and his brothers "
         "Knuckle, David Jr. and Ankle) give hints, shop lines and item descriptions. 16 letters per line at "
         "most, 6 lines per page; keep Tingle's voice ('Kooloo-limpah!', calling Link 'Mr. Fairy').")


class GameRules(BaseGameRules):
    """Zelda: The Wind Waker -- Tingle Tuner text.

    The project's source folder is the disc's ``files/res/Gba`` (or any folder above it): ``msg_LZ.bin``
    (USA) or ``msg_LZ0..4.bin`` (Europe: English, German, French, Spanish, Italian). Each file is one
    block of 1,086 messages. Saving packs the file again (GBA LZ77) and refuses a text bigger than the
    GBA keeps room for; an unchanged file is written back byte for byte. The USA client program
    (``client_u.bin``) holds the font (Font Editor) and two strings of its own ("Calling..." and the
    no-link error screen), a block of two strings changed in place; other client files open empty.
    """

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"
    show_spaces_as_dots_default = True

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._last_loaded: Optional[bytes] = None
        self._save_source: Optional[bytes] = None
        self._save_name = "msg_LZ.bin"

    def get_display_name(self) -> str:
        return "Zelda: The Wind Waker (Tingle Tuner, GBA)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".bin",), "bytes", "Tingle Tuner messages"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        try:
            parsed = tuner.parse(data)
        except tuner.FormatError as error:
            strings = self._program_strings(data)
            if strings is None:
                log_debug(f"zelda_tingle: not a Tingle Tuner file ({error})")
                return [[]], {}
            return [[tuner.decode(text) for text in strings]], {"0": "Tingle Tuner program text"}
        return [[tuner.decode(message, parsed.usa) for message in parsed.messages]], {"0": "Tingle Tuner"}

    def _client_params(self) -> Dict[str, Any]:
        return dict((self._plugin_json_list("font_sources.json") or [{}])[0].get("params") or {})

    def _program_strings(self, data: bytes) -> Optional[List[bytes]]:
        """The strings of a USA client program, or None for any other file."""
        try:
            return tuner.program_strings(gba_tiles.read_program(data, self._client_params()))
        except (ValueError, KeyError):
            return None

    def prepare_save_context(self, context) -> None:
        """A save rebuilds the file from its source (the oldest version offered); the file name picks the
        GBA's room for it."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None
        self._save_name = os.path.basename(str(context.relative_path or "")) or "msg_LZ.bin"

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        texts = (data or [[]])[0]
        missing: Set[str] = set()
        try:
            original = tuner.parse(source)
        except tuner.FormatError:
            return self._save_program(source, texts, missing)
        messages = list(original.messages)
        for index, text in enumerate(texts[:len(messages)]):
            messages[index] = tuner.encode(text, original.usa, missing)
        if missing:
            log_warning(f"zelda_tingle: no glyph for {''.join(sorted(missing))!r}; written as '?'")
        if messages == original.messages:
            return source
        return tuner.pack(tuner.MessageFile(messages, original.halfword_offsets), self._save_name)

    def _save_program(self, source: bytes, texts: List[str], missing: Set[str]) -> bytes:
        strings = self._program_strings(source)
        if strings is None:
            return source
        new = [tuner.encode(text, True, missing) for text in texts[:len(strings)]] + strings[len(texts):]
        if new == strings:
            return source
        params = self._client_params()
        program = tuner.write_program_strings(gba_tiles.read_program(source, params), new)
        return gba_tiles.replace_program(source, program, params)

    def reset_runtime_state(self) -> None:
        self._last_loaded = self._save_source = None

    # -- context ---------------------------------------------------------------

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        return {"content_role": _ROLE[0], "role_instruction": _ROLE[1]}

    def get_font_sources(self) -> List[Dict[str, Any]]:
        """The client program's font, with this plugin's character table and Ukrainian slots."""
        sources = self._plugin_json_list("font_sources.json")
        chars = {f"0x{code:02X}": char for code, char in tuner.char_table(True).items()}
        slots = {"codes": {f"0x{code:02X}": f"0x{tile:02X}" for code, tile in tuner.SLOT_TILES.items()},
                 "tables": [[f"0x{a:02X}", f"0x{b:02X}", f"0x{t:08X}", f"0x{o:02X}"]
                            for a, b, t, o in tuner.SLOT_TABLES]}
        for source in sources:
            params = source.setdefault("params", {})
            params.setdefault("chars", chars)
            params.setdefault("slots", slots)
        return sources

    # -- editor ----------------------------------------------------------------

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        if self._is_program_block(block_idx):
            return {"max_width": tuner.SCREEN_WIDTH, "warn_width": tuner.SCREEN_WIDTH}
        return {"max_width": tuner.LINE_WIDTH, "warn_width": tuner.LINE_WIDTH,
                "lines_per_page": tuner.LINES_PER_PAGE}

    def _is_program_block(self, block_idx: int) -> bool:
        """The block comes from a client_*.bin (by the project's file name)."""
        try:
            project = self.mw.project_manager.project
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            name = Path(str(project.blocks[block_map.get(block_idx, block_idx)].source_file)).name
        except (AttributeError, IndexError, TypeError):
            return False
        return name.lower().startswith("client")

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        return tuner.line_width(text)

    def get_spellcheck_ignore_pattern(self) -> str:
        return tuner.TAG_RE.pattern

    def get_tag_tooltip(self, tag: str) -> str:
        match = tuner.TAG_RE.fullmatch(str(tag))
        if not match:
            return ""
        name, value, bare, raw = match.groups()
        if raw:
            return f"Glyph 0x{raw.upper()} of the GBA font"
        return {
            "icon": "Button icon (0 +, 1 A, 2 B, 3 START, 4 SELECT, 5 L, 6 R, 7 heart)",
            "anim": "Tingle's animation", "speed": "Text speed", "sound": "Sound effect",
            "choice3": "Three-way choice: the next three lines are the options",
            "choice2": "Two-way choice: the next two lines are the options",
            "wait": "Pause (frames)", "color": "Text colour (0 white)",
        }.get(name or "", f"Control code {bare}") + (f": {value}" if value else "")

    def process_pasted_segment(self, segment_to_insert: str, original_text_for_tags: str,
                               editor_player_tag_const: str) -> Tuple[str, str, str]:
        return clean_spaces(segment_to_insert), "OK", ""

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
