"""Script Markup Studio core: convert raw walkthrough scripts into the
standardized Picoripi script format ([Chapter:]/[Location:]/{Action:}/SPEAKER:).

This package is UI-agnostic and deterministic so it can be unit-tested and
reused across plugins. The Qt dialog lives in ui/script_markup_studio_dialog.py.
"""
from .markup_recipe import MarkupRecipe, default_recipe, LineKind
from .markup_engine import classify_lines, render_psm, convert, ConversionResult, ClassifiedLine
from .picoripi_rules import (
    parse_with_rules,
    transcript_to_psm,
    summarize_transcript,
    highlight_kinds_from_transcript,
)
from .line_map import build_line_map, nearest_output

__all__ = [
    "MarkupRecipe",
    "default_recipe",
    "LineKind",
    "classify_lines",
    "render_psm",
    "convert",
    "ConversionResult",
    "ClassifiedLine",
    "parse_with_rules",
    "transcript_to_psm",
    "summarize_transcript",
    "highlight_kinds_from_transcript",
    "build_line_map",
    "nearest_output",
]
