from __future__ import annotations

from typing import Dict, Optional

from core.story_context_overrides import get_story_context_override
from core.translation.story_context_bundle import build_story_context_bundle
from core.translation.layout_contract import layout_signature, resolve_lines_per_window
from utils.logging_utils import log_debug


class StoryMixin:
    """MemPalace / wing / block / story context helpers."""

    def _get_mempalace_client(self) -> Optional[object]:
        return self.story_context.get_mempalace_client()

    def _get_wing_name(self) -> str:
        return self.story_context.get_wing_name()

    def _get_block_label(self, block_idx: int) -> str:
        return self.story_context.get_block_label(block_idx)

    def _fetch_story_context(self, block_idx: int, s_idx: int, text: str) -> Optional[str]:
        manual = get_story_context_override(self.mw, block_idx, s_idx)
        structure_id = manual.get("structure_id")
        if structure_id == "story:none":
            return None
        structure_path = [str(part) for part in manual.get("structure_path") or () if str(part)]
        if structure_id is not None and structure_path:
            return "Manually assigned Story structure: " + " > ".join(structure_path)
        return self.story_context.fetch_story_context(
            block_idx, s_idx, text, self.script_speaker_finder, self.data_processor,
            include_normalized=False,
        )

    def _get_structured_story_context(self, block_idx: int, string_idx: int) -> Dict:
        try:
            return build_story_context_bundle(
                self._get_mempalace_client(),
                str(block_idx),
                string_idx,
                self._get_wing_name(),
            )
        except Exception as exc:
            log_debug(f"AIPromptComposer: structured story context failed: {exc}")
            return {}

    def _layout_contract_for_string(
        self, text: str, block_idx: Optional[int], string_idx: Optional[int]
    ) -> Dict:
        signature = layout_signature(
            text,
            resolve_lines_per_window(self.mw, block_idx, string_idx),
        )
        try:
            from utils.utils import resolve_width_limits

            metadata = getattr(self.mw, 'string_metadata', {}).get(
                (block_idx, string_idx), {}
            )
            warning_width, max_width = resolve_width_limits(
                metadata,
                getattr(self.mw, 'current_game_rules', None),
                block_idx,
                string_idx,
                getattr(self.mw, 'line_width_warning_threshold_pixels', 280),
                getattr(self.mw, 'game_dialog_max_width_pixels', 300),
            )
            signature['warning_line_width_px'] = warning_width
            signature['max_line_width_px'] = max_width
        except (AttributeError, TypeError, ValueError):
            pass
        return signature
