"""A project file that opens into several blocks (a KMSG file split by id range; an N64 ROM: messages, credits,
title strings): the Blocks tree shows each block, and a session older than the plugin's code is not restored when it holds no edits."""
import os
from types import SimpleNamespace

from handlers.project_action.session_mixin import SessionMixin
from plugins.zelda_oot64.rules import GameRules
from ui.updaters.block_list.problems_mixin import ProblemsMixin


def test_a_project_block_lists_every_data_block_it_opens_into():
    owner = SimpleNamespace(mw=SimpleNamespace(block_to_project_file_map={0: 0, 1: 0, 2: 0, 3: 1}))
    assert ProblemsMixin._data_blocks_of(owner, 0) == [0, 1, 2]
    assert ProblemsMixin._data_blocks_of(owner, 1) == [3]      # one data block, after a split file
    assert ProblemsMixin._data_blocks_of(SimpleNamespace(mw=SimpleNamespace()), 4) == [4]


def _mixin(tmp_path, edited=None):
    store = SimpleNamespace(edited_data=edited or {}, unsaved_changes=False)
    window = SimpleNamespace(data_store=store, project_manager=SimpleNamespace(project_dir=str(tmp_path)),
                             current_game_rules=GameRules())
    return SimpleNamespace(mw=window)


def test_a_session_older_than_the_plugin_code_is_not_restored_unless_it_holds_edits(tmp_path):
    session = tmp_path / ".picoripi_session"
    session.write_bytes(b"x")
    os.utime(session, (1, 1))                                   # written long before the plugin code
    assert SessionMixin._session_predates_plugin_code(_mixin(tmp_path)) is True
    assert SessionMixin._session_predates_plugin_code(_mixin(tmp_path, {(0, 0): "edit"})) is False
    os.utime(session, None)                                     # written now: newer than the code
    assert SessionMixin._session_predates_plugin_code(_mixin(tmp_path)) is False


class _Tree(ProblemsMixin):
    """The Blocks tree's folder walk over a fake window: blocks render as plain items named by data index."""

    def __init__(self, block_map, categories=(), data=None):
        from PyQt6.QtWidgets import QTreeWidget
        blocks = [SimpleNamespace(id="file0", categories=[]), SimpleNamespace(id="file1", categories=list(categories))]
        self.mw = SimpleNamespace(
            project_manager=SimpleNamespace(project=SimpleNamespace(blocks=blocks)),
            data_store=SimpleNamespace(block_names={"3": "credits"}, show_unsaved_blocks_only=False, data=data),
            block_to_project_file_map=block_map, block_list_widget=QTreeWidget())

    def _create_block_tree_item(self, idx, *args):
        from PyQt6.QtWidgets import QTreeWidgetItem
        return QTreeWidgetItem([f"block {idx}"])

    def _get_block_display_name_with_ext(self, idx, name):
        return name

    def _get_aggregated_problems_for_block(self, *args, **kwargs):
        return {}

    def _set_item_style_icon(self, *args):
        pass

    _register_item_in_cache = _apply_issues_and_tooltip = _stamp_item_paint_stats = _set_item_style_icon

    def folder(self, name, block_id):
        from PyQt6.QtCore import Qt
        folder = SimpleNamespace(id=name, name=name, is_expanded=True, children=[], block_ids=[block_id])
        root = self.mw.block_list_widget.invisibleRootItem()
        self._add_virtual_folder_to_tree(root, folder, {}, None)
        item = root.child(root.childCount() - 1)
        return item.text(0), [item.child(i).text(0) for i in range(item.childCount())], item.data(0, Qt.ItemDataRole.UserRole)

    def shown(self, folder):
        """The tree's lines under ``folder``, indented by depth."""
        root = self.mw.block_list_widget.invisibleRootItem()
        self._add_virtual_folder_to_tree(root, folder, {}, None)

        def lines(item, depth):
            return [f"{'  ' * depth}{item.text(0)}"] + [l for i in range(item.childCount()) for l in lines(item.child(i), depth + 1)]
        return [l for i in range(root.childCount()) for l in lines(root.child(i), 0)]


def test_a_one_file_folder_lists_every_block_its_file_opens_into(qtbot):
    tree = _Tree({0: 0, 1: 0, 2: 0, 3: 1})
    assert tree.folder("messages", "file0") == ("messages", ["block 0", "block 1", "block 2"], None)
    assert tree.folder("staff", "file1") == ("staff / credits", [], 3)    # compacted onto its own data block
    assert _Tree({}).folder("plain", "file1")[2] == 1                     # no map: data index = project index


def _folder(name, block_ids=(), children=()):
    return SimpleNamespace(id=name, name=name, is_expanded=True, children=list(children), block_ids=list(block_ids))


def test_blocks_without_rows_and_the_folders_they_empty_are_not_shown(qtbot):
    """Luigi's Mansion: eventNN.szp holds message/messageNN (text) and text/eventNN (a script, no rows)."""
    tree = _Tree({0: 0, 1: 1}, data=[["Hello", "Bye"], []])
    event = _folder("event03.szp", children=[_folder("message", ["file0"]), _folder("text", ["file1"])])
    assert tree.shown(event) == ["event03.szp / message / Block 0"]      # compacts onto the one block left
    assert _Tree({0: 0, 1: 1}, data=[["Hi"], []]).shown(_folder("event07.szp", children=[_folder("text", ["file1"])])) == []


def test_a_file_that_opens_into_several_blocks_shows_only_those_with_rows(qtbot):
    tree = _Tree({0: 0, 1: 0, 2: 0, 3: 1}, data=[["a"], [], ["c"], ["d"]])
    assert tree.folder("messages", "file0") == ("messages", ["block 0", "block 2"], None)


def test_an_empty_folder_the_user_made_and_blocks_not_loaded_yet_stay(qtbot):
    assert _Tree({}, data=[[], []]).shown(_folder("new folder")) == ["new folder"]
    assert _Tree({}, data=None).shown(_folder("text", ["file1"])) == ["text / Block 1"]


def test_the_overall_bar_counts_translated_rows_of_rows_that_need_one(qtbot):
    from components.blocks_progress_bar import BlocksProgressBar
    bar = BlocksProgressBar()
    needs, translated = {0: {0, 1, 2}, 1: set(), 2: {0}}, {0: {0, 2, 5}, 1: {0}, 2: set()}
    owner = SimpleNamespace(mw=SimpleNamespace(
        blocks_progress_bar=bar, data_store=SimpleNamespace(data=[["", "", ""], [""], [""]]),
        data_processor=SimpleNamespace(get_needs_translation_set=needs.__getitem__,
                                       get_translated_set=translated.__getitem__)))
    ProblemsMixin._update_overall_progress(owner)
    assert (bar.value(), bar.maximum(), bar.text()) == (2, 4, "2 / 4 (50%)")
    bar.show_progress(0, 0)
    assert bar.isHidden()


def test_a_one_file_folder_keeps_the_block_item_when_the_block_has_categories(qtbot):
    """The categories hang under the block's own item (Yo-kai Watch's "Japanese source" lines)."""
    assert _Tree({}, categories=["Japanese source"]).folder("map", "file1") == ("map", ["block 1"], None)
