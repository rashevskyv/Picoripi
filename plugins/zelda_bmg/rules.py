import os
import re
import json
from typing import Any, Tuple, Dict, List, Set, Optional
from PyQt6.QtGui import QTextCharFormat, QColor, QFont

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_info, log_warning, log_debug, log_error
from utils.utils import convert_spaces_to_dots_for_display

# Load mapping for Ukrainian letters
plugin_dir = os.path.dirname(os.path.abspath(__file__))

from .config import (
    PROBLEM_DEFINITIONS,
    PROBLEM_TAG_WARNING,
    PROBLEM_WIDTH_EXCEEDED,
    PROBLEM_SHORT_LINE,
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY,
    PROBLEM_SINGLE_WORD_SUBLINE,
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START,
    PROBLEM_EMPTY_FIRST_LINE_OF_PAGE,
    PROBLEM_BAD_SPACING,
    PROBLEM_MISSING_ICON_SPACING,
    PROBLEM_STAR_TAG_RULES
)
from .tag_manager import TagManager
from .problem_analyzer import ProblemAnalyzer
from .text_fixer import TextFixer
from .tag_logic import process_segment_tags_aggressively_zbmg
from .tag_catalog import (
    ESCAPE_ICON_SPECS,
    ESCAPE_TAGS,
    ICON_TAG_WIDTH as CATALOG_ICON_TAG_WIDTH,
    describe_escape_tag,
    build_static_escape_aliases,
    escape_tag_to_editor_alias,
    get_escape_tag_spec,
)

# In-game text color table from the Twilight Princess message renderer
# (dusklight src/d/d_msg_class.cpp, getFontCCColorTable). Index is the byte
# argument of the {escape:255:0000XX} color tag; None = default (white).
TP_COLOR_TABLE = {
    0: None,        # white (default)
    1: "#f07878",   # red
    2: "#aadc8c",   # green
    3: "#a0b4dc",   # blue
    4: "#dcdc82",   # yellow
    5: "#b4c8e6",   # light blue
    6: "#c8a0dc",   # purple
    7: None,        # white
    8: "#dcaa78",   # orange
}

# Friendly color names for alias/legacy tags -> color index in TP_COLOR_TABLE
TP_COLOR_NAMES = {
    "white": 0,
    "default": 0,
    "red": 1,
    "green": 2,
    "blue": 3,
    "yellow": 4,
    "light_blue": 5,
    "purple": 6,
    "white2": 7,
    "orange": 8,
    # legacy names from earlier plugin versions
    "grey": 5,
    "gray": 5,
}

# {COLOR_RED}/{color:red} style tags (alias/legacy forms)
_COLOR_TAG_RE = re.compile(r'\{(?:COLOR_|color:)([A-Za-z_0-9]+)\}')
# Raw BMG escape form of a color switch: group 255, data = 2-byte code + index byte
_ESCAPE_COLOR_RE = re.compile(r'\{escape:255:0000([0-9a-fA-F]{2})\}')
# Raw BMG escape form of the text scale tag (MSGTAG_SCALE): group 255, code 1,
# argument = u16 scale in percent (e.g. 0096 = 150%)
_ESCAPE_SCALE_RE = re.compile(r'\{escape:255:0001([0-9a-fA-F]{4})\}')
# Friendly editor form of the scale tag: {scale:150} (percent)
_SCALE_TAG_RE = re.compile(r'\{scale:(\d{1,4})\}')
# Any escape tag: group + at least the 2-byte tag code
_ESCAPE_ANY_RE = re.compile(r'\{escape:(\d+):([0-9a-fA-F]{4,})\}')

# All in-game icons are drawn by do_outfont at 24x24 px (times the active text
# scale) and advance the cursor by 24*scale + charSpace (d_msg_class.cpp).
ICON_TAG_WIDTH = 24

# (group, tag_code) -> preview drawing spec for every do_outfont icon tag.
# Colors come from COutFont_c::createPane (d_msg_out_font.cpp).
_ICON_SPECS: Dict[Tuple[int, int], Dict[str, Any]] = {
    # Group 0: GameCube buttons and icons
    (0, 0x0A): {"kind": "circle", "label": "A", "color": "#62a32e"},
    (0, 0x0B): {"kind": "circle", "label": "B", "color": "#c82727"},
    (0, 0x0C): {"kind": "circle", "label": "C", "color": "#c8a032"},
    (0, 0x0D): {"kind": "rect", "label": "L", "color": "#8c8c8c"},
    (0, 0x0E): {"kind": "rect", "label": "R", "color": "#8c8c8c"},
    (0, 0x0F): {"kind": "circle", "label": "X", "color": "#8c8c8c"},
    (0, 0x10): {"kind": "circle", "label": "Y", "color": "#8c8c8c"},
    (0, 0x11): {"kind": "circle", "label": "Z", "color": "#5046a5"},
    (0, 0x12): {"kind": "char", "label": "✚", "color": "#c8c8c8"},
    (0, 0x13): {"kind": "char", "label": "◉", "color": "#c8c8c8"},
    (0, 0x14): {"kind": "char", "label": "◄", "color": "#c8c8c8"},
    (0, 0x15): {"kind": "char", "label": "►", "color": "#c8c8c8"},
    (0, 0x16): {"kind": "char", "label": "▲", "color": "#c8c8c8"},
    (0, 0x17): {"kind": "char", "label": "▼", "color": "#c8c8c8"},
    (0, 0x18): {"kind": "char", "label": "↑", "color": "#c8c8c8"},
    (0, 0x19): {"kind": "char", "label": "↓", "color": "#c8c8c8"},
    (0, 0x1A): {"kind": "char", "label": "←", "color": "#c8c8c8"},
    (0, 0x1B): {"kind": "char", "label": "→", "color": "#c8c8c8"},
    (0, 0x1C): {"kind": "char", "label": "↕", "color": "#c8c8c8"},
    (0, 0x1D): {"kind": "char", "label": "↔", "color": "#c8c8c8"},
    (0, 0x23): {"kind": "char", "label": "◎", "color": "#dc3232"},
    (0, 0x24): {"kind": "char", "label": "◎", "color": "#ffc832"},
    (0, 0x27): {"kind": "circle", "label": "A", "color": "#62a32e"},
    (0, 0x2A): {"kind": "char", "label": "◎", "color": "#ffffff"},
    (0, 0x2C): {"kind": "char", "label": "◆", "color": "#00ffb4"},
    (0, 0x2E): {"kind": "circle", "label": "X", "color": "#8c8c8c"},
    (0, 0x2F): {"kind": "circle", "label": "Y", "color": "#8c8c8c"},
    (0, 0x30): {"kind": "circle", "label": "●", "color": "#464646"},
    (0, 0x39): {"kind": "char", "label": "♥", "color": "#ff3232"},
    (0, 0x3A): {"kind": "char", "label": "♪", "color": "#ffc832"},
    # Group 3: Wii buttons
    (3, 0x01): {"kind": "circle", "label": "A", "color": "#e8e8e8", "fg": "#222222"},
    (3, 0x02): {"kind": "circle", "label": "B", "color": "#e8e8e8", "fg": "#222222"},
    (3, 0x03): {"kind": "rect", "label": "⌂", "color": "#e8e8e8", "fg": "#222222"},
    (3, 0x04): {"kind": "circle", "label": "−", "color": "#e8e8e8", "fg": "#222222"},
    (3, 0x05): {"kind": "circle", "label": "+", "color": "#e8e8e8", "fg": "#222222"},
    (3, 0x06): {"kind": "circle", "label": "1", "color": "#e8e8e8", "fg": "#222222"},
    (3, 0x07): {"kind": "circle", "label": "2", "color": "#e8e8e8", "fg": "#222222"},
    (3, 0x08): {"kind": "char", "label": "✚", "color": "#c8c8c8"},
    (3, 0x09): {"kind": "char", "label": "↑", "color": "#c8c8c8"},
    (3, 0x0A): {"kind": "char", "label": "↓", "color": "#c8c8c8"},
    (3, 0x0B): {"kind": "char", "label": "↔", "color": "#c8c8c8"},
    (3, 0x0C): {"kind": "char", "label": "→", "color": "#c8c8c8"},
    (3, 0x0D): {"kind": "char", "label": "←", "color": "#c8c8c8"},
    (3, 0x0E): {"kind": "rect", "label": "▭", "color": "#e8e8e8", "fg": "#222222"},
    (3, 0x0F): {"kind": "char", "label": "◎", "color": "#78d2ff"},
    (3, 0x10): {"kind": "rect", "label": "N", "color": "#e8e8e8", "fg": "#222222"},
    (3, 0x11): {"kind": "rect", "label": "▭", "color": "#e8e8e8", "fg": "#222222"},
    (3, 0x12): {"kind": "char", "label": "✦", "color": "#ffffff"},
    (3, 0x13): {"kind": "circle", "label": "C", "color": "#e8e8e8", "fg": "#222222"},
    (3, 0x14): {"kind": "circle", "label": "Z", "color": "#e8e8e8", "fg": "#222222"},
    # Group 6: bullet marker and its indent
    (6, 0x0A): {"kind": "char", "label": "▪", "color": "#ffffff"},
    (6, 0x0B): {"kind": "blank", "label": "", "color": "#000000"},
}

# TAGS.md is the authoritative source.  Keep all preview semantics in the
# catalogue so parsing, descriptions, and icon rendering cannot drift apart.
ICON_TAG_WIDTH = CATALOG_ICON_TAG_WIDTH
_ICON_SPECS = ESCAPE_ICON_SPECS


class ProblemIDs:
    """Problem i ds implementation."""
    PROBLEM_TAG_WARNING = PROBLEM_TAG_WARNING
    PROBLEM_WIDTH_EXCEEDED = PROBLEM_WIDTH_EXCEEDED
    PROBLEM_SHORT_LINE = PROBLEM_SHORT_LINE
    PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY = PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY
    PROBLEM_SINGLE_WORD_SUBLINE = PROBLEM_SINGLE_WORD_SUBLINE
    PROBLEM_SINGLE_WORD_SUBLINE_NON_START = PROBLEM_SINGLE_WORD_SUBLINE_NON_START
    PROBLEM_EMPTY_FIRST_LINE_OF_PAGE = PROBLEM_EMPTY_FIRST_LINE_OF_PAGE
    PROBLEM_BAD_SPACING = PROBLEM_BAD_SPACING
    PROBLEM_MISSING_ICON_SPACING = PROBLEM_MISSING_ICON_SPACING
    PROBLEM_STAR_TAG_RULES = PROBLEM_STAR_TAG_RULES

class GameRules(BaseGameRules):
    """Game rules and translation logic for Game."""
    def __init__(self, main_window_ref=None):
        """Initialize a new instance."""
        super().__init__(main_window_ref)
        self.problem_definitions_cache = PROBLEM_DEFINITIONS
        self.problem_ids = ProblemIDs
        self.tag_manager = TagManager(main_window_ref)
        self.problem_analyzer = ProblemAnalyzer(main_window_ref, self.tag_manager,
                                                self.problem_definitions_cache, ProblemIDs)
        self.text_fixer = TextFixer(main_window_ref, self.tag_manager, self.problem_analyzer)
        self.problem_analyzer.game_rules = self
        self.text_fixer.game_rules = self
        self.last_loaded_bmg = None
        self.translation_map = {}
        self.reverse_translation_map = {}
        self._last_map_path = None
        self._last_map_mtime = 0
        self.load_translation_map()

    def get_dynamic_name_tags(self) -> dict:
        """Twilight Princess BMG dynamic name escape tags.

        In TP BMG files, the player name (Link) and the horse name (Epona)
        are stored as escape tags that the game replaces at runtime.
        These substitutions allow distilled script-matching to find strings
        that contain these tags by treating them as plain text.

        Tag format in editor: {escape:<type>:<hex_data>}
          - Link  -> {escape:0:0000}
          - Epona -> {escape:0:0022}
        """
        return {
            "{PLAYER}": "Link",
            "{escape:0:0000}": "Link",
            "{escape:0:0022}": "Epona",
        }

    def replace_runtime_names_for_ai(self, text: str) -> str:
        """Expose TP's two project-specific runtime names to the language model.

        This is deliberately independent of editor aliases: even if aliases
        have not been loaded yet, AI input contains Link/Epona rather than the
        opaque BMG escapes.  Other control tags remain untouched and can be
        preserved in the translated message.
        """
        result = str(text or "")
        replacements = {
            "{PLAYER}": "Link",
            "{F:Link}": "Link",
            "{f:Link}": "Link",
            "{escape:0:0000}": "Link",
            "{F:Epona}": "Epona",
            "{f:Epona}": "Epona",
            "{escape:0:0022}": "Epona",
            "{escape:6:0000}": "Link's",
            "{escape:6:0001}": "Epona's",
        }
        for tag, visible_name in replacements.items():
            result = result.replace(tag, visible_name)
        return result

    def get_escape_tag_description(self, tag: str) -> str:
        """Return a human-readable explanation for a raw BMG escape tag."""
        match = _ESCAPE_ANY_RE.fullmatch(str(tag))
        if not match:
            return ""
        return describe_escape_tag(int(match.group(1)), match.group(2))

    def get_tag_tooltip(self, tag: str) -> str:
        """Explain a raw or aliased TP tag shown under the mouse cursor."""
        raw = self.replace_aliases_with_tags(str(tag))
        return self.get_escape_tag_description(raw)

    def _ensure_escape_aliases(self, text: str) -> None:
        """Register catalogue names as real, editable aliases for raw tags."""
        if not self.mw:
            return
        mappings = getattr(self.mw, "default_tag_mappings", None)
        if mappings is None:
            mappings = {}
            self.mw.default_tag_mappings = mappings
        for match in _ESCAPE_ANY_RE.finditer(str(text)):
            raw_tag = match.group(0)
            # Existing project/user aliases win.  This is important because
            # Edit Alias persists through project settings.
            if any(original == raw_tag for original in mappings.values()):
                continue
            alias = escape_tag_to_editor_alias(raw_tag)
            if alias in mappings and mappings[alias] != raw_tag:
                group, data = match.group(1), match.group(2).lower()
                alias = f"{alias[:-1]}:{group}-{data}}}"
            mappings[alias] = raw_tag

    def replace_tags_with_aliases(self, text: str) -> str:
        """Register missing semantic aliases, then use the standard alias engine."""
        self._ensure_escape_aliases(str(text))
        return super().replace_tags_with_aliases(str(text))

    def get_escape_tag_catalog(self) -> Dict[Tuple[int, int], Any]:
        """Expose a copy of the documented Zelda BMG tag catalogue to UI tools."""
        return dict(ESCAPE_TAGS)



    def load_translation_map(self):
        """Load translation map."""
        project_dir = None
        if self.mw and hasattr(self.mw, 'project_manager') and self.mw.project_manager:
            project_dir = self.mw.project_manager.project_dir

        path = None
        if project_dir:
            proj_path = os.path.join(project_dir, 'translation_map.json')
            if not os.path.exists(proj_path):
                # Автоматично копіюємо з папки плагіна або створюємо порожній
                plugin_map_path = os.path.join(plugin_dir, 'translation_map.json')
                try:
                    if os.path.exists(plugin_map_path):
                        import shutil
                        shutil.copy2(plugin_map_path, proj_path)
                        log_info(f"Copied default translation_map.json from plugin to project: {proj_path}")
                    else:
                        with open(proj_path, 'w', encoding='utf-8') as f:
                            f.write("{}")
                        log_info(f"Created empty translation_map.json in project: {proj_path}")
                except Exception as e:
                    log_warning(f"Failed to copy/create translation_map.json in project: {e}")
            path = proj_path
        else:
            path = os.path.join(plugin_dir, 'translation_map.json')

        try:
            mtime = os.path.getmtime(path) if os.path.exists(path) else 0
        except Exception:
            mtime = 0

        if path != self._last_map_path or mtime != self._last_map_mtime:
            self._last_map_path = path
            self._last_map_mtime = mtime
            self.translation_map = {}
            self.reverse_translation_map = {}
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        raw_map = json.loads(f.read())
                        self.translation_map = {}
                        for k, v in raw_map.items():
                            # Accept synthetic keys "#g{idx}" (empty-glyph mappings) as-is
                            if k.startswith("#g") or v.startswith("#g"):
                                self.translation_map[k] = v
                            elif len(k) == 1 and len(v) == 1:
                                self.translation_map[k] = v
                                
                        # Rebuild reverse map only from normal (non-synthetic) entries
                        self.reverse_translation_map = {
                            v: k for k, v in self.translation_map.items()
                            if not k.startswith("#g") and not v.startswith("#g")
                        }
                    log_info(f"Loaded {len(self.translation_map)} translation characters mappings from {path}")
                except Exception as e:
                    log_warning(f"Error loading translation_map.json from {path}: {e}")

    def decode_string_with_mapping(self, s: str) -> str:
        """Decode CP1252 string (with active umlauts) into Ukrainian letters."""
        self.load_translation_map()
        result = []
        for char in s:
            # 1. Try normal reverse translation mapping
            decoded = self.reverse_translation_map.get(char)
            if decoded:
                result.append(decoded)
                continue
                
            # 2. Try synthetic reverse mapping: check if ord(char) corresponds to a synthetic key
            synth_key = f"#g{ord(char) - 1}"
            decoded_synth = self.translation_map.get(synth_key)
            if decoded_synth:
                result.append(decoded_synth)
                continue
                
            result.append(char)
        return "".join(result)

    def encode_string_with_mapping(self, s: str) -> str:
        """Encode Ukrainian letters back into CP1252 characters for BMG compatibility."""
        self.load_translation_map()
        result = []
        for char in s:
            # 1. Get mapped value
            val = self.translation_map.get(char, char)
            
            # 2. If it's a synthetic empty-glyph mapping like "#g224", encode as character with code 225 (glyph_idx + 1)
            if val.startswith("#g"):
                try:
                    glyph_idx = int(val[2:])
                    val = chr(glyph_idx + 1)
                except Exception:
                    pass
            result.append(val)
        return "".join(result)

    def msg_to_editor_text(self, bmg_msg: Any) -> str:
        """Convert BMG message parts to editor representation."""
        parts = []
        for item in bmg_msg.parts:
            if isinstance(item, str):
                parts.append(self.decode_string_with_mapping(item))
            elif isinstance(item, dict) and item.get("type") == "escape":
                esc_type = item.get("escape_type")
                hex_data = item.get("data", "")
                parts.append(f"{{escape:{esc_type}:{hex_data}}}")
        return "".join(parts)

    def editor_text_to_msg_content(self, text: str) -> list:
        """Convert editor representation back to BMG message parts list."""
        content = []
        pattern = r'(\{escape:\d+:[0-9a-fA-F]*\})'
        tokens = re.split(pattern, text)
        for token in tokens:
            if not token:
                continue
            match = re.match(r'\{escape:(\d+):([0-9a-fA-F]*)\}', token)
            if match:
                esc_type = int(match.group(1))
                hex_data = match.group(2)
                content.append({
                    "type": "escape",
                    "escape_type": esc_type,
                    "data": hex_data
                })
            else:
                content.append(self.encode_string_with_mapping(token))
        return content

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Optional[Dict[str, str]]]:
        """Load data from json obj."""
        if not isinstance(json_obj, bytes):
            # Fallback to standard BaseGameRules logic if not binary
            return super().load_data_from_json_obj(json_obj)

        log_info("Parsing BMG binary data in zelda_bmg plugin...")
        from bmg_tool import BMGFile
        
        bmg = BMGFile()
        try:
            bmg.load(json_obj)
        except Exception as e:
            log_warning(f"Error parsing BMG in plugin: {e}")
            return [], {}

        self.last_loaded_bmg = bmg
        
        strings_list = []
        block_names = {}
        
        for idx, msg in enumerate(bmg.messages):
            strings_list.append(self.msg_to_editor_text(msg))
            msg_id = getattr(msg, 'id', idx)
            block_names[str(idx)] = f"Message ID: {msg_id} (Idx {idx})"

        log_info(f"Loaded {len(strings_list)} messages from BMG.")
        return [strings_list], block_names

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        """Save data to json obj."""
        try:
            log_debug(f"zelda_bmg: save_data_to_json_obj called. data type={type(data)}, len={len(data) if data else 0}", category="file_ops")
            if data and len(data) > 0:
                log_debug(f"zelda_bmg: data[0] type={type(data[0])}, len={len(data[0]) if hasattr(data[0], '__len__') else 'N/A'}", category="file_ops")
            if not data or not isinstance(data[0], list):
                log_warning("zelda_bmg: save_data_to_json_obj early exit because data is empty or data[0] is not a list!", category="file_ops")
                return b""

            strings_list = data[0]
            from bmg_tool import BMGFile, BMGMessage

            bmg = self.last_loaded_bmg
            if not bmg:
                # Fallback if no file was previously loaded
                bmg = BMGFile()
                bmg.endianness = '>'
                bmg.encoding = 'cp1252'
                bmg.id = 0

            new_messages = []
            for idx, text in enumerate(strings_list):
                orig_msg = bmg.messages[idx] if bmg and idx < len(bmg.messages) else None
                msg_id = getattr(orig_msg, 'id', idx) if orig_msg else idx
                info = getattr(orig_msg, 'info', b'\x00\x00\x00\x00') if orig_msg else b'\x00\x00\x00\x00'
                is_null = getattr(orig_msg, 'is_null', False) if orig_msg else False
                
                msg = BMGMessage(info=info, parts=self.editor_text_to_msg_content(text), is_null=is_null)
                msg.id = msg_id
                new_messages.append(msg)

            bmg.messages = new_messages

            out_bytes = bmg.save()
            log_info(f"Successfully packed {len(new_messages)} messages into BMG binary.", category="file_ops")
            return out_bytes
        except Exception as e:
            log_error(f"Error packing BMG in plugin: {e}", exc_info=True, category="file_ops")
            return b""

    # ── AI translation flow context (TP message flow FLW1/FLI1) ──────────────

    def _make_flow_msg_label(self, bmg):
        """Label callable: message index -> '[msg ID] "text snippet"'."""
        def label(msg_index: int) -> str:
            try:
                msg = bmg.messages[msg_index]
            except Exception:
                return f"line #{msg_index}"
            msg_id = getattr(msg, "id", msg_index)
            try:
                text = self.msg_to_editor_text(msg)
            except Exception:
                text = ""
            text = re.sub(r'\{[^}]*\}', "", str(text)).replace("\n", " / ").strip()
            if len(text) > 90:
                text = text[:90] + "…"
            return f'[msg {msg_id}] "{text}"'
        return label

    def _get_flow_actor_map(self):
        cached = getattr(self, "_flow_actor_map", None)
        if cached is None:
            from .msg_flow import load_flow_actor_map
            cached = load_flow_actor_map(plugin_dir)
            self._flow_actor_map = cached
        return cached

    def _flow_context_from_bmg_cached(self, bmg, cache_key, resource_name=None):
        from .msg_flow import actor_map_for_bmg, flow_context_from_bmg
        cache = getattr(self, "_flow_ctx_cache", None)
        if cache is None:
            cache = {}
            self._flow_ctx_cache = cache
        if cache_key in cache:
            return cache[cache_key]
        ctx = None
        try:
            actor_map = actor_map_for_bmg(self._get_flow_actor_map(), resource_name)
            ctx = flow_context_from_bmg(
                bmg,
                msg_label=self._make_flow_msg_label(bmg),
                actor_map=actor_map,
            )
        except Exception as e:
            log_debug(f"zelda_bmg: failed to build flow context: {e}")
        cache[cache_key] = ctx
        if len(cache) > 64:
            cache.pop(next(iter(cache)))
        return ctx

    # How long a resolved (block -> parsed BMG) entry is trusted before the
    # file is re-checked on disk. Width checks and gutter painting hit this
    # many times per frame, so the hot path must be dict-lookup cheap.
    _BMG_CACHE_TTL_SECONDS = 2.0

    def _get_bmg_for_block(self, block_idx):
        """Resolve and parse the BMG file behind a data block.

        Returns (bmg, cache_key, resource_name); falls back to the most
        recently loaded BMG (single-file workflows, tests).

        Hot-path safe: results are cached per block with a short TTL, and the
        file is only read/parsed when its mtime (or archive member) changes.
        """
        import time
        from bmg_tool import BMGFile

        block_cache = getattr(self, "_bmg_block_resolve_cache", None)
        if block_cache is None:
            block_cache = {}
            self._bmg_block_resolve_cache = block_cache

        now = time.monotonic()
        cached = block_cache.get(block_idx)
        if cached is not None and now - cached[0] < self._BMG_CACHE_TTL_SECONDS:
            return cached[1], cached[2], cached[3]

        bmg = None
        cache_key = None
        resource_name = None
        try:
            pm = getattr(self.mw, 'project_manager', None)
            block_map = getattr(self.mw, 'block_to_project_file_map', {}) or {}
            proj_idx = block_map.get(block_idx, block_idx)
            blocks = pm.project.blocks if pm and getattr(pm, 'project', None) else []
            if isinstance(proj_idx, int) and 0 <= proj_idx < len(blocks):
                block = blocks[proj_idx]
                meta = getattr(block, 'metadata', {}) or {}
                if meta.get('is_archive_member'):
                    arc = meta.get('archive_rel_path')
                    inner = meta.get('archive_file_name')
                    resource_name = inner
                    # archive members can't be cheaply revalidated; key by
                    # member identity and rely on the TTL for freshness
                    cache_key = f"arc:{arc}:{inner}"
                    bmg = self._load_bmg_cached(
                        cache_key,
                        lambda: pm.get_archive_container(arc, is_translation=False).read_file(inner))
                else:
                    path = pm.get_absolute_path(block.source_file)
                    if path and os.path.exists(path):
                        resource_name = os.path.basename(path)
                        # stat only (no read) to build the cache key
                        cache_key = f"file:{path}:{os.stat(path).st_mtime_ns}"
                        bmg = self._load_bmg_cached(
                            cache_key,
                            lambda: open(path, 'rb').read())
        except Exception as e:
            log_debug(f"zelda_bmg: BMG file resolution failed for block {block_idx}: {e}")

        if bmg is None:
            # Fallback: the most recently loaded BMG (single-file workflows, tests)
            if self.last_loaded_bmg is not None:
                bmg = self.last_loaded_bmg
                cache_key = f"last:{id(bmg)}"
                resource_name = None
            else:
                cache_key = None
                resource_name = None

        block_cache[block_idx] = (now, bmg, cache_key, resource_name)
        if len(block_cache) > 64:
            block_cache.pop(next(iter(block_cache)))
        return bmg, cache_key, resource_name

    def _load_bmg_cached(self, cache_key, read_bytes):
        """Parse a BMG only when the cache key is new; read lazily."""
        from bmg_tool import BMGFile
        bmg_cache = getattr(self, "_bmg_block_cache", None)
        if bmg_cache is None:
            bmg_cache = {}
            self._bmg_block_cache = bmg_cache
        if cache_key in bmg_cache:
            return bmg_cache[cache_key]
        try:
            raw = read_bytes()
        except Exception:
            return None
        bmg = BMGFile()
        try:
            bmg.load(raw)
        except Exception:
            return None
        bmg_cache[cache_key] = bmg
        if len(bmg_cache) > 16:
            bmg_cache.pop(next(iter(bmg_cache)))
        return bmg

    def _get_flow_context_for_block(self, block_idx):
        """Resolve the BMG file behind a data block and build its dialogue-flow
        context (cached by file path + mtime)."""
        bmg, cache_key, resource_name = self._get_bmg_for_block(block_idx)
        if bmg is None:
            return None
        return self._flow_context_from_bmg_cached(bmg, cache_key, resource_name)

    def get_ai_flow_context_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        """Per-line dialogue-flow context for the AI translation prompt."""
        ctx = self._get_flow_context_for_block(block_idx)
        if ctx is None:
            return None
        try:
            return ctx.context_for_message(int(string_idx))
        except (TypeError, ValueError):
            return None

    def get_ai_flow_overview(self, block_idx: int, string_indices) -> Optional[str]:
        """Conversation outlines covering the given lines, for the AI prompt."""
        ctx = self._get_flow_context_for_block(block_idx)
        if ctx is None:
            return None
        try:
            indices = [int(i) for i in string_indices]
        except (TypeError, ValueError):
            return None
        return ctx.overview_for_messages(indices)

    def get_display_name(self) -> str:
        """Get the display name."""
        return "Zelda: Twilight Princess BMG"

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Get the problem definitions."""
        return self.problem_definitions_cache

    def get_short_problem_name(self, problem_id: str) -> str:
        """Get the short problem name."""
        if problem_id == PROBLEM_WIDTH_EXCEEDED: return "Width"
        if problem_id == PROBLEM_SHORT_LINE: return "Short"
        if problem_id == PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY: return "EmptyOddD"
        if problem_id == PROBLEM_SINGLE_WORD_SUBLINE: return "1Word"
        if problem_id == PROBLEM_SINGLE_WORD_SUBLINE_NON_START: return "1WordO"
        if problem_id == PROBLEM_EMPTY_FIRST_LINE_OF_PAGE: return "Empty1st"
        if problem_id == PROBLEM_BAD_SPACING: return "Spacing"
        if problem_id == PROBLEM_MISSING_ICON_SPACING: return "TagSpacing"
        if problem_id == PROBLEM_STAR_TAG_RULES: return "StarTag"
        return super().get_short_problem_name(problem_id)

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        """Get the syntax highlighting rules."""
        return self.tag_manager.get_syntax_highlighting_rules()

    def get_legitimate_tags(self) -> Set[str]:
        """Get the legitimate tags."""
        return self.tag_manager.get_legitimate_tags()

    def is_tag_legitimate(self, tag_to_check: str) -> bool:
        """Check if is tag legitimate."""
        return self.tag_manager.is_tag_legitimate(tag_to_check)

    def get_spellcheck_ignore_pattern(self) -> str:
        # Ignore curly braces {...} which are used for tags and escape sequences
        """Get the spellcheck ignore pattern."""
        return r'\{[^}]*\}'

    def get_editor_page_size(self) -> int:
        """Get the editor page size."""
        return 1

    def analyze_subline(self,
                        text: str,
                        next_text: Optional[str],
                        subline_number_in_data_string: int,
                        qtextblock_number_in_editor: int,
                        is_last_subline_in_data_string: bool,
                        editor_font_map: dict,
                        editor_line_width_threshold: int,
                        full_data_string_text_for_logical_check: str,
                        is_target_for_debug: bool = False,
                        logical_hard_limit: Optional[int] = None) -> Set[str]:
        """Analyze subline."""
        all_problems = self.problem_analyzer.analyze_data_string(full_data_string_text_for_logical_check, editor_font_map, editor_line_width_threshold, logical_hard_limit)

        if subline_number_in_data_string < len(all_problems):
            line_specific_problems = self.problem_analyzer.analyze_subline(
                text, next_text, subline_number_in_data_string, qtextblock_number_in_editor, is_last_subline_in_data_string,
                editor_font_map, editor_line_width_threshold, full_data_string_text_for_logical_check, is_target_for_debug,
                logical_hard_limit=logical_hard_limit
            )
            all_problems[subline_number_in_data_string].update(line_specific_problems)
            return all_problems[subline_number_in_data_string]

        return self.problem_analyzer.analyze_subline(
            text, next_text, subline_number_in_data_string, qtextblock_number_in_editor, is_last_subline_in_data_string,
            editor_font_map, editor_line_width_threshold, full_data_string_text_for_logical_check, is_target_for_debug,
            logical_hard_limit=logical_hard_limit
        )

    def autofix_data_string(self,
                             data_string: str,
                             editor_font_map: dict,
                             editor_line_width_threshold: int,
                             logical_hard_limit: Optional[int] = None,
                             allowed_problems: Optional[Set[str]] = None,
                             block_idx: Optional[int] = None,
                             string_idx: Optional[int] = None,
                             page_local: bool = False,
                             disable_pagination: bool = False) -> Tuple[str, bool]:
        """Autofix data string."""
        return self.text_fixer.autofix_data_string(
            data_string, editor_font_map, editor_line_width_threshold, logical_hard_limit, allowed_problems, block_idx, string_idx, page_local, disable_pagination
        )

    def process_pasted_segment(self,
                                segment_to_insert: str,
                                original_text_for_tags: str,
                                editor_player_tag_const: str) -> Tuple[str, str, str]:
        """Process pasted segment."""
        from utils.utils import clean_spaces
        cleaned_segment = clean_spaces(segment_to_insert)
        return process_segment_tags_aggressively_zbmg(
            cleaned_segment,
            original_text_for_tags,
            editor_player_tag_const
        )

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        """Measure the visible result of BMG tags, including 24px icons."""
        if not font_map:
            default_char_width = 10
        icon_sequences = getattr(self.mw, 'icon_sequences', [])
        from utils.utils import calculate_string_width
        clean_text, _, scales, icons = self.prepare_preview_glyph_text(text)
        icons = icons or {}
        scales = scales or [1.0] * len(clean_text)
        total = 0.0
        for index, char in enumerate(clean_text):
            scale = scales[index] if index < len(scales) else 1.0
            if index in icons:
                total += float(icons[index].get("width", ICON_TAG_WIDTH)) * scale
            else:
                total += calculate_string_width(
                    char, font_map, default_char_width, icon_sequences=icon_sequences
                ) * scale
        return int(round(total))

    def prepare_preview_glyph_text(self, text: str) -> Tuple[str, Optional[List[Optional[str]]], Optional[List[float]], Optional[Dict[int, Dict[str, Any]]]]:
        """Convert editor text into renderable text + per-char colors and scales
        for the visual preview, mimicking the TP message processor:
          - dynamic name escape tags are substituted with their runtime names
            (Link / Epona), like the game does when building a message;
          - color tags ({escape:255:0000XX} / {color:*} / {COLOR_*}) switch the
            active text color using the original game's color table
            (d_msg_class.cpp, getFontCCColorTable);
          - scale tags ({escape:255:0001XXXX} / {scale:NNN}, percent) switch the
            active text scale (do_scale); like in game, a scale above 1.0 resets
            back to 1.0 at the end of the line (do_character newline handling);
          - icon tags (buttons, arrows, targets, hearts... — everything drawn by
            do_outfont) are replaced with a U+FFFC placeholder plus a drawing
            spec so the preview can render them at the game's 24px icon size;
          - all remaining {...} tags are dropped from the rendered text.

        Returns (clean_text, colors|None, scales|None, icons|None) where icons
        maps character index in clean_text -> icon drawing spec dict.
        """
        # Convert both canonical aliases ({GC:A}, {pause:10f}, ...) and legacy
        # project aliases ({(A)}, {pause}, ...) to raw escape form first so a
        # single parsing path handles preview and width semantics losslessly.
        raw = self.convert_editor_text_to_data(str(text))
        for tag, name in self.get_dynamic_name_tags().items():
            raw = raw.replace(tag, name)

        out_chars: List[str] = []
        out_colors: List[Optional[str]] = []
        out_scales: List[float] = []
        out_icons: Dict[int, Dict[str, Any]] = {}
        current_color: Optional[str] = None
        current_scale = 1.0
        has_color = False
        has_scale = False
        pos = 0
        tag_re = re.compile(r'\{[^}]*\}')

        def append_preview_text(value: str) -> None:
            """Append a semantic runtime/literal substitution with active styling."""
            nonlocal current_scale
            for preview_char in value:
                out_chars.append(preview_char)
                out_colors.append(current_color)
                out_scales.append(current_scale)
                if preview_char == '\n' and current_scale > 1.0:
                    current_scale = 1.0

        while pos < len(raw):
            m = tag_re.match(raw, pos)
            if m:
                tag = m.group(0)
                color_idx = None
                esc_m = _ESCAPE_COLOR_RE.fullmatch(tag)
                if esc_m:
                    color_idx = int(esc_m.group(1), 16)
                else:
                    name_m = _COLOR_TAG_RE.fullmatch(tag)
                    if name_m:
                        color_idx = TP_COLOR_NAMES.get(name_m.group(1).lower())
                if color_idx is not None:
                    current_color = TP_COLOR_TABLE.get(color_idx)
                    if current_color:
                        has_color = True
                    pos = m.end()
                    continue

                scale_m = _ESCAPE_SCALE_RE.fullmatch(tag)
                percent = None
                if scale_m:
                    percent = int(scale_m.group(1), 16)
                else:
                    friendly_m = _SCALE_TAG_RE.fullmatch(tag)
                    if friendly_m:
                        percent = int(friendly_m.group(1))
                if percent is not None and percent > 0:
                    current_scale = percent / 100.0
                    if current_scale != 1.0:
                        has_scale = True
                    pos = m.end()
                    continue

                # Icon tags (do_outfont): replace with a placeholder character
                # carrying a drawing spec; advance = 24px like in game
                any_m = _ESCAPE_ANY_RE.fullmatch(tag)
                if any_m:
                    group = int(any_m.group(1))
                    data = any_m.group(2)
                    code = int(data[:4], 16)
                    spec = _ICON_SPECS.get((group, code))
                    if spec is not None:
                        out_chars.append('\ufffc')
                        out_colors.append(current_color)
                        out_scales.append(current_scale)
                        icon_spec = dict(spec)
                        icon_spec.setdefault("width", ICON_TAG_WIDTH)
                        out_icons[len(out_chars) - 1] = icon_spec
                        pos = m.end()
                        continue

                    tag_spec = get_escape_tag_spec(group, data)
                    if tag_spec is not None:
                        if tag_spec.render in {"text", "dynamic"}:
                            append_preview_text(tag_spec.preview_text)
                        # Control and ruby tags affect game state/layout but do
                        # not produce a standalone visible glyph here.
                        pos = m.end()
                        continue

                # any other tag is just dropped from the rendered text
                pos = m.end()
                continue

            char = raw[pos]
            out_chars.append(char)
            out_colors.append(current_color)
            out_scales.append(current_scale)
            if char == '\n' and current_scale > 1.0:
                # game rule: enlarged text reverts to normal size on newline
                current_scale = 1.0
            pos += 1

        return ("".join(out_chars),
                (out_colors if has_color else None),
                (out_scales if has_scale else None),
                (out_icons if out_icons else None))

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, int]]:
        """Decoded INF1 attributes of a message (window kind, speaker SE,
        camera, animations...), or None if the message can't be resolved."""
        from .window_kinds import decode_message_attributes
        try:
            string_idx = int(string_idx)
        except (TypeError, ValueError):
            return None
        bmg, _, _ = self._get_bmg_for_block(block_idx)
        if bmg is None:
            return None
        messages = getattr(bmg, "messages", None) or []
        if not (0 <= string_idx < len(messages)):
            return None
        return decode_message_attributes(getattr(messages[string_idx], "info", b""))

    def get_preview_window_style(self, block_idx: Optional[int] = None,
                                 string_idx: Optional[int] = None) -> Dict[str, Any]:
        """Visual style of the message window for the game-like preview.

        The window TYPE comes from the message's own INF1 attributes
        (fuki_kind byte, dusklight JMSMesgEntry_c): talk box, wooden/stone
        sign, item-get window (item icon + indented text), cutscene
        subtitles, location plate, Midna / light-spirit talk variants, etc.
        Shared values extracted from dusklight sources:
          - talk frame alpha 0.9 (mBoxTalkAlphaP), text offset +4.5,0
            (mTextPosX/Y), black text shadow at +2,+2 (shadow pane TEV);
          - per-character halo colors per window kind (dMsgScrnLight_c);
          - text brightness: main text modulated by TEV white (200,200,200).
        """
        from .window_kinds import window_style_for_kind, layout_for_kind
        fuki_kind = None
        if block_idx is not None and string_idx is not None:
            attrs = self.get_message_attributes(block_idx, string_idx)
            if attrs:
                fuki_kind = attrs.get("fuki_kind")
        # window_layouts.json drives pagination and lets users name/describe
        # window kinds the catalog doesn't know yet
        layout = layout_for_kind(self._get_window_layouts(), fuki_kind)
        return window_style_for_kind(fuki_kind, layout)

    def _get_window_layouts(self):
        cached = getattr(self, "_window_layouts", None)
        if cached is None:
            from .window_kinds import load_window_layouts
            cached = load_window_layouts(plugin_dir)
            self._window_layouts = cached
        return cached

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """Window-kind layout defaults for one string (widths, font,
        lines-per-page), from window_layouts.json keyed by the message's
        fuki_kind. Used by the app's width checks / autofix / AI wrapping
        unless the string has an explicit override.

        Width values may be the string "auto": then the limit is calibrated
        from the project's ORIGINAL text — the longest original line of the
        same window kind (originals always fit the real game box)."""
        attrs = self.get_message_attributes(block_idx, string_idx)
        if attrs is None:
            return None
        from .window_kinds import layout_for_kind
        fuki_kind = attrs.get("fuki_kind")
        layout = layout_for_kind(self._get_window_layouts(), fuki_kind)
        layout = self._resolve_auto_widths(layout, fuki_kind)
        return layout or None

    _AUTO_WIDTH_CACHE_VERSION = 1

    def _auto_width_signature(self) -> str:
        """Fingerprint the settings that affect measured string widths."""
        import hashlib
        import json

        payload = {
            "version": self._AUTO_WIDTH_CACHE_VERSION,
            "font_map": getattr(self.mw, 'font_map', None) or {},
            "icon_sequences": getattr(self.mw, 'icon_sequences', []) or [],
            "tag_mappings": getattr(self.mw, 'default_tag_mappings', None) or {},
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    def export_runtime_session_state(self) -> Dict[str, Any]:
        """Return small derived caches that are safe to persist with a session."""
        cached = getattr(self, "_auto_kind_widths_cache", None)
        if not cached:
            return {}
        ds = getattr(self.mw, 'data_store', None) if self.mw else None
        data = getattr(ds, 'data', None) if ds is not None else None
        if not isinstance(data, list) or cached[0] != (id(data), len(data)):
            return {}
        return {
            "version": self._AUTO_WIDTH_CACHE_VERSION,
            "auto_kind_widths": dict(cached[1]),
            "auto_kind_widths_signature": self._auto_width_signature(),
        }

    def restore_runtime_session_state(self, state: Dict[str, Any]) -> None:
        """Restore calibrated widths when their width-affecting settings match."""
        if not isinstance(state, dict) or state.get("version") != self._AUTO_WIDTH_CACHE_VERSION:
            return
        if state.get("auto_kind_widths_signature") != self._auto_width_signature():
            return
        raw_widths = state.get("auto_kind_widths")
        if not isinstance(raw_widths, dict):
            return
        try:
            widths = {int(kind): int(width) for kind, width in raw_widths.items() if int(width) > 0}
        except (TypeError, ValueError):
            return
        ds = getattr(self.mw, 'data_store', None) if self.mw else None
        data = getattr(ds, 'data', None) if ds is not None else None
        if not isinstance(data, list) or not data:
            return
        cache_token = (id(data), len(data))
        self._auto_kind_widths_cache = (cache_token, widths)
        log_info(f"zelda_bmg: restored calibrated window-kind widths from session: {widths}")

    def _resolve_auto_widths(self, layout: Dict[str, Any], fuki_kind) -> Dict[str, Any]:
        """Replace "auto" width values with limits measured from the original
        text of the same window kind; drop them if calibration is impossible."""
        if not layout:
            return layout
        wants_auto = layout.get("max_width") == "auto" or layout.get("warn_width") == "auto"
        if not wants_auto:
            return layout
        layout = dict(layout)
        auto_max = self._get_auto_kind_widths().get(int(fuki_kind or 0), 0)
        if auto_max > 0:
            if layout.get("max_width") == "auto":
                layout["max_width"] = auto_max
            if layout.get("warn_width") == "auto":
                layout["warn_width"] = max(1, auto_max - 20)
        else:
            # calibration unavailable -> fall back to the global settings
            for key in ("max_width", "warn_width"):
                if layout.get(key) == "auto":
                    layout.pop(key)
        return layout

    def _get_auto_kind_widths(self) -> Dict[int, int]:
        """Per-window-kind width limits measured from the project's original
        text: for every fuki_kind, the widest original line (in font px).

        Computed once per loaded dataset and cached; a few thousand strings
        take well under a second and every later lookup is a dict hit.
        """
        ds = getattr(self.mw, 'data_store', None) if self.mw else None
        data = getattr(ds, 'data', None) if ds is not None else None
        if not isinstance(data, list) or not data:
            return {}

        cache_token = (id(data), len(data))
        cached = getattr(self, "_auto_kind_widths_cache", None)
        if cached is not None and cached[0] == cache_token:
            return cached[1]

        from .window_kinds import decode_message_attributes
        from utils.utils import calculate_string_width

        font_map = getattr(self.mw, 'font_map', None) or {}
        icon_sequences = getattr(self.mw, 'icon_sequences', [])
        tag_mappings = getattr(self.mw, 'default_tag_mappings', None)
        result: Dict[int, int] = {}
        try:
            for b_idx, block in enumerate(data):
                if not isinstance(block, list) or not block:
                    continue
                bmg, _, _ = self._get_bmg_for_block(b_idx)
                messages = getattr(bmg, "messages", None) if bmg is not None else None
                if not messages:
                    continue
                for s_idx, text in enumerate(block):
                    if s_idx >= len(messages):
                        break
                    kind = decode_message_attributes(
                        getattr(messages[s_idx], "info", b"")).get("fuki_kind", 0)
                    for line in str(text).split('\n'):
                        if not line:
                            continue
                        w = calculate_string_width(
                            line, font_map, icon_sequences=icon_sequences,
                            default_tag_mappings=tag_mappings)
                        if w > result.get(kind, 0):
                            result[kind] = w
        except Exception as e:
            log_debug(f"zelda_bmg: auto width calibration failed: {e}")

        self._auto_kind_widths_cache = (cache_token, result)
        log_info(f"zelda_bmg: calibrated window-kind widths from originals: {result}")
        return result

    def get_text_representation_for_preview(self, data_string: str) -> str:
        """Get the text representation for preview."""
        newline_symbol = "↵"
        if self.mw and hasattr(self.mw, "newline_display_symbol"):
            val = self.mw.newline_display_symbol
            if isinstance(val, str):
                newline_symbol = val
        aliased = self.replace_tags_with_aliases(str(data_string))
        processed_string = aliased.replace('\n', newline_symbol)
        
        show_dots = False
        if self.mw and hasattr(self.mw, "show_multiple_spaces_as_dots"):
            val = self.mw.show_multiple_spaces_as_dots
            if isinstance(val, bool):
                show_dots = val
        return convert_spaces_to_dots_for_display(processed_string, show_dots)

    def get_text_representation_for_editor(self, data_string_subline: str) -> str:
        """Get the text representation for editor."""
        return super().get_text_representation_for_editor(str(data_string_subline))

    def convert_editor_text_to_data(self, text: str) -> str:
        """Convert editor text to data."""
        return super().convert_editor_text_to_data(str(text))

    def get_default_tag_mappings(self) -> Dict[str, str]:
        """Canonical aliases generated from the authoritative escape catalogue."""
        return build_static_escape_aliases()
