"""CRUD, seed/suggest, session changes, and global replace for GlossaryManager."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import re

from core.glossary.models import (
    STATUS_CONFIRMED,
    STATUS_SEEDED,
    STATUS_TRANSLATED,
    DescriptionFragment,
    GlossaryEntry,
    GlossaryOccurrence,
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

    def _index_of(self, original: str, *, fold: bool = True) -> Optional[int]:
        """Index of the entry ``original`` refers to, or None.

        The one lookup every mutator uses, so "found by one method, missed by
        the next" cannot happen again: exact spelling, then case and spacing
        (``normalize_term``), then an alias, then -- when ``fold`` -- the
        canonical key (plural, article, possessive). An exact or normalized
        match always wins, so two entries that share a canonical key are both
        still reachable by their own spelling.
        """
        key = (original or '').strip()
        if not key:
            return None
        for index, entry in enumerate(self._entries):
            if entry.original == key:
                return index
        normalized = self.normalize_term(key)
        for index, entry in enumerate(self._entries):
            if self.normalize_term(entry.original) == normalized:
                return index
        for index, entry in enumerate(self._entries):
            if any(self.normalize_term(alias) == normalized for alias in entry.aliases):
                return index
        if fold:
            canonical = self.canonical_key(key)
            if canonical:
                for index, entry in enumerate(self._entries):
                    if self.canonical_key(entry.original) == canonical:
                        return index
        return None

    def add_entry(
        self,
        original: str,
        translation: str,
        notes: str,
        section: Optional[str] = None,
        profiled: bool = False,
        user_notes: str = "",
        *,
        fold_variants: bool = True,
    ) -> Optional[GlossaryEntry]:
        """Add an entry, or update the one this term already has. Never appends a duplicate.

        A term that differs from an existing entry only by case or spacing
        updates that entry. With ``fold_variants`` (the default, used by every
        automatic source) a plural, article or possessive variant of an existing
        term is folded into it too: the existing translation and notes are kept
        when they are set, and only gaps are filled -- a variant spelling is not
        a reason to overwrite a decided translation. Pass ``fold_variants=False``
        for a deliberate manual addition of a separate entry.
        """
        original_key = (original or '').strip()
        if not original_key:
            return None
        index = self._index_of(original_key, fold=fold_variants)
        if index is not None:
            existing = self._entries[index]
            same_term = self.normalize_term(existing.original) == self.normalize_term(original_key)
            if same_term:
                return self.update_entry(
                    existing.original, translation, notes, section=section, profiled=profiled, user_notes=user_notes
                )
            return self.update_entry(
                existing.original,
                existing.translation or translation,
                existing.notes or notes,
                section=existing.section if existing.section is not None else section,
            )
        new_entry = GlossaryEntry(
            original=original_key,
            translation=translation.strip(),
            notes=notes.strip(),
            section=section,
            profiled=profiled,
            user_notes=user_notes,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        if section and section not in self._section_order:
            self._section_order.append(section)
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
        user_notes: Optional[str] = None,
    ) -> Optional[GlossaryEntry]:
        """Update the entry, preserving lifecycle fields unless overridden.

        Lifecycle fields (``status``, ``icon``, ``fragments``,
        ``translation_variants``, ``user_notes``) are carried over from the existing entry when
        not passed, so a plain edit never silently drops them.
        """
        original_key = (original or '').strip()
        updated_translation = translation.strip()
        updated_notes = notes.strip()
        if not original_key:
            return None

        idx = self._index_of(original_key)
        if idx is None:
            return None
        entry = self._entries[idx]
        # The entry's own spelling is its key from here on, whatever the caller wrote.
        original_key = entry.original
        updated_entry = replace(
            entry,
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
            # Everything not named here (provisional, suggested name,
            # aliases) is carried over: a plain edit of the translation
            # must not quietly turn a placeholder term into one that
            # looks decided.
            user_notes=user_notes if user_notes is not None else entry.user_notes,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        if section and section not in self._section_order:
            self._section_order.append(section)
        new_entries = list(self._entries)
        new_entries[idx] = updated_entry
        self._entries = new_entries
        if self._occurrence_index and original_key in self._occurrence_index:
            target_section = section if section is not None else entry.section
            if target_section == entry.section:
                existing_occs = self._occurrence_index[original_key]
                self._occurrence_index[original_key] = [
                    GlossaryOccurrence(
                        entry=updated_entry,
                        start=occ.start,
                        end=occ.end,
                        block_idx=occ.block_idx,
                        string_idx=occ.string_idx,
                        line_idx=occ.line_idx,
                        line_text=occ.line_text,
                        kind=occ.kind,
                    )
                    for occ in existing_occs
                ]
            else:
                self._occurrence_index.pop(original_key, None)
        else:
            self._occurrence_index = {}
        self._session_changes[original_key] = updated_entry
        self._persist()
        return updated_entry

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

        # A rename is an explicit request about two named entries: case and
        # spacing are forgiven, but nothing is folded by canonical key.
        old_index = self._index_of(old_key, fold=False)
        if old_index is None:
            return None
        old_entry = self._entries[old_index]
        old_key = old_entry.original

        target_index = self._index_of(new_key, fold=False)
        target_entry = self._entries[target_index] if target_index not in (None, old_index) else None
        if target_entry is not None:
            new_key = target_entry.original

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
            user_notes=target_entry.user_notes or old_entry.user_notes,
            aliases=_merged_aliases(target_entry, old_entry, self.normalize_term),
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
        idx = self._index_of(original_key, fold=False)
        if idx is not None:
            entry = self._entries[idx]
            original_key = entry.original
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

        existing_index = self._index_of(original_key)
        if existing_index is not None:
            return self._entries[existing_index]

        new_entry = GlossaryEntry(
            original=original_key,
            translation="",
            notes=(description or "").strip(),
            section=section,
            status=status,
            icon=(icon or "").strip(),
            provisional=provisional,
            updated_at=datetime.now(timezone.utc).isoformat(),
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
        # Deleting never folds: only the entry that was named goes.
        index = self._index_of(original_key, fold=False)
        if index is None:
            return False
        original_key = self._entries[index].original
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

                # replace(), not a fresh GlossaryEntry: status, variants,
                # fragments, user notes and aliases must survive a text replace.
                new_entry = replace(entry, original=new_original, translation=new_translation, notes=new_notes)

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

    def merge_canonical_duplicates(self, *, dry_run: bool = True) -> List[Dict[str, Any]]:
        """Merge entries that share a canonical key. Returns what was (or would be) merged.

        Never called automatically: two entries with one key can be two real
        things ("Clawshot" / "Clawshots"), so this runs only when asked --
        ``dry_run`` first, to show the report. In each group the survivor is
        the confirmed entry, else a translated one, else the one with the most
        notes; the others are merged into it through ``rename_original`` and
        their spellings stay behind as aliases. ``diverging`` lists translations
        that differ from the survivor's, so nothing disappears unseen.
        """
        report: List[Dict[str, Any]] = []
        for group in self.canonical_groups():
            survivor = max(group, key=_merge_rank)
            others = [entry for entry in group if entry is not survivor]
            report.append({
                "canonical": self.canonical_key(survivor.original),
                "survivor": survivor.original,
                "merged": [entry.original for entry in others],
                "diverging": {
                    entry.original: entry.translation
                    for entry in others
                    if entry.translation and entry.translation != survivor.translation
                },
            })
            if dry_run:
                continue
            for entry in others:
                self.merge_into(survivor.original, entry.original)
        return report

    def merge_into(self, survivor: str, absorbed: str) -> Optional[GlossaryEntry]:
        """Merge the entry ``absorbed`` into the entry ``survivor``.

        The absorbed spelling stays behind as an alias and its translation, when
        it differs, as a variant the user can switch back to. ``None`` when
        either entry is missing or they are already one entry -- so merging
        twice is harmless.
        """
        survivor_index = self._index_of(survivor, fold=False)
        absorbed_index = self._index_of(absorbed, fold=False)
        if survivor_index is None or absorbed_index is None or survivor_index == absorbed_index:
            return None
        target, other = self._entries[survivor_index], self._entries[absorbed_index]
        if other.translation and other.translation != target.translation:
            variants = list(target.translation_variants)
            if all(v.translation != other.translation for v in variants):
                variants.append(TranslationVariant(other.translation, f"merged from '{other.original}'"))
                self.update_entry(
                    target.original, target.translation, target.notes,
                    translation_variants=tuple(variants),
                )
        return self.rename_original(other.original, target.original)


def _merge_rank(entry: GlossaryEntry) -> Tuple[int, int, int]:
    """Higher wins a merge: confirmed, then translated, then the fuller entry."""
    return (
        2 if entry.status == STATUS_CONFIRMED else 1 if (entry.status == STATUS_TRANSLATED or entry.translation) else 0,
        len(entry.notes or ""),
        len(entry.translation or ""),
    )


def _merged_aliases(target: GlossaryEntry, absorbed: GlossaryEntry, normalize) -> Tuple[str, ...]:
    """Aliases of ``target`` after it absorbs ``absorbed``: both lists plus the absorbed spelling."""
    seen = {normalize(target.original)}
    result: List[str] = []
    for alias in (*target.aliases, absorbed.original, *absorbed.aliases):
        key = normalize(alias)
        if key and key not in seen:
            seen.add(key)
            result.append(alias)
    return tuple(result)
