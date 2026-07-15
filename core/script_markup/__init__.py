"""Script Markup Studio core: convert raw walkthrough scripts into the
standardized Picoripi script format ([Chapter:]/[Location:]/{Action:}/SPEAKER:).

This package is UI-agnostic and deterministic so it can be unit-tested and
reused across plugins. The Qt dialog lives in ui/script_markup_studio_dialog.py.
"""
from .markup_recipe import MarkupRecipe, default_recipe, LineKind
from .markup_engine import classify_lines, render_psm, convert, ConversionResult, ClassifiedLine
from .hierarchy_markup import (
    BREAKER_LINE,
    HierarchyMark,
    HierarchyNode,
    HierarchyType,
    HierarchyTypeDefinition,
    build_hierarchy_tree,
    default_type_definitions,
    line_styles_for_marks,
    mark_text,
    render_hierarchy_markdown,
    resolve_structure_name_iterator,
)
from .hierarchy_ai import (
    MAX_AUTO_MARKUP_PROMPT_CHARS,
    HierarchyAIMessages,
    HierarchyAIPromptTooLarge,
    build_hierarchy_auto_markup_messages,
    parse_hierarchy_auto_markup_response,
)
from .hierarchy_ai_jobs import (
    HIERARCHY_AI_REQUEST_TIMEOUT_SECONDS,
    HIERARCHY_FORMAT_VERSION,
    HIERARCHY_PROJECT_FORMAT,
    HierarchyAIPrepareWorker,
    HierarchyAIWorker,
    prepare_hierarchy_ai_jobs_from_snapshot,
)
from .hierarchy_project import (
    HierarchyImportStatus,
    HierarchyProject,
    HierarchyProjectError,
    hierarchy_import_status,
    load_hierarchy_project,
    parse_hierarchy_project,
)
from .local_autofill import LocalAutofillResult, infer_hierarchy_marks_from_examples
from .picoripi_rules import (
    parse_with_rules,
    transcript_to_psm,
    summarize_transcript,
    annotate_source_lines,
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
    "BREAKER_LINE",
    "HierarchyMark",
    "HierarchyNode",
    "HierarchyType",
    "HierarchyTypeDefinition",
    "build_hierarchy_tree",
    "default_type_definitions",
    "line_styles_for_marks",
    "mark_text",
    "render_hierarchy_markdown",
    "resolve_structure_name_iterator",
    "MAX_AUTO_MARKUP_PROMPT_CHARS",
    "HierarchyAIMessages",
    "HierarchyAIPromptTooLarge",
    "build_hierarchy_auto_markup_messages",
    "parse_hierarchy_auto_markup_response",
    "HIERARCHY_AI_REQUEST_TIMEOUT_SECONDS",
    "HIERARCHY_FORMAT_VERSION",
    "HIERARCHY_PROJECT_FORMAT",
    "HierarchyAIPrepareWorker",
    "HierarchyAIWorker",
    "prepare_hierarchy_ai_jobs_from_snapshot",
    "HierarchyImportStatus",
    "HierarchyProject",
    "HierarchyProjectError",
    "hierarchy_import_status",
    "load_hierarchy_project",
    "parse_hierarchy_project",
    "LocalAutofillResult",
    "infer_hierarchy_marks_from_examples",
    "parse_with_rules",
    "transcript_to_psm",
    "summarize_transcript",
    "annotate_source_lines",
    "highlight_kinds_from_transcript",
    "build_line_map",
    "nearest_output",
]
