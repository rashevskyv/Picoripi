"""Dialog for merging speaker aliases.

Compatibility shim: implementation lives in components.speaker_merge.*.
"""
from __future__ import annotations

from components.speaker_merge import (
    SpeakerMergeDialog,
    NameOnlyDelegate,
    describe_code,
    extract_candidates,
)

__all__ = [
    "SpeakerMergeDialog",
    "NameOnlyDelegate",
    "describe_code",
    "extract_candidates",
]
