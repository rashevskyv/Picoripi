"""Regression gate over the shipped glossary (WP3 3.7).

Ported from docs/audit/2026-10-01/scripts/glossary_consistency.py, which found
the problems this work package fixes. It runs on a copy of
``translation_prompts/glossary.json`` and fails when the glossary gets worse:
a new pair of entries that are one term spelled twice, or a merge that loses
something. Families whose members render a shared word differently are listed
as a warning -- deciding those is a person's (or the reconcile pass's) job.
"""
import collections
import warnings
from pathlib import Path

import pytest

from core.glossary_build.reconcile_driver import clusters
from core.glossary_manager import GlossaryManager

GLOSSARY = Path("translation_prompts/glossary.json")
# Groups of entries that share a canonical key today (the list is in
# docs/audit/2026-10-01/glossary_canonical_report.md). Lower this number when
# groups are merged; a build must never raise it.
KNOWN_CANONICAL_GROUPS = 18


@pytest.fixture
def manager(tmp_path):
    copy = tmp_path / "glossary.json"
    raw = GLOSSARY.read_text(encoding="utf-8")
    copy.write_text(raw, encoding="utf-8")
    manager = GlossaryManager()
    manager.load_from_text(plugin_name=None, glossary_path=copy, raw_text=raw)
    return manager


def _spellings(groups):
    return "; ".join(" / ".join(entry.original for entry in group) for group in groups)


def test_no_entry_is_stored_twice(manager):
    by_term = collections.Counter(manager.normalize_term(entry.original) for entry in manager.get_entries())

    assert [term for term, count in by_term.items() if count > 1] == []


def test_no_new_spelling_variants_of_an_existing_term(manager):
    groups = manager.canonical_groups()

    assert len(groups) <= KNOWN_CANONICAL_GROUPS, (
        f"{len(groups)} groups of entries are one term spelled differently "
        f"(was {KNOWN_CANONICAL_GROUPS}): {_spellings(groups)}"
    )


def test_merging_the_variants_leaves_no_collision_and_loses_nothing(manager):
    before = {entry.original: entry.translation for entry in manager.get_entries()}

    manager.merge_canonical_duplicates(dry_run=False)

    assert manager.canonical_groups() == []
    reloaded = GlossaryManager()
    reloaded.load_from_text(
        plugin_name=None,
        glossary_path=manager.glossary_path,
        raw_text=manager.glossary_path.read_text(encoding="utf-8"),
    )
    assert reloaded.canonical_groups() == []
    for original, translation in before.items():
        entry = reloaded.get_entry(original)            # by its own spelling or as an alias
        assert entry is not None, original
        kept = {entry.translation, *(variant.translation for variant in entry.translation_variants)}
        assert translation in kept, (original, translation)


def test_a_second_merge_has_nothing_left_to_do(manager):
    manager.merge_canonical_duplicates(dry_run=False)

    assert manager.merge_canonical_duplicates(dry_run=False) == []


def test_families_that_render_a_shared_word_differently_are_reported(manager):
    """Not a failure: a list for the reconcile pass and for a person to look at."""
    groups = clusters(manager.get_entries())
    if groups:
        sample = "; ".join(
            " / ".join(f"{entry.original} → {entry.translation}" for entry in group[:3]) for group in groups[:8]
        )
        warnings.warn(
            f"{len(groups)} glossary families may render a shared word differently, e.g. {sample}",
            stacklevel=1,
        )
    assert all(len(group) > 1 for group in groups)
