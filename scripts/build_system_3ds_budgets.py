"""Write plugins/system_3ds/budgets.json from decrypted 3DS system titles and the owner's 3ds-ua tools.

    python scripts/build_system_3ds_budgets.py <nand_dec folder> <3ds-ua repo folder> [--out FILE]

<nand_dec folder> holds the decrypted titles as <tid high>/<tid low>/content/*.app (NoCrypto NCCH, lowercase ids).
Each title's romfs is unpacked into a temporary folder (deleted at the end); nothing is written into either folder.
The budgets are the owner's own (its tools/validate.py, imported read-only, no bytecode): per MSBT label the widest
official localisation (label_budgets, with its budget_groups and budget_px) and its line count (the most lines of any
official localisation), per layout pane the widest line of the languages the mod does not take (validate_layouts), and per country or region file (areas)
the widest name of the file's own archive (validate_area). The file holds numbers and identifiers only, no game text.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.containers.n3ds import N3dsImage  # noqa: E402

DEFAULT_OUT = os.path.join(ROOT, "plugins", "system_3ds", "budgets.json")
AREA_TID = "0004009B00010402"  # the `area` archive: country and region names (validate_area)


def unpack_romfs(content_dir: Path, dest: Path) -> bool:
    """The romfs of the title's program (the .app with exefs/code.bin, else the one with the most romfs files)."""
    best = None
    for app in sorted(content_dir.glob("*.app")):
        with open(app, "rb") as handle:
            paths = [entry.path for entry in N3dsImage(handle).entries()]
        rank = ("exefs/code.bin" in paths, sum(path.startswith("romfs/") for path in paths))
        if rank[1] and (best is None or rank > best[0]):
            best = (rank, app)
    if best is None:
        return False
    with open(best[1], "rb") as handle:
        image = N3dsImage(handle)
        for entry in image.entries():
            if entry.path.startswith("romfs/"):
                target = dest / entry.path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(image.read(entry))
    return True


def build(nand_dec: Path, repo: Path, work: Path) -> dict:
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(repo / "tools"))
    import bclyt  # noqa: E402  (the owner's tools)
    import darc
    import lz10
    import lz11
    import validate

    widths = validate.load_widths()  # read from the repo before ROOT points at the unpacked titles
    validate.ROOT = work
    labels, lines, panes, missing = {}, {}, {}, []
    for name, cfg in validate.TITLES.items():
        tid = cfg["source_tid"].lower()
        content = nand_dec / tid[:8] / tid[8:] / "content"
        romfs = work / "work" / cfg["source_tid"] / "romfs"
        if not content.is_dir() or not unpack_romfs(content, romfs.parent):
            # No decrypted dump (the New 3DS titles): the owner's own romfs folder, when the repo has one.
            owner = repo / "work" / cfg["source_tid"] / "romfs"
            if not owner.is_dir():
                missing.append(name)
                continue
            romfs.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(owner, romfs)
        # Only the labels the mod's string files carry (validate.py skips the "_" files too).
        known = {label for path in (repo / "src" / "strings" / name).glob("*.json") if not path.name.startswith("_")
                 for label, entry in json.loads(path.read_text(encoding="utf-8")).items() if isinstance(entry, dict)}
        budgets = validate.label_budgets(name, widths)
        labels[name] = {label: budget.width_px for label, budget in sorted(budgets.items())
                        if budget.width_px and label in known}
        lines[name] = {label: budgets[label].lines for label in labels[name]}
        spec_file = repo / "src" / "layouts" / f"{name}.json"
        if not spec_file.is_file():
            continue
        for rel, files in json.loads(spec_file.read_text(encoding="utf-8")).items():
            packed = (romfs / rel).read_bytes()
            archive = dict(darc.parse((lz11 if packed[0] == 0x11 else lz10).decompress(packed)).files())
            for inner, by_pane in files.items():
                texts = {pane.name: pane.text.split("\n") for pane in bclyt.texts(archive[inner].data)}
                for pane, entries in by_pane.items():
                    taken = {entry[key] for entry in entries for key in ("en", "ru") if key in entry}
                    others = [line for line in texts[pane] if line not in taken]
                    if others:
                        panes.setdefault(name, {})[f"{rel}/{inner}/{pane}"] = max(
                            validate.pixel_width(line, widths) for line in others)
    areas = {}
    area_romfs = work / "work" / AREA_TID / "romfs"
    area_content = nand_dec / AREA_TID[:8].lower() / AREA_TID[8:].lower() / "content"
    if area_content.is_dir() and unpack_romfs(area_content, area_romfs.parent):
        import area as area_mod  # the owner's tools/area.py
        for path in sorted((repo / "src" / "strings" / "area").glob("EU_*.json")):
            code = path.stem.split("_", 1)[1]
            original = area_romfs / "EU" / f"{code}_LZ.bin"
            if not code.isdigit() or not original.is_file():
                continue
            # The owner's validate_area: the widest of the twelve official names in the file, no slack.
            table = area_mod.load(original)
            areas[code] = max((validate.pixel_width(name, widths)
                               for record in table.records for name in record.names[:12] if name), default=0)
    else:
        missing.append("area")
    return {"labels": labels, "lines": lines, "panes": panes, "areas": areas, "missing": missing}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("nand_dec")
    parser.add_argument("repo")
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="system_3ds_romfs_") as work:
        found = build(Path(args.nand_dec), Path(args.repo), Path(work))
    doc = {"_comment": ("Generated by scripts/build_system_3ds_budgets.py (do not edit). The owner's width budgets in "
                        "system-font pixels: labels = per title (src/strings/<title>) per MSBT label, the widest "
                        "official localisation; panes = per layout spec (src/layouts/<title>.json) per pane, the widest "
                        "line of the languages the mod does not take. Titles without a decrypted dump: see missing."),
           **found}
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(doc, handle, ensure_ascii=False, indent=1, sort_keys=False)
        handle.write("\n")
    print(f"{sum(map(len, found['labels'].values()))} label budgets in {len(found['labels'])} titles, "
          f"{sum(map(len, found['panes'].values()))} pane budgets; no dump: {', '.join(found['missing']) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
