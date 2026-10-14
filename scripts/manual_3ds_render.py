"""3DS electronic-manual simulator: draw a built manual page as the console shows it, or check renders against
console screenshots. Headless (Pillow only); reads the owner's repo_manual folder and build folders at run time.

    python scripts/manual_3ds_render.py render sound 3 --size small --scroll 120 --out page.png
    python scripts/manual_3ds_render.py all --out <folder>                  # every page of every manual + defects
    python scripts/manual_3ds_render.py validate --shots shots.json --calib D:\\calib --out <folder>
    python scripts/manual_3ds_render.py table [--out table.json]            # console page <-> Page_NNN <-> Index

Common options: --repo <repo_manual folder> (default: the folder the preview panel saved, or
$PICORIPI_ROMHACKING/_shared/3ds_sysfont_ua/repo_manual), --build <folder of built manuals> (default
<repo>/tmp/cand_r18), --chrome <folder of chrome crops> (default <data>/plugins/manual_3ds/chrome).
Page numbers on the command line are the console's (the badge): page 3 is the file Page_002.
`render` writes <out> (the 400 x 480 canvas) plus <out>_top.png and <out>_bottom.png.
"""
from __future__ import annotations

import argparse
import base64
import html
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image  # noqa: E402

from plugins.manual_3ds import console_render as cr  # noqa: E402
from plugins.manual_3ds import sim_screens as ss  # noqa: E402
from plugins.manual_3ds import simulator as sim_mod  # noqa: E402
from plugins.manual_3ds.simulator import Simulator, comparison_sheet, find_defects, load_pair, match_shot, page_table  # noqa: E402

SIZES = ("large", "small")


def _default_repo() -> str:
    try:
        from plugins.manual_3ds.preview_panel import load_folder
        saved = load_folder()
    except Exception:
        saved = ""
    if saved:
        return saved
    root = os.environ.get("PICORIPI_ROMHACKING", "")
    return str(Path(root) / "_shared" / "3ds_sysfont_ua" / "repo_manual") if root else ""


def _default_chrome() -> str:
    try:
        from utils.constants import user_plugin_dir
        return str(user_plugin_dir("manual_3ds") / "chrome")
    except Exception:
        return ""


def _simulator(args: argparse.Namespace, build: Optional[Path] = None) -> Simulator:
    repo = args.repo or _default_repo()
    if not repo:
        raise SystemExit("no repo_manual folder: pass --repo or set PICORIPI_ROMHACKING")
    build = build or (Path(args.build) if args.build else Path(repo) / "tmp" / "cand_r18")
    chrome = Path(args.chrome) if args.chrome else (Path(_default_chrome()) if _default_chrome() else None)
    return Simulator(repo, build, chrome, args.wrap_slack)


def _png_data(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


# -- render -----------------------------------------------------------------------------------------


def cmd_render(args: argparse.Namespace) -> None:
    sim = _simulator(args)
    page_file = args.page - 1
    render = sim.render(args.manual, page_file, args.size, args.scroll, buttons=args.buttons, arrows=args.arrows)
    out = Path(args.out)
    render.canvas.convert("RGB").save(out)
    top, bottom = ss.split(render.canvas)
    top.save(out.with_name(out.stem + "_top.png"))
    bottom.save(out.with_name(out.stem + "_bottom.png"))
    defects = [d for d in find_defects(sim, args.manual, page_file, args.size)]
    print(f"{out}: {args.manual} page {args.page} ({args.size}) scroll {render.scroll} of {render.scroll_max}, "
          f"{len(render.runs)} lines, {len(defects)} defects on the page")
    for defect in defects:
        print(f"  {defect.kind:13} scroll {defect.scroll:4}  {defect.pane:12} {defect.text[:60]!r}  {defect.detail}")


# -- all --------------------------------------------------------------------------------------------


def cmd_all(args: argparse.Namespace) -> None:
    sim = _simulator(args)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    manuals = [args.manual] if args.manual else sorted(sim.files)
    defects: List[Dict[str, Any]] = []
    pages: List[Dict[str, Any]] = []
    for name in manuals:
        manual = sim.manual(name)
        for size in SIZES:
            for page_file in manual.pages(size):
                column, runs, missing, _layouts = sim.column(name, page_file, size)
                found = find_defects(sim, name, page_file, size)
                defects.extend(sim_mod.defects_json(found))
                number = manual.index.number_of(page_file)
                stem = f"{name}_p{number:02d}_{size}"
                sheet = sim_mod._column_sheet(column)
                sheet.save(out / f"{stem}_column.png")
                render = sim.render(name, page_file, size, 0)
                render.canvas.convert("RGB").save(out / f"{stem}_scroll0.png")
                for defect in found:
                    if defect.scroll:
                        sim.render(name, page_file, size, defect.scroll).canvas.convert("RGB").save(
                            out / f"{stem}_scroll{defect.scroll}.png")
                pages.append({"manual": name, "console_page": number, "page_file": f"Page_{page_file:03d}", "size": size,
                              "title": manual.index.title_of(page_file), "column_height": column.height - 2 * cr.TOP_MARGIN_ROWS,
                              "scroll_max": render.scroll_max, "lines": len(runs), "defects": len(found),
                              "missing_glyphs": "".join(missing)})
                print(f"{stem}: {len(runs)} lines, {len(found)} defects")
    sim_mod.dump_json(out / "defects.json", defects)
    sim_mod.dump_json(out / "pages.json", pages)
    sim_mod.dump_json(out / "page_table.json", {name: page_table(sim, name) for name in manuals})
    print(f"{len(pages)} pages, {len(defects)} defects -> {out}")


# -- table ------------------------------------------------------------------------------------------


def cmd_table(args: argparse.Namespace) -> None:
    sim = _simulator(args)
    table = {name: page_table(sim, name) for name in ([args.manual] if args.manual else sorted(sim.files))}
    if args.out:
        sim_mod.dump_json(Path(args.out), table)
    for name, rows in table.items():
        print(f"== {name} ({sim.files[name].name}): {len(rows)} pages")
        for row in rows:
            listed = "" if row["category_listed"] else " (not in the contents)"
            print(f"  console {row['console_page']:2}  {row['page_file']}  {row['title']!r}  [{row['category']}{listed}]  "
                  f"blocks L{row['blocks_large']} S{row['blocks_small']}  files L{row['files_large']} S{row['files_small']}")


# -- validate ---------------------------------------------------------------------------------------


def _builds(repo: Path, args: argparse.Namespace) -> List[Path]:
    if args.builds:
        return [Path(p) for p in args.builds]
    tmp = repo / "tmp"
    return sorted(p for p in tmp.iterdir() if p.is_dir() and (p.name.startswith("cand") or p.name.startswith("calib")))


def cmd_validate(args: argparse.Namespace) -> None:
    repo = Path(args.repo or _default_repo())
    chrome = Path(args.chrome) if args.chrome else (Path(_default_chrome()) if _default_chrome() else None)
    shots = json.loads(Path(args.shots).read_text(encoding="utf-8"))
    calib = Path(args.calib)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sims = {build.name: Simulator(str(repo), build, chrome, args.wrap_slack) for build in _builds(repo, args)}
    results: List[Dict[str, Any]] = []
    for entry in shots:
        if not entry.get("viewer") or not entry.get("manual") or not entry.get("page_file"):
            continue
        folder = calib / entry["folder"]
        stem = entry["stem"]
        tops = [p for p in folder.glob(f"{stem}_top.*")]
        bottoms = [p for p in folder.glob(f"{stem}_bot.*")]
        if not tops or not bottoms:
            print(f"{entry['folder']}/{stem}: files missing")
            continue
        shot = load_pair(tops[0], bottoms[0])
        page_file = int(entry["page_file"].split("_")[1])
        sizes = [entry["size"]] if entry.get("size") in SIZES else list(SIZES)
        buttons = 2 if entry.get("notes", "").find("2-button") >= 0 else 3
        if args.buttons:
            buttons = args.buttons
        best, render, per_build = match_shot(sims, shot, entry["manual"], page_file, sizes, buttons, args.arrows,
                                             preferred=entry.get("build", ""))
        if best is None or render is None:
            print(f"{entry['folder']}/{stem}: no build has {entry['manual']} {entry['page_file']}")
            continue
        canvas = render.canvas.convert("RGB")
        sheet = comparison_sheet(shot, canvas)
        sheet_name = f"{entry['folder']}_{stem}.png"
        sheet.save(out / sheet_name)
        twins = sorted(b for b, m in per_build.items() if m.size == best.size
                       and (m.page_hash == best.page_hash or m.text_diff - best.text_diff <= sim_mod.SAME_EPS))
        record = {
            "folder": entry["folder"], "stem": stem, "manual": entry["manual"], "page_file": entry["page_file"],
            "console_page": render.info.number, "title": render.info.title, "size": best.size, "scroll": best.scroll,
            "scroll_max": render.scroll_max, "build": best.build, "same_page_in": twins, "text_diff": round(best.text_diff, 2),
            "bad_text_pixels": best.bad_text_pixels, "regions": best.regions, "sheet": sheet_name,
            "classified_build": entry.get("build", ""),
            "other_builds": {b: round(m.text_diff, 2) for b, m in sorted(per_build.items())},
        }
        results.append(record)
        print(f"{entry['folder']}/{stem}: {entry['manual']} p{render.info.number} {best.size} scroll {best.scroll} "
              f"build {best.build} text diff {best.text_diff:.2f} bad px {best.bad_text_pixels} regions {best.regions}")
    sim_mod.dump_json(out / "validation.json", results)
    _write_report(out, results, sims)
    print(f"{len(results)} pairs -> {out / 'validation.json'}, {out / 'index.html'}")


def _write_report(out: Path, results: List[Dict[str, Any]], sims: Dict[str, Simulator]) -> None:
    """One HTML page: per-folder residuals, every pair side by side, the page-number tables."""
    by_folder: Dict[str, List[Dict[str, Any]]] = {}
    for record in results:
        by_folder.setdefault(record["folder"], []).append(record)
    parts = ["<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Manual simulator</title>",
             "<style>body{font-family:sans-serif;margin:16px;background:#fafafa;color:#222}table{border-collapse:collapse}"
             "td,th{border:1px solid #ccc;padding:2px 6px;font-size:13px}img{max-width:100%}.pair{margin:12px 0;border-top:1px solid #ddd}"
             ".bad{background:#fdd}.ok{background:#dfd}</style></head><body>",
             "<h1>3DS manual simulator: console versus render</h1>",
             "<p>Each pair: the console pair (top screen over bottom screen), the simulator at the matched scroll, "
             "the pixel difference. The text diff is the mean absolute difference over the text bands (0..255), "
             "bad pixels differ by more than 64 there.</p><h2>Per folder</h2><table><tr><th>folder</th><th>pairs</th>"
             "<th>builds matched</th><th>median text diff</th><th>max text diff</th><th>median bad pixels</th></tr>"]
    for folder, records in sorted(by_folder.items()):
        diffs = sorted(r["text_diff"] for r in records)
        bad = sorted(r["bad_text_pixels"] for r in records)
        builds = sorted({r["build"] for r in records})
        parts.append(f"<tr><td>{folder}</td><td>{len(records)}</td><td>{', '.join(builds)}</td>"
                     f"<td>{diffs[len(diffs) // 2]:.2f}</td><td>{diffs[-1]:.2f}</td><td>{bad[len(bad) // 2]}</td></tr>")
    parts.append("</table><h2>Page numbers</h2>")
    first = next(iter(sims.values()), None)
    if first is not None:
        for name in sorted(first.files):
            rows = page_table(first, name)
            parts.append(f"<h3>{html.escape(name)} ({html.escape(first.files[name].name)}, {first.build.name})</h3>"
                         "<table><tr><th>console page</th><th>file</th><th>title</th><th>category</th><th>480-px blocks L/S</th></tr>")
            for row in rows:
                note = "" if row["category_listed"] else " (not listed)"
                parts.append(f"<tr><td>{row['console_page']}</td><td>{row['page_file']}</td><td>{html.escape(row['title'])}</td>"
                             f"<td>{html.escape(row['category'])}{note}</td><td>{row['blocks_large']} / {row['blocks_small']}</td></tr>")
            parts.append("</table>")
    parts.append("<h2>Pairs</h2>")
    for record in results:
        cls = "ok" if record["text_diff"] < 6 else "bad"
        parts.append(f"<div class='pair'><p class='{cls}'><b>{html.escape(record['folder'])}/{html.escape(record['stem'])}</b> "
                     f"{html.escape(record['manual'])} page {record['console_page']} ({html.escape(record['title'])}) "
                     f"{record['size']}, scroll {record['scroll']}/{record['scroll_max']}, build {html.escape(record['build'])} "
                     f"(same page in {html.escape(', '.join(record['same_page_in']))}); text diff {record['text_diff']}, "
                     f"bad pixels {record['bad_text_pixels']}, regions {html.escape(json.dumps(record['regions']))}</p>"
                     f"<img src='{_png_data(Image.open(out / record['sheet']))}' alt='console, render, difference'></div>")
    parts.append("</body></html>")
    (out / "index.html").write_text("\n".join(parts), encoding="utf-8")


# -- main -------------------------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default="", help="the owner's repo_manual folder")
    parser.add_argument("--build", default="", help="folder of built manuals (default <repo>/tmp/cand_r18)")
    parser.add_argument("--chrome", default="", help="folder of chrome crops (default <data>/plugins/manual_3ds/chrome)")
    parser.add_argument("--wrap-slack", type=float, default=None,
                        help=f"px short of its pane width at which the viewer breaks a line (default {cr.WRAP_SLACK})")
    sub = parser.add_subparsers(dest="command", required=True)

    render = sub.add_parser("render", help="one page at one scroll")
    render.add_argument("manual")
    render.add_argument("page", type=int, help="console page number (the badge)")
    render.add_argument("--size", choices=SIZES, default="small")
    render.add_argument("--scroll", type=int, default=0)
    render.add_argument("--buttons", type=int, choices=(2, 3), default=3)
    render.add_argument("--arrows", action="store_true")
    render.add_argument("--out", required=True)
    render.set_defaults(func=cmd_render)

    every = sub.add_parser("all", help="every page of every manual in the build")
    every.add_argument("--manual", default="")
    every.add_argument("--out", required=True)
    every.set_defaults(func=cmd_all)

    table = sub.add_parser("table", help="console page number <-> Page_NNN <-> Index")
    table.add_argument("--manual", default="")
    table.add_argument("--out", default="")
    table.set_defaults(func=cmd_table)

    validate = sub.add_parser("validate", help="match console screenshot pairs against every build")
    validate.add_argument("--shots", required=True, help="classification JSON (folder, stem, manual, page_file, size)")
    validate.add_argument("--calib", required=True, help="folder holding the screenshot folders")
    validate.add_argument("--builds", nargs="*", help="build folders (default: <repo>/tmp/cand* and calib_*)")
    validate.add_argument("--buttons", type=int, choices=(2, 3), default=0)
    validate.add_argument("--arrows", action="store_true")
    validate.add_argument("--out", required=True)
    validate.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
