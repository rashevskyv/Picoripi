"""MCP server (stdio) over ``mcp_server.tools``. Start with ``python -m mcp_server``."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.mcpserver import MCPServer

from mcp_server import tools

mcp = MCPServer(
    "picoripi",
    instructions="Picoripi projects, read from files on disk; unsaved edits in an open Picoripi window are not visible. "
                 "Every tool reads only, except write_translations and import_font. ask_ai sends a prompt to the AI provider Picoripi "
                 "translates with; translate_strings translates project strings the way Picoripi does.",
)


@mcp.tool()
def list_projects() -> List[Dict[str, Any]]:
    """List the projects in the Picoripi Project Manager (path, id, platform)."""
    return tools.list_projects()


@mcp.tool()
def get_issue_rules(plugin: str) -> Dict[str, Dict[str, Any]]:
    """Problem rules of a game plugin, e.g. plugin="zelda_mc". Maps problem id to its definition."""
    return tools.issue_rules(plugin)


@mcp.tool()
def list_issues(project: str, block: Optional[int] = None, problem: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
    """Issues from the last scan of a project (cached; `source` and `cache_mtime` tell how fresh). `project` is the .uiproj path."""
    return tools.issue_summary(project, block, problem, limit)


@mcp.tool()
def check_fit(project: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Measure translated strings in the project's translation font: px per line against the message's window,
    lines per page, plugin problem rules, tags. `items` = [{"block": 0, "string": 12, "text": "..."}]."""
    return tools.check_fit(project, items)


@mcp.tool()
def scan_string(plugin: str, text: str, source_text: str = "") -> Dict[str, Any]:
    """Check one translated string with a plugin's rules (tags, spacing, ...). Width is not measured."""
    return tools.scan_string(plugin, text, source_text)


@mcp.tool()
def get_string_context(project: str, block: int, string: int) -> Dict[str, Any]:
    """Full translation context for one game string: story structure, speaker, neighbours, existing translation. `project` is the .uiproj path."""
    return tools.string_context(project, block, string)


@mcp.tool()
def ask_ai(prompt: str, system: str = "") -> Dict[str, Any]:
    """Send one prompt to the AI provider Picoripi translates with (Settings -> AI Translation, e.g. the Gemini proxy)
    and return its reply text. Use it for bulk text work (UI strings, drafts) instead of the agent's own model."""
    return tools.ask_ai(prompt, system)


@mcp.tool()
def translate_strings(project: str, block: int, strings: Optional[List[int]] = None) -> Dict[str, Any]:
    """Translate strings of one block with Picoripi's own AI block translation: the same system prompt, glossaries,
    story and speaker context, tag protection, review and reply checks. Writes nothing; returns
    {provider, model, rows: [{block, string, source, text}], errors}. `project` is the .uiproj path; `strings` are
    string numbers of the block (all when omitted). Write the rows you keep with write_translations."""
    from mcp_server import translate
    return translate.translate_strings(project, block, strings)


@mcp.tool()
def write_translations(project: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Write translations into a project: `items` are {block, string, text}. Picoripi's save of chosen strings writes
    the translation files and the session. Close the project in Picoripi first: an open window does not see the
    change and overwrites it with its next save."""
    from mcp_server import translate
    return translate.write_translations(project, items)


@mcp.tool()
def list_fonts(project: str) -> List[Dict[str, Any]]:
    """The project's bitmap fonts: label, format, file. `project` is the .uiproj path."""
    return tools.list_fonts(project)


@mcp.tool()
def export_font(project: str, label: str, out_dir: str) -> Dict[str, Any]:
    """Write a font's sheets as PNG into `out_dir` (sheet_<n>.png = the translation, original_<n>.png = the game's
    own) and return the cell size and each character's cell {sheet, x, y}. Edit sheet_<n>.png, then import_font."""
    return tools.export_font(project, label, out_dir)


@mcp.tool()
def import_font(project: str, label: str, in_dir: str) -> Dict[str, Any]:
    """Write the edited sheet_<n>.png of `in_dir` (same sizes as exported) into the font's translation file.
    Close that font in Picoripi's font editor first."""
    return tools.import_font(project, label, in_dir)
