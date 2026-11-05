"""Luigi's Mansion (GameCube, USA, GLME01 rev 0): the message tables of the event archives.

Each ``message/messageNN.csv`` member of an event archive (``files/Event/eventNN.szp``, Yay0 around a RARC) is one
block; ``messages.py`` reads and writes it. Unpack writes the whole disc (``sys/`` and ``files/``) with each archive
folded into a folder. Build target: ``gc_iso``, the translated disc image.

The English slot is the only one this plugin edits; the Japanese script in ``text/eventNN.txt`` is not a text table.
Fonts: ``system/system.arc/font_12.bfn`` and the dialogue font inside ``sys/main.dol`` (``font_sources.json``;
the executable member is ``dol_font.py``). The preview draws the game's message window (``window.py``): the event
script gives each message its window and speaker colour.
"""
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from core.containers import ContainerManager
from core.i18n import tr
from core.project_library import images
from utils.logging_utils import log_debug
from utils.width import calculate_string_width
from plugins.common.disc_source import write_source_mark
from plugins.common.table_rules import TableRules

from . import build, messages, window
from .dol_font import DolFont
from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TAG_RE, TagManager

GAME_ID = "GLME01"
REVISION = 0


class GameRules(TableRules):
    """Luigi's Mansion (GameCube, USA)."""

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        ContainerManager.register(DolFont, (".dol",))   # the dialogue font inside sys/main.dol
        self._speakers: Dict[int, Dict[int, Tuple[int, int]]] = {}   # block -> message -> (window, colour)
        self._frames: Dict[Tuple[int, int], Any] = {}                # (window, colour) -> frame QImage (or None)

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    display_name = "Luigi's Mansion (GameCube)"
    file_formats = (((".csv",), "Luigi's Mansion message table (CSV, Shift-JIS)"),
                    ((".txt",), "Luigi's Mansion event script (Shift-JIS, not a text table)"))
    default_script_name = "luigis_mansion_1_script.md"
    lines_per_page = DEFAULT_LINES_PER_PAGE
    spellcheck_ignore = TAG_RE.pattern

    def parse_table(self, raw: bytes):
        try:
            return messages.Table(raw)
        except ValueError:
            return None

    def get_capabilities(self) -> Set[str]:
        return {"strict_tags", "message_window_preview"}

    def reset_runtime_state(self) -> None:
        super().reset_runtime_state()
        self._speakers.clear()
        self._frames.clear()

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        if not self._locate(block_idx):
            return {}
        return {"role": "Dialogue / menu text",
                "description": "A line of the game. A line break inside a message is a new line on screen; "
                               "<TAG>(n) tags (for example <COLOR>(3)...<COLOR>(0)) stay as they are."}

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        return None

    # ----- the font draws і ї є ґ in the Ё/Ъ/Э/Ы cells (messages.SLOT_OF): measure and preview them there

    def prepare_preview_glyph_text(self, text: str) -> Tuple[str, Optional[List[Optional[str]]]]:
        cleaned, colors = super().prepare_preview_glyph_text(text)
        return cleaned.translate(messages.TO_SLOT), colors

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 6) -> Optional[int]:
        if not any(ch in messages.SLOT_OF for ch in text):
            return None
        return calculate_string_width(text.translate(messages.TO_SLOT), font_map,
                                      icon_sequences=getattr(self.mw, "icon_sequences", []),
                                      default_tag_mappings=getattr(self.mw, "default_tag_mappings", {}))

    # ----- preview: the game's message window

    def _speaker(self, block_idx: Optional[int], string_idx: Optional[int]) -> Tuple[int, int]:
        """(window, colour) the event script shows a message with; (0, 0) when the script does not show it."""
        if block_idx is None or string_idx is None:
            return 0, 0
        if block_idx not in self._speakers:
            found: Dict[int, Tuple[int, int]] = {}
            try:
                pm = self.mw.project_manager
                block = pm.project.blocks[(self.mw.block_to_project_file_map or {}).get(block_idx, block_idx)]
                table = Path(pm.get_absolute_path(block.source_file))
                if table.suffix.lower() == ".csv":
                    for script in sorted((table.parent.parent / "text").glob("*.txt")):
                        for message, style in window.speakers(script.read_bytes().decode("cp932", "replace")).items():
                            found.setdefault(message, style)
            except (AttributeError, IndexError, KeyError, OSError, TypeError) as error:
                log_debug(f"luigis_mansion_1_gc: no event script behind block {block_idx}: {error}")
            self._speakers[block_idx] = found
        return self._speakers[block_idx].get(int(string_idx), (0, 0))

    def get_preview_window_style(self, block_idx: Optional[int] = None, string_idx: Optional[int] = None):
        win, colour = self._speaker(block_idx, string_idx)
        shadow = window.SHADOW * window.CELL / window.FONT_Y   # +2 screen pixels, in font pixels
        return {"window": win, "colour": colour, "geometry": window.geometry(win), "lines_per_page": self.lines_per_page,
                "default_text_color": "#ffffff", "shadow": {"dx": shadow, "dy": shadow, "color": "#000000"}}

    def get_window_frame(self, style: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """The message window from the project's own textures; None when they are not there."""
        key = (int((style or {}).get("window", 0)), int((style or {}).get("colour", 0)))
        if key not in self._frames:
            self._frames[key] = self._compose_frame(*key)
        image = self._frames[key]
        return {"geometry": style.get("geometry"), "image": image} if image is not None else None

    def _compose_frame(self, win: int, colour: int):
        try:
            metadata = self.mw.project_manager.project.metadata
            roots = [Path(metadata[key]) for key in ("translation_path", "source_path") if metadata.get(key)]
        except (AttributeError, KeyError, TypeError):
            return None
        from PyQt6.QtGui import QImage

        from core import texture_formats
        try:
            canvas = window.frame_image(win, colour, roots,
                                        lambda path: texture_formats.read("bti", path.read_bytes())[0].image)
        except (OSError, ValueError, KeyError, IndexError) as error:
            log_debug(f"luigis_mansion_1_gc: cannot compose window {win}: {error}")
            return None
        if canvas is None:
            return None
        return QImage(canvas.tobytes(), canvas.width, canvas.height, canvas.width * 4,
                      QImage.Format.Format_RGBA8888).copy()

    # ----- Project Manager and wizard: the disc is unpacked whole; its archives become folders

    def get_platforms(self) -> list:
        return [{"id": "gc", "label": tr("GameCube")}]

    def identify_source(self, path: str) -> Optional[Dict[str, str]]:
        found = images.identify(path)
        if not found or found["kind"] != images.KIND_GC or found["game_id"] != GAME_ID or found["revision"] != REVISION:
            return None
        return {"role": "base", "platform": "gc"}

    def unpack_sources(self, sources: Dict[str, str], target_dir: str,
                       progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> Optional[str]:
        base = sources.get("base")
        if not base:
            return None
        done = images.extract(base, target_dir, progress, is_cancelled)
        if done is None or not build.fold_archives(target_dir, is_cancelled):
            return None
        write_source_mark(target_dir, base)
        return done

    def get_source_subfolder(self) -> Optional[str]:
        return None

    def unpack_key_consoles(self) -> List[str]:
        return []   # a GameCube disc needs no key file

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": "gc_iso", "label": tr("GameCube disc image (ISO)"), "platforms": ["gc"], "kind": "patch"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress, is_cancelled) -> str:
        if target_id == "gc_iso":
            return build.build_gc_iso(source_dir, translation_dir, output_dir, progress, is_cancelled)
        return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
