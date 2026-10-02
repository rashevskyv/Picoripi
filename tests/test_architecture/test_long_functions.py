"""The two functions that were 746 and 542 lines long stay split (WP6 6.5)."""
import ast
from pathlib import Path

import pytest

LIMIT = 120


@pytest.mark.parametrize("module", [
    "handlers/translation/worker/run_mixin.py",
    "ui/updaters/block_list/populate_mixin.py",
])
def test_no_function_in_the_split_modules_grows_past_the_limit(module):
    tree = ast.parse(Path(module).read_text(encoding="utf-8"))
    too_long = {
        node.name: node.end_lineno - node.lineno + 1
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.end_lineno - node.lineno + 1 > LIMIT
    }

    assert too_long == {}
