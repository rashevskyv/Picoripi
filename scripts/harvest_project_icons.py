"""Harvest project icons: take each game's icon from its own files into <project>\\picoripi\\icon.png.

Dry run by default: prints a table (project | source file | format | result). ``--apply`` writes icon.png next to
project.uiproj, only where no icon.png exists yet. Nothing else is written; game files are only read.

    python scripts/harvest_project_icons.py --registry <data>\\project_manager.json [--apply] [--table out.tsv]
    python scripts/harvest_project_icons.py --root E:\\Emulators\\RomHacking [--apply]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.game_icons import Icon, extract_icon  # noqa: E402
from core.project_library.icons import scale_image_bytes  # noqa: E402  the Project Manager's atomic PNG writer

PICOPRIPI_DIR, PROJECT_FILE, ICON_NAME = "picoripi", "project.uiproj", "icon.png"
PRUNE = {"source", "reports", "_tmp", "tools", "docs", "_reference", ".git", "__pycache__"}
MAX_DEPTH = 6
KEYED_EXTENSIONS = (".nsp", ".nsz", ".xci", ".cia", ".cxi", ".nca")
RU_TOKEN = re.compile(r"(^|[^a-z])(ru|rus|russian|ntsc_ru|kruptar|zelda64rus|vit)([^a-z]|$)", re.IGNORECASE)
EXE_DENY = ("unins", "7za", "ffmpeg", "apphost", "build-script", "snesrecomp", "kruptar", "yaz0enc", "config",
            "mgba", "duckstation", "ppsspp", "azahar", "dotnet", "setup", "launcher", "editor", "updater", "crash",
            "mednafen", "cemu", "dolphin", "redist", "uninstall", "tool", "analyze", "dxwebsetup", "installer",
            "extractor", "patcher", "ryujinx", "eden", "project64", "mupen", "retroarch", "emulator", "vc_")
IMAGE_NAMES = {"icon.png", "icon.jpg", "icon.jpeg", "cover.png", "cover.jpg", "boxart.png", "boxart.jpg",
               "appicon.png", "icon0.png"}
IMAGE_DENY_DIRS = {"graphics", "gfx", "src", "platform", "assets", "res", "docs"}

# priority: lower is tried first. Native icons come before banners, banners before images.
P_SMDH, P_NDS, P_NRO, P_PBP, P_TGA, P_BNR, P_DISC, P_EXE, P_CONTENTS, P_IMAGE = range(10)


@dataclass(frozen=True)
class Candidate:
    priority: int
    path: str


def _parts(rel: str) -> List[str]:
    return [p.lower() for p in re.split(r"[\\/]", rel) if p]


def collect(folder: str) -> Tuple[List[Candidate], List[str]]:
    """Icon source candidates of one project folder, best first, and the keyed files that are not read."""
    found: List[Candidate] = []
    blocked: List[str] = []
    for dirpath, dirnames, filenames in os.walk(folder):
        rel_dir = os.path.relpath(dirpath, folder)
        depth = 0 if rel_dir == "." else rel_dir.count(os.sep) + 1
        if depth >= MAX_DEPTH:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if d.lower() not in PRUNE]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, folder)
            parts = _parts(rel)
            low = name.lower()
            ext = os.path.splitext(low)[1]
            if ext in KEYED_EXTENSIONS:
                blocked.append(rel)
                continue
            if RU_TOKEN.search(rel):
                continue
            pri = _priority(parts, low, ext)
            if pri is not None:
                found.append(Candidate(pri, full))
    found.sort(key=lambda c: (c.priority, "build" not in c.path.lower(), len(c.path), c.path))
    return found, blocked


def _priority(parts: List[str], low: str, ext: str) -> Optional[int]:
    if low == "icon.bin" and "exefs" in parts and "update" not in parts:
        return P_SMDH
    if ext == ".smdh":
        return P_SMDH
    if ext == ".nds":
        return P_NDS
    if ext == ".nro" and "_reference" not in parts:
        return P_NRO
    if ext == ".pbp":
        return P_PBP
    if low == "opening.bnr":
        return P_BNR
    if ext in (".iso", ".gcm"):
        return P_DISC
    if low == "icontex.tga":
        return P_TGA
    if ext == ".exe":
        if any(word in low for word in EXE_DENY) or "tools" in parts or "emulator" in parts:
            return None
        return P_EXE
    if ext in (".png", ".jpg", ".jpeg") and "atmosphere" in parts and "contents" in parts and low == "icon.jpg":
        return P_CONTENTS
    if low in IMAGE_NAMES and len(parts) <= 5 and not IMAGE_DENY_DIRS.intersection(parts[:-1]):
        return P_IMAGE
    return None


def _is_square(path: str) -> bool:
    from PIL import Image
    with Image.open(path) as opened:
        width, height = opened.size
    return width >= 32 and 0.8 <= width / height <= 1.25


def harvest_one(folder: str) -> Tuple[Optional[Icon], str, str, List[str]]:
    """``(icon or None, source file, format, notes)`` for one project folder. Stops at the first icon."""
    candidates, blocked = collect(folder)
    notes: List[str] = []
    for candidate in candidates:
        rel = os.path.relpath(candidate.path, folder)
        try:
            if candidate.priority == P_IMAGE and not _is_square(candidate.path):
                notes.append(f"not square: {rel}")
                continue
            icon = extract_icon(candidate.path)
        except Exception as error:  # a bad game file must not stop the batch; the reason goes in the table
            notes.append(f"error {type(error).__name__}: {rel}")
            continue
        if icon is not None:
            return icon, rel, icon.format, notes
        notes.append(f"no icon: {rel}")
    if blocked:
        notes.append("keyed input not read (blocked): " + "; ".join(blocked[:3]))
    return None, "", "", notes


def load_projects(registry: Optional[str], root: Optional[str]) -> List[Tuple[str, str]]:
    """``(project folder, icon target)`` pairs from the registry, or from a scan of ``root``."""
    pairs: List[Tuple[str, str]] = []
    if registry:
        with open(registry, encoding="utf-8") as handle:
            data = json.load(handle)
        for entry in data.get("projects", []):
            uiproj = entry["path"]
            pairs.append((os.path.dirname(os.path.dirname(uiproj)), os.path.join(os.path.dirname(uiproj), ICON_NAME)))
        return pairs
    for dirpath, dirnames, filenames in os.walk(root):
        if os.path.basename(dirpath).lower() == PICOPRIPI_DIR and PROJECT_FILE in filenames:
            pairs.append((os.path.dirname(dirpath), os.path.join(dirpath, ICON_NAME)))
            dirnames[:] = []
        elif os.path.relpath(dirpath, root).count(os.sep) >= MAX_DEPTH:
            dirnames[:] = []
    return pairs


def write_icon(icon: Icon, target: str) -> None:
    """Write the PNG next to project.uiproj with the Project Manager's writer (atomic). Native size: no resampling."""
    buffer = io.BytesIO()
    icon.image.save(buffer, format="PNG")
    if not scale_image_bytes(buffer.getvalue(), Path(target), max(icon.image.size)):
        raise OSError(f"cannot write {target}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--registry", help="project_manager.json of the Project Manager")
    group.add_argument("--root", help="folder to scan for picoripi\\project.uiproj")
    parser.add_argument("--apply", action="store_true", help="write icon.png (default: dry run)")
    parser.add_argument("--table", help="also write the table as TSV to this file")
    args = parser.parse_args(argv)

    pairs = load_projects(args.registry, args.root)
    if not pairs:
        print("no project found", file=sys.stderr)
        return 1
    base = args.root or os.path.commonpath([folder for folder, _target in pairs])
    rows: List[List[str]] = []
    counts: Dict[str, int] = {}
    for folder, target in pairs:
        label = os.path.relpath(folder, base)
        if not os.path.isdir(folder):
            rows.append([label, "", "", "missing folder"])
            continue
        if os.path.exists(target):
            rows.append([label, "", "", "skip: icon.png exists"])
            continue
        icon, source, fmt, notes = harvest_one(folder)
        if icon is None:
            rows.append([label, "", "", "none: " + ("; ".join(notes) or "no candidate file")])
            counts["none"] = counts.get("none", 0) + 1
            continue
        result = f"{icon.image.width}x{icon.image.height}"
        if args.apply:
            write_icon(icon, target)
            result += " written"
        else:
            result += " (dry run)"
        rows.append([label, source, fmt, result])
        counts[fmt] = counts.get(fmt, 0) + 1

    lines = ["\t".join(["project", "source file", "format", "result"])]
    lines += ["\t".join(row) for row in rows]
    print("\n".join(lines))
    if args.table:
        with open(args.table, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    print("\nCounts by format:", json.dumps(counts, indent=1, sort_keys=True), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
