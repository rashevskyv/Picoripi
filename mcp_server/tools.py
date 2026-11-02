"""The tools of the MCP server as plain functions: no MCP types, no Qt, no window. Read only.

The server reads files on disk. Edits that sit unsaved in a running Picoripi window are not visible here.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.project_library import registry
from core.project_library.plugin_facts import default_load_rules
from utils.constants import SETTINGS_DIR
from utils.logging_utils import log_debug

ISSUES_CACHE_NAME = "issues_cache.json"


def list_projects(data_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Every project in the Project Manager registry: path, id, platform, whether the file exists."""
    document = registry.read(data_dir or SETTINGS_DIR, set_aside=False)
    return [
        {
            "path": entry.get("path", ""),
            "id": entry.get("id", ""),
            "platform": entry.get("platform", ""),
            "exists": os.path.isfile(entry.get("path", "")),
        }
        for entry in document.get("projects", [])
    ]


def issue_rules(plugin: str) -> Dict[str, Dict[str, Any]]:
    """The problem definitions of a game plugin: id -> definition (name, description, severity as the plugin gives it)."""
    rules = default_load_rules(plugin)
    return {pid: dict(definition) for pid, definition in rules.get_problem_definitions().items()}


def _project_dir(project: str) -> Path:
    path = Path(project)
    return path.parent if path.suffix.lower() == ".uiproj" else path


def issue_summary(project: str, block: Optional[int] = None, problem: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
    """What the project's last issue scan found, read from ``issues_cache.json``. Never rescans, never writes.

    ``block`` and ``problem`` filter the listed items; the counts always cover the whole project.
    """
    cache_path = _project_dir(project) / ISSUES_CACHE_NAME
    if not cache_path.is_file():
        return {"source": "none", "reason": f"{ISSUES_CACHE_NAME} not found; open the project in Picoripi once", "path": str(cache_path)}
    with cache_path.open("r", encoding="utf-8") as handle:
        cache = json.load(handle)
    by_problem: Counter = Counter()
    by_block: Counter = Counter()
    items: List[Dict[str, Any]] = []
    for block_key, entries in (cache.get("problems") or {}).items():
        for string_idx, subline_idx, ids in entries:
            by_problem.update(ids)
            by_block[block_key] += len(ids)
            if block is not None and int(block_key) != block:
                continue
            for pid in ids:
                if problem is None or pid == problem:
                    items.append({"block": int(block_key), "string": string_idx, "subline": subline_idx, "problem": pid})
    return {
        "source": "cached",
        "cache_mtime": cache_path.stat().st_mtime,
        "plugin_id": (cache.get("settings") or {}).get("plugin_id"),
        "total": sum(by_problem.values()),
        "by_problem": dict(by_problem.most_common()),
        "by_block": dict(by_block.most_common()),
        "items": items[:limit],
        "truncated": len(items) > limit,
    }


class _FitProject:
    """What a fit check needs from one project, read once: rules, settings, translation fonts, source BMGs."""

    def __init__(self, project: Path):
        from core.bfn_core import BfnCore
        from core.font_formats.sources import resolve
        from utils.constants import user_plugin_file_or_shipped

        document = json.loads(project.read_text(encoding="utf-8"))
        self.metadata = document.get("metadata") or {}
        self.blocks = document.get("blocks") or []
        self.plugin = document.get("plugin_name") or "default_plugin"
        self.rules = default_load_rules(self.plugin)
        settings_path = project.parent / "project_settings.json"
        self.settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.is_file() else {}
        # The editor reads the project's translation map first, then the plugin's (font_map_loader).
        map_path = project.parent / "translation_map.json"
        if not map_path.is_file():
            map_path = user_plugin_file_or_shipped(self.plugin, "translation_map.json")
        translation_map = json.loads(map_path.read_text(encoding="utf-8")) if map_path.is_file() else {}
        sources_path = user_plugin_file_or_shipped(self.plugin, "font_sources.json")
        descriptors = json.loads(sources_path.read_text(encoding="utf-8")) if sources_path.is_file() else []
        self.font_maps: Dict[str, Dict[str, Any]] = {}
        for source in resolve([d for d in descriptors if d.get("format") == "bfn"], self.metadata):
            try:
                font = BfnCore()
                font.load(source.read_current())
            except (OSError, ValueError, KeyError, IndexError) as error:
                log_debug(f"check_fit: font {source.label} skipped: {error}")
                continue
            self.font_maps.setdefault(Path(source.member or source.name).name, font.to_font_map(translation_map or None))
        self._bmgs: Dict[int, Any] = {}

    def source_bmg(self, block: int):
        """The original BMG behind a block (archive member or file), parsed once; None when it cannot be read."""
        if block in self._bmgs:
            return self._bmgs[block]
        from core.containers.container_manager import ContainerManager
        from plugins.zelda_bmg.bmg_tool import BMGFile

        bmg = None
        meta = (self.blocks[block].get("metadata") or {}) if 0 <= block < len(self.blocks) else {}
        if meta.get("is_archive_member"):
            try:
                container = ContainerManager.open((Path(self.metadata.get("source_path", "")) / meta["archive_rel_path"]).read_bytes())
                bmg = BMGFile()
                bmg.load(container.read_file(meta["archive_file_name"]))
            except (OSError, ValueError, KeyError, AttributeError) as error:
                log_debug(f"check_fit: block {block} source not read: {error}")
                bmg = None
        self._bmgs[block] = bmg
        return bmg


_FIT_CACHE: Dict[str, _FitProject] = {}


def check_fit(project: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Measure translated strings as the editor does: width of every line in the translation font against the
    window of that message, line count against lines per page, the plugin's problem rules and the tag check.

    ``items``: ``[{"block": 0, "string": 12, "text": "..."}]``. Reads files only; the open window is not used.
    """
    from handlers.analyzer_context import analyzer_string_context
    from utils.width import calculate_string_width, resolve_width_limits

    key = str(Path(project).resolve())
    fit = _FIT_CACHE.get(key)
    if fit is None:
        fit = _FIT_CACHE[key] = _FitProject(Path(project))
    rules = fit.rules
    analyzer = getattr(rules, "problem_analyzer", rules)
    definitions = rules.get_problem_definitions()
    default_warn = int(fit.settings.get("line_width_warning_threshold_pixels") or 280)
    default_max = int(fit.settings.get("game_dialog_max_width_pixels") or 300)
    default_lines = int(fit.settings.get("lines_per_page") or 0)
    first_font = next(iter(fit.font_maps.values()), {})
    results = []
    for item in items:
        block, string, text = int(item["block"]), int(item["string"]), str(item.get("text", ""))
        bmg = fit.source_bmg(block)
        source = ""
        if bmg is not None:
            # The plugin reads message attributes from its last loaded BMG when it has no window (single-file mode).
            rules.last_loaded_bmg = bmg
            getattr(rules, "_bmg_block_resolve_cache", {}).pop(block, None)
            if 0 <= string < len(bmg.messages):
                source = rules.msg_to_editor_text(bmg.messages[string]) if hasattr(rules, "msg_to_editor_text") else ""
        layout = (rules.get_string_layout(block, string) if hasattr(rules, "get_string_layout") else None) or {}
        warn, hard = resolve_width_limits({}, rules, block, string, default_warn, default_max)
        font_map = fit.font_maps.get(str(layout.get("font_file") or ""), first_font)
        lines = []
        for line in text.split("\n"):
            width = rules.calculate_string_width_override(line, font_map) if hasattr(rules, "calculate_string_width_override") else None
            if width is None:
                width = calculate_string_width(line, font_map)
            lines.append({"text": line, "px": int(width), "over_warn": width > warn, "over_max": width > hard})
        with analyzer_string_context(analyzer, block, string):
            sublines = analyzer.analyze_data_string(text, font_map, warn, hard) or []
        found = sorted({pid for subline in sublines for pid in subline})
        if source and analyzer.check_tags_mismatch(source, text) is True:
            found.append(getattr(analyzer.problem_ids, "PROBLEM_TAG_WARNING", "TAG_WARNING"))
        lines_per_page = int(layout.get("lines_per_page") or default_lines)
        results.append({
            "block": block, "string": string, "warn_width": warn, "max_width": hard, "lines_per_page": lines_per_page,
            "lines": lines, "ok": not found and not any(line["over_max"] for line in lines),
            "problems": [{"id": pid, "name": (definitions.get(pid) or {}).get("name", "")} for pid in found],
        })
    return {"source": "fresh", "width_checked": bool(fit.font_maps), "items": results}


def scan_string(plugin: str, text: str, source_text: str = "", width_threshold: int = 280) -> Dict[str, Any]:
    """Check one translated string with the plugin's rules.

    Width is not measured: it needs the project's font map, which this server does not load. The tag check and
    the plugin rules that do not need a font run as in the editor.
    """
    rules = default_load_rules(plugin)
    analyzer = rules.problem_analyzer
    sublines = analyzer.analyze_data_string(text, {}, width_threshold, None) or []
    found = sorted({pid for subline in sublines for pid in subline})
    if source_text and analyzer.check_tags_mismatch(source_text, text) is True:
        found.append(getattr(analyzer.problem_ids, "PROBLEM_TAG_WARNING", "TAG_WARNING"))
    definitions = rules.get_problem_definitions()
    return {
        "source": "fresh",
        "width_checked": False,
        "problems": [{"id": pid, "definition": definitions.get(pid, {})} for pid in found],
    }
