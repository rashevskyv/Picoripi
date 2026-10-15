"""3DS manual tools: the repo_manual folder's modules stay out of sys.modules, the font codec is chosen by its
first byte, the folder choice is stored by the render worker, and a message clears the title bar.

The folder tests build a synthetic folder of stub modules; the font decode test reads the owner's folder
(PICORIPI_ROMHACKING) and skips without it.
"""
import sys
from types import SimpleNamespace

import pytest

import romhacking_root
from plugins.manual_3ds import preview_panel, repo_tools
from plugins.manual_3ds import rules as m3d

_REPO_MANUAL = ("_shared", "3ds_sysfont_ua", "repo_manual")
_STUB_TOOLS = ("manual", "bcma", "bclyt", "bcfnt", "lz10", "lz11", "darc")


def _synthetic_folder(base):
    """A repo_manual-shaped folder whose tool modules are one-line stubs."""
    (base / "tools").mkdir(parents=True)
    for name in _STUB_TOOLS:
        body = 'BASE_SLOT = "EUR"\nMANUALS = {}\n' if name == "manual" else "VALUE = 1\n"
        (base / "tools" / f"{name}.py").write_text(body, encoding="utf-8")
    font = base / repo_tools.FONT_RELATIVE
    font.parent.mkdir(parents=True)
    font.write_bytes(b"x")
    return base


def test_load_tools_leaves_the_bare_tool_names_out_of_sys_modules(tmp_path, monkeypatch):
    for name in ("manual", "bcma", "lz10", "lz11", "bclyt", "bcfnt"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    sentinel = object()
    monkeypatch.setitem(sys.modules, "darc", sentinel)  # deslop: ignore[module-mocking] planted on purpose; line 44 checks it is kept
    root = _synthetic_folder(tmp_path / "repo")

    tools = repo_tools.load_tools(str(root))

    assert tools.manual.BASE_SLOT == "EUR"  # the tools keep their module objects
    for name in ("manual", "bcma", "lz10", "lz11", "bclyt", "bcfnt"):
        assert name not in sys.modules
    assert sys.modules["darc"] is sentinel


def _fake_tools(root, calls):
    """Tools whose decoders record which one ran; the font 'parse' returns its input."""
    lz10 = SimpleNamespace(decompress=lambda data: calls.append("lz10") or b"ten")
    lz11 = SimpleNamespace(decompress=lambda data: calls.append("lz11") or b"eleven")
    bcfnt = SimpleNamespace(parse=lambda data: ("font", data))
    return repo_tools.Tools(root=root, manual=None, bcma=None, bclyt=None, bcfnt=bcfnt, lz10=lz10, lz11=lz11)


def test_font_with_an_lz11_header_is_decoded_with_lz11(tmp_path):
    calls = []
    font = tmp_path / "lz11" / repo_tools.FONT_RELATIVE
    font.parent.mkdir(parents=True)
    font.write_bytes(bytes([0x11]) + b"\x00\x01\x00\x00rest")  # LZ11 header byte, then the rest of a stream
    tools = _fake_tools(tmp_path / "lz11", calls)

    assert repo_tools.load_font(tools) == ("font", b"eleven")
    assert calls == ["lz11"]


def test_font_with_an_lz10_header_is_decoded_with_lz10(tmp_path):
    calls = []
    font = tmp_path / "lz10" / repo_tools.FONT_RELATIVE
    font.parent.mkdir(parents=True)
    font.write_bytes(bytes([0x10]) + b"\x00\x01\x00\x00rest")
    tools = _fake_tools(tmp_path / "lz10", calls)

    assert repo_tools.load_font(tools) == ("font", b"ten")
    assert calls == ["lz10"]


def test_the_chosen_folder_is_stored_by_the_render_worker(monkeypatch, tmp_path):
    stored = []
    monkeypatch.setattr(preview_panel, "save_folder", lambda folder: stored.append(folder))
    monkeypatch.setattr(preview_panel, "load_folder", lambda: "")  # never read the user's own settings here
    request = preview_panel._Request("", "activity_log", "small/Page_003_small", {}, "", str(tmp_path))
    worker = preview_panel.PageRenderWorker(1, request, None)

    worker.run()  # no folder is set, so the drawing fails; the save must still happen first

    assert stored == [str(tmp_path)]


def test_a_message_clears_the_drawn_page(qtbot, monkeypatch):
    monkeypatch.setattr(preview_panel, "load_folder", lambda: "")
    rules = m3d.GameRules()
    rules.load_data_from_json_obj('{"index/Index#0": {"lines": 1, "width": 300.0, "en": "T", "ru": "T", "ua": "T"}}')
    panel = preview_panel.ManualPreviewPanel(SimpleNamespace(), rules)
    qtbot.addWidget(panel)
    panel._result = object()  # type: ignore[assignment]  a drawn page stands in here

    panel._show_message("Select a string of a manual page.")

    assert panel._result is None and panel._message == "Select a string of a manual page."


@pytest.mark.skipif(romhacking_root.missing(*_REPO_MANUAL, "tools", "manual.py") is not None,
                    reason=romhacking_root.missing(*_REPO_MANUAL, "tools", "manual.py") or "")
def test_the_real_system_font_decodes_with_the_real_tools():
    tools = repo_tools.load_tools(str(romhacking_root.path(*_REPO_MANUAL)))
    assert repo_tools.load_font(tools) is not None
