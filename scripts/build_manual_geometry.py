"""Write plugins/manual_3ds/geometry.json and widths.json from the owner's repo_manual tools and dumps.

    python scripts/build_manual_geometry.py <repo_manual folder> [--out FILE] [--widths FILE]

The facts come from the folder's own tools (tools/manual.py: pages_of, budgets, the pane model; validate.py: the
widths and the charset) through repo_tools.load_tools, read-only. A manual is taken when it has a dump on disk; its
entries are the keys of its src/manuals JSON, in file order. geometry.json records the owner's git commit it was
built from (owner_commit); the tests compare it with the folder's HEAD. The files hold numbers and identifiers
only: no game text and no art.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from plugins.manual_3ds import console_render as cr  # noqa: E402
from plugins.manual_3ds import layout, repo_tools, simulator  # noqa: E402

DEFAULT_OUT = os.path.join(ROOT, "plugins", "manual_3ds", "geometry.json")
DEFAULT_WIDTHS = os.path.join(ROOT, "plugins", "manual_3ds", "widths.json")
# The owner's line step when a pane has neither a line height nor a font size (manual.right_limit).
STEP_FALLBACK = 20.0


def _entry(flow, budget, manual):
    """The drawing facts of one paragraph, as the plugin reads them.

    "lines": the text panes of each line, each [x, width, abs_x, abs_y, step, char_space, style, origin, text_pos,
    text_align, mark]. The style numbering is manual._pools': 0 is the paragraph's own style, the others in order
    of appearance. mark is the pane's text when it is a button glyph or sign pane (manual.is_mark), else "".
    """
    base = flow.text_panes[0].style
    styles = {}
    lines = []
    for line in flow.lines:
        row = []
        for pane in line:
            if not pane.is_text:
                continue
            style = 0 if pane.style == base else styles.setdefault(pane.style, len(styles) + 1)
            step = pane.line_height or pane.font_size or STEP_FALLBACK
            mark = pane.text.strip() if manual.is_mark(pane.text) else ""
            row.append([pane.x, pane.width, pane.abs_x, pane.abs_y, step, pane.char_space, style,
                        pane.origin, pane.text_pos, pane.text_align, mark])
        lines.append(row)
    return {
        "part": flow.part,
        "font_size": flow.font_size,
        "char_space": flow.char_space,
        "fixed": bool(flow.fixed),
        "lines": lines,
        "icon_widths": [icon.width for icon in flow.icons],
        "budget": round(budget, 3),
    }


def _textures(tools, archive):
    """The manual's BCLIM textures (every picture archive), as the simulator reads them."""
    return cr.Textures.from_archive(archive, tools.manual.BASE_SLOT)


def _painted_frames(tools, archive, page, textures):
    """{window pane name: painted width of its right frame} for one page ("small/Page_003_small_0")."""
    part, file_name = page.split("/", 1)
    data = archive.read(f"{tools.manual.BASE_SLOT}_{part}")[f"{file_name}.bclyt"]
    parsed = cr.parse(data)
    return {pane.name: simulator._frame_width(parsed, pane, textures)
            for pane in parsed.panes if pane.kind == "wnd1" and pane.frames}


def build(tools):
    """-> {fingerprint: {"name", "entries", "pages"}} for every manual of the folder that has a dump."""
    manual = tools.manual
    widths = repo_tools.widths_of(tools)
    out = {}
    for name in manual.MANUALS:
        try:
            path = repo_tools.manual_path(tools, name)
        except repo_tools.ToolsError:
            continue  # no dump on this disk: no geometry, the plugin reports no layout for it
        archive = tools.bcma.load(path)
        pages = manual.pages_of(archive, manual.BASE_SLOT)
        budgets = manual.budgets(archive, manual.BASE_SLOT, widths)
        textures = _textures(tools, archive)
        entries, occluders = {}, {}
        for page, flows in pages.items():
            for index, flow in enumerate(flows):
                entries[f"{page}#{index}"] = _entry(flow, budgets[f"{page}#{index}"], manual)
            if flows:
                # The page's pictures and frames (manual.occluder_rules), the union over its flows: a flow's own
                # inline icons are not in its way (manual.paragraphs_of), so each entry lists those as "own"
                # (indexes to leave out). A window carries the painted width of its right frame (the opaque columns
                # of the frame texture, as the simulator measures it; 0 for a frame that paints nothing), None when
                # it has no frame texture.
                shared = {}
                for flow in flows:
                    for pane in flow.occluders:
                        shared.setdefault(id(pane), pane)
                painted = _painted_frames(tools, archive, page, textures)
                occluders[page] = [[p.kind, p.abs_x, p.abs_y, p.width, p.height,
                                    painted.get(p.name) if getattr(p, "frame_width", None) is not None else None]
                                   for p in shared.values()]
                for index, flow in enumerate(flows):
                    mine = {id(pane) for pane in flow.occluders}
                    own = [position for position, key in enumerate(shared) if key not in mine]
                    if own:
                        entries[f"{page}#{index}"]["own"] = own
        keys = list(entries)
        if keys != list(manual.load_json(name)):
            raise SystemExit(f"{name}: the dump's paragraphs differ from src/manuals/{name}.json")
        out[layout.fingerprint(keys)] = {"name": name, "entries": entries, "pages": occluders}
    return out


def build_widths(tools):
    """The widths.json the plugin's own layout reads: the owner's active glyph variant, advances and ink overhangs.

    The advances are the owner's load_widths() (the font table with the patched letters' donors) keyed by the
    charset, so a character is missing from the plugin exactly when the owner's gate says it has no glyph.
    """
    manual = tools.manual
    table = manual.load_homoglyphs()
    advances = repo_tools.widths_of(tools)
    if set(advances) != manual.load_charset():
        raise SystemExit("the owner's font widths and charset list different code points")
    return {
        "_comment": "Generated by scripts/build_manual_geometry.py from the owner's tools (do not edit). Glyph "
                    "advances of the 3DS system font (CWDH units; the console draws them at fontSize / 25) with "
                    "the patched letters' donors, as the manuals build measures them. overhangs: units between a "
                    "glyph's ink and the end of its advance (assets/font_ink.json). homoglyphs: the active variant "
                    "of src/homoglyphs.json (default real).",
        "font_width": layout.FONT_WIDTH,
        "word_apostrophe": table.get("ʼ") == "ʼ",
        "homoglyphs": {key: value for key, value in table.items() if key != "_comment"},
        "advances": {chr(code): float(width) for code, width in sorted(advances.items())},
        "overhangs": {chr(int(code, 16)): advance - left - ink
                      for code, (left, ink, advance) in sorted(manual.INK_METRICS.items())},
    }


def _write_json(path, data, **options):
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, **options)
    os.replace(temp, path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", help="the repo_manual folder (with tools/, src/ and work/)")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--widths", default=DEFAULT_WIDTHS)
    args = parser.parse_args(argv)
    tools = repo_tools.load_tools(args.folder)
    commit = repo_tools.owner_commit(tools.root)
    if not commit:
        raise SystemExit(f"{args.folder} is not a git checkout: its tools have no commit to record")
    data = build(tools)
    _write_json(args.out, {"owner_commit": commit, "manuals": data}, separators=(",", ":"))
    _write_json(args.widths, build_widths(tools), indent=1)
    print(f"{len(data)} manuals at owner commit {commit} -> {args.out}, {args.widths}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
