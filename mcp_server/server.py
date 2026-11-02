"""MCP server (stdio) over ``mcp_server.tools``. Start with ``python -m mcp_server``."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.mcpserver import MCPServer

from mcp_server import tools

mcp = MCPServer(
    "picoripi",
    instructions="Read-only view of Picoripi projects. Data comes from files on disk; unsaved edits in an open Picoripi window are not visible.",
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
