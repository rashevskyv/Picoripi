"""Speaker merge dialog package."""
from components.speaker_merge.dialog import SpeakerMergeDialog
from components.speaker_merge.widgets import (
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
