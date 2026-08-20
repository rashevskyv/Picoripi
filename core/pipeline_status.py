"""How far along each step of the localization pipeline is.

The wizard has to say where the user stands without pretending to know what
they meant. A glossary with 147 of 210 entries translated is not finished, but
it is not nothing either -- and the remaining 63 may well have been skipped on
purpose. A bare traffic light would either lie or nag, so every step reports a
count beside its state and lets the user decide whether the gap matters.

Pure and Qt-free: each probe takes the plain data it judges, so the wizard's
reading of the project is testable without a project.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from core.glossary_manager import STATUS_CONFIRMED
from core.script_markup.hierarchy_markup import HierarchyType


NOT_STARTED = "not_started"
PARTIAL = "partial"
DONE = "done"


@dataclass(frozen=True)
class StepState:
    """One step's progress: the state, and the numbers behind it."""

    state: str
    detail: str = ""

    @property
    def started(self) -> bool:
        return self.state != NOT_STARTED


def counted(done: int, total: int, noun: str) -> StepState:
    """A step measured as ``done of total``.

    The count travels with the state precisely because the state alone cannot
    be trusted to mean "act on this".
    """
    if total <= 0:
        return StepState(NOT_STARTED, f"no {noun} yet")
    detail = f"{done} / {total} {noun}"
    if done <= 0:
        return StepState(NOT_STARTED, detail)
    return StepState(DONE if done >= total else PARTIAL, detail)


def present(ok: bool, yes: str, no: str) -> StepState:
    """A step that is genuinely all-or-nothing."""
    return StepState(DONE, yes) if ok else StepState(NOT_STARTED, no)


# -- individual steps ---------------------------------------------------------


def markup_state(project: Any, *, has_script: bool = True) -> StepState:
    """How much of the script carries approved markup.

    Measured in source lines covered rather than marks made: twenty marks mean
    nothing on their own, while "340 of 1200 lines" says how much script is
    still undecided. Overlapping marks are counted once.

    A game with no script at all is a different answer from a script nobody has
    marked up yet, and the wizard has to say which one it is: the first is
    nothing to do, the second is work waiting.

    Only lines that *can* be marked are counted. A blank line carries nothing to
    decide about, and one stray empty line in a 15k-line script is enough to
    hold the step at 15821/15822 forever while Markup Studio rightly shows
    nothing left to do.
    """
    if not has_script:
        return StepState(NOT_STARTED, "no script found for this game")
    if project is None:
        return StepState(NOT_STARTED, "script not marked up")

    lines = (getattr(project, "raw_text", "") or "").splitlines()
    markable = {index for index, line in enumerate(lines) if line.strip()}
    covered = set()
    for mark in getattr(project, "approved_marks", ()) or ():
        # "Unmarked" is the type for text that still needs a decision, so it is
        # the one mark that does not mean the line has been dealt with.
        if getattr(mark, "type_id", "") == HierarchyType.UNMARKED:
            continue
        covered.update(range(mark.start_line, mark.end_line + 1))
    return counted(len(covered & markable), len(markable), "lines marked up")


def speaker_names_state(
    aliases: Optional[Mapping[str, str]],
    codes: Optional[Iterable[str]],
) -> StepState:
    """How many of the game's placeholder speaker codes have a real name.

    ``codes`` is every code the plugin still reports as a placeholder, named or
    not, so this is a fraction rather than a tally. Reporting "27 named" alone
    read as finished, when 27 of 59 is the truth and the step is half done.
    """
    placeholders = set(codes or ())
    if not placeholders:
        return StepState(NOT_STARTED, "no speaker codes found")
    named = sum(1 for code in placeholders if (aliases or {}).get(code))
    return counted(named, len(placeholders), "speaker codes named")


def structural_seed_state(
    seeds: Optional[Sequence[Any]],
    entries: Optional[Sequence[Any]],
) -> StepState:
    """How many of the game's structural seeds are present in the glossary."""
    raw_seeds = list(seeds or ())
    if not raw_seeds:
        return StepState(NOT_STARTED, "no game data seeds available")

    existing_terms = {
        str(getattr(e, "original", "") or getattr(e, "term", "")).strip().lower()
        for e in (entries or [])
    }
    seeded = 0
    for s in raw_seeds:
        term = str(s.get("term") or "").strip().lower() if isinstance(s, dict) else str(s).strip().lower()
        if term and term in existing_terms:
            seeded += 1

    return counted(seeded, len(raw_seeds), "game terms seeded")


def glossary_states(entries: Sequence[Any]) -> Dict[str, StepState]:
    """Seed / describe / translate / confirm, from one pass over the entries."""
    total = len(entries)
    described = sum(1 for e in entries if str(getattr(e, "notes", "") or "").strip())
    translated = sum(1 for e in entries if str(getattr(e, "translation", "") or "").strip())
    confirmed = sum(1 for e in entries if getattr(e, "status", "") == STATUS_CONFIRMED)
    return {
        "seed": counted(total, total, "terms") if total else StepState(NOT_STARTED, "glossary is empty"),
        "describe": counted(described, total, "terms described"),
        "translate": counted(translated, total, "terms translated"),
        "confirm": counted(confirmed, total, "terms confirmed"),
    }


def translation_state(
    data: Optional[Iterable[Sequence[str]]],
    edited_file_data: Optional[Sequence[Sequence[str]]] = None,
    edited_data: Optional[Mapping[Any, str]] = None,
) -> StepState:
    """How many non-empty rows now read differently from the original.

    An approximation, and knowingly so: a line that is correct untranslated --
    a number, a name kept as-is -- counts as untouched. It undercounts rather
    than flatter, which is the right way for a progress number to be wrong.
    """
    rows = list(data or [])
    saved = list(edited_file_data or [])
    pending = dict(edited_data or {})

    total = 0
    changed = 0
    for block_idx, block in enumerate(rows):
        if not isinstance(block, (list, tuple)):
            continue
        for string_idx, original in enumerate(block):
            source = str(original or "")
            if not source.strip():
                continue
            total += 1
            current = pending.get((block_idx, string_idx))
            if current is None:
                saved_block = saved[block_idx] if block_idx < len(saved) else None
                if isinstance(saved_block, (list, tuple)) and string_idx < len(saved_block):
                    current = saved_block[string_idx]
            if current is not None and str(current) != source:
                changed += 1
    return counted(changed, total, "rows translated")


def overall(states: Iterable[StepState]) -> StepState:
    """One line for the whole pipeline: how many steps are finished."""
    steps: List[StepState] = list(states)
    done = sum(1 for step in steps if step.state == DONE)
    return counted(done, len(steps), "steps complete")
