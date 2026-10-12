"""What a plugin declares about a family: its members, their parents, and how their units are read.

A plugin returns a FamilyPlan from ``BaseGameRules.family_plan``. Core never guesses members from file names.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class FamilyMember:
    """One console or version of the game in the family.

    key: short id used in the store ("gc", "wii"). label: the name the user sees. path: the source it was
    recognised from. parents: members this one may link to, in order (the base has none; the others default to
    the base). The base member owns every unit it has.
    """

    key: str
    label: str
    path: str
    base: bool = False
    parents: Tuple[str, ...] = ()


@dataclass
class FamilyPlan:
    """The members of a family and the reader that lists their units.

    read(member_key) -> [(unit_id, text)] in file order. unit_id is a stable id the plugin chooses (for example
    "bmgres.arc/zel_00.bmg#12"); text is the translator-visible source text. match_key(text) -> the key that
    decides whether two units are the same (default: the text itself). shared_files maps a file to "shared"
    (identical bytes wanted in every member, copied from the base) or "per-member" (each member keeps its own).
    """

    members: Tuple[FamilyMember, ...]
    read: Callable[[str], List[Tuple[str, str]]]
    match_key: Optional[Callable[[str], str]] = None
    shared_files: Dict[str, str] = field(default_factory=dict)

    @property
    def base(self) -> str:
        """Key of the base member; the plan is invalid without exactly one."""
        bases = [m.key for m in self.members if m.base]
        if len(bases) != 1:
            raise ValueError(f"a family needs exactly one base member, got {bases}")
        return bases[0]

    def member(self, key: str) -> FamilyMember:
        for member in self.members:
            if member.key == key:
                return member
        raise KeyError(key)
