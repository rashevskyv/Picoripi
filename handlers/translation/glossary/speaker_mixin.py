from typing import List

from core.glossary_manager import GlossaryEntry
from core.speaker_alias_merge import (
    is_applyable_speaker_alias,
    load_speaker_aliases,
    split_shared_speaker_names,
)
from utils.logging_utils import log_debug


class SpeakerMixin:
    def _handle_discuss_variants_from_dialog(self, entry: GlossaryEntry) -> None:
        """Open AI chat with term context to discuss proposed variants."""
        if not entry:
            return
        ai_chat_handler = getattr(self.mw, "ai_chat_handler", None)
        if not ai_chat_handler:
            return
        context_text = self.format_variant_discussion_context(entry)
        ai_chat_handler.show_chat_window(initial_text=context_text)

    def format_variant_discussion_context(self, entry: GlossaryEntry) -> str:
        """Format the exact context and constraints for discussing glossary variants in AI chat."""
        target_lang = getattr(self.mw, "target_language", "Ukrainian")
        if not isinstance(target_lang, str) or not target_lang.strip():
            target_lang = "Ukrainian"
        parts = [
            f"Term: {entry.original}",
            f"Target language: {target_lang}",
        ]
        if entry.notes:
            parts.append(f"Description:\n{entry.notes}")
        fragments = [
            str(getattr(f, "text", "") or str(f)).strip()
            for f in getattr(entry, "fragments", ()) or ()
            if str(getattr(f, "text", "") or str(f)).strip()
        ]
        if fragments:
            parts.append("Description fragments:\n- " + "\n- ".join(fragments))
        variants = getattr(entry, "translation_variants", ()) or ()
        if variants:
            variant_lines = []
            for v in variants:
                line = f"- {v.translation}"
                if getattr(v, "rationale", ""):
                    line += f" (Rationale: {v.rationale})"
                variant_lines.append(line)
            parts.append("Proposed translation candidates:\n" + "\n".join(variant_lines))
        parts.append(
            "Instruction:\n"
            "Analyze the term, description, and proposed translation candidates. "
            "You must recommend exactly one of the displayed candidates above, verbatim. "
            "Choose only from the existing candidates."
        )
        return "\n\n".join(parts)

    def _placeholder_speaker_callback(self):
        """Classify legacy glossary Character terms from the active game rules."""
        hook = getattr(getattr(self.mw, "current_game_rules", None), "is_placeholder_speaker", None)
        if not callable(hook):
            return None
        aliases = self._load_speaker_aliases()

        def is_placeholder(term: str) -> bool:
            term = str(term or "").strip()
            if not term or is_applyable_speaker_alias(aliases.get(term)):
                return False
            try:
                return bool(hook(term))
            except Exception as exc:
                log_debug(f"Glossary: is_placeholder_speaker failed: {exc}")
                return False

        return is_placeholder

    def _load_speaker_aliases(self) -> dict:
        project_dir = getattr(getattr(self.mw, "project_manager", None), "project_dir", None)
        try:
            return load_speaker_aliases(project_dir)
        except (TypeError, ValueError):
            return {}

    def _confirmed_speaker_codes(self, permanent_name: str) -> List[str]:
        """Game codes explicitly mapped to this permanent Character term.

        A shared voice counts for each named character: zrSPA assigned to
        ``SPRING ZORA #1 / SPRING ZORA #2`` belongs to both terms.
        """
        target = str(permanent_name or "").strip().casefold()
        if not target:
            return []
        aliases = self._load_speaker_aliases()
        return sorted(
            str(code).strip()
            for code, name in aliases.items()
            if is_applyable_speaker_alias(name)
            and target in {part.casefold() for part in split_shared_speaker_names(name)}
        )

    def _handle_reassign_speaker_name(
        self, speaker_code: str, current_name: str, permanent_name: str
    ) -> None:
        """Change an already-confirmed game code to another character name."""
        merge_handler = getattr(self.mw, "speaker_merge_handler", None)
        reassign = getattr(merge_handler, "reassign_name", None)
        if not callable(reassign):
            return
        if reassign(speaker_code, current_name, permanent_name) and self.dialog:
            self.dialog.focus_term(permanent_name)

