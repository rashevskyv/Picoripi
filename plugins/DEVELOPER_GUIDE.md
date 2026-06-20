# Picoripi Plugin Developer Guide (AI-Oriented)

This guide provides absolute technical specifications and code templates for creating new game plugins for **Picoripi**. Since plugin development is frequently performed or assisted by AI models, this document is structured to serve as a direct instructions manual for AI coding assistants.

Current quick-start path:

- Copy `plugins/default_plugin/` to `plugins/<your_plugin_name>/`.
- Follow `docs/PLUGIN_AUTHORING_GUIDE.md`.
- Use `plugins/default_plugin/AI_PLUGIN_ASSISTANT_PROMPT.md` to gather requirements before coding.
- Use PyQt6 imports only.

---

## 1. Architectural Overview

Every game plugin in Picoripi is a Python package located in `plugins/<plugin_name>/`. The workbench discovers plugins dynamically by scanning directories containing a `rules.py` file with a `GameRules` class.

### Directory Structure of a Standard Plugin
```text
plugins/my_game_plugin/
├── __init__.py
├── rules.py                 # Core class inheriting from BaseGameRules
├── config.py                # Definition of problems, limits, and control codes
├── tag_manager.py           # Parsing and matching of game-specific tags
├── problem_analyzer.py      # Real-time layout and width validation logic
├── text_fixer.py            # Automatic text wrapping and alignment rules
├── tag_checker_handler.py   # Mismatch checks between original and translated tags
├── font_map.json            # Character width specifications and alias overrides
└── translation_prompts/     # Optional per-plugin overrides for LLMs
    └── prompts.json
```

---

## 2. Implementing `rules.py` (The Entry Point)

Your class `GameRules` **must** inherit from `BaseGameRules` (`plugins/base_game_rules.py`). Below is the complete template representing the minimum required class structure:

```python
import os
import re
from typing import Optional, Set, Dict, Any, Tuple, List
from PyQt6.QtGui import QTextCharFormat

from plugins.base_game_rules import BaseGameRules
from .config import (
    PROBLEM_DEFINITIONS,
    CONTROL_CODES,
    PROBLEM_WIDTH_EXCEEDED
)
from .tag_manager import TagManager
from .problem_analyzer import ProblemAnalyzer
from .text_fixer import TextFixer
from .tag_checker_handler import TagCheckerHandler

class GameRules(BaseGameRules):
    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self.tag_manager = TagManager(main_window_ref)
        self.problem_analyzer = ProblemAnalyzer(
            main_window_ref, self.tag_manager, PROBLEM_DEFINITIONS
        )
        self.text_fixer = TextFixer(
            main_window_ref, self.tag_manager, self.problem_analyzer
        )

    def get_display_name(self) -> str:
        """Friendly name displayed in Settings and title bar."""
        return "My Custom Game Title"

    def get_default_script_name(self) -> Optional[str]:
        """
        Return the filename of the Markdown timeline script.
        Picoripi will automatically discover this file in the project folder.
        """
        return "my_game_script.md"

    def load_data_from_json_obj(self, json_data: Any) -> Tuple[list, dict]:
        """
        Convert raw JSON/text files from disk into List[List[str]] (blocks of lines).
        Returns: (data_list, block_names_dict)
        """
        return super().load_data_from_json_obj(json_data)

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        """Serialize internal List[List[str]] data structure back to disk format."""
        return super().save_data_to_json_obj(data, block_names)

    def get_problem_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Return problem IDs mapped to colors, names, and tooltips."""
        return PROBLEM_DEFINITIONS

    def get_legitimate_tags(self) -> Set[str]:
        """Set of regex patterns or literal tag strings allowed in text."""
        return self.tag_manager.get_legitimate_tags()

    def get_syntax_highlighting_rules(self) -> List[Tuple[str, QTextCharFormat]]:
        """QTextCharFormat styles applied by the editor syntax highlighter."""
        return self.tag_manager.get_syntax_highlighting_rules()

    def analyze_subline(self,
                        text: str,
                        next_text: Optional[str],
                        subline_number_in_data_string: int,
                        qtextblock_number_in_editor: int,
                        is_last_subline_in_data_string: bool,
                        editor_font_map: dict,
                        editor_line_width_threshold: int,
                        full_data_string_text_for_logical_check: str,
                        is_target_for_debug: bool = False,
                        logical_hard_limit: Optional[int] = None) -> Set[str]:
        """
        Analyze a single display subline (separated by physical newlines) for warnings.
        Returns: Set[str] of active problem IDs.
        """
        return self.problem_analyzer.analyze_subline(
            text, next_text, subline_number_in_data_string, qtextblock_number_in_editor,
            is_last_subline_in_data_string, editor_font_map, editor_line_width_threshold,
            full_data_string_text_for_logical_check, is_target_for_debug,
            logical_hard_limit=logical_hard_limit
        )

    def autofix_data_string(self,
                            data_string: str,
                            editor_font_map: dict,
                            editor_line_width_threshold: int) -> Tuple[str, bool]:
        """Perform programmatic auto-wrapping or alignment fixes on user request."""
        return self.text_fixer.autofix_data_string(
            data_string, editor_font_map, editor_line_width_threshold
        )

    def get_editor_page_size(self) -> int:
        """Max lines per screen/page for page building and warning logic."""
        return 3

    def get_dynamic_name_tags(self) -> Dict[str, str]:
        """
        Map BMG control tags to actual names to ensure correct script matching.
        E.g. maps '{escape:0:0022}' to 'Epona' during distillation.
        """
        return {}
```

---

## 3. Configuration & Problems (`config.py`)

The `config.py` file exposes standard layout limitations. Here is a baseline configuration:

```python
# Problem IDs
PROBLEM_WIDTH_EXCEEDED = "width_exceeded"
PROBLEM_SHORT_LINE = "short_line"
PROBLEM_TAG_WARNING = "tag_warning"

PROBLEM_DEFINITIONS = {
    PROBLEM_WIDTH_EXCEEDED: {
        "name": "Width Exceeded",
        "description": "Text exceeds the target text box pixel boundary.",
        "color": "#FF0000",       # Red
        "priority": 1,
        "half_height": False
    },
    PROBLEM_SHORT_LINE: {
        "name": "Short Line",
        "description": "Line is short enough to pull up words from the next line.",
        "color": "#00FF00",       # Green
        "priority": 2,
        "half_height": False
    },
    PROBLEM_TAG_WARNING: {
        "name": "Malformed Tag",
        "description": "Tag is unknown or lacks closing syntax.",
        "color": "#FFFF00",       # Yellow
        "priority": 3,
        "half_height": True
    }
}

# Control tags recognized by the spellchecker pattern and tokenizer
CONTROL_CODES = ["{Color:Red}", "{Color:Blue}", "{Color:Default}", "{Clear}"]
```

---

## 4. Characters Width Mapping (`font_map.json`)

The `font_map.json` maps characters to pixel widths for layout calculation:

```json
{
  "widths": {
    "32": 4,
    "33": 2,
    "65": 7,
    "97": 5
  },
  "aliases": {
    "{PLAYER}": {
      "alias": "Link",
      "width": 24
    }
  },
  "default_width": 6
}
```
*Note: Decimal keys in the `"widths"` dictionary represent Unicode code points (e.g. `32` is space, `65` is 'A').*

---

## 5. Guidelines for AI Writing New Plugins

When tasked with creating a new plugin:

1. **Inherit Standard Implementations**: Prefer importing helpers from `plugins/common/` (e.g., `BaseProblemAnalyzer` inside `plugins/common/problem_analyzer.py`) rather than rewriting standard bounding check logic.
2. **Tag Preservation Hook**: Always map important gameplay tags (like player name or buddy tags) under the `"aliases"` field inside the font map. If a tag is a proper noun, prepend `F:` to its alias (e.g., `{F:Link}`) so Picoripi's **Force-Alias** subsystem translates surrounding text with correct grammatical cases before restoring the tag.
3. **Markdown Timeline Scripts**: Implement `get_default_script_name()` returning `<plugin_name>_script.md` to instantly enable local, zero-API-cost character/location context parsing.
4. **Writing Tests**: Always create a corresponding test package under `tests/test_plugins/test_<plugin_name>/` containing assertions for custom tag boundaries, wrapping margins, and font metrics loading.
