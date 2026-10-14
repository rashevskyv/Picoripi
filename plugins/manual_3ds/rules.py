"""3DS electronic manuals (Instruction Manual viewer): one JSON file per manual, one block, one string per paragraph.

Each file is ``{key: {"lines", "width", "en", "ru", "ua"}}``: ``lines`` is the paragraph's line count on the
console, ``width`` its column in pixels (the widest line any official localisation drew there). The original is
``en``; the Russian ``ru`` is reference context only; the translation is ``ua``. The source file has no ``ua`` key,
the translation file has one, so the content alone says which of the two a load is.

The layout facts (font size, pane positions, icon widths) are not in the JSON. They come from ``geometry.json``
in this folder, keyed by a fingerprint of the file's key list. Saving writes ``ua`` back into the translation file
and keeps every other key and the key order.
"""
import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.problem_analyzer import GenericProblemAnalyzer

from . import layout
from .page_render import group_key_of
from .config import CUSTOM_IDS, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

_DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def fingerprint(keys: List[str]) -> str:
    """Which manual a file is: a hash of its keys in order (the keys come from the console's own document)."""
    return hashlib.sha1("\n".join(keys).encode("utf-8")).hexdigest()[:16]


def parse_manual(text: str) -> Dict[str, Dict[str, Any]]:
    doc = json.loads(text)
    if not isinstance(doc, dict) or not doc or not all(isinstance(v, dict) and "en" in v for v in doc.values()):
        raise ValueError("not an electronic manual file (key -> {lines, width, en, ru, ua})")
    return doc


def render_manual(doc: Dict[str, Any]) -> str:
    """The same layout the source files have: indent 2, UTF-8 text, one trailing newline."""
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


class _Data:
    """The layout facts and the widths, read once from the plugin folder."""

    def __init__(self) -> None:
        self.widths: Optional[layout.Widths] = None
        self.geometry: Optional[Dict[str, Dict[str, Any]]] = None

    def load(self) -> None:
        if self.widths is None:
            with open(os.path.join(_DATA_DIR, "widths.json"), encoding="utf-8") as handle:
                self.widths = layout.Widths(json.load(handle))
        if self.geometry is None:
            try:
                with open(os.path.join(_DATA_DIR, "geometry.json"), encoding="utf-8") as handle:
                    self.geometry = json.load(handle)
            except (OSError, ValueError):
                self.geometry = {}


_DATA = _Data()


def _geometry_for(entries: Dict[str, Dict[str, Any]], fp: str) -> Tuple[str, Dict[str, layout.Geometry]]:
    """-> (manual name, {key: Geometry}) for a file, or ("", {}) when the file is not one of the 18 manuals."""
    _DATA.load()
    found = _DATA.geometry.get(fp) if _DATA.geometry else None
    if not found:
        return "", {}
    out: Dict[str, layout.Geometry] = {}
    for key, facts in found["entries"].items():
        out[key] = layout.Geometry(
            part=facts["part"],
            font_size=float(facts["font_size"]),
            char_space=float(facts["char_space"]),
            lines=[layout.Line(float(x), float(box)) for x, box in facts["lines"]],
            icon_widths=[float(w) for w in facts.get("icon_widths", [])],
            fixed=bool(facts.get("fixed", False)),
            budget=float(facts["budget"]) if facts.get("budget") is not None else None,
            panes={int(style): int(count) for style, count in (facts.get("panes") or {}).items()},
        )
    return found["name"], out


class ManualProblemAnalyzer(GenericProblemAnalyzer):
    """Reports the manual's own problems for the string the host is scanning.

    The host sets the block and string index before a scan. The generic text rules (tags, sublines, widths of the
    whole paragraph) do not apply: the paragraph is wrapped by the viewer, so they would be false alarms.
    """

    def analyze_data_string(self, data_string, font_map, threshold, logical_hard_limit=None):
        rules = getattr(self, "game_rules", None)
        block = getattr(self, "_current_scan_block_idx", None)
        string = getattr(self, "_current_scan_string_idx", None)
        if rules is None or block is None or string is None:
            return [set()]
        return [rules.manual_problems(block, string, data_string)]


class GameRules(BaseGameRules):
    """Electronic manuals of the Nintendo 3DS system titles (Ukrainian), through the manual viewer's pane layout."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    problem_analyzer_class = ManualProblemAnalyzer
    tag_style = "curly"
    data_dir = _DATA_DIR

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._doc: Optional[Dict[str, Dict[str, Any]]] = None
        self._save_doc: Optional[Dict[str, Dict[str, Any]]] = None
        self._keys: List[str] = []
        self._fp = ""
        self._name = ""
        self._geo: Dict[str, layout.Geometry] = {}
        self._block_meta: List[Dict[str, Any]] = []
        self._problem_cache: Dict[Tuple[int, int, str], Tuple[Set[str], Dict[str, str]]] = {}
        # (block, string) -> {problem id: detail text} from the last analysis of that string
        self._problem_details: Dict[Tuple[int, int], Dict[str, str]] = {}

    def get_display_name(self) -> str:
        return "Electronic manuals (3DS, Ukrainian)"

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((".json",), "text", "3DS electronic manual text")]

    # -- loading and saving ---------------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, str):
            return super().load_data_from_json_obj(json_obj)
        doc = parse_manual(json_obj)
        self._doc = doc
        self._keys = list(doc.keys())
        self._fp = fingerprint(self._keys)
        self._name, self._geo = _geometry_for(doc, self._fp)
        translation = any("ua" in entry for entry in doc.values())
        texts = [str(entry.get("ua", "")) if translation else str(entry["en"]) for entry in doc.values()]
        self._problem_cache = {}
        self._problem_details = {}
        self._block_meta = [{"key": key, "ru": str(entry.get("ru", "")), "lines": entry.get("lines"),
                             "width": entry.get("width")} for key, entry in doc.items()]
        return [texts], {"0": self._name or "Manual"}

    def prepare_save_context(self, context: Any) -> None:
        """The translation file is written over its newest existing version (translation, else the source)."""
        self._save_doc = None
        for version in context.existing_versions():
            try:
                self._save_doc = parse_manual(version.decode("utf-8-sig"))
                break
            except (ValueError, UnicodeDecodeError):
                continue

    def save_data_to_json_obj(self, data: list, block_names: Optional[dict] = None) -> Any:
        base = self._save_doc or self._doc
        if base is None:
            raise ValueError("3DS manual: nothing loaded to save into")
        texts = data[0] if data else []
        doc: Dict[str, Dict[str, Any]] = {}
        for index, (key, entry) in enumerate(base.items()):
            new = dict(entry)
            if index < len(texts):
                new["ua"] = str(texts[index])
            doc[key] = new
        return render_manual(doc)

    def reset_runtime_state(self) -> None:
        self._doc = None
        self._save_doc = None
        self._geo = {}
        self._problem_cache = {}
        self._problem_details = {}

    # -- reference (Russian, context only) ------------------------------------------------

    def supports_reference_patch(self) -> bool:
        return True

    def get_reference_language_label(self) -> str:
        return "Russian (RU)"

    def load_reference_patch(self, patch_path: str, block_names: Any = None) -> Dict[Tuple[int, int], str]:
        """The ``ru`` column of every manual file in ``patch_path`` (a folder or one file), matched by key list."""
        if not self._block_meta:
            return {}
        paths = [patch_path] if os.path.isfile(patch_path) else [
            os.path.join(patch_path, name) for name in sorted(os.listdir(patch_path)) if name.endswith(".json")]
        wanted = {fingerprint([meta["key"] for meta in self._block_meta]): 0}
        out: Dict[Tuple[int, int], str] = {}
        for path in paths:
            try:
                with open(path, encoding="utf-8-sig") as handle:
                    doc = parse_manual(handle.read())
            except (OSError, ValueError):
                continue
            if fingerprint(list(doc.keys())) not in wanted:
                continue
            for index, entry in enumerate(doc.values()):
                out[(0, index)] = str(entry.get("ru", ""))
        return out

    # -- problems -------------------------------------------------------------------------

    def manual_problems(self, block_idx: int, string_idx: int, text: str) -> Set[str]:
        """The problem ids of the paragraph ``string_idx`` with translation ``text``."""
        if block_idx != 0 or not (0 <= string_idx < len(self._block_meta)):
            return set()
        cache_key = (block_idx, string_idx, text)
        if cache_key not in self._problem_cache:
            meta = self._block_meta[string_idx]
            key = meta["key"]
            geo = self._geo.get(key)
            entry = self._doc.get(key, {}) if self._doc else {}
            _DATA.load()
            found = layout.check_entry(text, meta["ru"], entry, geo, _DATA.widths)
            ids: Set[str] = set()
            details: Dict[str, str] = {}
            for name, message in found:
                pid = f"{PLUGIN_PREFIX}_{name}"
                if pid not in CUSTOM_IDS:
                    continue
                ids.add(pid)
                details[pid] = f"{details[pid]}; {message}" if pid in details else message
            self._problem_cache[cache_key] = (ids, details)
        ids, details = self._problem_cache[cache_key]
        self._problem_details[(block_idx, string_idx)] = details
        return set(ids)

    def get_problem_detail(self, block_idx: int, string_idx: int, problem_id: str) -> str:
        """The layout message of one problem of the last analysed text of the paragraph."""
        return self._problem_details.get((block_idx, string_idx), {}).get(problem_id, "")

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        if block_idx != 0 or not (0 <= string_idx < len(self._block_meta)):
            return None
        meta = self._block_meta[string_idx]
        if not meta.get("width"):
            return None
        return {"max_width": int(round(float(meta["width"]))), "warn_width": int(round(float(meta["width"]))),
                "lines_per_page": int(meta.get("lines") or 1)}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        if block_idx != 0 or not (0 <= string_idx < len(self._block_meta)):
            return {}
        key = self._block_meta[string_idx]["key"]
        part, _, page = key.partition("/")
        meta = self._block_meta[string_idx]
        return {"content_role": "Manual text",
                "role_instruction": (f"Electronic manual, {part} text of page {page.split('#')[0]}: at most "
                                     f"{meta.get('lines')} lines of about {meta.get('width')} px. Keep every "
                                     "{i0}, {s1|...} and {br} marker.")}

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        if block_idx != 0 or not (0 <= string_idx < len(self._block_meta)):
            return {}
        key = self._block_meta[string_idx]["key"]
        return {"scene": self._name or "Manual", "resource": key}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        return None

    # -- live preview ---------------------------------------------------------------------

    def get_custom_preview_widget(self, main_window: Any) -> Optional[Any]:
        """The manual viewer preview (plugins/manual_3ds/preview_panel.py); needs the repo_manual folder to draw."""
        from plugins.manual_3ds.preview_panel import ManualPreviewPanel
        return ManualPreviewPanel(main_window, self)

    def manual_name(self) -> str:
        return self._name

    def string_key(self, string_idx: int) -> Optional[str]:
        """The manual key ("large/Page_003_large_0#4") of a string, or None."""
        if not (0 <= string_idx < len(self._block_meta)):
            return None
        return self._block_meta[string_idx]["key"]

    def strings_of_group(self, group: str) -> Dict[str, int]:
        """{key: string index} of every paragraph of a page group, e.g. "large/Page_003_large"."""
        return {meta["key"]: index for index, meta in enumerate(self._block_meta)
                if group_key_of(meta["key"]) == group}

    def index_string_of_page(self, page: int) -> Optional[int]:
        """The string index of the Index entry that names a page ("index/Index#<page>"), or None."""
        key = f"index/Index#{page}"
        for index, meta in enumerate(self._block_meta):
            if meta["key"] == key:
                return index
        return None

    def preview_budget(self, key: str) -> Optional[float]:
        """The column width a paragraph is drawn in on the console (from geometry.json), or None."""
        geo = self._geo.get(key)
        return geo.budget if geo is not None else None
