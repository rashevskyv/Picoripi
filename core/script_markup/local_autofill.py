"""Local hierarchy auto-fill for Script Markup Studio.

Identity-preserving barrel: implementation lives in ``core.script_markup.autofill``.
Existing ``from core.script_markup.local_autofill import ...`` imports keep working.

This module intentionally does not call AI. It uses conservative patterns from
already approved marks and leaves uncertain text unmarked.
"""
from __future__ import annotations

from core.script_markup.autofill.infer import LocalAutofillResult, infer_hierarchy_marks_from_examples

__all__ = [
    "LocalAutofillResult",
    "infer_hierarchy_marks_from_examples",
]
