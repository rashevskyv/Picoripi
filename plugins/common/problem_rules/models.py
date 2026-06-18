from dataclasses import dataclass, field
from typing import Set, Tuple, Dict, Any, Optional

@dataclass
class ProblemMatch:
    problem_id: str
    line_index: int
    span: Optional[Tuple[int, int]] = None
    payload: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FixResult:
    text: str
    changed: bool
    fixed_problem_ids: Set[str] = field(default_factory=set)
