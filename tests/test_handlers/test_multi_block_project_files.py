"""A project file that opens into several blocks (an N64 ROM: messages, credits, title strings): the Blocks tree
shows each block, and a session older than the plugin's code is not restored when it holds no edits."""
import os
from types import SimpleNamespace

from handlers.project_action.session_mixin import SessionMixin
from plugins.zelda_oot64.rules import GameRules
from ui.updaters.block_list.problems_mixin import ProblemsMixin


def test_a_project_block_lists_every_data_block_it_opens_into():
    owner = SimpleNamespace(mw=SimpleNamespace(block_to_project_file_map={0: 0, 1: 0, 2: 0, 3: 1}))
    assert ProblemsMixin._data_blocks_of(owner, 0) == [0, 1, 2]
    assert ProblemsMixin._data_blocks_of(owner, 1) == [1]      # one data block: the old behaviour
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
