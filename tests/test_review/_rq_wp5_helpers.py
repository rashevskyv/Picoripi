"""Shared harness for the WP5 review-queue checks: the same functions run on the current code (tests) and on
the pre-audit baseline worktree (``tests/fixtures/review_queue/wp5/make_golden.py``).

Product modules are imported inside the functions, so whichever ``plugins``/``core`` package is first on
``sys.path`` is the one exercised.
"""
from __future__ import annotations

import functools
import importlib
import struct
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "review_queue" / "wp5"
TP_DUMP_MSG = Path(r"E:\Emulators\RomHacking\Zelda\Twilight Princess\GC + Wii\ISO\ENG\root\res\Msgus")
REAL_ARC = "bmgres3.arc"
REAL_MEMBER = "zel_03.bmg"

# Two saves, one edit each: (message index, new editor text). The tag is the colour escape the game uses.
SYNTH_EDITS = [(2, "Edited line with {escape:255:000001}colour{escape:255:000000}\nand a second line."),
               (4, "You got the {escape:255:000001}Sling{escape:255:000000}!")]
REAL_EDITS = [(1, "And then...the human REALLY\nwon, Brother!"), (2, "Really, Brother?!")]


def synthetic_bmg_bytes() -> bytes:
    """A small Twilight Princess-like BMG (cp1252, 16-byte INF1 entries, escape tags, an empty message)."""
    from bmg_tool import BMGFile, BMGMessage

    bmg = BMGFile()
    bmg.endianness = ">"
    bmg.encoding = "cp1252"
    bmg.section_order = ["INF1", "DAT1", "MID1"]
    texts = [
        [],
        ["Hello there, traveller!\nWelcome to the village."],
        ["This is the line\nthat ", {"type": "escape", "escape_type": 255, "data": "000001"}, "will",
         {"type": "escape", "escape_type": 255, "data": "000000"}, " be edited."],
        ["Sign: Ordon Spring"],
        ["You got the ", {"type": "escape", "escape_type": 255, "data": "000001"}, "Slingshot",
         {"type": "escape", "escape_type": 255, "data": "000000"}, "!\nUse it with care."],
        ["Last message."],
    ]
    for idx, parts in enumerate(texts):
        info = struct.pack(">HH", 0x1388 + idx, 0) + bytes.fromhex("37000000ff000100") + struct.pack(">HH", idx, 0x0400)
        msg = BMGMessage(info=info, parts=parts)
        msg.id = 5000 + idx
        bmg.messages.append(msg)
    return bmg.save()


def u8_archive(member: str, payload: bytes) -> bytes:
    """A one-file U8 archive (the layout ``tests/test_core/test_arc_bmg_integration.py`` uses)."""
    name = member.encode("ascii")
    nodes = struct.pack(">HHII", 0x0100, 0, 1, 2) + struct.pack(">HHII", 0x0000, 1, 0x60, len(payload))
    strings = b"\x00" + name + b"\x00"
    header = struct.pack(">IIII", 0x55AA382D, 0x20, len(nodes) + len(strings), 0x60) + b"\x00" * 16
    data = bytearray(header + nodes + strings)
    data += b"\x00" * (0x60 - len(data))
    data += payload
    data += b"\x00" * ((32 - len(data) % 32) % 32)
    return bytes(data)


def synthetic_arc_bytes() -> bytes:
    return u8_archive("zel_rq.bmg", synthetic_bmg_bytes())


def new_rules(plugin: str):
    """The plugin's GameRules, created the way the plugin handler does (no main window)."""
    module = importlib.import_module(f"plugins.{plugin}.rules")
    return module.GameRules(main_window_ref=None)


def _run_load_worker(pm, rules) -> dict:
    from handlers.project_action.load_worker import ProjectLoadWorker

    worker = ProjectLoadWorker(pm, rules)
    result = {}
    signal = getattr(worker, "finished_with_result", None) or worker.finished
    signal.connect(result.update)
    worker.run()  # inline: the same code the thread runs
    return result


class _SaveWindow:
    """The attributes ``DataStateProcessor._perform_save_impl`` reads in project mode (old and new)."""

    def __init__(self, pm, rules, loaded):
        self.data_store = self
        self.project_manager = pm
        self.current_game_rules = rules
        self.block_to_project_file_map = loaded["block_to_project_file_map"]
        self.data = loaded["data"]
        self.edited_file_data = loaded["edited_file_data"]
        self.block_names = loaded["block_names"]
        self.edited_data = {}
        self.state = None


def tp_save_roundtrip(arc_bytes: bytes, arc_name: str, member: str, edits, workdir) -> dict:
    """Open a zelda_bmg project whose source folder holds ``res/Msgus/<arc_name>``; for each ``(index, text)``
    in ``edits``: reopen the project, edit that one message, save through the host save path (so the second
    save patches the translation archive the first one wrote). Returns, per save, the written ``.bmg`` and the
    packed archive, plus the source and translation strings read back after the last save."""
    from core.data_state_processor import DataStateProcessor
    from core.project_manager import ProjectManager

    workdir = Path(workdir)
    src_root = workdir / "src"
    trans_root = workdir / "trans"
    (src_root / "res" / "Msgus").mkdir(parents=True)
    trans_root.mkdir()
    (src_root / "res" / "Msgus" / arc_name).write_bytes(arc_bytes)

    pm = ProjectManager()
    assert pm.create_new_project(workdir / "proj", "rq", "zelda_bmg", source_path=str(src_root),
                                 translation_path=str(trans_root), is_directory_mode=True)
    pm.sync_project_files(plugin=new_rules("zelda_bmg"))
    arc_rel = f"res/Msgus/{arc_name}"
    bmg_path = Path(pm.get_absolute_path(f".extracted/translation/{arc_rel}/{member}", is_translation=True))
    arc_path = Path(pm.get_absolute_path(arc_rel, is_translation=True))

    saves = []
    for msg_idx, new_text in edits:
        rules = new_rules("zelda_bmg")
        loaded = _run_load_worker(pm, rules)
        output = [list(edited) or list(src) for edited, src in zip(loaded["edited_file_data"], loaded["data"])]
        output[0][msg_idx] = new_text
        changes = {(0, msg_idx): new_text}
        window = _SaveWindow(pm, rules, loaded)
        window.edited_data = dict(changes)
        dsp = DataStateProcessor(window)
        ok, _warnings, errors = dsp._perform_save_impl(output, edited_data_for_transaction=changes)
        for timer in (getattr(dsp, "autosave_timer", None), getattr(dsp, "durable_session_timer", None)):
            if timer is not None:
                timer.stop()
        saves.append({
            "ok": ok,
            "errors": list(errors),
            "bmg": bmg_path.read_bytes() if bmg_path.exists() else b"",
            "arc": arc_path.read_bytes() if arc_path.exists() else b"",
        })

    reopened = _run_load_worker(pm, new_rules("zelda_bmg"))
    return {"saves": saves, "source": reopened["data"][0], "reopened": reopened["edited_file_data"][0]}


# --- Twilight Princess game-like preview ------------------------------------------------------------------

TP_DUMP_ROOT = TP_DUMP_MSG.parent.parent  # .../root
_COLOR_ON = {"type": "escape", "escape_type": 255, "data": "000001"}
_COLOR_OFF = {"type": "escape", "escape_type": 255, "data": "000000"}

# (label, message_id, fuki_kind, item_no, parts). The index in this list is the message index.
PREVIEW_MESSAGES = [
    ("dialogue", 0x0400, 0, 0, ["Hey, Link! Over here!\nThe ", _COLOR_ON, "goats", _COLOR_OFF, " got out again."]),
    ("wood_sign", 0x0401, 2, 0, ["Ordon Village\nRanch ahead.\nBeware of goats."]),
    ("stone_sign", 0x0402, 6, 0, ["Here lies\nthe hero of old."]),
    ("item", 0x02A5, 0, 0, ["You got the ", _COLOR_ON, "Slingshot", _COLOR_OFF, "!\nNow you can shoot\npumpkins."]),
    ("item_no", 0x0410, 9, 0x4B, ["You got a ", _COLOR_ON, "Heart Piece", _COLOR_OFF, "!"]),
    ("place", 0x0403, 12, 0, ["Faron Woods"]),
    ("subtitles", 0x0404, 1, 0, ["Long ago, the light spirits sealed the darkness."]),
    ("boss", 0x0405, 19, 0, ["Twilit Parasite Diababa"]),
    ("howl", 0x0406, 17, 0, ["Howl along with the melody!"]),
    ("staff", 0x0407, 7, 0, ["Producer\nSomebody\n\nDirector\nSomeone else"]),
    ("midna", 0x0408, 13, 0, ["Heh! Not bad,\nfor a beast."]),
    ("spirit", 0x0409, 8, 0, ["O brave one...\nThe shadows grow."]),
]
PREVIEW_SIZE = (560, 300)


def _preview_info(message_id: int, fuki_kind: int, item_no: int) -> bytes:
    data = bytearray(16)
    data[0], data[1] = (message_id >> 8) & 0xFF, message_id & 0xFF
    data[5] = fuki_kind
    data[8] = item_no
    return bytes(data)


def preview_bmg():
    from bmg_tool import BMGFile, BMGMessage

    bmg = BMGFile()
    bmg.encoding = "cp1252"
    bmg.section_order = ["INF1", "DAT1", "MID1"]
    for idx, (_label, message_id, kind, item_no, parts) in enumerate(PREVIEW_MESSAGES):
        msg = BMGMessage(info=_preview_info(message_id, kind, item_no), parts=list(parts))
        msg.id = idx
        bmg.messages.append(msg)
    loaded = BMGFile()
    loaded.load(bmg.save())
    return loaded


def synthetic_bfn():
    """A BFN with an ASCII map whose glyph cells carry a pattern unique to each glyph, so a shifted or
    swapped glyph changes pixels."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QImage, QPainter

    from core.bfn_core import BfnCore

    bfn = BfnCore()
    bfn.inf1 = [{"encoding": 1, "ascent": 20, "descent": 4, "width": 12, "leading": 24, "fallback_code": 0,
                 "unk1": 0}]
    bfn.gly1 = [{"start_glyph": 0, "end_glyph": 95, "cell_width": 24, "cell_height": 24, "page_data_size": 0,
                 "texture_format": 0, "glyph_horizontal_count": 5, "glyph_vertical_count": 5,
                 "texture_width": 120, "texture_height": 120, "sheets_binary": []}]
    bfn.map1 = [{"mapping_type": 2, "first_char": 32, "last_char": 127, "mapping_entry_count": 96,
                 "entries": list(range(96))}]
    bfn.wid1 = [{"first_code_included": 0, "last_code_included": 95,
                 "packets": [{"kerning": 1, "width": 12 + (code % 7)} for code in range(96)]}]
    sheets = []
    for sheet in range(4):
        img = QImage(120, 120, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        for cell in range(25):
            glyph = sheet * 25 + cell
            if glyph == 0:  # space
                continue
            x, y = (cell % 5) * 24, (cell // 5) * 24
            painter.fillRect(x + 2, y + 4, 4 + glyph % 10, 14, QColor(255, 255, 255))
            painter.fillRect(x + 2 + glyph % 9, y + 2 + glyph % 5, 3, 3, QColor(255, 255, 255, 128))
        painter.end()
        sheets.append(img)
    bfn._qimages_cache = sheets
    return bfn


@functools.lru_cache(maxsize=1)
def dump_bfn():
    """The game's own font from the retail dump (never stored in the repository)."""
    from core.bfn_core import BfnCore
    from core.containers import ContainerManager

    container = ContainerManager.open((TP_DUMP_ROOT / "res" / "Fontus" / "fontres.arc").read_bytes())
    name = sorted(n for n in container.list_files() if n.lower().endswith(".bfn"))[0]
    bfn = BfnCore()
    bfn.load(container.read_file(name))
    return bfn


class _PreviewStore:
    def __init__(self):
        self.physical_block_idx = 0
        self.current_block_idx = 0
        self.current_string_idx = 0
        self.json_path = "zel_rq.bmg"
        self.edited_json_path = None


class _PreviewWindow:
    """Main-window attributes the preview reads, with the default preview settings."""

    def __init__(self, font, dump_root):
        self.data_store = _PreviewStore()
        self.active_game_plugin = "zelda_bmg"
        self.current_game_rules = None
        self.project_manager = None
        self.block_to_project_file_map = {}
        self.string_metadata = {}
        self.all_bfn_fonts = {"rq.bfn": font}
        self.default_font_file = None
        self.preview_enabled = True
        self.preview_bg_image_path = ""
        self.preview_bg_scale = 100
        self.preview_bg_offset_x = 0
        self.preview_bg_offset_y = 0
        self.preview_bg_hidden = False
        self.preview_line_spacing = 10
        self.preview_text_rect = [15, 15, 300, 120]
        self.preview_text_color = "#ffffff"
        self.preview_shadow_enabled = False
        self.preview_glow_enabled = False
        self.preview_fix_font_scale = False
        self.preview_fixed_font_scale = 1.0
        self.preview_char_spacing = 0
        self.use_per_window_layouts = True
        self.lines_per_page = 4
        self.show_multiple_spaces_as_dots = False
        self.default_tag_mappings = {}
        self.newline_display_symbol = "↵"
        if dump_root is not None:
            self.zelda_game_root = str(dump_root)


def _use_dump(dump_root):
    """Point the frame loader at the dump, or make sure it finds none."""
    from plugins.zelda_bmg import window_frame_loader as loader

    loader._LAYOUT_ROOT = None
    loader._CACHE.clear()
    if dump_root is None:
        loader._KNOWN_DUMP = Path(__file__).parent / "_no_dump_here"


def png_bytes(image) -> bytes:
    from PyQt6.QtCore import QBuffer, QIODevice

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def _paint(widget):
    from PyQt6.QtCore import QPoint
    from PyQt6.QtGui import QImage, QRegion
    from PyQt6.QtWidgets import QWidget

    # Pre-audit code only: it kept the halo of the first style it painted per window class (a Midna or
    # light-spirit window after a dialogue window got the dialogue halo). Forget it so the golden is what
    # the old code paints for this style; the current code has no such cache, so this is a no-op there.
    widget.__dict__.pop("_dump_frame_cls", None)
    widget.__dict__.pop("_dump_frame_style", None)
    image = QImage(widget.size(), QImage.Format.Format_ARGB32)
    image.fill(0)
    widget.render(image, QPoint(), QRegion(), QWidget.RenderFlag.DrawWindowBackground)
    return image


def _preview_session(dump_root):
    from ui.components.bfn_preview.chrome import BfnPreviewWindowBar
    from ui.components.bfn_preview_widget import BfnPreviewWidget

    font = dump_bfn() if dump_root is not None else synthetic_bfn()
    mw = _PreviewWindow(font, dump_root)
    rules = importlib.import_module("plugins.zelda_bmg.rules").GameRules(main_window_ref=mw)
    rules.last_loaded_bmg = preview_bmg()
    mw.current_game_rules = rules
    widget = BfnPreviewWidget(mw)
    widget.resize(*PREVIEW_SIZE)
    bar = BfnPreviewWindowBar(widget)
    widget.show()
    return mw, rules, widget, bar


def _close_session(widget, bar):
    widget.hide()
    bar.deleteLater()
    widget.deleteLater()


def _show_message(mw, rules, widget, idx):
    mw.data_store.current_string_idx = idx
    widget.update_preview_text(rules.msg_to_editor_text(rules.last_loaded_bmg.messages[idx]))


def preview_cases():
    """Case names in render order: every message on Auto, then message 0 with each forced preset."""
    presets = list(importlib.import_module("plugins.zelda_bmg.window_kinds").PREVIEW_WINDOW_PRESETS)
    auto = [(f"auto_{idx:02d}_{label}", idx, 0) for idx, (label, *_r) in enumerate(PREVIEW_MESSAGES)]
    forced = [(f"forced_{step:02d}_{presets[step]}", 0, step) for step in range(1, len(presets))]
    return auto + forced


def render_tp_previews(dump_root=None, fresh=False):
    """Render every case of ``preview_cases()``; a forced preset is reached by clicking the bar's "next"
    button. ``fresh``: a new preview widget per case (no state carried over from the previous case).
    Returns {case: {"image": QImage, "label": bar text, "bar_visible": bool}}, plus "wrapped" (the label
    after cycling past the last preset) and "bar" (the label's minimum width)."""
    _use_dump(dump_root)
    out = {}
    session = _preview_session(dump_root)
    clicked = 0
    cases = preview_cases()
    for name, idx, clicks in cases:
        if fresh:
            _close_session(*session[2:])
            session, clicked = _preview_session(dump_root), 0
        mw, rules, widget, bar = session
        _show_message(mw, rules, widget, idx)
        for _ in range(clicks - clicked):
            bar.btn_next.click()
        clicked = clicks
        out[name] = {"image": _paint(widget), "label": bar.label.text(), "bar_visible": not bar.isHidden()}
    session[3].btn_next.click()  # past the last preset: back to Auto
    out["wrapped"] = {"label": session[3].label.text()}
    out["bar"] = {"label_min_width": session[3].label.minimumWidth()}
    _close_session(*session[2:])
    return out


def pixel_digest(image) -> str:
    """sha256 of the ARGB32 pixels (independent of the PNG encoder)."""
    import hashlib

    from PyQt6.QtGui import QImage

    converted = image.convertToFormat(QImage.Format.Format_ARGB32)
    data = converted.constBits()
    data.setsize(converted.sizeInBytes())
    return hashlib.sha256(bytes(data)).hexdigest()


# --- Problem analyzers, text fixers, autofix, short-line merging, width warnings -------------------------

PLUGINS = ["zelda_bmg", "zelda_ww", "zelda_mc", "pokemon_fr", "plain_text", "default_plugin"]
REPO_PLUGINS = Path(__file__).resolve().parents[2] / "plugins"
# (warning width, hard limit) the corpus is checked with.
LIMITS = {"zelda_bmg": (400, 435)}
DEFAULT_LIMITS = (208, 240)

# Tags of each game's own style; {A}/{B} in the templates are replaced by them.
TAGS = {
    "zelda_bmg": ("{COLOR_RED}", "{COLOR_DEFAULT}", "{escape:6:000a}", "{escape:6:000b}"),
    "zelda_ww": ("[Color:Red]", "[/C]", "[Name]", "[Color:Blue]"),
    "plain_text": ("[Color:Red]", "[/C]", "[Name]", "[Color:Blue]"),
    "zelda_mc": ("{Player}", "{Color:Red}", "{Sound:01}", "{Color:White}"),
    "pokemon_fr": ("{PLAYER}", "{COLOR RED}", "\\p", "{RIVAL}"),
    "default_plugin": ("[PLAYER]", "{COLOR}", "{/COLOR}", "[A]"),
}
LONG = "This line is deliberately far too long to fit into any of the game windows at all"
TEMPLATES = [
    "Hello there!",
    "Hello  there,friend !",
    "Hi\n\nthere",
    "\nStarts with an empty line.\nThen text.",
    "A\nB\nC\nD\nE\nF\nG\nH\nI",
    "Word\nshort\nlines that could\nbe merged",
    LONG,
    LONG + "\nand a second line.",
    "Some text {A}here{B} and more text after it.",
    "{A}Name{B}, listen to me.",
    "{C}First section\n{C}Second section\n{D}Indented",
    "Ends with a single\nword",
    "Line one\nlonely\nline three goes on and on and on and on and on.",
    "Icon:{A} -{B}- text",
    "Two pages here\nsecond line\nthird line\nfourth line\n\nfifth on page two",
    "Trailing space \nand  double  spaces .",
    "",
]
# (original, translation) pairs for the pasted/mismatched tag checks.
TAG_PAIRS = [
    ("{A}x{B} y", "{A}x{B} y"),
    ("{A}x{B} y", "x y"),
    ("{A}x{B} y", "{A}x{A}x{B}{B} y"),
    ("{D}x{B} y", "{A}x{B} y"),
    ("{C} one", "{D} one"),
    ("plain", "{A}plain{B}"),
]


def corpus_for(plugin: str):
    a, b, c, d = TAGS[plugin]

    def fill(text):
        return text.replace("{A}", a).replace("{B}", b).replace("{C}", c).replace("{D}", d)

    if plugin == "pokemon_fr":  # the data keeps line breaks as the escape \n
        texts = [fill(t).replace("\n", "\\n") for t in TEMPLATES]
    else:
        texts = [fill(t) for t in TEMPLATES]
    pairs = [(fill(o), fill(t)) for o, t in TAG_PAIRS]
    if plugin == "plain_text":
        pairs += PLAIN_TEXT_PAIRS
    return texts, pairs


# Plain text checks pasted tags kind by kind (5.2): same total, different kinds; curly tags count too.
PLAIN_TEXT_PAIRS = [
    ("[Color:Red]x[/C] y", "[Color:Red]x[/C] {Name} y"),
    ("[Name] and [/C]", "[Color:Red] and [/C]"),
    ("{Name} said", "{Item} said"),
    ("[Color:Red]a[/C] [Color:Blue]b[/C]", "[Color:Blue]a[/C] [Color:Red]b[/C]"),
]
# What the current code answers for every plain_text pair (TAG_PAIRS filled, then PLAIN_TEXT_PAIRS).
PLAIN_TEXT_PASTE_STATUS = ["OK", "WARNING", "WARNING", "OK", "WARNING", "WARNING",
                           "WARNING", "WARNING", "WARNING", "OK"]
# The pre-audit answers differ for pairs 7 and 9 only: it ignored curly tags ({Name} vs {Item}).
PLAIN_TEXT_CHANGED_PAIRS = (6, 8)


def _font_map(plugin: str) -> dict:
    import json

    path = REPO_PLUGINS / plugin / "font_map.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


class _AnalyzerWindow:
    def __init__(self):
        self.data_store = self
        self.data = [[]]
        self.edited_data = {}
        self.show_multiple_spaces_as_dots = False
        self.default_tag_mappings = {}
        self.icon_sequences = []
        self.newline_display_symbol = "\u21b5"


def _sorted_sets(problems):
    return [sorted(p) for p in problems]


def analyze_corpus(plugin: str, texts, pairs) -> dict:
    """Every analyzer / fixer output of the plugin for the given strings, as plain JSON data."""
    import utils.utils as uu

    uu._ACTIVE_FONT_MAP = None
    uu._ACTIVE_TAG_MAPPINGS = None
    uu._ACTIVE_ICON_SEQUENCES = None
    mw = _AnalyzerWindow()
    rules = importlib.import_module(f"plugins.{plugin}.rules").GameRules(main_window_ref=mw)
    font_map = _font_map(plugin)
    warn, hard = LIMITS.get(plugin, DEFAULT_LIMITS)
    definitions = sorted(rules.get_problem_definitions())
    analyzer = getattr(rules, "problem_analyzer", None)

    strings = []
    for text in texts:
        mw.data = [[text]]
        if analyzer is not None:
            analyzer._current_scan_block_idx, analyzer._current_scan_string_idx = 0, 0
        whole = analyzer.analyze_data_string(text, font_map, warn, hard) if analyzer is not None else []
        sublines = [sorted(rules.analyze_subline(text.split("\n")[k] if k < len(text.split("\n")) else "", None,
                                                 k, k, k == len(whole) - 1, font_map, warn, text,
                                                 logical_hard_limit=hard))
                    for k in range(max(1, len(whole)))]
        fixed_all = list(rules.autofix_data_string(text, font_map, warn, hard))
        fixed_each = {pid: list(rules.autofix_data_string(text, font_map, warn, hard, allowed_problems={pid}))
                      for pid in definitions}
        strings.append({"text": text, "whole": _sorted_sets(whole), "sublines": sublines,
                        "autofix": fixed_all, "autofix_each": fixed_each})

    tag_checks = []
    for original, translation in pairs:
        mw.data = [[original]]
        entry = {"original": original, "translation": translation,
                 "paste": list(rules.process_pasted_segment(translation, original, "{Player}"))}
        if analyzer is not None:
            analyzer._current_scan_block_idx, analyzer._current_scan_string_idx = 0, 0
            entry["whole"] = _sorted_sets(analyzer.analyze_data_string(translation, font_map, warn, hard))
            if hasattr(analyzer, "check_tags_mismatch"):
                entry["mismatch"] = bool(analyzer.check_tags_mismatch(original, translation))
        tag_checks.append(entry)

    problem_ids = getattr(rules, "problem_ids", None)
    return {
        "definitions": definitions,
        "short_names": {pid: rules.get_short_problem_name(pid) for pid in definitions},
        "empty_odd_marker": getattr(problem_ids, "PROBLEM_EMPTY_ODD_SUBLINE_DISPLAY", None),
        "strings": strings,
        "tag_checks": tag_checks,
    }


def tp_dump_texts(limit: int = 200):
    """Editor text of real Twilight Princess messages (read from the dump, never stored), plus a damaged
    copy of each (lines joined, one tag dropped) so that every rule has something to find."""
    from core.containers import ContainerManager

    container = ContainerManager.open((TP_DUMP_MSG / REAL_ARC).read_bytes())
    from bmg_tool import BMGFile

    bmg = BMGFile()
    bmg.load(container.read_file(REAL_MEMBER))
    rules = new_rules("zelda_bmg")
    texts = [rules.msg_to_editor_text(m) for m in bmg.messages[:limit]]
    damaged = []
    for text in texts:
        t = text.replace("\n", " ", 1)
        start = t.find("{")
        if start >= 0:
            end = t.find("}", start)
            t = t[:start] + t[end + 1:]
        damaged.append(t + " " + LONG)
    return texts + damaged


def corpus_digest(result: dict) -> str:
    """sha256 of the analyzer and fixer outputs (strings, tag checks) without the labels."""
    import hashlib
    import json

    kept = {"strings": result["strings"], "tag_checks": result["tag_checks"]}
    return hashlib.sha256(json.dumps(kept, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# --- Effective plugin settings (config.json + built-in defaults) ----------------------------------------

class _SettingsStore:
    def __init__(self):
        self.block_names = {}


class _SettingsWindow:
    """A main window before any project is open."""

    def __init__(self, plugin):
        self.active_game_plugin = plugin
        self.data_store = _SettingsStore()
        self.project_manager = None
        self.current_game_rules = None


def _plain(value):
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(_plain(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def effective_plugin_settings(plugin: str) -> dict:
    """What a plugin opens with: the settings dict and the window attributes PluginSettings.load sets."""
    from core.settings.plugin_settings import PluginSettings

    mw = _SettingsWindow(plugin)
    settings = {}
    PluginSettings(mw).load(settings)
    attributes = {k: v for k, v in vars(mw).items() if k not in ("data_store", "project_manager", "current_game_rules")}
    attributes["block_names"] = mw.data_store.block_names
    return {"settings": _plain(settings), "window": _plain(attributes)}


# --- Archive members, Pokémon FireRed keys --------------------------------------------------------------

def _restore_plugin_state(rules, backup):
    """What the host does with the state the load worker kept: core.formats now, an attribute before."""
    try:
        from core import formats
    except ImportError:  # pre-audit host
        if backup is not None and hasattr(rules, "original_keys"):
            rules.original_keys = backup
        return
    formats.restore_state(rules, backup)


class _Provider:
    """The dialogs the data processor asks through: always 'yes', messages dropped."""

    def ask_yes_no(self, *args, **kwargs):
        return True

    def show_message(self, *args, **kwargs):
        pass


def _open_project(workdir, plugin, files):
    from core.project_manager import ProjectManager

    workdir = Path(workdir)
    src_root, trans_root = workdir / "src", workdir / "trans"
    src_root.mkdir(parents=True)
    trans_root.mkdir()
    for name, payload in files.items():
        (src_root / name).write_bytes(payload)
    pm = ProjectManager()
    assert pm.create_new_project(workdir / "proj", "rq", plugin, source_path=str(src_root),
                                 translation_path=str(trans_root), is_directory_mode=True)
    pm.sync_project_files(plugin=new_rules(plugin))
    return pm, trans_root


def _load(pm, plugin, rules=None):
    rules = rules or new_rules(plugin)
    loaded = _run_load_worker(pm, rules)
    _restore_plugin_state(rules, loaded.get("plugin_keys_backup"))
    return rules, loaded


ARCHIVE_MEMBER_CASES = [
    ("zelda_mc", "strings.json", b'[["Hello", "World"]]'),
    ("plain_text", "strings.txt", b"Hello\nWorld\n"),
    ("pokemon_fr", "p.json", b'{"B": {"k": "v"}}'),
    ("zelda_bmg", "zel_rq.bmg", None),   # None: the synthetic BMG
]


def archive_member_load(plugin: str, member: str, payload: bytes, workdir) -> list:
    """Data blocks a project gets from one member of a U8 archive."""
    if payload is None:
        payload = synthetic_bmg_bytes()
    pm, _trans = _open_project(workdir, plugin, {"pack.arc": u8_archive(member, payload)})
    _rules, loaded = _load(pm, plugin)
    return loaded["data"]


POKEMON_FILES = {
    "text_a.json": {"Z_town": {"t3": "Welcome to PALLET TOWN!", "t1": "Shades of your journey await!"},
                    "A_lab": {"l9": r"PROF. OAK: Hello there!\nWelcome to the world of POKeMON!",
                              "l2": r"This is a POKeDEX.\pIt records data."}},
    "text_b.json": {"M_mart": {"m5": r"Welcome!\nMay I help you?", "m0": "Thank you!"}},
}
# A project of one Pokémon file with one block: the shape that is not split into sub-blocks.
POKEMON_SINGLE = {"text_c.json": {"Q_route": {"r7": "Route 1", "r2": r"Tall grass\nahead."}}}


def pokemon_roundtrip(workdir, files=None, snapshot=None) -> dict:
    """A pokemon_fr project (default: two files, three blocks). Save one edit; restore the plugin keys from a
    session snapshot (``snapshot``, or the one this code writes) into a fresh plugin and save another edit;
    then revert the project.
    Returns the text of the translation files after each step and the session snapshot."""
    import json

    from core.data_state_processor import DataStateProcessor

    files = {name: json.dumps(content, ensure_ascii=False).encode("utf-8")
             for name, content in (files or POKEMON_FILES).items()}
    pm, trans_root = _open_project(workdir, "pokemon_fr", files)
    rules, loaded = _load(pm, "pokemon_fr")

    def texts():
        return {p.name: p.read_text(encoding="utf-8") for p in sorted(trans_root.glob("*.json"))}

    def save(window, block, string, text):
        output = [list(edited) or list(src) for edited, src in zip(window.edited_file_data, window.data)]
        output[block][string] = text
        changes = {(block, string): text}
        window.edited_data = dict(changes)
        dsp = DataStateProcessor(window)
        ok, _warnings, errors = dsp._perform_save_impl(output, edited_data_for_transaction=changes)
        _stop_timers(dsp)
        assert ok and not errors, errors
        return dsp

    names = [loaded["block_names"][str(i)] for i in range(len(loaded["data"]))]
    window = _SaveWindow(pm, rules, loaded)
    window.ui_provider = _Provider()
    last = len(loaded["data"]) - 1                       # a block of the second file
    dsp = save(window, last, 0, "Welcome, trainer!")
    after_save = texts()

    written = json.loads(json.dumps(dsp.session_manager._attach_runtime_session_state({})))
    snapshot = written if snapshot is None else snapshot
    fresh, reloaded = _load(pm, "pokemon_fr", rules=None)
    if hasattr(fresh, "original_keys"):
        fresh.original_keys = []                         # a new plugin instance knows no keys yet
    window2 = _SaveWindow(pm, fresh, reloaded)
    window2.ui_provider = _Provider()
    restorer = DataStateProcessor(window2)
    restorer.session_manager._restore_runtime_session_state(snapshot)
    _stop_timers(restorer)
    dsp2 = save(window2, 0, 1, "Edited after the session restore")
    after_session = texts()

    dsp2.revert_manager.revert_edited_file_to_original()
    _stop_timers(dsp2)
    after_revert = texts()
    return {"names": names, "after_save": after_save, "snapshot": written,
            "after_session": after_session, "after_revert": after_revert}


def _stop_timers(dsp):
    for timer in (getattr(dsp, "autosave_timer", None), getattr(dsp, "durable_session_timer", None)):
        if timer is not None:
            timer.stop()


# --- A fake OpenAI-compatible server ------------------------------------------------------------------

class FakeChatServer:
    """POST /v1/chat/completions on 127.0.0.1: records each request body and answers ``reply(body)``."""

    def __init__(self, reply):
        import http.server
        import json
        import threading

        self.requests = []
        server_self = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                server_self.requests.append(body)
                content = reply(body)
                payload = json.dumps({"id": "rq", "object": "chat.completion", "model": body.get("model", "m"),
                                      "choices": [{"index": 0, "finish_reason": "stop",
                                                   "message": {"role": "assistant", "content": content}}],
                                      "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
                data = payload.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}/v1"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def close(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(5)
