"""Write plugins/manual_3ds/geometry.json from the owner's repo_manual dumps.

    python scripts/build_manual_geometry.py <repo_manual folder> [--out FILE]

The facts come from the folder's own tools (tools/manual.py: pages_of, budgets, the pane model) through
repo_tools.load_tools, read-only. A manual is taken when it has a dump on disk; its entries are the keys of its
src/manuals JSON, in file order. The file holds numbers and identifiers only: no game text and no art.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from plugins.manual_3ds import layout, repo_tools  # noqa: E402

DEFAULT_OUT = os.path.join(ROOT, "plugins", "manual_3ds", "geometry.json")
# The owner's line step when a pane has neither a line height nor a font size (manual.right_limit).
STEP_FALLBACK = 20.0


def _entry(flow, budget):
    """The drawing facts of one paragraph, as the plugin reads them."""
    base = flow.text_panes[0].style
    styles, panes = {}, {}
    for pane in flow.text_panes:
        # The same style numbering as manual.to_edits: 0 is the paragraph's own style.
        style = 0 if pane.style == base else styles.setdefault(pane.style, len(styles) + 1)
        panes[str(style)] = panes.get(str(style), 0) + 1
    lines = []
    for line in flow.lines:
        first = next(pane for pane in line if pane.is_text)
        step = first.line_height or first.font_size or STEP_FALLBACK
        lines.append([first.x, first.width, first.abs_x, first.abs_y, step])
    return {
        "part": flow.part,
        "font_size": flow.font_size,
        "char_space": flow.char_space,
        "fixed": bool(flow.fixed),
        "panes": {style: panes[style] for style in sorted(panes, key=int)},
        "lines": lines,
        "icon_widths": [icon.width for icon in flow.icons],
        "budget": round(budget, 3),
    }


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
        entries, occluders = {}, {}
        for page, flows in pages.items():
            for index, flow in enumerate(flows):
                entries[f"{page}#{index}"] = _entry(flow, budgets[f"{page}#{index}"])
            if flows:
                # Every flow of a page shares the page's pictures and frames (manual.occluder_rules).
                occluders[page] = [[p.kind, p.abs_x, p.abs_y, p.width, p.height] for p in flows[0].occluders]
        keys = list(entries)
        if keys != list(manual.load_json(name)):
            raise SystemExit(f"{name}: the dump's paragraphs differ from src/manuals/{name}.json")
        out[layout.fingerprint(keys)] = {"name": name, "entries": entries, "pages": occluders}
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", help="the repo_manual folder (with tools/, src/ and work/)")
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    tools = repo_tools.load_tools(args.folder)
    data = build(tools)
    temp = args.out + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
    os.replace(temp, args.out)
    print(f"{len(data)} manuals -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
