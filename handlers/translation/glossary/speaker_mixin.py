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
        """Format the exact context and constraints for discussing glossary entries/variants in AI chat."""
        target_lang = getattr(self.mw, "target_language", "Ukrainian")
        if not isinstance(target_lang, str) or not target_lang.strip():
            target_lang = "Ukrainian"
        parts = [
            f"Term: {entry.original}",
        ]
        if getattr(entry, "section", None):
            parts.append(f"Category: {entry.section}")
        if getattr(entry, "translation", None):
            parts.append(f"Current translation: {entry.translation}")
        parts.append(f"Target language: {target_lang}")

        wiki_url = None
        if hasattr(self, "_get_external_reference_url"):
            wiki_url = self._get_external_reference_url(entry.original)
        elif hasattr(self, "mw"):
            rules = getattr(self.mw, "current_game_rules", None)
            getter = getattr(rules, "get_external_reference_url", None)
            if callable(getter):
                try:
                    wiki_url = getter(entry.original)
                except Exception:
                    wiki_url = None
        if wiki_url:
            parts.append(f"Wiki reference: {wiki_url}")

        if hasattr(self, "_confirmed_speaker_codes"):
            codes = self._confirmed_speaker_codes(entry.original)
            if codes:
                parts.append(f"Speaker code(s): {', '.join(codes)}")
        if getattr(entry, "suggested_name", ""):
            parts.append(f"Suggested character name: {entry.suggested_name}")
        if getattr(entry, "suggested_name_evidence", ""):
            parts.append(f"Speaker name evidence: {entry.suggested_name_evidence}")

        if entry.notes:
            parts.append(f"Description:\n{entry.notes}")
        fragments = [
            str(getattr(f, "text", "") or str(f)).strip()
            for f in getattr(entry, "fragments", ()) or ()
            if str(getattr(f, "text", "") or str(f)).strip()
        ]
        if fragments:
            parts.append("Description fragments:\n- " + "\n- ".join(fragments))

        occs = []
        if getattr(self, "dialog", None) and hasattr(self.dialog, "_occurrences"):
            occs = self.dialog._occurrences.get(entry.original, [])
        elif hasattr(self, "glossary_manager") and hasattr(self.glossary_manager, "occurrences"):
            occs = self.glossary_manager.occurrences.get(entry.original, [])

        if occs:
            spoken_occs = [o for o in occs if getattr(o, "kind", "mention") == "spoken"]
            mention_occs = [o for o in occs if getattr(o, "kind", "mention") != "spoken"]
            parts.append(f"Occurrences: {len(mention_occs)} mentions, {len(spoken_occs)} spoken")
            sample_lines = []
            seen = set()
            for o in spoken_occs + mention_occs:
                preview = getattr(o, "line_text", "") or getattr(o, "preview_text", "")
                if preview and preview not in seen:
                    seen.add(preview)
                    clean_preview = " ".join(preview.split())
                    prefix = "[Spoken]" if getattr(o, "kind", "mention") == "spoken" else "[Mention]"
                    sample_lines.append(f"- {prefix} Block {o.block_idx}, Line {o.string_idx + 1}: \"{clean_preview}\"")
                    if len(sample_lines) >= 5:
                        break
            if sample_lines:
                parts.append("In-game dialogue occurrences:\n" + "\n".join(sample_lines))

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
                "Recommend the most appropriate candidate or suggest refined/creative alternatives, "
                f"explaining your reasoning in the context of the game lore and {target_lang} localization standards."
            )
        else:
            parts.append(
                "Instruction:\n"
                "Analyze the glossary term in the context of the game lore, category, wiki reference, and in-game dialogue occurrences. "
                f"Discuss and suggest the most appropriate translation into {target_lang}."
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

