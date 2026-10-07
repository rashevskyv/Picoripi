"""A project file that opens into several blocks (a KMSG file split by id range, an N64 ROM): the Blocks tree
shows each block."""
from types import SimpleNamespace

from ui.updaters.block_list.problems_mixin import ProblemsMixin


def test_a_project_block_lists_every_data_block_it_opens_into():
    owner = SimpleNamespace(mw=SimpleNamespace(block_to_project_file_map={0: 0, 1: 0, 2: 0, 3: 1}))
    assert ProblemsMixin._data_blocks_of(owner, 0) == [0, 1, 2]
    assert ProblemsMixin._data_blocks_of(owner, 1) == [1]      # one data block: the old behaviour
    assert ProblemsMixin._data_blocks_of(SimpleNamespace(mw=SimpleNamespace()), 4) == [4]
