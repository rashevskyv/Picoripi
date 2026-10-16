"""The manual simulator: a built manual's pages drawn as the console shows them, checked against screenshots.

Pulls together console_render (the page column), sim_screens (the viewer's chrome) and the owner's tools
(repo_tools: the archive reader and the font). Three jobs, all headless (Pillow only), used by
scripts/manual_3ds_render.py and by the preview panel:

- ``Simulator.render(...)``: one page of one build at one scroll -> the two screens;
- ``find_defects(...)``: what the render shows wrong: a line whose ink runs past the card's edge onto the scroll
  track, a line the viewer broke inside its pane, a line over a picture or a frame, a line painted over by a pane
  drawn after it, a line that leaves the filled cell it starts in, two lines whose ink overlaps, a glyph the font lacks;
- ``match_shot(...)``: which build, scroll and size a console screenshot pair shows, and how far the render is from it.

Nothing here reads JSON translations: the pages come from the archives a build wrote (the console reads the same).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from PIL import Image, ImageChops

from plugins.manual_3ds import console_render as cr
from plugins.manual_3ds import repo_tools
from plugins.manual_3ds import sim_screens as ss

CARD_EDGE = 320.0           # page x of the card's right edge (the scroll track starts there)
LINE_LIMIT = CARD_EDGE      # a line that reaches past this runs onto the scroll track (top screen) or is lost (bottom)
PICTURE_MIN = (24.0, 12.0)  # smaller pictures are icons set inside the text (the owner's OCC_MIN_W/H)
BOX_MIN_WIDTH = 200.0       # a window the text sits inside is a box only when this wide (the owner's OCC_BOX_MIN_W)
TEXT_BANDS = ((48, 48, 352, 230), (48, 240, 352, 450))   # canvas boxes the scroll is matched on (chrome excluded)
REGIONS = {
    "text": [(48, 48, 352, 230), (48, 240, 352, 450)],
    "header": [(0, 0, 400, 38)],
    "sides": [(0, 38, 40, 240), (360, 38, 400, 240)],
    "bottom_bar": [(40, 452, 360, 480)],
}
MATCH_STEP = 4              # coarse scroll search step; refined by +-MATCH_STEP after
# Two ink boxes must meet by more than this (px, both ways) to be an occlusion or an overlap: a line's box is its
# whole step (fontSize y), so a line that sits on a box frame is none, and Nintendo's own adjacent glyph panes
# (the circled digits of home_menu_manual page 14 meet by 1.6 px) are none.
OVERLAP_SLACK = 2.0
CELL_MIN_WIDTH = 24.0       # a filled box narrower than this is a marker, not a cell a line can leave
# Ink may run this far (px) past a box's filled inside before it has left the cell: Nintendo's own lines reach
# 6.0 px past the filled inside into the box's clear frame (health_safety_n3ds page 12, large, "протрите их сухой").
CELL_SLACK = 6.5
SAME_EPS = 0.1              # builds whose text-band difference is this close to the best show the same page here


def manual_file_name(tools: Any, name: str) -> str:
    """The file a build folder keeps a manual in: the viewer's short name, or <name>.bin for a romfs member."""
    cfg = tools.manual.MANUALS[name]
    if cfg.get("romfs_member"):
        return f"{name}.bin"
    return tools.manual.luma_hook.manual_file_name(cfg["tid"])


def build_files(tools: Any, build: Path) -> Dict[str, Path]:
    """{manual name: Manual.bcma path} for the manuals a build folder holds."""
    out = {}
    for name in tools.manual.MANUALS:
        path = build / manual_file_name(tools, name)
        if path.is_file():
            out[name] = path
    return out


@dataclass
class Defect:
    kind: str                   # over_edge | wrapped | over_picture | over_frame | covered | over_cell | text_overlap | missing_glyph
    manual: str
    page: int                   # console page number
    page_file: str              # Page_NNN
    size: str                   # large | small
    pane: str
    text: str
    page_y: float               # page y of the line's top (0 at the text origin, down is negative)
    scroll: int                 # a scroll that puts the line in the top screen
    detail: str = ""


@dataclass
class RenderedPage:
    """What one page's BCLYT files draw: the column and everything the defect finder reads off the render."""

    column: Image.Image
    runs: List[cr.TextRun]
    missing: List[str]
    covers: List[cr.Cover]
    layouts: List[cr.Layout]


def render_page(files: List[bytes], textures: cr.Textures, glyphs: cr.Glyphs, wrap_slack: Optional[float] = None) -> RenderedPage:
    """One page drawn as the console draws it. The preview panel (the page it built from the current text) and the
    CLI (the page of a build folder) both go through here, so the live preview is the simulator."""
    renderer = cr.PageRenderer(textures, glyphs)
    if wrap_slack is not None:
        renderer.wrap_slack = wrap_slack
    column = renderer.render(files)
    return RenderedPage(column, renderer.runs, sorted(renderer.missing), renderer.covers, [cr.parse(data) for data in files])


def page_defects(page: RenderedPage, textures: cr.Textures, name: str, number: int, page_name: str, size: str) -> List[Defect]:
    return defects_of(page.runs, page.missing, page.layouts, textures, name, number, page_name, size, page.covers)


@dataclass
class ScreenRender:
    canvas: Image.Image
    column: Image.Image
    runs: List[cr.TextRun]
    missing: List[str]
    scroll: float
    scroll_max: int
    info: ss.PageInfo


class Manual:
    """One manual archive of one build: its index, textures and page files, read once."""

    def __init__(self, tools: Any, name: str, path: Path):
        self.name = name
        self.path = path
        self.archive = tools.bcma.load(path)
        slot = tools.manual.BASE_SLOT
        self.index = cr.read_index(self.archive.read(f"{slot}_index")["Index.bclyt"])
        self.textures = cr.Textures.from_archive(self.archive, slot)
        self._parts: Dict[str, Dict[str, bytes]] = {}
        self._slot = slot

    def files(self, size: str) -> Dict[str, bytes]:
        if size not in self._parts:
            self._parts[size] = self.archive.read(f"{self._slot}_{size}")
        return self._parts[size]

    def pages(self, size: str) -> List[int]:
        return cr.page_numbers(self.files(size), size)

    def page_files(self, page_file: int, size: str) -> List[bytes]:
        return cr.page_files(self.files(size), page_file, size)

    def page_hash(self, page_file: int, size: str) -> str:
        digest = hashlib.sha1()
        for data in self.page_files(page_file, size):
            digest.update(data)
        return digest.hexdigest()[:12]


class Simulator:
    """Renders pages of the manuals in a build folder with the owner's tools and font."""

    def __init__(self, root: str, build: Path, chrome_dir: Optional[Path] = None, wrap_slack: Optional[float] = None):
        self.tools = repo_tools.load_tools(root)
        self.font = repo_tools.load_font(self.tools)
        self.glyphs = cr.Glyphs(self.font, self.tools.bcfnt)
        self.build = build
        self.files = build_files(self.tools, build)
        self.chrome = ss.Chrome.load(chrome_dir)
        self.wrap_slack = cr.WRAP_SLACK if wrap_slack is None else wrap_slack
        self._manuals: Dict[str, Manual] = {}
        self._pages: Dict[Tuple[str, int, str], RenderedPage] = {}

    def manual(self, name: str) -> Manual:
        if name not in self._manuals:
            if name not in self.files:
                raise repo_tools.ToolsError(f"{name}: no file in {self.build}")
            self._manuals[name] = Manual(self.tools, name, self.files[name])
        return self._manuals[name]

    def column(self, name: str, page_file: int, size: str):
        """-> (column image, text runs, missing glyphs, layouts) of one page, cached."""
        page = self.page(name, page_file, size)
        return page.column, page.runs, page.missing, page.layouts

    def page(self, name: str, page_file: int, size: str) -> "RenderedPage":
        key = (name, page_file, size)
        if key not in self._pages:
            manual = self.manual(name)
            files = manual.page_files(page_file, size)
            if not files:
                raise repo_tools.ToolsError(f"{name}: no {size} page file {page_file}")
            self._pages[key] = render_page(files, manual.textures, self.glyphs, self.wrap_slack)
        return self._pages[key]

    def info(self, name: str, page_file: int, size: str, buttons: int = 3) -> ss.PageInfo:
        manual = self.manual(name)
        pages = manual.pages(size)
        return ss.PageInfo(manual.index.number_of(page_file), manual.index.title_of(page_file),
                           manual.index.category_of(page_file), has_previous=page_file - 1 in pages,
                           has_next=page_file + 1 in pages, large=(size == "large"), buttons=buttons)

    def render(self, name: str, page_file: int, size: str, scroll: float = 0.0, buttons: int = 3,
               arrows: bool = False, neighbours: bool = True) -> ScreenRender:
        column, runs, missing, _layouts = self.column(name, page_file, size)
        info = self.info(name, page_file, size, buttons)
        previous = following = None
        if neighbours:
            pages = self.manual(name).pages(size)
            if page_file - 1 in pages:
                previous = self.column(name, page_file - 1, size)[0]
            if page_file + 1 in pages:
                following = self.column(name, page_file + 1, size)[0]
        limit = ss.scroll_range(column.height)
        scroll = max(0.0, min(float(scroll), float(limit)))
        canvas = ss.compose(column, scroll, info, self.chrome, self.glyphs, (previous, following), arrows=arrows)
        return ScreenRender(canvas, column, runs, missing, scroll, limit, info)


# -- defects ----------------------------------------------------------------------------------------


def _scroll_for(page_y: float) -> int:
    """A scroll that shows a line (top at page_y) a third of the way down the top screen."""
    return max(0, int(round(-page_y - 60)))


def find_defects(sim: Simulator, name: str, page_file: int, size: str) -> List[Defect]:
    """What the render of one page of a build shows wrong (see the module docstring)."""
    manual = sim.manual(name)
    return page_defects(sim.page(name, page_file, size), manual.textures, name, manual.index.number_of(page_file),
                        f"Page_{page_file:03d}", size)


def defects_of(runs: List[cr.TextRun], missing: Iterable[str], layouts: List[cr.Layout], textures: cr.Textures,
               name: str, number: int, page_name: str, size: str, covers: Iterable[cr.Cover] = ()) -> List[Defect]:
    """The defects a rendered page shows: a cut line, a line the viewer broke, a line over a picture or a frame,
    a line a later pane paints over (`covers`, from the renderer), two lines whose ink overlaps, a missing glyph.
    An overrun under cr.SUB_PIXEL is none. Pure: works on what PageRenderer.render left behind."""
    out: List[Defect] = []
    out.extend(_occlusions(runs, covers, name, number, page_name, size))
    for ch in missing:
        out.append(Defect("missing_glyph", name, number, page_name, size, "", ch, 0.0, 0, f"U+{ord(ch):04X}"))
    pictures = []
    windows = []
    for layout in layouts:
        for pane in layout.panes:
            if not pane.visible:
                continue
            left, top = pane.top_left
            if pane.kind == "pic1" and pane.w >= PICTURE_MIN[0] and pane.h >= PICTURE_MIN[1]:
                pictures.append((pane.name, left, top, pane.w, pane.h))
            elif pane.kind == "wnd1" and pane.frames and pane.w >= BOX_MIN_WIDTH:
                frame = _frame_width(layout, pane, textures)
                if frame:
                    windows.append((pane.name, left, top, pane.w, pane.h, frame))
    for run in runs:
        if not run.text.strip():
            continue
        step = 20.0
        right = run.ink_right
        bottom = run.top - step
        where = f"{run.text[:50]!r}"
        if run.wrapped:
            out.append(Defect("wrapped", name, number, page_name, size, run.pane, run.text, run.top, _scroll_for(run.top),
                              "the viewer broke the stored line inside its pane; this part lands on the next line"))
        if right > LINE_LIMIT + cr.SUB_PIXEL:
            out.append(Defect("over_edge", name, number, page_name, size, run.pane, run.text, run.top, _scroll_for(run.top),
                              f"ink ends at {right:.1f} px, the card ends at {LINE_LIMIT:.0f} (drawn over the scroll track): {where}"))
        for pic_name, px, py, pw, ph in pictures:
            if (px < right - cr.SUB_PIXEL and px + pw > run.x + 1.0 and py > bottom + 1.0
                    and py - ph < run.top - 1.0 and px > run.x):
                out.append(Defect("over_picture", name, number, page_name, size, run.pane, run.text, run.top,
                                  _scroll_for(run.top), f"ink ends at {right:.1f} px, picture {pic_name} starts at {px:.1f}"))
        for win_name, wx, wy, ww, wh, fw in windows:
            inner_right = wx + ww - (fw or cr.FRAME_INNER)
            if wx <= run.x < wx + ww and wy > bottom + 1.0 and wy - wh < run.top - 1.0 and right > inner_right + cr.SUB_PIXEL:
                out.append(Defect("over_frame", name, number, page_name, size, run.pane, run.text, run.top,
                                  _scroll_for(run.top), f"ink ends at {right:.1f} px, the frame {win_name} starts at {inner_right:.1f}"))
    return out


def _occlusions(runs: List[cr.TextRun], covers: Iterable[cr.Cover], name: str, number: int, page_name: str,
                size: str) -> List[Defect]:
    """`covered`: a pane drawn after the line paints over its ink (the console shows the line cut there);
    `over_cell`: the line starts inside a filled box drawn before it and its ink leaves that box (a table label in
    white that runs out of its grey cell onto the white page: shots_r19 2011-01-01_21-00-53.280, page 8);
    `text_overlap`: the ink of two lines of different panes meets (a label running under the next cell's text).
    Overlaps of at most OVERLAP_SLACK px in either direction are none: adjacent panes touch by design."""
    out: List[Defect] = []
    inked = [run for run in runs if run.text.strip()]
    ordered = sorted(covers, key=lambda cover: cover.order)
    for run in inked:
        box = (run.ink_left, run.top, run.ink_right, run.top - run.height)
        for cover in ordered:
            if cover.order > run.order and cover.covers(*box, OVERLAP_SLACK):
                out.append(Defect("covered", name, number, page_name, size, run.pane, run.text, run.top, _scroll_for(run.top),
                                  f"{cover.pane} is drawn after this line and paints over it from {max(cover.left, run.x):.1f} px"))
                break
        # A line that starts inside a filled cell and leaves it: its ink runs over whatever is beside the cell (a
        # table's white label is invisible there and lands under the next cell's text).
        for cover in ordered:
            if (cover.order < run.order and cover.kind == "content" and cover.right - cover.left >= CELL_MIN_WIDTH
                    and cover.covers(*box, OVERLAP_SLACK) and cover.left <= run.ink_left
                    and run.ink_right > cover.right + CELL_SLACK):
                out.append(Defect("over_cell", name, number, page_name, size, run.pane, run.text, run.top, _scroll_for(run.top),
                                  f"the line starts in the filled box {cover.pane} and leaves it at {cover.right:.1f} px "
                                  f"(ink ends at {run.ink_right:.1f})"))
                break
    # ponytail: pairwise over the page's lines (a few hundred); a sweep if a manual ever has thousands.
    for index, run in enumerate(inked):
        for other in inked[index + 1:]:
            if other.pane == run.pane:
                continue
            if (min(run.ink_right, other.ink_right) - max(run.ink_left, other.ink_left) > OVERLAP_SLACK
                    and min(run.top, other.top) - max(run.top - run.height, other.top - other.height) > OVERLAP_SLACK):
                out.append(Defect("text_overlap", name, number, page_name, size, run.pane, run.text, run.top, _scroll_for(run.top),
                                  f"its ink meets {other.pane} {other.text[:40]!r} at {max(run.ink_left, other.ink_left):.1f} px"))
    return out


def _frame_width(layout: cr.Layout, pane: cr.Pane, textures: cr.Textures) -> float:
    """The painted width of a window's right frame: the texture columns from the outer edge inward that are
    opaque (Nintendo's box frames are 4 px textures whose inner 2 columns are clear, and its own lines end on
    them: home_menu_manual page 3 'кнопок, можно сделать скриншот' ends 1.9 px past the texture's inner edge).
    0 when the frame has no texture."""
    material, flip = pane.frames[1] if len(pane.frames) >= 4 else pane.frames[0]
    if material >= len(layout.materials) or not layout.materials[material].textures:
        return 0.0
    index = layout.materials[material].textures[0][0]
    if index >= len(layout.textures):
        return 0.0
    image = textures.get(layout.textures[index])
    if image is None:
        return 0.0
    drawn = cr._frame_image(image, flip) if len(pane.frames) >= 4 else image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    alpha = drawn.getchannel("A")
    # The opaque columns that run in from the outer edge (the last column). ponytail: an outline texture whose
    # outer column is clear counts as painting nothing; counting to the innermost painted column instead flags
    # Nintendo's own lines inside its shadowed 8 px frames (health_safety_n3ds page 12), so the outer run it is.
    width = 0
    for column in range(drawn.width - 1, -1, -1):
        strip = alpha.crop((column, 0, column + 1, drawn.height)).histogram()
        if sum(i * c for i, c in enumerate(strip)) / max(1, drawn.height) <= 127:
            break
        width += 1
    return float(width)


# -- screenshots ------------------------------------------------------------------------------------


def load_pair(top_path: Path, bottom_path: Path) -> Image.Image:
    """A console pair as the 400 x 480 canvas (top screen, then the bottom screen at x 40)."""
    canvas = Image.new("RGB", ss.CANVAS, (0, 0, 0))
    canvas.paste(Image.open(top_path).convert("RGB"), (0, 0))
    canvas.paste(Image.open(bottom_path).convert("RGB"), (ss.CARD_X, ss.TOP[1]))
    return canvas


def mean_diff(a: Image.Image, b: Image.Image, boxes: Iterable[Tuple[int, int, int, int]]) -> float:
    total = 0.0
    count = 0
    for box in boxes:
        hist = ImageChops.difference(a.crop(box), b.crop(box)).convert("L").histogram()
        total += sum(i * c for i, c in enumerate(hist))
        count += (box[2] - box[0]) * (box[3] - box[1])
    return total / count if count else 0.0


def bad_pixels(a: Image.Image, b: Image.Image, boxes: Iterable[Tuple[int, int, int, int]], threshold: int = 64) -> int:
    total = 0
    for box in boxes:
        hist = ImageChops.difference(a.crop(box), b.crop(box)).convert("L").histogram()
        total += sum(c for i, c in enumerate(hist) if i > threshold)
    return total


def _column_sheet(column: Image.Image) -> Image.Image:
    sheet = Image.new("RGB", column.size, (255, 255, 255))
    sheet.paste(column, (0, 0), column)
    return sheet


def best_scroll(shot: Image.Image, column: Image.Image, limit: int) -> Tuple[float, float]:
    """The scroll that puts the column closest to the screenshot's text bands: whole pixels at a coarse step,
    then whole pixels around the best, then eighth pixels (the console scrolls by fractions of a pixel)."""
    sheet = _column_sheet(column)
    bands = [(x0 - ss.CARD_X, y0, x1 - ss.CARD_X, y1) for x0, y0, x1, y1 in TEXT_BANDS]
    shot_bands = [shot.crop(box).convert("L") for box in TEXT_BANDS]

    def score(scroll: float) -> float:
        offset = cr.TOP_MARGIN_ROWS + scroll - ss.PAGE_TOP   # column row of canvas row 0
        whole = int(math.floor(offset))
        fraction = offset - whole
        total = 0.0
        count = 0
        for (x0, y0, x1, y1), reference in zip(bands, shot_bands):
            piece = sheet.crop((x0, y0 + whole, x1, y1 + whole + 1))
            if fraction > 1e-3:
                piece = piece.transform(piece.size, Image.Transform.AFFINE, (1.0, 0.0, 0.0, 0.0, 1.0, fraction),
                                        Image.Resampling.BILINEAR)
            piece = piece.crop((0, 0, piece.width, reference.height)).convert("L")
            hist = ImageChops.difference(reference, piece).histogram()
            total += sum(i * c for i, c in enumerate(hist))
            count += reference.width * reference.height
        return total / count

    coarse = min(((score(s), s) for s in range(0, limit + 1, MATCH_STEP)), default=(0.0, 0))
    around = range(max(0, coarse[1] - MATCH_STEP), min(limit, coarse[1] + MATCH_STEP) + 1)
    fine = min((score(s), s) for s in around)
    eighths = [fine[1] + q / 8.0 for q in range(-7, 8) if 0 <= fine[1] + q / 8.0 <= limit]
    best = min((score(s), s) for s in eighths)
    return best[1], best[0]


@dataclass
class Match:
    build: str
    size: str
    scroll: float
    text_diff: float            # mean absolute difference over the text bands (0..255)
    bad_text_pixels: int        # pixels that differ by more than 64 there
    regions: Dict[str, float] = field(default_factory=dict)
    page_hash: str = ""


def build_round(build: str) -> Tuple[int, int, str]:
    """Sort key of a build folder name: candidates by round number (`cand` is round 0), probe builds (calib_*) first."""
    digits = "".join(ch for ch in build if ch.isdigit())
    return (0 if build.startswith("calib") else 1, int(digits) if digits else 0, build)


def match_shot(sims: Dict[str, Simulator], shot: Image.Image, name: str, page_file: int, sizes: Iterable[str],
               buttons: int, arrows: bool, preferred: str = "") -> Tuple[Optional[Match], Optional[ScreenRender], Dict[str, Match]]:
    """The build and scroll whose render is closest to a console pair, over every build that has the page.

    Builds whose page renders alike are scored once; among those the `preferred` build (the one the folder was
    classified as; "a or b" names two) is named, else the newest round. Returns the best match, its render, and
    the result of every build (keyed by build name).
    """
    seen: Dict[Tuple[str, str], str] = {}
    results: Dict[str, Match] = {}
    best: Optional[Match] = None
    best_render: Optional[ScreenRender] = None
    for build, sim in sims.items():
        if name not in sim.files:
            continue
        manual = sim.manual(name)
        for size in sizes:
            if page_file not in manual.pages(size):
                continue
            # Builds whose page files are byte-identical render alike; so do builds whose files differ only in
            # bytes the render does not read, so the render itself is the twin key.
            digest = manual.page_hash(page_file, size)
            twin = seen.get((digest, size))
            if twin is None:
                column = sim.column(name, page_file, size)[0]
                digest = hashlib.sha1(column.tobytes()).hexdigest()[:12]
                twin = seen.get((digest, size))
            if twin is not None:
                results[build] = Match(build, size, results[twin].scroll, results[twin].text_diff, results[twin].bad_text_pixels,
                                       dict(results[twin].regions), digest)
                continue
            seen[(manual.page_hash(page_file, size), size)] = build
            seen[(digest, size)] = build
            column = sim.column(name, page_file, size)[0]
            limit = ss.scroll_range(column.height)
            scroll, _score = best_scroll(shot, column, limit)
            render = sim.render(name, page_file, size, scroll, buttons=buttons, arrows=arrows)
            canvas = render.canvas.convert("RGB")
            match = Match(build, size, scroll, mean_diff(shot, canvas, REGIONS["text"]), bad_pixels(shot, canvas, REGIONS["text"]),
                          {region: round(mean_diff(shot, canvas, boxes), 2) for region, boxes in REGIONS.items()}, digest)
            results[build] = match
            if best is None or match.text_diff < best.text_diff:
                best, best_render = match, render
    if best is not None:
        # Builds that render alike, or whose render differs from the best by less than SAME_EPS in the text bands
        # (they differ outside the part of the page the screenshot shows), are the same build for this pair.
        twins = [b for b, m in results.items()
                 if m.size == best.size and (m.page_hash == best.page_hash or m.text_diff - best.text_diff <= SAME_EPS)]
        wanted = [b.strip() for b in preferred.split(" or ") if b.strip() in twins]
        chosen = wanted[0] if wanted else max(twins, key=build_round)
        if chosen != best.build:
            best = Match(chosen, best.size, best.scroll, best.text_diff, best.bad_text_pixels, dict(best.regions), best.page_hash)
    return best, best_render, results


def comparison_sheet(shot: Image.Image, render: Image.Image) -> Image.Image:
    """console | simulator | difference, side by side."""
    sheet = Image.new("RGB", (ss.CANVAS[0] * 3, ss.CANVAS[1]), (0, 0, 0))
    sheet.paste(shot, (0, 0))
    sheet.paste(render, (ss.CANVAS[0], 0))
    sheet.paste(ImageChops.difference(shot, render), (ss.CANVAS[0] * 2, 0))
    return sheet


def page_table(sim: Simulator, name: str) -> List[Dict[str, Any]]:
    """Console page number <-> Page_NNN <-> title <-> category <-> sub-pages, from the manual's Index."""
    manual = sim.manual(name)
    index = manual.index
    rows = []
    large = manual.pages("large")
    small = manual.pages("small")
    for page_file, title in enumerate(index.titles):
        category = index.category_of(page_file)
        rows.append({
            "console_page": index.number_of(page_file),
            "page_file": f"Page_{page_file:03d}",
            "title": title,
            "category": index.categories[category].name if index.categories else "",
            "category_index": category,
            "category_listed": index.categories[category].valid if index.categories else True,
            "blocks_large": index.splits_large[page_file] if page_file < len(index.splits_large) else None,
            "blocks_small": index.splits_small[page_file] if page_file < len(index.splits_small) else None,
            "files_large": sum(1 for _ in cr.page_files(manual.files("large"), page_file, "large")) - 1 if page_file in large else 0,
            "files_small": sum(1 for _ in cr.page_files(manual.files("small"), page_file, "small")) - 1 if page_file in small else 0,
        })
    return rows


def defects_json(defects: List[Defect]) -> List[Dict[str, Any]]:
    return [asdict(defect) for defect in defects]


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
