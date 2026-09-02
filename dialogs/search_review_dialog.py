"""Dialog for interactive searching and replacing of text in a block.

Compatibility shim: implementation lives in dialogs.search_review.*.
"""
from __future__ import annotations

from dialogs.search.search_worker import SearchWorker
from dialogs.search.search_utils import adjust_replacement_case
from dialogs.search_review import SearchReviewDialog

__all__ = [
    "SearchReviewDialog",
    "SearchWorker",
    "adjust_replacement_case",
]
