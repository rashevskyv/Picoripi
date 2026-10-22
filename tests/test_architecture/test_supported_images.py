"""Every plugin declares the images it opens (config.json "supported_images"), and the declared ids are in its code.

A plugin whose identify_source reads its ids from its declaration is the table itself, so it is not searched for them.
"""
import json
from pathlib import Path

import pytest

from core.project_library.supported_images import ID_KINDS, appears_in, normalise, problems
from plugins.validate import plugin_names

PLUGINS = Path("plugins")


def _config(name):
    return json.loads((PLUGINS / name / "config.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", plugin_names())
def test_every_plugin_declares_its_images(name):
    assert problems(_config(name).get("supported_images")) == []


@pytest.mark.parametrize("name", plugin_names())
def test_every_declared_id_is_in_the_plugin_code(name):
    entries = normalise(_config(name).get("supported_images"))
    folder = PLUGINS / name
    sources = [path for path in folder.rglob("*") if path.suffix in (".py", ".json")
               and path.name != "config.json" and "tests" not in path.parts and "translation_prompts" not in path.parts]
    if any("_declared_ids" in path.read_text(encoding="utf-8") for path in sources if path.suffix == ".py"):
        return
    text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in sources)
    missing = [item["id"] for item in entries if item["kind"] in ID_KINDS and not appears_in(item["id"], text)]
    assert missing == [], f"declared ids the code does not contain: {missing}"


def test_the_rules_class_answers_the_declaration():
    from plugins.zelda_tww.rules import GameRules

    assert GameRules(None).get_supported_images()[0]["id"] == "GZLE01"
    assert GameRules(None)._declared_ids() == ("GZLE01",)
