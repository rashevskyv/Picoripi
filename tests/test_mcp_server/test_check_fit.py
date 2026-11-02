"""check_fit: width, window limits and tags of translated strings, read from the project files (no MCP needed)."""
import json
import shutil
from pathlib import Path

from mcp_server import tools

ROOT = Path(__file__).resolve().parents[2]


def test_check_fit_measures_lines_against_the_message_window(tmp_path):
    shutil.copy(ROOT / "tests/fixtures/review_queue/wp5/tp_save/synthetic_source.arc", tmp_path / "bmgres.arc")
    block = {"name": "zel_rq", "metadata": {"is_archive_member": True, "archive_rel_path": "bmgres.arc", "archive_file_name": "zel_rq.bmg"}}
    document = {"plugin_name": "zelda_bmg", "metadata": {"source_path": str(tmp_path)}, "blocks": [block]}
    (tmp_path / "project.uiproj").write_text(json.dumps(document), encoding="utf-8")
    items = [
        {"block": 0, "string": 3, "text": "Табличка: джерело Ордона"},
        {"block": 0, "string": 3, "text": "Ш" * 60},
        {"block": 0, "string": 4, "text": "Ти отримав рогатку!"},  # the source has colour tags
    ]
    result = tools.check_fit(str(tmp_path / "project.uiproj"), items)["items"]
    assert result[0]["problems"] == []
    assert result[0]["max_width"] > 0 and len(result[0]["lines"]) == 1
    assert result[1]["lines"][0]["over_max"] is True and result[1]["ok"] is False
    assert "ZBMG_TAG_WARNING" in [problem["id"] for problem in result[2]["problems"]]
