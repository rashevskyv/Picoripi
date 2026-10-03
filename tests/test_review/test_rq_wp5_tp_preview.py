"""WP5 review queue: "The game-like preview of Twilight Princess now gets everything through plugin hooks (5.7)".

The real preview widget and its "Auto / forced window" bar render every window kind (dialogue, signs, item
window, location plate, subtitles, boss, howl, credits, Midna, light spirit) and then message 0 with every
forced preset. Pixels, bar labels and the bar width must equal what the pre-audit code produced
(``tests/fixtures/review_queue/wp5/make_golden.py``; tolerance 0). Then Settings -> "limits by window type":
edit, OK, reopen keeps the value, and the file is written exactly as the old dialog wrote it.
"""
import json
from pathlib import Path

import pytest
from PyQt6.QtGui import QImage

from . import _rq_wp5_helpers as h

GOLDEN = h.FIXTURES / "preview"
HAS_DUMP = (h.TP_DUMP_ROOT / "res" / "Layout" / "msgres01.arc").exists()


@pytest.fixture
def no_layout_cache():
    from plugins.zelda_bmg import window_frame_loader as loader

    saved = (loader._LAYOUT_ROOT, loader._KNOWN_DUMP, dict(loader._CACHE))
    yield
    loader._LAYOUT_ROOT, loader._KNOWN_DUMP = saved[0], saved[1]
    loader._CACHE.clear()
    loader._CACHE.update(saved[2])


def _same_pixels(actual: QImage, golden: QImage) -> bool:
    fmt = QImage.Format.Format_ARGB32
    return actual.convertToFormat(fmt) == golden.convertToFormat(fmt)


def test_every_window_kind_and_forced_preset_paints_as_before(qapp, no_layout_cache):
    meta = json.loads((GOLDEN / "synthetic.json").read_text(encoding="utf-8"))
    rendered = h.render_tp_previews(None)

    assert set(rendered) == set(meta)
    differing = []
    for name, value in rendered.items():
        if "image" not in value:
            assert value == meta[name], name
            continue
        golden = QImage(str(GOLDEN / f"{name}.png"))
        assert not golden.isNull(), name
        if not _same_pixels(value["image"], golden):
            differing.append(name)
        assert value["label"] == meta[name]["label"], name
        assert value["bar_visible"] is True and meta[name]["bar_visible"] is True
    assert differing == []
    # The bar names the window it shows: Auto follows the message, a forced preset is named plainly.
    assert rendered["auto_03_item"]["label"] == "Auto: Item get"     # message 0x02A5 forces the item window
    assert rendered["forced_02_2"]["label"] == "Wooden sign"
    assert rendered["wrapped"]["label"] == "Auto: Dialogue"


@pytest.mark.skipif(not HAS_DUMP, reason="retail Twilight Princess dump not on this machine")
def test_with_the_retail_dump_frames_icons_and_font_paint_as_before(qapp, no_layout_cache):
    """The game's own frames, item icons and font. Only pixel digests are stored."""
    golden = json.loads((GOLDEN / "dump_digests.json").read_text(encoding="utf-8"))
    rendered = h.render_tp_previews(h.TP_DUMP_ROOT)

    actual = {name: ({"pixels": h.pixel_digest(v["image"]), "label": v["label"]} if "image" in v else v)
              for name, v in rendered.items()}
    assert actual == golden


@pytest.mark.skipif(not HAS_DUMP, reason="retail Twilight Princess dump not on this machine")
def test_a_window_s_halo_does_not_depend_on_the_previous_message(qapp, no_layout_cache):
    """Intended difference from the old code: it reused the halo of the first window of the same frame class
    (a light-spirit message after a Midna message glowed blue). Now each window paints its own halo."""
    in_order = h.render_tp_previews(h.TP_DUMP_ROOT)
    one_by_one = h.render_tp_previews(h.TP_DUMP_ROOT, fresh=True)

    for name in in_order:
        if "image" in in_order[name]:
            assert _same_pixels(in_order[name]["image"], one_by_one[name]["image"]), name


# --- Settings -> limits by window type -------------------------------------------------------------------

def _dialog(mw):
    from ui.settings_dialog import SettingsDialog

    return SettingsDialog(mw)


# The rows of the pre-audit dialog (ui/settings/plugin_tabs_mixin.py at 691699c0, _ZELDA_BMG_WINDOW_GROUPS).
_BASELINE_GROUPS = (
    ("dialog", None), ("signs", ("2", "6")), ("kanban_talk", ("15",)), ("item", ("9",)),
    ("explain", ("16",)), ("subtitles", ("1", "5")), ("titles", ("12", "19")), ("howling", ("17",)),
    ("credits", ("7",)),
)


def _baseline_document(original, values):
    """What the pre-audit persist_zelda_bmg_window_rules() wrote for these table values."""
    document = json.loads(json.dumps(original))
    defaults = document.setdefault("default", {})
    kinds = document.setdefault("kinds", {})
    for key, target_kinds in _BASELINE_GROUPS:
        targets = [defaults] if target_kinds is None else [kinds.setdefault(kind, {}) for kind in target_kinds]
        for target in targets:
            target.update(values[key])
    return json.dumps(document, indent=4, ensure_ascii=False) + "\n"


def _table(dialog):
    return {key: {name: spin.value() for name, spin in controls.items()}
            for key, controls in dialog._zelda_window_layout_controls.items()}


def test_window_limits_table_edit_ok_reopen_keeps_the_value(qapp, tmp_path, monkeypatch):
    from test_ui.test_settings.test_settings_dialog_presets import _zelda_bmg_window

    source = Path("plugins/zelda_bmg/window_layouts.json")
    source_text = source.read_text(encoding="utf-8")
    original = json.loads(source_text)
    target = tmp_path / "window_layouts.json"
    target.write_text(source_text, encoding="utf-8")
    mw = _zelda_bmg_window(target)
    rules = mw.current_game_rules
    rules._get_window_layouts()  # the preview has already read the limits

    dialog = _dialog(mw)
    assert [key for key, _label, _kinds in rules.get_window_layout_groups()] == [k for k, _ in _BASELINE_GROUPS]
    item = dialog._zelda_window_layout_controls["item"]
    item["warn_width"].setValue(311)
    item["max_width"].setValue(333)
    item["lines_per_page"].setValue(3)
    values = _table(dialog)
    dialog.accept()

    reopened = _dialog(mw)
    assert _table(reopened) == values
    assert values["item"] == {"warn_width": 311, "max_width": 333, "lines_per_page": 3}
    reopened.reject()

    assert target.read_text(encoding="utf-8") == _baseline_document(original, values)
    # The preview uses the new limit at once: the forced item window pages after three lines.
    assert rules.get_window_style_for_preset(9)["lines_per_page"] == 3
    assert source.read_text(encoding="utf-8") == source_text      # the plugin's own file is untouched
