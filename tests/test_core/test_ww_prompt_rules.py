"""The Wind Waker prompts tell the model to address the player with the informal singular."""
import json
from pathlib import Path

import pytest

PLUGINS = Path(__file__).resolve().parents[2] / "plugins"


@pytest.mark.parametrize("plugin", ["zelda_tww", "zelda_ww"])
def test_prompt_has_the_addressing_rule_inside_the_ukrainian_block(plugin):
    data = json.loads((PLUGINS / plugin / "translation_prompts" / "prompts.json").read_text("utf-8"))
    prompt = data["translation"]["system_prompt"]
    start = prompt.index("12. **Addressing the player")
    opening = prompt.rfind("[IF_TARGET_LANG: Ukrainian]", 0, start)
    closing = prompt.index("[/IF_TARGET_LANG]", start)
    assert opening != -1 and prompt.rfind("[/IF_TARGET_LANG]", 0, start) < opening
    rule = prompt[start:closing]
    assert "«ти»" in rule and "NEVER use" in rule
    assert prompt.index("Follow these rules for every line") > closing
