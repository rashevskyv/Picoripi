"""Family projects: one translation for the strings that several consoles of one game share.

The plugin declares the family (``BaseGameRules.family_plan``): its members, which member links to which, and how
each member's units are read. This package is the generic engine: alignment by match key, the shared store,
per-member overrides, seeding and fan-out. It never reads a game format.
"""
