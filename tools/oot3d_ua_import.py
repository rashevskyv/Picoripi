"""Import a translator's Ocarina of Time 3D (EU) package into a Picoripi workspace's ``translation\\romfs``.

    python tools/oot3d_ua_import.py --workspace <ws> --sheet <translation.json> [--package <Luma.zip>] [--dry-run]

- ``--sheet``: the translator's sheet as JSON (``{"values": [...]}``, row 1 is the header).
- ``eu.qm``: the English slot of the game's ``message/eu/eu.qm`` (``<ws>\\source\\romfs``) is replaced with the sheet
  text. The file must equal the package's own ``eu.qm`` when ``--package`` is given.
- ``--package``: a LayeredFS zip (``luma/titles/<TitleID>/romfs/...``). Every romfs file in it that differs from
  the workspace's original is written to ``<ws>\\translation\\romfs\\<same path>``. Files identical to the original
  are skipped (``zt build`` ignores them anyway).

The workspace's original files are read from ``source\\romfs`` first, then ``romfs``. Nothing else is deleted or
changed. The import writes a JSON report next to the workspace (``reports\\oot3d_ua_import.json``).
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugins.zelda_oot3d import sheet_import  # noqa: E402  (needs the repo root on sys.path)

TITLE_ID = "0004000000033600"
PACKAGE_PREFIX = f"luma/titles/{TITLE_ID}/romfs/"
EU_QM = "message/eu/eu.qm"
LAYOUT_CODES = frozenset({"NL", "CENTER"})     # line breaks and centring: the translator adds them freely


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.remove(temp)
        raise


def _original(workspace: Path, rel: str) -> Optional[bytes]:
    for base in (workspace / "source" / "romfs", workspace / "romfs"):
        path = base / rel
        if path.is_file():
            return path.read_bytes()
    return None


def _functional(changes: List[dict]) -> List[dict]:
    """Messages whose control codes differ apart from line breaks and centring."""
    out = []
    for change in changes:
        english = collections.Counter(c.split(":")[0] for c in change["english"] if c.split(":")[0] not in LAYOUT_CODES)
        ukrainian = collections.Counter(c.split(":")[0] for c in change["ukrainian"] if c.split(":")[0] not in LAYOUT_CODES)
        if english != ukrainian:
            out.append({"id": change["id"], "english": change["english"], "ukrainian": change["ukrainian"]})
    return out


def run(workspace: Path, sheet_path: Path, package: Optional[Path], dry_run: bool) -> dict:
    sheet = json.loads(sheet_path.read_text(encoding="utf-8"))
    source_qm = _original(workspace, EU_QM)
    if source_qm is None:
        raise SystemExit(f"No {EU_QM} in {workspace / 'source' / 'romfs'}: run 1_unpack.bat first.")
    result = sheet_import.build_eu_qm(source_qm, sheet)
    problems = sheet_import.check_editor_readable(result.data)
    if problems:
        raise SystemExit(f"The plugin cannot read the new eu.qm: {problems[:5]}")

    files: Dict[str, bytes] = {EU_QM: result.data}
    report: dict = {
        "sheet": str(sheet_path), "sheet_sha256": _sha256(sheet_path.read_bytes()),
        "messages": len(sheet["values"]) - 1, "translated": result.translated,
        "fallback_ids": [f"0x{i:08X}" for i in result.fallback_ids], "repaired_ids": result.repaired_ids,
        "code_changes_all": len(result.code_changes),
        "code_changes_functional": _functional(result.code_changes),
        "package": None, "written": [], "same_as_original": [], "dry_run": dry_run,
    }
    if package is not None:
        with zipfile.ZipFile(package) as archive:
            report["package"] = {"path": str(package), "sha256": _sha256(package.read_bytes()), "romfs_files": 0}
            for info in archive.infolist():
                if not info.filename.startswith(PACKAGE_PREFIX) or info.is_dir():
                    continue
                rel = info.filename[len(PACKAGE_PREFIX):]
                report["package"]["romfs_files"] += 1
                data = archive.read(info)
                if rel == EU_QM:
                    report["package"]["eu_qm_equal"] = data == result.data
                    continue
                files[rel] = data
    translation = workspace / "translation" / "romfs"
    for rel in sorted(files):
        data = files[rel]
        original = _original(workspace, rel)
        if original == data:
            report["same_as_original"].append(rel)
            continue
        if not dry_run:
            _atomic_write(translation / rel, data)
        report["written"].append(rel)
    report["written_count"] = len(report["written"])
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--sheet", required=True, type=Path)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    report = run(args.workspace, args.sheet, args.package, args.dry_run)
    target = args.report or args.workspace / "reports" / "oot3d_ua_import.json"
    if not args.dry_run:
        _atomic_write(target, (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({k: v for k, v in report.items() if k not in ("code_changes_functional",)}, ensure_ascii=False,
                     indent=2))
    print(f"functional code changes: {len(report['code_changes_functional'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
