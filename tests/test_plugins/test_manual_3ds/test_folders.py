"""3DS manual block-tree folders: Small text, Large text, Sections and Contents, built from synthetic keys
(and, when PICORIPI_ROMHACKING is set, from every real manual file, read only)."""
import json
from collections import Counter

import pytest

import romhacking_root
from core.i18n import tr
from plugins.manual_3ds.folders import build_folders

# Strings of block 2: index titles for pages 3 and 5 (page 5 is blank in the translation), page 4 has no index entry.
KEYS = [
    "index/Index#3",          # 0
    "small/Page_003_small_0#1",  # 1
    "small/Page_003_small_1#2",  # 2
    "large/Page_003_large_0#3",  # 3
    "index/Index#5",          # 4
    "small/Page_005_small_0#4",  # 5
    "large/Page_004_large_0#5",  # 6
    "large/Page_003_large_1#6",  # 7
]
TITLES = {0: "  Battery\n pack ", 4: ""}


def _text_of(string_idx):
    return TITLES.get(string_idx, "")


def _folders():
    return build_folders(2, KEYS, _text_of)


def _by_title(nodes, title):
    matches = [node for node in nodes if node["title"] == title]
    assert len(matches) == 1, [node["title"] for node in nodes]
    return matches[0]


def test_top_folders_come_in_order_and_contents_lists_index_strings():
    folders = _folders()
    assert [node["title"] for node in folders] == [
        tr("Small text"), tr("Large text"), tr("Sections"), tr("Contents"),
    ]
    assert _by_title(folders, tr("Contents"))["rows"] == [(2, 0), (2, 4)]


def test_small_and_large_have_one_subfolder_per_page_in_page_order():
    folders = _folders()
    small = _by_title(folders, tr("Small text"))["children"]
    large = _by_title(folders, tr("Large text"))["children"]
    assert [node["title"] for node in small] == ["Battery pack", "Page 5"]
    assert small[0]["rows"] == [(2, 1), (2, 2)]
    assert small[1]["rows"] == [(2, 5)]
    assert [node["title"] for node in large] == ["Battery pack", "Page 4"]
    assert large[0]["rows"] == [(2, 3), (2, 7)]
    assert large[1]["rows"] == [(2, 6)]


def test_sections_hold_small_then_large_for_each_page():
    sections = _by_title(_folders(), tr("Sections"))["children"]
    assert [node["title"] for node in sections] == ["Battery pack", "Page 4", "Page 5"]
    battery = sections[0]["children"]
    assert [node["title"] for node in battery] == [tr("Small text"), tr("Large text")]
    assert battery[0]["rows"] == [(2, 1), (2, 2)]
    assert battery[1]["rows"] == [(2, 3), (2, 7)]
    assert sections[1]["children"] == [{"title": tr("Large text"), "rows": [(2, 6)]}]
    assert sections[2]["children"] == [{"title": tr("Small text"), "rows": [(2, 5)]}]


def test_a_string_sits_in_two_places():
    folders = _folders()
    small_page = _by_title(_by_title(folders, tr("Small text"))["children"], "Battery pack")["rows"]
    section_small = _by_title(
        _by_title(_by_title(folders, tr("Sections"))["children"], "Battery pack")["children"],
        tr("Small text"),
    )["rows"]
    assert small_page == section_small == [(2, 1), (2, 2)]


def test_blank_index_title_falls_back_to_page_number():
    folders = _folders()
    titles = [node["title"] for node in _by_title(folders, tr("Small text"))["children"]]
    assert titles[1] == tr("Page {0}").format(5)


def test_no_strings_gives_no_folders():
    assert build_folders(0, ["index/Index#1"], lambda s: "Start") == [
        {"title": tr("Contents"), "rows": [(0, 0)]},
    ]
    assert build_folders(0, [], lambda s: "") == []


_MANUALS = romhacking_root.path("_shared", "3ds_sysfont_ua", "repo_manual", "src", "manuals")
_MANUALS_GATE = romhacking_root.missing("_shared", "3ds_sysfont_ua", "repo_manual", "src", "manuals")


@pytest.mark.skipif(_MANUALS_GATE is not None, reason=_MANUALS_GATE or "")
def test_every_real_manual_file_places_each_page_key_once_per_folder_kind():
    """Old and New 3DS manuals alike: every text key sits once under Small or Large text and once under Sections,
    every index entry under Contents. Reads the owner's files only."""
    files = sorted(_MANUALS.glob("*.json"))
    assert files
    for path in files:
        keys = list(json.loads(path.read_text(encoding="utf-8")))
        folders = build_folders(0, keys, lambda s: "")
        small_keys = {s for s, key in enumerate(keys) if key.startswith("small/")}
        large_keys = {s for s, key in enumerate(keys) if key.startswith("large/")}
        index_keys = {s for s, key in enumerate(keys) if key.startswith("index/")}
        assert len(small_keys | large_keys | index_keys) == len(keys), path.name

        for title, expected in ((tr("Small text"), small_keys), (tr("Large text"), large_keys)):
            top = [node for node in folders if node["title"] == title]
            counts = Counter(row[1] for node in top for leaf in _leaves(node) for row in leaf["rows"])
            assert set(counts) == expected, path.name
            assert all(count == 1 for count in counts.values()), path.name
        sections = [node for node in folders if node["title"] == tr("Sections")]
        for title, expected in ((tr("Small text"), small_keys), (tr("Large text"), large_keys)):
            counts = Counter(
                row[1]
                for section in sections for page in section["children"]
                for part in page["children"] if part["title"] == title
                for row in part["rows"]
            )
            assert set(counts) == expected, path.name
            assert all(count == 1 for count in counts.values()), path.name
        contents = [node for node in folders if node["title"] == tr("Contents")]
        assert {row[1] for node in contents for row in node["rows"]} == index_keys, path.name


def _leaves(node):
    if not node.get("children"):
        yield node
        return
    for child in node["children"]:
        yield from _leaves(child)
