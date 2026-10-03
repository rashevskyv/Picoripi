"""Block-tree scenario run by both the pre-audit baseline (tree_make_golden.py) and the review test.

It only uses APIs that exist unchanged in both trees: ProjectManager, MemePalaceClient, MainWindow and
File > Open Project. ``run(...)`` returns a JSON-able dict of what the block tree showed.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

WING = "Plain_Text"  # the wing name the plain_text plugin's display name resolves to


def _blocks():
    blocks = {}
    for folder, prefix in (("town", "t"), ("field", "f")):
        for i in range(10):
            blocks[f"{folder}/{prefix}{i:02d}"] = [f"{prefix}{i:02d} line {n}" for n in range(3)]
    for i in range(4):
        blocks[f"r{i:02d}"] = [f"r{i:02d} line {n}" for n in range(3)]
    blocks["r03"][1] = "Wallet"            # an item of the reference catalogue (normalized story)
    blocks["r03"][2] = "Hello there."      # the dialogue line of the normalized story
    return blocks


def build_project(root: Path, story: str) -> Path:
    """A plain_text project with virtual folders; ``story`` is "legacy" (chapters) or "normalized"."""
    from core.project_manager import ProjectManager

    source, translation = root / "source", root / "translation"
    for rel, lines in _blocks().items():
        for base in (source, translation):
            path = base / f"{rel}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    project_dir = root / "project"
    manager = ProjectManager()
    assert manager.create_new_project(
        project_dir=project_dir, name="Tree", plugin_name="plain_text", source_path=str(source),
        translation_path=str(translation), is_directory_mode=True, auto_create_translations=True,
    )
    manager.project.version = "1.0"  # the next load migrates the file structure into virtual folders
    manager.sync_project_files()
    manager.save()
    manager = ProjectManager()
    assert manager.load(project_dir / "project.uiproj")
    by_name = {block.name: block for block in manager.project.blocks}
    # Speakers by manual assignment, and one translator note (the Notated facet).
    by_name["t00"].metadata["character_assignments"] = {"0": "Hero", "1": "Hero"}
    by_name["f03"].metadata["character_assignments"] = {"2": "Zelda"}
    by_name["r01"].metadata["story_context_assignments"] = {"0": {"notated": True, "translator_note": "pun"}}
    manager.save()
    project_file = project_dir / "project.uiproj"

    from core.mempalace_client import MemePalaceClient
    client = MemePalaceClient(project_dir=str(project_dir))
    if story == "legacy":
        client.save_chapters_to_db(WING, [
            {"num": "Act 1, Ch 1", "title": "Arrival", "start_line": 0, "end_line": 9},
            {"num": "Act 1, Ch 2", "title": "Field", "start_line": 10, "end_line": 19},
            {"num": "Act 2, Ch 1", "title": "Return", "start_line": 20, "end_line": 29},
        ])
        client.save_mappings_to_db(WING, [
            {"bmg_id": "t01_Str_0", "script_line": 1, "bmg_text": "t01 line 0"},
            {"bmg_id": "t02_Str_1", "script_line": 2, "bmg_text": "t02 line 1"},
            {"bmg_id": "f05_Str_2", "script_line": 12, "bmg_text": "f05 line 2"},
            {"bmg_id": "r00_Str_0", "script_line": 21, "bmg_text": "r00 line 0"},
        ])
    else:
        _normalized_story(client, manager)
    close = getattr(client, "close", None)
    if callable(close):
        close()
    return project_file


def _normalized_story(client, manager) -> None:
    from core.script_markup import (
        HIERARCHY_FORMAT_VERSION, HIERARCHY_PROJECT_FORMAT, HierarchyType, default_type_definitions,
        parse_hierarchy_project,
    )
    from core.mempalace.story_timeline import normalize_hierarchy_project

    marks = [
        (0, 6, 0, HierarchyType.STRUCTURE, "Act I"),
        (1, 4, 1, HierarchyType.STRUCTURE, "Chapter One"),
        (2, 4, 2, HierarchyType.STRUCTURE, "Scene One"),
        (3, 3, 3, HierarchyType.SPEAKER, "MIDNA"),
        (4, 4, 4, HierarchyType.TEXT, "Hello there."),
        (5, 5, 4, HierarchyType.ITEM, None),
        (6, 6, 5, HierarchyType.ITEM_DESCRIPTION, None),
    ]
    payload = {
        "format": HIERARCHY_PROJECT_FORMAT,
        "version": HIERARCHY_FORMAT_VERSION,
        "source_path": "C:/scripts/raw.txt",
        "raw_text": "Act I\nChapter One\nScene One\nMIDNA\nHello there.\nWallet\nA wallet from your childhood.\n",
        "type_definitions": [
            {"type_id": d.type_id, "label": d.label, "description": d.description, "color": d.color}
            for d in default_type_definitions().values()
        ],
        "hierarchy_marks": [
            dict({"start_line": s, "end_line": e, "depth": depth, "type_id": kind, "order": n + 1,
                  "origin": "manual", "approved": True}, **({"text": text} if text else {}))
            for n, (s, e, depth, kind, text) in enumerate(marks)
        ],
    }
    project = parse_hierarchy_project(payload, source_path="C:/project/markup.json", source_hash="h1")
    result = client.sync_story_timeline(project)
    dialogue = [node for node in normalize_hierarchy_project(project) if node.node_type == "dialogue"][-1]
    stored = client.get_story_node(result.document_id, dialogue.stable_id)
    block_idx = [block.name for block in manager.project.blocks].index("r03")
    conn = client._get_connection()
    conn.execute(
        """
        INSERT INTO story_dialogue_relations (
            document_id, game_block_id, game_block_name, string_index, game_string_id, dialogue_node_id,
            source_text_snapshot, relation_method, score, game_coverage, relation_status
        ) VALUES (?, ?, 'r03', 2, 'r03_Str_2', ?, 'Hello there.', 'exact_or_contained', 1.0, 1.0, 'supported')
        """,
        (result.document_id, str(block_idx), stored.id),
    )
    conn.commit()


# ------------------------------------------------------------------ the tree

def _item_record(item, role_base):
    record = {"text": item.text(0)}
    for offset in (0, 4, 11, 13, 15, 16, 17, 19):
        value = item.data(0, role_base + offset)
        if value is not None:
            record[str(offset)] = json.loads(json.dumps(value, default=list))
    children = [_item_record(item.child(i), role_base) for i in range(item.childCount())]
    if children:
        record["children"] = children
    return record


def dump_tree(tree) -> list:
    from PyQt6.QtCore import Qt
    root = tree.invisibleRootItem()
    return [_item_record(root.child(i), Qt.ItemDataRole.UserRole) for i in range(root.childCount())]


def _path(item):
    names = []
    while item is not None:
        names.insert(0, item.text(0))
        item = item.parent()
    return names


def _find(tree, path):
    root = tree.invisibleRootItem()
    item = None
    for name in path:
        parent = item or root
        names = [parent.child(i).text(0) for i in range(parent.childCount())]
        matches = [i for i, text in enumerate(names) if text == name or text.startswith(name + " ")]
        assert matches, f"{name!r} not among {names}"
        item = parent.child(matches[0])
    return item


def _story_state(tree):
    root = tree.invisibleRootItem()
    for i in range(root.childCount()):
        if root.child(i).text(0).startswith("Story"):
            story = root.child(i)
            return [story.child(n).text(0) for n in range(story.childCount())]
    return None


def no_machine_script() -> None:
    """Speakers must not come from a game script that happens to exist on this machine (a fixed E: drive path)."""
    from core.translation.script_speaker_finder import ScriptSpeakerFinder
    ScriptSpeakerFinder.find_script_path = lambda self: None


def run(mw, project_file: Path, open_project, wait_until, story: str) -> dict:
    """Open the project in ``mw`` and record the tree through the steps the review item lists."""
    updater = mw.ui_updater.block_list_updater
    tree = mw.block_list_widget
    story_states = []
    original = updater.populate_blocks

    def recording(*args, **kwargs):
        result = original(*args, **kwargs)
        state = _story_state(tree)
        if not story_states or story_states[-1] != state:
            story_states.append(state)
        return result

    updater.populate_blocks = recording

    def settled():
        state = _story_state(tree)
        return (
            bool(mw.data_store.data) and not mw.is_loading_data and state is not None
            and "Loading..." not in state and not getattr(updater, "_is_loading_chapters", False)
        )

    open_project(project_file)
    wait_until(settled)
    # Two equal dumps a moment apart: nothing is rebuilding any more.
    previous = None
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        current = dump_tree(tree)
        if current == previous:
            break
        previous = current
        end = time.monotonic() + 0.2
        wait_until(lambda: time.monotonic() > end)
    result = {"initial": previous, "story_states": story_states}

    # Selection and scroll position survive a rebuild.
    mw.show()
    tree.setFixedHeight(120)
    wait_until(lambda: tree.verticalScrollBar().maximum() > 0)
    target = _find(tree, ["field", "f04"])
    tree.setCurrentItem(target)
    scrollbar = tree.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())
    scroll_before = scrollbar.value()
    updater.populate_blocks()
    result["after_rebuild_selected"] = _path(tree.currentItem()) if tree.currentItem() else None
    scroll_now = scrollbar.value()
    end = time.monotonic() + 0.3
    wait_until(lambda: time.monotonic() > end)
    # At once, and once the event loop has run: was the position the tree had before the rebuild kept?
    result["scroll_kept"] = [scroll_now == scroll_before, scrollbar.value() == scroll_before]

    # "Show unsaved only": one edited string in t07 and one in r02.
    mw.data_processor.update_edited_data(_index(mw, "t07"), 1, "edited")
    mw.data_processor.update_edited_data(_index(mw, "r02"), 0, "edited too")
    mw.show_unsaved_blocks_checkbox.setChecked(True)
    wait_until(lambda: getattr(mw.data_store, "show_unsaved_blocks_only", False) is True)
    updater.populate_blocks()
    result["unsaved_only"] = [entry["text"] for entry in dump_tree(tree)]
    result["unsaved_only_tree"] = dump_tree(tree)
    updater.populate_blocks = original
    return result


def _index(mw, name):
    return next(int(key) for key, value in mw.data_store.block_names.items() if Path(value).stem == name)
