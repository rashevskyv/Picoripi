"""The MCP server: tool functions on a fixture project, and one real stdio round trip."""
import asyncio
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")
from mcp import Client, StdioServerParameters

from mcp_server import tools

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    cache = {
        "settings": {"plugin_id": "Default"},
        "problems": {"0": [[1, 0, ["DEFAULT_SHORT_LINE", "DEFAULT_BAD_SPACING"]], [2, 0, ["DEFAULT_SHORT_LINE"]]],
                     "3": [[0, 1, ["DEFAULT_TAG_WARNING"]]]},
    }
    (tmp_path / "issues_cache.json").write_text(json.dumps(cache), encoding="utf-8")
    return tmp_path / "project.uiproj"


def test_issue_summary_counts_and_filters(project):
    summary = tools.issue_summary(str(project))
    assert summary["source"] == "cached"
    assert summary["total"] == 4
    assert summary["by_problem"]["DEFAULT_SHORT_LINE"] == 2
    assert summary["by_block"] == {"0": 3, "3": 1}
    only_block = tools.issue_summary(str(project), block=3)
    assert only_block["items"] == [{"block": 3, "string": 0, "subline": 1, "problem": "DEFAULT_TAG_WARNING"}]
    assert tools.issue_summary(str(project), limit=1)["truncated"] is True


def test_issue_summary_without_cache(tmp_path):
    assert tools.issue_summary(str(tmp_path / "project.uiproj"))["source"] == "none"


def test_scan_string_reports_tag_mismatch():
    result = tools.scan_string("default_plugin", "Привіт", source_text="Hi {x}")
    assert [p["id"] for p in result["problems"]] == ["DEFAULT_TAG_WARNING"]
    assert result["width_checked"] is False


def test_issue_rules_lists_definitions():
    assert "DEFAULT_TAG_WARNING" in tools.issue_rules("default_plugin")


def test_stdio_round_trip(project):
    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server"], cwd=ROOT)
        async with Client(params) as client:
            names = {tool.name for tool in (await client.list_tools()).tools}
            result = await client.call_tool("list_issues", {"project": str(project)})
            return names, result.structured_content

    names, content = asyncio.run(run())
    assert names == {"list_projects", "get_issue_rules", "list_issues", "scan_string"}
    assert content["result"]["total"] == 4 and content["result"]["source"] == "cached"
