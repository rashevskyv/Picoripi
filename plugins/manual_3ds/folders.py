"""Folders of one manual in the block tree: Small text, Large text, Sections and Contents.

Keys come from the manual file: "small/Page_003_small_1#7" is a paragraph of page 3, "index/Index#3" is the index
entry that names page 3 (its text is the section title). Pure key parsing and grouping: no widgets, no disk.
"""
import re
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from core.i18n import tr

_TEXT_KEY = re.compile(r"(large|small)/Page_(\d+)_(?:large|small)_\d+(?:#\d+)?")
_INDEX_KEY = re.compile(r"index/Index#(\d+)")


def _section_title(page: int, index_string: Optional[int], text_of: Callable[[int], str]) -> str:
    """The text of the page's index entry, one line; "Page N" when there is none or it is blank."""
    if index_string is not None:
        title = " ".join(text_of(index_string).split())
        if title:
            return title
    return tr("Page {0}").format(page)


def build_folders(block_idx: int, keys: Sequence[str], text_of: Callable[[int], str]) -> List[Dict[str, Any]]:
    """The manual's folder nodes (see GameRules.get_virtual_folders). Rows keep the key order of the file.

    Small text and Large text hold one subfolder per page; Sections holds one subfolder per page with its small
    and large strings, so a string sits in two places. Contents holds the index entries. Empty folders are left out.
    """
    small: Dict[int, List[Tuple[int, int]]] = {}
    large: Dict[int, List[Tuple[int, int]]] = {}
    index_of: Dict[int, int] = {}
    for string_idx, key in enumerate(keys):
        text = _TEXT_KEY.fullmatch(key)
        if text:
            target = small if text.group(1) == "small" else large
            target.setdefault(int(text.group(2)), []).append((block_idx, string_idx))
            continue
        index = _INDEX_KEY.fullmatch(key)
        if index:
            index_of[int(index.group(1))] = string_idx

    contents = [(block_idx, index_of[page]) for page in sorted(index_of)]
    pages = sorted(set(small) | set(large))
    titles = {page: _section_title(page, index_of.get(page), text_of) for page in sorted(set(pages) | set(index_of))}

    def pages_of(group: Dict[int, List[Tuple[int, int]]]) -> List[Dict[str, Any]]:
        return [{"title": titles[page], "rows": group[page]} for page in pages if group.get(page)]

    sections = []
    for page in pages:
        parts = []
        if small.get(page):
            parts.append({"title": tr("Small text"), "rows": small[page]})
        if large.get(page):
            parts.append({"title": tr("Large text"), "rows": large[page]})
        sections.append({"title": titles[page], "children": parts})

    folders = []
    if small:
        folders.append({"title": tr("Small text"), "children": pages_of(small)})
    if large:
        folders.append({"title": tr("Large text"), "children": pages_of(large)})
    if pages:
        folders.append({"title": tr("Sections"), "children": sections})
    if contents:
        folders.append({"title": tr("Contents"), "rows": contents})
    return folders
