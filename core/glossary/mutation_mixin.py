"""CRUD, seed/suggest, session changes, and global replace for GlossaryManager."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import re

from core.glossary.models import (
    STATUS_SEEDED,
    DescriptionFragment,
    GlossaryEntry,
    TranslationVariant,
)
from core.glossary.replace import replace_preserve_case


class MutationMixin:
    """CRUD, seed/suggest, session changes, and global replace."""

    def bind_project_rows(
        self,
        data_store=None,
        rules=None,
        speaker_aliases=None,
        speaker_pool: Optional[Dict[Tuple[int, int], str]] = None,
    ) -> None:
        """Attach block names and speaker attribution used to own rows."""
        names: Dict[int, str] = {}
        raw = {}
        if data_store is not None:
            raw = getattr(data_store, "block_names", None) or {}
        for key, value in raw.items():
            try:
                names[int(key)] = str(value)
            except (TypeError, ValueError):
                continue
        self._block_names = names
        getter = getattr(rules, "get_speaker_for_string", None) if rules is not None else None
        self._speaker_for = getter if callable(getter) else None
        self._speaker_aliases = dict(speaker_aliases or {})
        self._speaker_pool = dict(speaker_pool or {}) if speaker_pool is not None else None

    def get_session_changes(self) -> Dict[str, Optional[GlossaryEntry]]:
        """Return a copy of the session's glossary modifications."""
        return self._session_changes.copy()

    def clear_session_changes(self) -> None:
        """Clear the tracked session glossary modifications."""
        self._session_changes.clear()

    def add_entry(self, original: str, translation: str, notes: str, section: Optional[str] = None, profiled: bool = False) -> Optional[GlossaryEntry]:
        """Add entry."""
        original_key = (original or '').strip()
        if not original_key:
            return None
        existing = next((entry for entry in self._entries if entry.original == original_key), None)
        if existing:
            return self.update_entry(
                original_key, translation, notes, section=section, profiled=profiled
            )
        new_entry = GlossaryEntry(
            original=original_key,
            translation=translation.strip(),
            notes=notes.strip(),
            section=section,
            profiled=profiled
        )
        self._session_changes[original_key] = new_entry
        new_entries = list(self._entries)
        new_entries.append(new_entry)
        self._entries = new_entries
        self._occurrence_index = {}
        self._persist()
        return new_entry

    def update_entry(
        self,
        original: str,
        translation: str,
        notes: str,
        section: Optional[str] = None,
        profiled: Optional[bool] = None,
        *,
        status: Optional[str] = None,
        icon: Optional[str] = None,
        fragments: Optional[Tuple[DescriptionFragment, ...]] = None,
        translation_variants: Optional[Tuple[TranslationVariant, ...]] = None,
    ) -> Optional[GlossaryEntry]:
        """Update the entry, preserving lifecycle fields unless overridden.

        Lifecycle fields (``status``, ``icon``, ``fragments``,
        ``translation_variants``) are carried over from the existing entry when
        not passed, so a plain edit never silently drops them.
        """
        original_key = (original or '').strip()
        updated_translation = translation.strip()
        updated_notes = notes.strip()
        if not original_key:
            return None

        for idx, entry in enumerate(self._entries):
            if entry.original == original_key:
                updated_entry = GlossaryEntry(
                    original=entry.original,
                    translation=updated_translation,
                    notes=updated_notes,
                    section=section if section is not None else entry.section,
                    profiled=profiled if profiled is not None else entry.profiled,
                    status=status if status is not None else entry.status,
                    icon=icon if icon is not None else entry.icon,
                    fragments=fragments if fragments is not None else entry.fragments,
                    translation_variants=(
                        translation_variants
                        if translation_variants is not None
                        else entry.translation_variants
                    ),
                    # Carried over like every other lifecycle field: a plain
                    # edit of the translation must not quietly turn a
                    # placeholder term into one that looks decided.
                    provisional=entry.provisional,
                    suggested_name=entry.suggested_name,
                    suggested_name_evidence=entry.suggested_name_evidence,
                )
                new_entries = list(self._entries)
                new_entries[idx] = updated_entry
                self._entries = new_entries
                self._occurrence_index = {}
                self._session_changes[original_key] = updated_entry
                self._persist()
                return updated_entry
        return None

    def rename_original(self, old_original: str, new_original: str) -> Optional[GlossaryEntry]:
        """Rename an entry's original term, merging evidence on collision.

        Confirms a placeholder term (``provisional=False``) and clears AI name
        suggestions. If ``new_original`` already exists in the glossary, the two
        entries are merged: the target entry's active translation and lifecycle
        fields are preferred, but distinct notes, fragments, and translation
        variants from the provisional entry are retained.
        """
        old_key = (old_original or "").strip()
        new_key = (new_original or "").strip()
        if not old_key or not new_key:
            return None
        if old_key == new_key:
            return self.get_entry(old_key)

        old_entry = next((e for e in self._entries if e.original == old_key), None)
        if old_entry is None:
            return None

        from dataclasses import replace

        target_entry = next((e for e in self._entries if e.original == new_key), None)

        if target_entry is None:
            updated_entry = replace(
                old_entry,
                original=new_key,
                provisional=False,
                suggested_name="",
                suggested_name_evidence="",
            )
            new_entries = [
                updated_entry if e.original == old_key else e
                for e in self._entries
            ]
            self._entries = new_entries
            self._session_changes[old_key] = None
            self._session_changes[new_key] = updated_entry
            self._occurrence_index = {}
            self._persist()
            return updated_entry

        # Merge old_entry into target_entry (collision case)
        merged_notes = target_entry.notes
        if old_entry.notes and old_entry.notes not in (target_entry.notes or ""):
            if target_entry.notes:
                merged_notes = f"{target_entry.notes}\n\n{old_entry.notes}"
            else:
                merged_notes = old_entry.notes

        merged_frags = list(target_entry.fragments)
        for f in old_entry.fragments:
            if f not in merged_frags:
                merged_frags.append(f)

        merged_vars = list(target_entry.translation_variants)
        for v in old_entry.translation_variants:
            if v not in merged_vars:
                merged_vars.append(v)

        merged_entry = replace(
            target_entry,
            original=new_key,
            translation=target_entry.translation or old_entry.translation,
            notes=merged_notes,
            section=target_entry.section if target_entry.section is not None else old_entry.section,
            profiled=target_entry.profiled or old_entry.profiled,
            status=target_entry.status or old_entry.status,
            icon=target_entry.icon or old_entry.icon,
            fragments=tuple(merged_frags),
            translation_variants=tuple(merged_vars),
            provisional=False,
            suggested_name="",
            suggested_name_evidence="",
        )

        new_entries = []
        for e in self._entries:
            if e.original == old_key:
                continue
            if e.original == new_key:
                new_entries.append(merged_entry)
            else:
                new_entries.append(e)

        self._entries = new_entries
        self._session_changes[old_key] = None
        self._session_changes[new_key] = merged_entry
        self._occurrence_index = {}
        self._persist()
        return merged_entry

    def suggest_name(self, original: str, name: str, evidence: str = "") -> Optional[GlossaryEntry]:
        """Record a candidate real name for a placeholder term.

        Stored, never applied: renaming a character is a decision with reach --
        every line they speak carries it -- so this waits for a person.
        """
        original_key = (original or "").strip()
        if not original_key:
            return None
        for idx, entry in enumerate(self._entries):
            if entry.original != original_key:
                continue
            from dataclasses import replace

            updated = replace(
                entry,
                suggested_name=(name or "").strip(),
                suggested_name_evidence=(evidence or "").strip(),
            )
            new_entries = list(self._entries)
            new_entries[idx] = updated
            self._entries = new_entries
            self._session_changes[original_key] = updated
            self._persist()
            return updated
        return None

    def seed_entry(
        self,
        original: str,
        section: Optional[str] = None,
        *,
        icon: str = "",
        status: str = STATUS_SEEDED,
        description: str = "",
        provisional: bool = False,
    ) -> Optional[GlossaryEntry]:
        """Insert a term-only seed entry when the term is not already present.

        Seeding fills gaps; it never overwrites an existing entry, which may
        already carry a translation or a richer description (roadmap section 4).
        Returns the entry now representing the term, or None for a blank term.
        """
        original_key = (original or '').strip()
        if not original_key:
            return None

        existing = next((e for e in self._entries if e.original == original_key), None)
        if existing is not None:
            return existing

        new_entry = GlossaryEntry(
            original=original_key,
            translation="",
            notes=(description or "").strip(),
            section=section,
            status=status,
            icon=(icon or "").strip(),
            provisional=provisional,
        )
        self._session_changes[original_key] = new_entry
        self._entries = list(self._entries) + [new_entry]
        self._occurrence_index = {}
        self._persist()
        return new_entry

    def delete_entry(self, original: str) -> bool:
        """Remove entry."""
        original_key = (original or '').strip()
        if not original_key:
            return False
        index = next((idx for idx, entry in enumerate(self._entries) if entry.original == original_key), None)
        if index is None:
            return False
        new_entries = list(self._entries)
        del new_entries[index]
        self._entries = new_entries
        self._occurrence_index = {}
        self._session_changes[original_key] = None
        self._persist()
        return True

    def clear_all(self) -> int:
        """Remove every entry, returning how many were removed.

        The glossary file is copied to ``<name>.bak`` first: this wipes work that
        has no undo, and the copy costs nothing.
        """
        removed = len(self._entries)
        if not removed:
            return 0
        self.backup_file()
        for entry in self._entries:
            self._session_changes[entry.original] = None
        self._entries = []
        self._occurrence_index = {}
        self._persist()
        return removed

    def global_replace(self, find_word: str, replace_word: str) -> List[Tuple[GlossaryEntry, str, GlossaryEntry]]:
        """
        Replaces find_word with replace_word in all entries of the glossary
        (original, translation, notes), keeping the case.
        Returns a list of tuples: (old_entry, old_translation, new_entry)
        for entries where the translation has changed.
        """
        if not find_word:
            return []

        modified_entries: List[Tuple[GlossaryEntry, str, GlossaryEntry]] = []
        new_entries: List[GlossaryEntry] = []

        for entry in self._entries:
            has_find = (
                re.search(re.escape(find_word), entry.original, re.IGNORECASE) is not None
                or re.search(re.escape(find_word), entry.translation, re.IGNORECASE) is not None
                or re.search(re.escape(find_word), entry.notes, re.IGNORECASE) is not None
            )

            if has_find:
                new_original = replace_preserve_case(entry.original, find_word, replace_word)
                new_translation = replace_preserve_case(entry.translation, find_word, replace_word)
                new_notes = replace_preserve_case(entry.notes, find_word, replace_word)

                new_entry = GlossaryEntry(
                    original=new_original,
                    translation=new_translation,
                    notes=new_notes,
                    section=entry.section,
                    profiled=entry.profiled
                )

                new_entries.append(new_entry)

                # Record in session changes
                if entry.original != new_original:
                    self._session_changes[entry.original] = None
                    self._session_changes[new_original] = new_entry
                else:
                    self._session_changes[entry.original] = new_entry

                # Track all modified entries (original, translation, or notes)
                modified_entries.append((entry, entry.translation, new_entry))
            else:
                new_entries.append(entry)

        if modified_entries or len(new_entries) != len(self._entries) or any(e1 != e2 for e1, e2 in zip(self._entries, new_entries)):
            self._entries = new_entries
            self._occurrence_index = {}
            self._persist()

        return modified_entries
