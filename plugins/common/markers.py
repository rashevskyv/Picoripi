"""
Common visual markers used by plugins and utility modules.

These constants were originally defined in plugins/pokemon_fr/config.py,
but are needed by core utils (utils.py, syntax_highlighter.py).
Moving them here breaks the circular dependency where low-level modules
import from high-level plugin packages.
"""

# Visual editor markers for Pokemon FR-style newline characters (\p, \l)
P_VISUAL_EDITOR_MARKER = "▶"
L_VISUAL_EDITOR_MARKER = "▷"

# Newline markers (same symbols, used in different contexts)
P_NEWLINE_MARKER = "▶"
L_NEWLINE_MARKER = "▷"
