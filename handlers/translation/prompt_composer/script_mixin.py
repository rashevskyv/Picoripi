from __future__ import annotations

from typing import Optional, Tuple


class ScriptMixin:
    """Script path and speaker lookup helpers."""

    def _find_script_path(self) -> Optional[str]:
        return self.script_speaker_finder.find_script_path()

    def _translate_speaker(self, speaker: str) -> str:
        glossary_manager = self.main_handler._glossary_manager
        return self.script_speaker_finder.translate_speaker(speaker, glossary_manager)

    def _find_speaker_in_script(self, block_idx: int, s_idx: int, text: str) -> Optional[Tuple[str, Optional[str]]]:
        block_label = self.story_context.get_block_label(block_idx)
        default_wing_name = self.story_context.get_wing_name()
        return self.script_speaker_finder.find_speaker_in_script(
            block_idx, s_idx, text, default_wing_name, block_label
        )
