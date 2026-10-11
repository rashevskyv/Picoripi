"""Layton Brothers: Mystery Room plugin: the strings the workspace's 1_unpack.bat exports from the Unity data files.

A source file is ``{"strings": [...]}`` (one file per Unity data file, strings in object order, Unity rich text such as
``[#ffffff]`` kept in the text); Translation holds the same shape. The workspace's build puts the changed strings back
into the objects' data (zt/layton_mr.py in the RomHacking _shared folder, run in the UnityPy venv).
"""
from typing import Any

from plugins.base_game_rules import BaseGameRules

from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS


class GameRules(BaseGameRules):
    """Mystery Room strings as one block per Unity data file."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS

    def get_display_name(self) -> str:
        return "Layton Brothers: Mystery Room"

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        return {"strings": [str(s) for s in (data[0] if data else [])]}
