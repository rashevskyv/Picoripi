import re
from typing import Tuple, List, Optional, Set
from plugins.common.text_fixer import GenericTextFixer

NEWLINE_TAGS_PATTERN = re.compile(r'(\\n|\\p|\\l)')

class TextFixer(GenericTextFixer):
    """Text fixer implementation for Pokemon FR."""
    def __init__(self, main_window_ref, tag_manager_ref, problem_analyzer_ref):
        """Initialize a new instance."""
        super().__init__(main_window_ref, tag_manager_ref, problem_analyzer_ref)

    def _get_sublines_with_tags(self, text: str) -> List[Tuple[str, str]]:
        if not text:
            return []
        sublines = []
        parts = NEWLINE_TAGS_PATTERN.split(text)
        current_text = parts[0]
        for i in range(1, len(parts), 2):
            newline_tag = parts[i]
            text_after = parts[i+1]
            sublines.append((current_text, newline_tag))
            current_text = text_after
        if current_text or (not sublines and text):
            sublines.append((current_text, ""))
        return sublines

    def _reassemble_data_string(self, sublines_with_tags: List[Tuple[str, str]]) -> str:
        return "".join([text + tag for text, tag in sublines_with_tags])

    def autofix_data_string(self,
                             data_string: str,
                             editor_font_map: dict,
                             editor_line_width_threshold: int,
                             logical_hard_limit: Optional[int] = None,
                             allowed_problems: Optional[Set[str]] = None,
                             block_idx: Optional[int] = None,
                             string_idx: Optional[int] = None,
                             page_local: bool = False,
                             disable_pagination: bool = False) -> Tuple[str, bool]:
        """Split by page breaks (\\p, \\l), autofix each page independently, and reassemble."""
        if not data_string:
            return data_string, False

        # Split by page breaks (\\p or \\l)
        parts = re.split(r'(\\p|\\l)', data_string)

        any_changed = False
        new_parts = []

        for i in range(len(parts)):
            if i % 2 == 1:
                # This is a page break tag (\\p or \\l), keep as is
                new_parts.append(parts[i])
            else:
                # This is a page text
                page_text = parts[i]
                if not page_text:
                    new_parts.append("")
                    continue

                # Replace Pokemon newline \\n with standard \n for base autofix
                normalized_page = page_text.replace('\\n', '\n')

                fixed_page_text, page_changed = super().autofix_data_string(
                    normalized_page,
                    editor_font_map,
                    editor_line_width_threshold,
                    logical_hard_limit,
                    allowed_problems,
                    block_idx,
                    string_idx,
                    page_local,
                    disable_pagination
                )

                if page_changed:
                    any_changed = True

                # Convert standard \n back to Pokemon \\n
                fixed_page_data = fixed_page_text.replace('\n', '\\n')
                new_parts.append(fixed_page_data)

        if not any_changed:
            return data_string, False

        final_text = "".join(new_parts)
        return final_text, True
