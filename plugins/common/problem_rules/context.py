from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

@dataclass
class GameProblemProfile:
    problem_ids: Dict[str, str] = field(default_factory=dict)
    tag_style: str = "curly"  # "curly" | "square" | "mixed"
    closing_color_tags: List[str] = field(default_factory=list)
    page_break_patterns: List[str] = field(default_factory=list)
    tab_tags: List[str] = field(default_factory=list)
    star_section_mode: bool = False
    lines_per_page: int = 4
    punctuation_chars: List[str] = field(default_factory=list)
    width_calculator: Optional[Any] = None
    main_window: Optional[Any] = None
    problem_definitions: Dict[str, Dict[str, Any]] = field(default_factory=dict)

@dataclass
class RuleContext:
    text: str
    font_map: Dict[str, Any]
    width_threshold: int
    logical_hard_limit: int
    lines_per_page: int
    default_tag_mappings: Dict[str, str]
    icon_sequences: List[str]
    original_text: Optional[str] = None
    block_idx: Optional[int] = None
    string_idx: Optional[int] = None
    game_profile: Optional[GameProblemProfile] = None
