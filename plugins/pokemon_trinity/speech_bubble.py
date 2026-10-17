"""Legends: Z-A boxes measured or derived from the game files, kept as facts in config.json:

- ``speech_bubble``: the NPC speech bubble, MEASURED on an Eden frame (font, glyph size, pen and baseline per line).
- ``hud_message``: the lower-left message window, LAYOUT-DERIVED (hud_msg_00.bflyt pane T_talk_00), frame pending.

Both become preview box specs; the shared renderer (plugins/common/switch_message_preview) draws them.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from plugins.common.switch_message_preview import BoxSpec, speech_spec

CONFIG_PATH = Path(__file__).with_name("config.json")


def _facts(key: str) -> Dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))[key]


def load_facts() -> Dict[str, Any]:
    """The speech bubble facts (``speech_bubble``)."""
    return _facts("speech_bubble")


def speech_box() -> BoxSpec:
    """The speech bubble as a box spec."""
    return speech_spec(load_facts())


def hud_box() -> BoxSpec:
    """The lower-left message window (``hud_message``) as a box spec; its label is 'Message window (HUD)'."""
    facts = _facts("hud_message")
    return speech_spec(facts, label="Message window (HUD)")


__all__ = ["hud_box", "load_facts", "speech_box"]
