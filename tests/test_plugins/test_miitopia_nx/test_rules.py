"""Miitopia (Switch) plugin: the 3DS plugin's MSBT rules with the Switch's font and picture formats."""
import json
from pathlib import Path

from plugins.testing import check_loads, check_validator

PLUGIN = "miitopia_nx"
FOLDER = Path(__file__).resolve().parents[3] / "plugins" / PLUGIN


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert rules.get_display_name() == "Miitopia (Switch)"
    assert rules.problem_prefix == "MIINX"
    check_validator(PLUGIN)


def test_sources_use_the_switch_formats():
    fonts = json.loads((FOLDER / "font_sources.json").read_text(encoding="utf-8"))
    pictures = json.loads((FOLDER / "texture_sources.json").read_text(encoding="utf-8"))
    assert {f["format"] for f in fonts} == {"bffnt"}
    assert {t["format"] for t in pictures} == {"bntx"}
