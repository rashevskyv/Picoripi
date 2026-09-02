"""Local hierarchy auto-fill package (split from local_autofill.py)."""

from .infer import LocalAutofillResult, infer_hierarchy_marks_from_examples

__all__ = [
    "LocalAutofillResult",
    "infer_hierarchy_marks_from_examples",
]
