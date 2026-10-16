"""3DS electronic manuals (Instruction Manual viewer): one JSON file per manual, one block, one string per paragraph.

Each file is ``{key: {"lines", "width", "en", "ru", "ua"}}``: ``lines`` is the paragraph's line count on the
console, ``width`` its column in pixels (the widest line any official localisation drew there). The original is
``en`` (``ru`` when ``en`` is empty: a page the English manual does not have); the Russian ``ru`` is reference
context; the translation is ``ua``. One file may hold all three (a project that reads the owner's files in place),
so the host's load role (``set_load_role``), not the content, says which a parse returns.

A project holds many manuals: each parsed file is one data block, kept in load order (block index = position),
and the list travels with the host as the plugin's runtime state (a restored session parses no file).

The layout facts (font size, pane positions, icon widths) are not in the JSON. They come from ``geometry.json``
in this folder, keyed by a fingerprint of the file's key list. Saving writes ``ua`` back into the translation file
and keeps every other key and the key order.
"""
import json
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from PyQt6.QtCore import QObject, pyqtSignal

from plugins.base_game_rules import BaseGameRules
from plugins.common.problem_analyzer import GenericProblemAnalyzer
from utils import app_mode
from utils.logging_utils import log_warning

from . import layout, page_build, repo_tools
from .layout import fingerprint
from .config import CUSTOM_IDS, PLUGIN_PREFIX, PROBLEM_DEFINITIONS

# The defects only the render can see (page_build.RENDER_PROBLEMS) as the editor's problem ids.
RENDER_IDS = {kind: f"{PLUGIN_PREFIX}_{name}" for kind, name in page_build.RENDER_PROBLEMS.items()}

_DATA_DIR = os.path.dirname(os.path.abspath(__file__))
_STRING_KEY_PATTERN = re.compile(r"(large|small)/Page_(\d+)_(large|small)_\d+")


def group_key_of(string_key: str) -> Optional[str]:
    """"small/Page_003_small_1#4" -> "small/Page_003_small", or None for an index entry."""
    match = _STRING_KEY_PATTERN.fullmatch(string_key.split("#", 1)[0])
    if not match:
        return None
    return f"{match.group(1)}/Page_{match.group(2)}_{match.group(1)}"


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
        # {fingerprint: facts} of the manuals; the owner commit the file was built from is in owner_commit.
        self.geometry: Optional[Dict[str, Dict[str, Any]]] = None
        self.owner_commit: str = ""

    def load(self) -> None:
        if self.widths is None:
            with open(os.path.join(_DATA_DIR, "widths.json"), encoding="utf-8") as handle:
                self.widths = layout.Widths(json.load(handle))
        if self.geometry is None:
            try:
                with open(os.path.join(_DATA_DIR, "geometry.json"), encoding="utf-8") as handle:
                    doc = json.load(handle)
                self.owner_commit = str(doc.get("owner_commit", ""))
                self.geometry = doc.get("manuals", {})
            except (OSError, ValueError, AttributeError):
                self.geometry = {}


_DATA = _Data()


def _geometry_for(entries: Dict[str, Dict[str, Any]], fp: str) -> Tuple[str, Dict[str, layout.Geometry]]:
    """-> (manual name, {key: Geometry}) for a file, or ("", {}) when the file is not one of the 18 manuals."""
    _DATA.load()
    found = _DATA.geometry.get(fp) if _DATA.geometry else None
    if not found:
        return "", {}
    # Pictures and frames per page: [kind, abs_x, abs_y, width, height, frame width or null] (the page is the key
    # minus its "#n").
    pages = {page: [layout.Occluder(str(kind), float(x), float(y), float(w), float(h), None if fw is None else float(fw))
                    for kind, x, y, w, h, fw in items]
             for page, items in (found.get("pages") or {}).items()}
    out: Dict[str, layout.Geometry] = {}
    for key, facts in found["entries"].items():
        own = set(facts.get("own", []))   # the paragraph's own inline icons: not in the way of its lines
        out[key] = layout.Geometry(
            part=facts["part"],
            font_size=float(facts["font_size"]),
            char_space=float(facts["char_space"]),
            lines=[[_line(pane) for pane in row] for row in facts["lines"]],
            icon_widths=[float(w) for w in facts.get("icon_widths", [])],
            fixed=bool(facts.get("fixed", False)),
            budget=float(facts["budget"]) if facts.get("budget") is not None else None,
            occluders=[occ for index, occ in enumerate(pages.get(key.split("#", 1)[0], [])) if index not in own],
        )
    return found["name"], out


def _line(pane: List[Any]) -> layout.Line:
    """One text pane of geometry.json: [x, width, abs_x, abs_y, step, char_space, style, origin, text_pos, text_align, mark]."""
    return layout.Line(*(float(v) for v in pane[:6]), *(int(v) for v in pane[6:10]), *(str(v) for v in pane[10:11]))


@dataclass
class _Manual:
    """One loaded manual file (one data block). The geometry is looked up on first use (``resolved``)."""

    doc: Dict[str, Dict[str, Any]]
    keys: List[str]
    fp: str
    name: Optional[str] = None  # None until the geometry is looked up; "" when the file has none
    geo: Dict[str, layout.Geometry] = field(default_factory=dict)

    @classmethod
    def of(cls, doc: Dict[str, Dict[str, Any]]) -> "_Manual":
        keys = list(doc.keys())
        return cls(doc, keys, fingerprint(keys))

    def resolved(self) -> "_Manual":
        if self.name is None:
            name, geo = _geometry_for(self.doc, self.fp)
            self.geo = geo  # geo before name: a reader that sees the name sees the geometry
            self.name = name
        return self


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


class _Rescan(QObject):
    """Carries a finished background render to the UI thread, where the host rescans the block."""

    block_done = pyqtSignal(int)


class GameRules(BaseGameRules):
    """Electronic manuals of the Nintendo 3DS system titles (Ukrainian), through the manual viewer's pane layout."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    problem_analyzer_class = ManualProblemAnalyzer
    tag_style = "curly"
    data_dir = _DATA_DIR

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._manuals: List[_Manual] = []  # one per data block, in load order
        self._save_doc: Optional[Dict[str, Dict[str, Any]]] = None
        self._save_block: Optional[int] = None
        self._load_role = "source"
        self._problem_cache: Dict[Tuple[int, int, str], Tuple[Set[str], Dict[str, str]]] = {}
        # (block, string) -> {problem id: detail text} from the last analysis of that string
        self._problem_details: Dict[Tuple[int, int], Dict[str, str]] = {}
        # (block, page group) -> (the page's texts it was rendered with, {string key: {problem id: detail}}).
        # The render sees what the geometry cannot (a label leaving its cell, two paragraphs' ink meeting), so a
        # page is built from every current text on it and judged once; a changed text renders it again.
        self._page_problems: Dict[Tuple[int, str], Tuple[Tuple[Tuple[str, str], ...], Dict[str, Dict[str, str]]]] = {}
        self._render_lock = threading.Lock()
        self._rendering: Set[int] = set()     # blocks a background render is working on
        # Made on the UI thread when the first background render is scheduled (a queued signal lands on the thread
        # that owns the object). A render of a rules object the host replaced emits into nothing: harmless.
        self._rescan: Optional[_Rescan] = None
        self._render_warned = False
        self._root: Optional[str] = None      # the owner's folder, read from disk once per load (None: not yet)

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
        # Every parse is the next data block. The host re-parses (translation files, a save, a revert) between
        # export_runtime_state and restore_runtime_state, so those extra blocks never stay.
        manual = _Manual.of(doc).resolved()
        self._manuals.append(manual)
        if self._load_role == "translation":
            texts = [str(entry.get("ua", "")) for entry in doc.values()]
        else:
            texts = [str(entry.get("en") or entry.get("ru", "")) for entry in doc.values()]
        return [texts], {"0": manual.name or "Manual"}

    def set_load_role(self, role: str) -> None:
        self._load_role = role

    def export_runtime_state(self) -> Any:
        """The loaded manuals without their translation (the editor holds it): a restored session parses no file."""
        return {"manuals": [{key: {name: value for name, value in entry.items() if name != "ua"}
                             for key, entry in manual.doc.items()} for manual in self._manuals]}

    def restore_runtime_state(self, state: Any) -> None:
        docs = state.get("manuals") if isinstance(state, dict) else None
        if not isinstance(docs, list):
            return
        self._manuals = [_Manual.of(doc) for doc in docs if isinstance(doc, dict)]
        self._problem_cache = {}
        self._problem_details = {}
        self._page_problems = {}
        self._root = None

    def prepare_save_context(self, context: Any) -> None:
        """The translation file is written over its newest existing version (translation, else the source)."""
        self._save_doc = None
        self._save_block = next(iter(context.block_indices), None)
        for version in context.existing_versions():
            try:
                self._save_doc = parse_manual(version.decode("utf-8-sig"))
                break
            except (ValueError, UnicodeDecodeError):
                continue

    def save_data_to_json_obj(self, data: list, block_names: Optional[dict] = None) -> Any:
        fallback = self._manual(self._save_block) if self._save_block is not None else None
        if fallback is None and self._manuals:
            fallback = self._manuals[-1]
        base = self._save_doc or (fallback.doc if fallback is not None else None)
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
        self._manuals = []
        self._save_doc = None
        self._save_block = None
        self._problem_cache = {}
        self._problem_details = {}
        self._page_problems = {}
        self._root = None

    def _manual(self, block_idx: Optional[int]) -> Optional[_Manual]:
        """The manual of a data block, its geometry looked up, or None."""
        manuals = self._manuals  # one read: the UI thread may replace the list while the preview worker asks
        if block_idx is None or not (0 <= block_idx < len(manuals)):
            return None
        return manuals[block_idx].resolved()

    def _entry(self, block_idx: int, string_idx: int) -> Optional[Tuple[_Manual, str, Dict[str, Any]]]:
        """(manual, key, entry) of one paragraph, or None."""
        manual = self._manual(block_idx)
        if manual is None or not (0 <= string_idx < len(manual.keys)):
            return None
        key = manual.keys[string_idx]
        return manual, key, manual.doc[key]

    # -- reference (Russian, context only) ------------------------------------------------

    def supports_reference_patch(self) -> bool:
        return True

    def get_reference_language_label(self) -> str:
        return "Russian (RU)"

    def load_reference_patch(self, patch_path: str, block_names: Any = None) -> Dict[Tuple[int, int], str]:
        """The ``ru`` column of every manual file in ``patch_path`` (a folder or one file), matched by key list."""
        if not self._manuals:
            return {}
        paths = [patch_path] if os.path.isfile(patch_path) else [
            os.path.join(patch_path, name) for name in sorted(os.listdir(patch_path)) if name.endswith(".json")]
        wanted: Dict[str, List[int]] = {}
        for block, manual in enumerate(self._manuals):
            wanted.setdefault(manual.fp, []).append(block)
        out: Dict[Tuple[int, int], str] = {}
        for path in paths:
            try:
                with open(path, encoding="utf-8-sig") as handle:
                    doc = parse_manual(handle.read())
            except (OSError, ValueError):
                continue
            for block in wanted.get(fingerprint(list(doc.keys())), []):
                for index, entry in enumerate(doc.values()):
                    out[(block, index)] = str(entry.get("ru", ""))
        return out

    # -- problems -------------------------------------------------------------------------

    def manual_problems(self, block_idx: int, string_idx: int, text: str) -> Set[str]:
        """The problem ids of the paragraph ``string_idx`` with translation ``text``.

        The layout facts give the paragraph's own problems; the render of its page (the owner's folder set) adds
        what only a drawn page shows: a line leaving its cell, two paragraphs' ink meeting, a line painted over.
        """
        found_entry = self._entry(block_idx, string_idx)
        if found_entry is None:
            return set()
        cache_key = (block_idx, string_idx, text)
        if cache_key not in self._problem_cache:
            manual, key, entry = found_entry
            _DATA.load()
            found = layout.check_entry(text, str(entry.get("ru", "")), entry, manual.geo.get(key), _DATA.widths)
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
        rendered = self._render_problems(block_idx, found_entry[0], found_entry[1])
        self._problem_details[(block_idx, string_idx)] = {**details, **rendered}
        return set(ids) | set(rendered)

    # -- the render's problems ---------------------------------------------------------------

    def _folder(self) -> str:
        """The owner's repo_manual folder (the preview panel's setting), read from disk once per load."""
        if self._root is None:
            self._root = page_build.load_folder()
        return self._root

    def _render_problems(self, block_idx: int, manual: _Manual, key: str) -> Dict[str, str]:
        """{render problem id: detail} of one string: from the page cache, rendered now off the UI thread, or scheduled."""
        group = group_key_of(key)
        if group is None or not manual.name or not self._folder():
            return {}
        keys = [k for k in manual.keys if group_key_of(k) == group]
        texts = self._page_texts(block_idx, manual, keys)
        if not any(texts.values()):
            return {}   # an untouched page draws Nintendo's own text: nothing to judge
        signature = tuple(sorted(texts.items()))
        cached = self._page_problems.get((block_idx, group))
        if cached is not None and cached[0] == signature:
            return dict(cached[1].get(key, {}))
        if app_mode.headless or threading.current_thread() is not threading.main_thread():
            found = self._render_page_problems(manual, group, keys, texts)
            self._page_problems[(block_idx, group)] = (signature, found)
            return dict(found.get(key, {}))
        self._render_later(block_idx)   # never a render on the UI thread: the host rescans the block when it is done
        return {}

    def _page_texts(self, block_idx: int, manual: _Manual, keys: List[str]) -> Dict[str, str]:
        """The current text of every string of a page: the editor's (edits included), else the loaded file's."""
        processor = getattr(self.mw, "data_processor", None)
        if processor is None:
            return {key: str(manual.doc[key].get("ua", "")) for key in keys}
        index = {key: position for position, key in enumerate(manual.keys)}
        return {key: str(processor.get_current_string_text(block_idx, index[key])[0] or "") for key in keys}

    def _render_page_problems(self, manual: _Manual, group: str, keys: List[str], texts: Dict[str, str]) -> Dict[str, Dict[str, str]]:
        """{string key: {problem id: detail}} of one page; {} (logged once) when the owner's tools cannot draw it.

        Any failure is caught: the result is cached for these texts either way, so a page that cannot be drawn
        never makes the background render and the host's rescan chase each other.
        """
        try:
            tools = repo_tools.load_tools(self._folder())
            part, page_name = group.split("/", 1)
            page = int(page_name.split("_")[1])
            budgets = {key: (manual.geo[key].budget if key in manual.geo else None) for key in keys}
            kinds, _failed = page_build.page_kinds(tools, manual.name or "", part, page, texts, budgets)
        except Exception as exc:  # the owner's tools, the font or a file: the scan goes on without the render
            if not self._render_warned:
                self._render_warned = True
                log_warning(f"manual_3ds: the page render for the problem scan is off: {exc!r}")
            return {}
        return {key: {RENDER_IDS[kind]: detail for kind, detail in found.items() if kind in RENDER_IDS}
                for key, found in kinds.items()}

    def _render_later(self, block_idx: int) -> None:
        """Schedule a background render of the block (UI thread only): one thread per block at a time."""
        with self._render_lock:
            if block_idx in self._rendering:
                return
            self._rendering.add(block_idx)
        if self._rescan is None:
            self._rescan = _Rescan()
            self._rescan.block_done.connect(self._rescan_block)
        # ponytail: one daemon thread per block (18 manuals at most); a single queue if they ever thrash.
        threading.Thread(target=self._render_block, args=(block_idx,), name="manual_3ds-scan-render", daemon=True).start()

    def _render_block(self, block_idx: int) -> None:
        """Background: render every page of the block whose texts changed, then ask the host to rescan the block."""
        try:
            manual = self._manual(block_idx)
            if manual is None or not manual.name:
                return
            groups = sorted({group for group in (group_key_of(key) for key in manual.keys) if group})
            for group in groups:
                keys = [k for k in manual.keys if group_key_of(k) == group]
                try:
                    texts = self._page_texts(block_idx, manual, keys)
                except Exception as exc:  # the editor's data changed under the read: the next scan renders the page
                    log_warning(f"manual_3ds: {group} not rendered for the scan: {exc!r}")
                    continue
                if not any(texts.values()):
                    continue
                signature = tuple(sorted(texts.items()))
                cached = self._page_problems.get((block_idx, group))
                if cached is None or cached[0] != signature:
                    self._page_problems[(block_idx, group)] = (signature, self._render_page_problems(manual, group, keys, texts))
        finally:
            with self._render_lock:
                self._rendering.discard(block_idx)
        try:
            if self._rescan is not None:
                self._rescan.block_done.emit(block_idx)
        except RuntimeError:
            pass   # the rules were replaced while the render ran: nothing to rescan

    def _rescan_block(self, block_idx: int) -> None:
        scanner = getattr(self.mw, "issue_scan_handler", None)
        if scanner is not None:
            scanner.rescan_issues_for_single_block(block_idx, show_message_on_completion=False)

    def get_problem_detail(self, block_idx: int, string_idx: int, problem_id: str) -> str:
        """The layout message of one problem of the last analysed text of the paragraph."""
        return self._problem_details.get((block_idx, string_idx), {}).get(problem_id, "")

    def get_string_layout(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._entry(block_idx, string_idx)
        if found is None or not found[2].get("width"):
            return None
        meta = found[2]
        return {"max_width": int(round(float(meta["width"]))), "warn_width": int(round(float(meta["width"]))),
                "lines_per_page": int(meta.get("lines") or 1)}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._entry(block_idx, string_idx)
        if found is None:
            return {}
        _, key, meta = found
        part, _, page = key.partition("/")
        return {"content_role": "Manual text",
                "role_instruction": (f"Electronic manual, {part} text of page {page.split('#')[0]}: at most "
                                     f"{meta.get('lines')} lines of about {meta.get('width')} px. Keep every "
                                     "{i0}, {s1|...} and {br} marker.")}

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._entry(block_idx, string_idx)
        if found is None:
            return {}
        return {"scene": found[0].name or "Manual", "resource": found[1]}

    def calculate_string_width_override(self, text: str, font_map: dict, default_char_width: int = 8) -> Optional[int]:
        return None

    # -- live preview ---------------------------------------------------------------------

    def get_custom_preview_widget(self, main_window: Any) -> Optional[Any]:
        """The manual viewer preview (plugins/manual_3ds/preview_panel.py); needs the repo_manual folder to draw."""
        from plugins.manual_3ds.preview_panel import ManualPreviewPanel
        return ManualPreviewPanel(main_window, self)

    # The lookups below that need no geometry (string_key, strings_of_group, index_string_of_page) are cheap enough
    # for the UI thread; manual_name and preview_budget may read geometry.json once, so the preview calls them from
    # its worker.

    def manual_name(self, block_idx: int) -> str:
        manual = self._manual(block_idx)
        return (manual.name or "") if manual is not None else ""

    def manual_loaded(self, block_idx: int) -> bool:
        """Whether the block's manual is known (a session restored without plugin state knows none until the host
        has read the files)."""
        return 0 <= block_idx < len(self._manuals)

    def _keys_of(self, block_idx: int) -> List[str]:
        manuals = self._manuals  # one read (see _manual)
        return manuals[block_idx].keys if 0 <= block_idx < len(manuals) else []

    def string_key(self, block_idx: int, string_idx: int) -> Optional[str]:
        """The manual key ("large/Page_003_large_0#4") of a string, or None."""
        keys = self._keys_of(block_idx)
        return keys[string_idx] if 0 <= string_idx < len(keys) else None

    def strings_of_group(self, block_idx: int, group: str) -> Dict[str, int]:
        """{key: string index} of every paragraph of a page group, e.g. "large/Page_003_large"."""
        return {key: index for index, key in enumerate(self._keys_of(block_idx)) if group_key_of(key) == group}

    def index_string_of_page(self, block_idx: int, page: int) -> Optional[int]:
        """The string index of the Index entry that names a page ("index/Index#<page>"), or None."""
        keys = self._keys_of(block_idx)
        key = f"index/Index#{page}"
        return keys.index(key) if key in keys else None

    def preview_budget(self, block_idx: int, key: str) -> Optional[float]:
        """The column width a paragraph is drawn in on the console (from geometry.json), or None."""
        manual = self._manual(block_idx)
        geo = manual.geo.get(key) if manual is not None else None
        return geo.budget if geo is not None else None
