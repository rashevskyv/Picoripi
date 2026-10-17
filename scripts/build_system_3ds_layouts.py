"""Write plugins/system_3ds/layout_links.json: which layout and text pane draws each 3DS system string.

    python scripts/build_system_3ds_layouts.py <repo_manual folder> [--out FILE]

The folder is the owner's repo_manual (its tools/ and src/, and work/<title id>/romfs, read only; nothing is written
there). Two kinds of link, both per part (src/strings/<part>):
  - spec: a line of a text pane baked into a layout, the layouts of src/layouts/<part>.json. The key is the
    string id of the spec (archive/layout/pane#index); line is the index of the English line in the pane.
  - label: a text pane whose user data (a usd1 section right after it) names the MSBT label. The key is the label.
    A label linked to several layouts takes the first layout in romfs order.
The file holds ids, names, paths and indices only, no game text.
"""
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DEFAULT_OUT = os.path.join(ROOT, "plugins", "system_3ds", "layout_links.json")
PANE_KINDS = (b"pan1", b"pic1", b"txt1", b"wnd1", b"bnd1")
NUL = bytes([0])  # a name in a usd1 section ends with a NUL byte


def _load(repo: Path, name: str):
    spec = importlib.util.spec_from_file_location("owner_" + name, repo / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _decode(data: bytes, lz10, lz11) -> bytes:
    if data[:1] in (bytes([0x10]), bytes([0x11])):
        return (lz11 if data[0] == 0x11 else lz10).decompress(data)
    return data


def walk(data: bytes, file_rel: str, chain: tuple, modules, out: list) -> None:
    """Every layout (CLYT) under a romfs file: (file, DARC member chain, bytes). Members that do not decode are skipped."""
    darc, lz10, lz11 = modules
    try:
        blob = _decode(data, lz10, lz11)
        if blob[:4] == b"CLYT":
            out.append((file_rel, chain, blob))
            return
        if blob[:4] != b"darc":
            return
        members = list(darc.parse(blob).files())
    except Exception:
        return
    for name, entry in members:
        if not entry.is_dir and entry.data is not None:
            walk(bytes(entry.data), file_rel, chain + (name,), modules, out)


def usd_sections(data: bytes):
    """(pane magic, pane name, usd1 bytes) for each usd1 section, with the pane section just before it."""
    count = int.from_bytes(data[0x10:0x12], "little")
    pos = int.from_bytes(data[0x06:0x08], "little")
    last = None
    found = []
    for _ in range(count):
        magic = data[pos:pos + 4]
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        if magic in PANE_KINDS:
            name = data[pos + 0x0C:pos + 0x1C].split(NUL)[0].decode("ascii", "replace")
            last = (magic, name)
        elif magic == b"usd1" and last is not None:
            found.append((last[0], last[1], data[pos:pos + size]))
        pos += size
    return found


def usd_names(body: bytes) -> list:
    """The entry names of a usd1 section, in order. Each entry is (u32, u32, u32 name length) in a table after the
    12-byte header; the names follow the table, each name is followed by its data string, and both end in a NUL."""
    count = int.from_bytes(body[8:12], "little")
    pos = 12 + 12 * count
    names = []
    for index in range(count):
        length = int.from_bytes(body[12 + 12 * index + 8:12 + 12 * index + 12], "little")
        names.append(body[pos:pos + length].decode("ascii", "replace"))
        pos += length + 1
        end = body.find(NUL, pos)
        pos = len(body) if end < 0 else end + 1
    return names


def names_in(body: bytes, labels) -> set:
    """The labels that are entry names of a usd1 section (data strings are not names)."""
    return set(usd_names(body)) & set(labels)


def build(repo: Path) -> dict:
    sys.dont_write_bytecode = True
    darc = _load(repo, "darc")
    lz10 = _load(repo, "lz10")
    lz11 = _load(repo, "lz11")
    bclyt = _load(repo, "bclyt")
    sys.path.insert(0, str(repo / "tools"))
    try:
        import validate  # noqa: E402  (the owner's tools, read only)
    finally:
        sys.path.pop(0)
    modules = (darc, lz10, lz11)
    links: dict = {}
    for part, cfg in validate.TITLES.items():
        romfs = repo / "work" / cfg["source_tid"] / "romfs"
        if not romfs.is_dir():
            continue
        strings = {}
        for path in sorted((repo / "src" / "strings" / part).glob("*.json")):
            if not path.name.startswith("_"):
                strings.update({k: v for k, v in json.loads(path.read_text(encoding="utf-8")).items()
                                if isinstance(v, dict)})
        found: list = []
        for root, _, files in os.walk(romfs):
            for fname in sorted(files):
                rel = os.path.relpath(os.path.join(root, fname), romfs).replace("\\", "/")
                with open(os.path.join(root, fname), "rb") as handle:
                    walk(handle.read(), rel, (), modules, found)
        table: dict = {}
        for file_rel, chain, data in found:
            for magic, pane, body in usd_sections(data):
                if magic != b"txt1":
                    continue
                for label in names_in(body, strings):
                    table.setdefault(label, {"kind": "label", "tid": cfg["source_tid"], "file": file_rel,
                                             "chain": list(chain), "pane": pane})
        spec_file = repo / "src" / "layouts" / f"{part}.json"
        if spec_file.is_file():
            for rel, layouts in json.loads(spec_file.read_text(encoding="utf-8")).items():
                packed = (romfs / rel).read_bytes()
                archive = dict(darc.parse(_decode(packed, lz10, lz11)).files())
                for inner, by_pane in layouts.items():
                    panes = {pane.name: pane for pane in bclyt.texts(bytes(archive[inner].data))}
                    for pane_name, entries in by_pane.items():
                        lines = panes[pane_name].text.split("\n")
                        for index, entry in enumerate(entries):
                            if entry.get("en") not in lines:
                                continue
                            key = f"{rel}/{inner}/{pane_name}#{index}"
                            table[key] = {"kind": "spec", "tid": cfg["source_tid"], "file": rel, "chain": [inner],
                                          "pane": pane_name, "line": lines.index(entry["en"])}
        if table:
            links[part] = table
    return {"links": links}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo")
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    found = build(Path(args.repo))
    doc = {"_comment": ("Generated by scripts/build_system_3ds_layouts.py (do not edit). Which layout and text pane draws "
                        "each 3DS system string: label links (user data names) and spec links (lines baked in a layout). "
                        "Ids, names, paths and indices only."), **found}
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(doc, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    counts = {part: len(table) for part, table in found["links"].items()}
    print(f"links per part: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
