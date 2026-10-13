"""Family projects: one translation for the strings that several consoles of one game share.

A family is one game on several platforms (Twilight Princess GC, Wii and HD). Strings with the same source text
are one unit: translated once, fanned out to every console that has the unit. A string that only one console
has is that console's own override. Pure logic only: the game format is read by the plugin (see
`plugins/zelda_bmg/family.py`).
"""
