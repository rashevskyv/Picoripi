"""Validate a MemPalace alignment report against TP BMG dialogue flows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bmg_tool import BMGFile
from core.mempalace.flow_validation import validate_flow_alignment
from core.project_manager import ProjectManager


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alignment-report", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    alignment = json.loads(args.alignment_report.read_text(encoding="utf-8"))
    manager = ProjectManager(args.project)
    blocks = []
    for block in manager.project.blocks:
        metadata = block.metadata or {}
        if metadata.get("is_archive_member"):
            container = manager.get_archive_container(
                metadata["archive_rel_path"], is_translation=False
            )
            raw = container.read_file(metadata["archive_file_name"])
        else:
            raw = Path(manager.get_absolute_path(block.source_file)).read_bytes()
        bmg = BMGFile()
        bmg.load(raw)
        blocks.append((block.name, bmg))

    report = validate_flow_alignment(alignment, blocks)
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    print(rendered)
    if args.json_out:
        args.json_out.write_text(rendered, encoding="utf-8")
    return 0 if report["acceptance"]["passed"] and report["integrity_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
