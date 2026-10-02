"""The BMG parser lives in the Twilight Princess plugin: ``plugins/zelda_bmg/bmg_tool.py``.

This file keeps ``from bmg_tool import BMGFile`` and
``python bmg_tool.py extract <input.bmg> <output.json>`` working.
"""
from plugins.zelda_bmg.bmg_tool import *  # noqa: F401,F403
from plugins.zelda_bmg.bmg_tool import BMGFile, BMGMessage, main  # noqa: F401

if __name__ == "__main__":
    main()
