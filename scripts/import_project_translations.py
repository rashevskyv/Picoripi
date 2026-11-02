"""Import a translation map into a Picoripi project without opening the window. Dry run unless --apply.

    python scripts/import_project_translations.py --project <project.uiproj> --lines <lines.json> --map <map.json> [--apply]

--lines is {id: {"id", "en", "file"}}. --map is {"translations": {id: text}} or {id: text}. With --apply the project
file is first copied to <project folder>\\data\\backups. The report is printed as JSON; exit code 1 when a line was
refused (see "problems").
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.project_library.translation_import import import_translations  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Import translations into a project's translation files.")
    parser.add_argument("--project", required=True, help="path to project.uiproj")
    parser.add_argument("--lines", required=True, help="lines file: {id: {id, en, file}}")
    parser.add_argument("--map", required=True, help="translations: {translations: {id: text}} or {id: text}")
    parser.add_argument("--apply", action="store_true", help="write the translation files (default: dry run)")
    args = parser.parse_args(argv)
    lines = json.loads(Path(args.lines).read_text(encoding="utf-8"))
    loaded = json.loads(Path(args.map).read_text(encoding="utf-8"))
    translations = loaded.get("translations", loaded)
    report = import_translations(args.project, lines, translations, apply=args.apply)
    report["mode"] = "apply" if args.apply else "dry run"
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
