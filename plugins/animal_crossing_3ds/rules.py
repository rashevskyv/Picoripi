"""Animal Crossing: New Leaf - Welcome amiibo and Animal Crossing: Happy Home Designer (3DS, EUR) plugin.

``1_unpack.bat`` of a workspace (``_shared/scripts/zt/acnl3ds.py``) fills the source folder at romfs paths:
``romfs/Script/**/*.umsbt`` (all text: a UMSBT holds one MSBT per language, English first; New Leaf 3,299
files, Happy Home Designer 507), ``romfs/Layout/Swkbd/message/EU_English/swkbd.msbt`` (the keyboard),
``romfs/Font/*.bcfnt`` / ``*.bffnt`` (3DS fonts) and the layout archives as folders of their images
(``romfs/Layout/<x>/<y>.arc/timg/*.bclim`` New Leaf darc, ``*.bflim`` Happy Home Designer SARC).

A UMSBT opens as one block: the English MSBT (``LANGUAGE_SLOT``). Saving re-encodes only the edited messages
and writes the other languages back untouched, so an unedited file is byte for byte the game's. Text may grow:
the UMSBT table is laid out again. The MSBT reading and saving is the Switch Thousand-Year Door one
(``plugins.paper_mario_nx``); the tag catalogue is chosen per file (``tags.py``), as the two games give the same
tag numbers different arguments.

Windows (``fit.py``, ``window_layouts.json``): every script file maps to the window its text shows in (dialogue,
bulletin board, letter, system dialog, answers, item / character names); the line width and lines per window come
from the game's layouts, widths from the game's own message font (``font_sources.json`` marks it ``preview``, so the
host measures with it and draws the preview with it). Autofix of ``WIDTH_EXCEEDED`` and the AI translation re-wrap a
line with the game's codes (newline, ``{pageBreak}``); the preview draws the window from the game's textures.
"""
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.common.msbt import MAGIC, Msbt
from plugins.paper_mario_nx.rules import GameRules as ThousandYearDoorRules
from plugins.paper_mario_nx.tag_manager import TagManager as ThousandYearDoorTagManager
from utils.logging_utils import log_debug, log_warning

from . import fit
from .config import LANGUAGE_SLOT, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .problems import ProblemAnalyzer
from .tags import CODEC, CODECS, TAG_RE


def umsbt_split(data: bytes) -> Optional[List[bytes]]:
    """The MSBT files of a UMSBT (``u32 offset, u32 size`` per language, then the files), None for another file."""
    if len(data) < 16:
        return None
    first = struct.unpack_from("<I", data, 0)[0]
    if first % 8 or not 8 <= first <= 0x100 or data[first:first + 8] != MAGIC:
        return None
    slots = []
    for at in range(0, first, 8):
        offset, size = struct.unpack_from("<II", data, at)
        if offset == 0:
            break
        slots.append(data[offset:offset + size])
    return slots


def umsbt_join(slots: List[bytes], header_size: int) -> bytes:
    """A UMSBT with ``slots`` laid out one after another behind a ``header_size``-byte table."""
    head, body = bytearray(header_size), bytearray()
    for index, blob in enumerate(slots):
        struct.pack_into("<II", head, index * 8, header_size + len(body), len(blob))
        body += blob
    return bytes(head) + bytes(body)


class TagManager(ThousandYearDoorTagManager):
    """Tags of the New Leaf catalogue (the editor's static tag list; files pick their own codec)."""

    codec = CODEC


class GameRules(ThousandYearDoorRules):
    """Animal Crossing: New Leaf / Happy Home Designer (Nintendo 3DS)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    problem_analyzer_class = ProblemAnalyzer
    codec = CODEC

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._umsbt: Optional[Tuple[List[bytes], int]] = None     # (language files, table size) of the file loaded
        self._paths: Dict[int, str] = {}                          # block -> its file, for the window kind
        self._frames: Dict[Optional[str], Any] = {}               # window kind -> composed frame QImage (or None)

    def get_display_name(self) -> str:
        return "Animal Crossing: New Leaf / Happy Home Designer (3DS)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".umsbt",), "bytes", "UMSBT"), FileFormat((".msbt",), "bytes", "MSBT"), *DEFAULT_FORMATS]

    def _take(self, raw: bytes) -> bytes:
        """Remember the UMSBT around ``raw`` (when it is one) and give the English MSBT; pick the file's codec."""
        slots = umsbt_split(raw)
        if slots is not None:
            self._umsbt = (slots, struct.unpack_from("<I", raw, 0)[0])
            raw = slots[LANGUAGE_SLOT]
        else:
            self._umsbt = None
        return raw

    def _pick_codec(self, msbt: Msbt) -> None:
        """The catalogue that names more of this file's tags (the two games differ)."""
        tagged = [tokens for tokens in msbt.messages if any(not isinstance(t, str) for t in tokens)]
        if not tagged:
            return
        raw_tags = {name: sum(codec.to_editor(tokens, msbt.little).count("{tag:") for tokens in tagged)
                    for name, codec in CODECS.items()}
        self.codec = CODECS[min(raw_tags, key=lambda name: (raw_tags[name], name != "new_leaf"))]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        self._umsbt = None
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        msbt = Msbt(self._take(bytes(json_obj)))
        self._pick_codec(msbt)
        self._msbt = msbt
        return [[self.codec.to_editor(tokens, msbt.little) for tokens in msbt.messages]], {}

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        saved = super().save_data_to_json_obj(data, block_names)
        if self._umsbt is None or not isinstance(saved, (bytes, bytearray)):
            return saved
        slots, header_size = self._umsbt
        slots = list(slots)
        slots[LANGUAGE_SLOT] = bytes(saved)
        return umsbt_join(slots, header_size)

    def prepare_save_context(self, context) -> None:
        """The MSBT is rebuilt from the newest existing version (English language file of a UMSBT)."""
        path = str(getattr(context, "relative_path", "")).lower()
        self._umsbt = None
        if not path.endswith((".umsbt", ".msbt")):
            self._msbt = None
            return
        self._msbt = None
        for raw in context.existing_versions():
            try:
                self._msbt = Msbt(self._take(bytes(raw)))
            except (ValueError, IndexError, struct.error) as error:
                log_warning(f"{type(self).__module__}: cannot read {context.relative_path}: {error}; "
                            "trying the next version")
                continue
            self._pick_codec(self._msbt)
            return

    def reset_runtime_state(self) -> None:
        super().reset_runtime_state()
        self._umsbt = None
        self._paths.clear()

    # -- windows: which one, how wide, re-wrapping ----------------------------------------------

    def get_capabilities(self) -> Set[str]:
        return {"message_window_preview", "strict_tags"}

    def _rel_path(self, block_idx: Optional[int]) -> str:
        """The block's file relative to the source folder (``romfs/Script/Talk/x.umsbt``), "" when unknown."""
        if block_idx is None:
            return ""
        if block_idx not in self._paths:
            path = ""
            try:
                project_idx = (getattr(self.mw, "block_to_project_file_map", None) or {}).get(block_idx, block_idx)
                path = Path(str(self.mw.project_manager.project.blocks[project_idx].source_file)).as_posix()
            except (AttributeError, IndexError, KeyError, TypeError) as error:
                log_debug(f"animal_crossing_3ds: no file behind block {block_idx}: {error}")
            self._paths[block_idx] = path
        return self._paths[block_idx]

    def _kind(self, block_idx: Optional[int]) -> Optional[str]:
        return fit.kind_for_path(self._rel_path(block_idx)) if block_idx is not None else None

    def window_spec(self, block_idx: Optional[int]) -> Dict[str, Any]:
        """The ``window_layouts.json`` entry of the block's window ({} when the file has none)."""
        return fit.layouts()["kinds"].get(self._kind(block_idx) or "", {})

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        """The window of the string's file: line width in message-font pixels and lines per window."""
        spec = fit.layouts()["kinds"].get(self._kind(block_idx) or "", {})
        layout = {key: spec[key] for key in ("warn_width", "max_width", "lines_per_page") if spec.get(key)}
        layout["font_file"] = fit.layouts()["font"]
        return layout

    def _measure(self, font_map: Optional[dict] = None) -> fit.Measure:
        font_map = font_map or getattr(self.mw, "font_map", None) or {}
        return fit.Measure(font_map, fit.layouts()["insert_width"])

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 10) -> Optional[int]:
        """Widest line in message-font pixels: ``{size}`` scales, name and number tags count as their usual
        width, other tags as nothing (``fit.Measure``)."""
        return self._measure(font_map).width(str(text))

    def fit_text_to_window(self, text: str, block_idx: Optional[int], string_idx: Optional[int]) -> Optional[str]:
        """The text re-wrapped to its window with the game's line and page breaks (answers kept); None for text
        that is not shown in a window of known width."""
        spec = self.window_spec(block_idx)
        if not spec.get("max_width"):
            return None
        return fit.fit(str(text), self._measure(), int(spec["max_width"]), int(spec.get("lines_per_page") or 99),
                       bool(spec.get("auto_pages")))

    def autofix_data_string(self, data_string: str, editor_font_map: dict, editor_line_width_threshold: int,
                            logical_hard_limit: Optional[int] = None, allowed_problems: Optional[Set[str]] = None,
                            block_idx: Optional[int] = None, string_idx: Optional[int] = None,
                            page_local: bool = False, disable_pagination: bool = False) -> Tuple[str, bool]:
        """The shared fixes, except that a too-wide line or a too-full window is re-wrapped by ``fit``."""
        width_ids = {f"{PLUGIN_PREFIX}_WIDTH_EXCEEDED", f"{PLUGIN_PREFIX}_PAGE_LINES"}
        if allowed_problems is None:
            allowed_problems = {key for key, on in (getattr(self.mw, "autofix_enabled", None) or {}).items() if on}
        text, changed = data_string, False
        if width_ids & set(allowed_problems):
            fitted = self.fit_text_to_window(data_string, block_idx, string_idx)
            if fitted is not None and fitted != data_string:
                text, changed = fitted, True
        rest = set(allowed_problems) - width_ids
        fixed, more = super().autofix_data_string(text, editor_font_map, editor_line_width_threshold,
                                                  logical_hard_limit, rest, block_idx, string_idx,
                                                  page_local, disable_pagination)
        return fixed, changed or more

    def get_shift_enter_char(self) -> str:
        return fit.PAGE_BREAK

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        kind = self._kind(block_idx)
        spec = fit.layouts()["kinds"].get(kind or "", {})
        if not spec:
            return {}
        lines = spec.get("lines_per_page")
        return {"content_role": f"{spec['label']} window" + (f", {lines} lines of about "
                                                             f"{spec['max_width'] // 10} letters" if lines else "")}

    # -- the preview: the game's window, font and colours ----------------------------------------

    def _game_key(self) -> str:
        return "happy_home" if self.codec is CODECS["happy_home"] else "new_leaf"

    def prepare_preview_glyph_text(self, text: str):
        """Text as the window shows it: tags out (names as samples), ``{color}`` / ``{size}`` per character,
        ``{pageBreak}`` filled up to the end of its window, answers left out (they are in their own window)."""
        doc = fit.layouts()
        colors = doc["colors"][self._game_key()]
        samples = doc["samples"]
        body, _answers = fit.split_choice(str(text or ""))
        lines_per_page = 3
        try:
            lines_per_page = int(self.get_string_layout(self.mw.data_store.physical_block_idx,
                                                        self.mw.data_store.current_string_idx).get("lines_per_page") or 3)
        except (AttributeError, TypeError, ValueError):
            pass
        out: List[str] = []
        color_of: List[Optional[str]] = []
        scale_of: List[float] = []
        color: Optional[str] = None
        scale = 1.0

        def put(chars: str) -> None:
            for char in chars:
                out.append(char)
                color_of.append(color)
                scale_of.append(scale)

        position = 0
        for match in list(TAG_RE.finditer(body)) + [None]:
            put(body[position:match.start() if match else len(body)])
            if match is None:
                break
            name, *args = match.group(0)[1:-1].split(":")
            if name in ("color", "Color", "G0_3") and args:
                color = None if args[0] in ("Reset", "Default", "65535") else colors.get(args[0])
            elif name in ("size", "Size", "G0_2") and args and args[0].isdigit():
                scale = int(args[0]) / 100
            elif name in ("pageBreak", "PageBreak", "G0_4"):
                used = "".join(out).count("\n") + 1
                put("\n" * (lines_per_page - (used - 1) % lines_per_page))
            elif name in samples:
                put(samples[name])
            position = match.end()
        clean = "".join(out)
        return clean, color_of, scale_of, None

    def _style(self, kind: Optional[str]) -> Dict[str, Any]:
        spec = fit.layouts()["kinds"].get(kind or "", {})
        preview = spec.get("preview")
        style: Dict[str, Any] = {"kind": kind, "kind_name": spec.get("label", "Text")}
        if spec.get("lines_per_page"):
            style["lines_per_page"] = spec["lines_per_page"]
        if preview:
            style["geometry"] = {"screen": preview["screen"], "text": preview["text"], "box": preview.get("box"),
                                 "asset_frame": True,
                                 "text_metrics": {"font_y": preview["font_y"], "line_space": preview["line_space"],
                                                  "char_space": 0}}
            style["default_text_color"] = preview.get("text_color", "#ffffff")
            if preview.get("text_align"):
                style["text_align"] = preview["text_align"]
        return style

    def get_preview_window_style(self, block_idx: Optional[int] = None, string_idx: Optional[int] = None):
        return self._style(self._kind(block_idx))

    def get_window_presets(self) -> list:
        return [None] + [kind for kind, spec in fit.layouts()["kinds"].items() if spec.get("preview")]

    def get_window_preset_label(self, preset, auto_style=None) -> str:
        if preset is None:
            return "Auto" + (f": {auto_style.get('kind_name')}" if isinstance(auto_style, dict) else "")
        return fit.layouts()["kinds"].get(preset, {}).get("label", str(preset))

    def get_window_style_for_preset(self, preset) -> Optional[Dict[str, Any]]:
        return self._style(preset) if preset in fit.layouts()["kinds"] else None

    def get_window_frame(self, style: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """The window drawn from the game's own textures (``window_layouts.json`` frame parts), from the
        project's files; None when the textures are not there."""
        kind = (style or {}).get("kind")
        if kind not in self._frames:
            self._frames[kind] = self._compose_frame(kind)
        image = self._frames[kind]
        return {"geometry": style.get("geometry"), "image": image} if image is not None else None

    def _compose_frame(self, kind: Optional[str]):
        preview = fit.layouts()["kinds"].get(kind or "", {}).get("preview") or {}
        if not preview.get("frame"):
            return None
        try:
            metadata = self.mw.project_manager.project.metadata
            roots = [Path(metadata[key]) for key in ("translation_path", "source_path") if metadata.get(key)]
        except (AttributeError, KeyError, TypeError):
            return None
        from PIL import Image, ImageOps
        from PyQt6.QtGui import QImage

        from core import texture_formats
        width, height = preview["screen"]
        canvas = Image.new("RGBA", (int(width), int(height)))
        for part in preview["frame"]:
            names = part["texture"] if isinstance(part["texture"], list) else [part["texture"]]   # New Leaf, HHD
            path = next((root / name for name in names for root in roots if (root / name).is_file()), None)
            if path is None:
                log_debug(f"animal_crossing_3ds: frame texture {part['texture']} not in the project")
                return None
            try:
                picture = texture_formats.read("bflim", path.read_bytes())[0].image.convert("RGBA")
            except (OSError, ValueError, KeyError, IndexError) as error:
                log_warning(f"animal_crossing_3ds: cannot read {path}: {error}")
                return None
            x, y, w, h = part["rect"]
            picture = picture.resize((max(1, round(w)), max(1, round(h))), Image.BILINEAR)
            if part.get("flip_h"):
                picture = ImageOps.mirror(picture)
            if part.get("flip_v"):
                picture = ImageOps.flip(picture)
            red, green, blue, alpha = picture.split()
            tint = part.get("tint", "#ffffff").lstrip("#")
            factors = [int(tint[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [part.get("alpha", 255) / 255]
            picture = Image.merge("RGBA", [band.point(lambda v, f=f: round(v * f))
                                           for band, f in zip((red, green, blue, alpha), factors)])
            layer = Image.new("RGBA", canvas.size)
            layer.paste(picture, (round(x), round(y)))
            canvas = Image.alpha_composite(canvas, layer)
        return QImage(canvas.tobytes(), canvas.width, canvas.height, canvas.width * 4,
                      QImage.Format.Format_RGBA8888).copy()
