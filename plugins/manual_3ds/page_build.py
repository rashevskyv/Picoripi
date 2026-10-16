"""Builds a manual page from the current texts the way the console build does, and judges it (no Qt here).

The preview panel and the editor's problem scan both come here: ``build_page`` lays the texts out with the owner's
tools on the page's own BCLYT files (as the console build writes them), ``simulator.render_page`` draws the files,
``simulator.page_defects`` judges them, and ``page_kinds`` hands each defect to the string that owns its pane. The
owner's archives, paragraphs, textures and indexes are read once per folder and manual.
"""
from __future__ import annotations

import copy
import json
import threading
from typing import Any, Callable, Dict, List, Tuple

from plugins.manual_3ds import console_render as cr
from plugins.manual_3ds import repo_tools, simulator

PLUGIN_NAME = "manual_3ds"
SETTINGS_FILE = "preview.json"
# The defect kinds only a render can see, and the editor problem each one is reported as (config.CUSTOM_PROBLEMS).
RENDER_PROBLEMS = {"over_cell": "CELL", "text_overlap": "OVERLAP", "covered": "COVERED"}

_GROUPS_LOCK = threading.Lock()
_ARCHIVES: Dict[Tuple[str, str], Any] = {}
_FLOWS: Dict[Tuple[str, str], Dict[str, List[Any]]] = {}
_TEXTURES: Dict[Tuple[str, str], cr.Textures] = {}
_INDEXES: Dict[Tuple[str, str], cr.Index] = {}
RENDER_LOCK = threading.Lock()   # the owner's layout model keeps per-flow state: one page build at a time


def load_folder() -> str:
    """The repo_manual folder the user chose, or "" (per user, outside the repository). Reads the disk."""
    from utils.constants import user_plugin_dir   # the user data folder: resolved when asked, not at import

    try:
        data = json.loads((user_plugin_dir(PLUGIN_NAME) / SETTINGS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    value = data.get("repo_manual", "") if isinstance(data, dict) else ""
    return value if isinstance(value, str) else ""


def save_folder(folder: str) -> None:
    from utils.atomic_io import atomic_write_json
    from utils.constants import user_plugin_dir

    target = user_plugin_dir(PLUGIN_NAME)
    target.mkdir(parents=True, exist_ok=True)
    atomic_write_json(target / SETTINGS_FILE, {"repo_manual": folder}, indent=2, ensure_ascii=False)


def archive_of(tools: Any, manual_name: str) -> Any:
    """The manual's archive, read once per folder. Called from a worker only."""
    key = (str(tools.root), manual_name)
    with _GROUPS_LOCK:
        if key not in _ARCHIVES:
            _ARCHIVES[key] = tools.bcma.load(repo_tools.manual_path(tools, manual_name))
        return _ARCHIVES[key]


def flows_of(tools: Any, manual_name: str) -> Dict[str, List[Any]]:
    """The owner's paragraphs of every page ({"small/Page_003_small_0": [Flow, ...]}), once per manual."""
    key = (str(tools.root), manual_name)
    archive = archive_of(tools, manual_name)
    with _GROUPS_LOCK:
        if key not in _FLOWS:
            _FLOWS[key] = tools.manual.pages_of(archive, tools.manual.BASE_SLOT)
        return _FLOWS[key]


def textures_of(tools: Any, manual_name: str) -> cr.Textures:
    key = (str(tools.root), manual_name)
    archive = archive_of(tools, manual_name)
    with _GROUPS_LOCK:
        if key not in _TEXTURES:
            files: Dict[str, bytes] = {}
            for member in ("Common_texture", f"{tools.manual.BASE_SLOT}_texture"):
                try:
                    files.update(archive.read(member))
                except KeyError:
                    pass
            _TEXTURES[key] = cr.Textures(files)
        return _TEXTURES[key]


def index_of(tools: Any, manual_name: str) -> cr.Index:
    key = (str(tools.root), manual_name)
    archive = archive_of(tools, manual_name)
    with _GROUPS_LOCK:
        if key not in _INDEXES:
            _INDEXES[key] = cr.read_index(archive.read(f"{tools.manual.BASE_SLOT}_index")["Index.bclyt"])
        return _INDEXES[key]


class RenderCancelled(Exception):
    """The caller asked the render to stop."""


def _never() -> bool:
    return False


def build_page(tools: Any, archive: Any, flows_by_key: Dict[str, List[Any]], part: str, page: int, texts: Dict[str, str],
               budgets: Dict[str, Any], should_stop: Callable[[], bool]) -> Tuple[List[bytes], Dict[str, str], Dict[str, str]]:
    """The page's BCLYT files with the current texts laid out on them, as the console build writes them.

    -> (files in draw order, pane name -> string key, string key -> layout error). A paragraph the owner's layout
    cannot place keeps the stored text (the console build would stop; the panel shows the page anyway).
    Byte-identical to the owner's build: every page of tmp/cand_r19 built from src/manuals (2026-10-15).
    """
    manual = tools.manual
    slot = manual.BASE_SLOT
    files = archive.read(f"{slot}_{part}")
    widths = repo_tools.widths_of(tools)
    table = manual.load_homoglyphs()
    out: List[bytes] = []
    owners: Dict[str, str] = {}
    failed: Dict[str, str] = {}
    backdrop = files.get(f"Page_{page:03d}_{part}_bg.bclyt")
    if backdrop is not None:
        out.append(backdrop)
    prefix = f"Page_{page:03d}_{part}_"
    subs = sorted((name for name in files if name.startswith(prefix) and name[len(prefix):-6].isdigit()),
                  key=lambda name: int(name[len(prefix):-6]))
    for file_name in subs:
        if should_stop():
            raise RenderCancelled()
        data = files[file_name]
        page_key = f"{part}/{file_name.removesuffix('.bclyt')}"
        edits: Dict[str, Any] = {}
        for index, flow in enumerate(flows_by_key.get(page_key, [])):
            key = f"{page_key}#{index}"
            for pane in flow.panes:
                owners[pane.name] = key
            text = texts.get(key)
            if not text:
                continue
            try:
                # The build's own steps on a copy: mark_panes_out reassigns the copy's lines (the shared flow
                # keeps its panes for the next render).
                laid = copy.copy(flow)
                manual.mark_panes_out(laid, text)
                rendered = manual.apply_homoglyphs(text, table)
                budget = budgets.get(key)
                limit = (float(budget) if budget else cr.COLUMN_WIDTH) + manual.WIDTH_SLACK
                lines = manual.layout_for(rendered, laid, limit, widths)
                edits.update(manual.to_edits(lines, laid))
            except Exception as exc:  # the owner's layout refuses the text: the page keeps the stored text there
                failed[key] = repr(exc)
        out.append(tools.bclyt.rewrite(data, edits) if edits else data)
    return out, owners, failed


def page_kinds(tools: Any, manual_name: str, part: str, page: int, texts: Dict[str, str],
               budgets: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str]]:
    """{string key: {defect kind: detail}} of one page built from `texts` and drawn once, plus the layout failures.

    What the editor's problem scan reports for the page's strings is what the preview draws: both call this
    build and ``simulator.page_defects``. The detail is the first flagged line's (the translator shortens by it).
    """
    archive = archive_of(tools, manual_name)
    flows = flows_of(tools, manual_name)
    with RENDER_LOCK:
        files, owners, failed = build_page(tools, archive, flows, part, page, texts, budgets, _never)
    if not files:
        return {}, failed
    textures = textures_of(tools, manual_name)
    rendered = simulator.render_page(files, textures, cr.Glyphs(repo_tools.load_font(tools), tools.bcfnt))
    number = index_of(tools, manual_name).number_of(page)
    out: Dict[str, Dict[str, str]] = {}
    for defect in simulator.page_defects(rendered, textures, manual_name, number, f"Page_{page:03d}", part):
        key = owners.get(defect.pane)
        if key is not None:
            out.setdefault(key, {}).setdefault(defect.kind, f"{defect.text[:40]!r}: {defect.detail}")
    return out, failed
