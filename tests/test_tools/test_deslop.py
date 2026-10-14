"""tools/deslop: each rule on good and bad snippets, then suppression, configuration, scanning and the baseline."""
import textwrap

import pytest

from tools.deslop import __main__ as deslop_cli
from tools.deslop import engine
from tools.deslop.rules import RULES


def _lines(source, rule, path="tests/test_sample.py", **options):
    found = engine.lint_source(textwrap.dedent(source), path, rule_ids=[rule], options=options or None)
    return [item.line for item in found]


class TestCallOnlyAssertions:
    def test_a_test_that_checks_only_mock_calls_is_flagged(self):
        source = """
        from unittest.mock import MagicMock

        def test_saves(handler):
            writer = MagicMock()
            handler.save(writer)
            writer.write.assert_called_once()
        """

        assert _lines(source, "call-only-assertions") == [4]

    def test_a_result_check_next_to_the_mock_check_is_enough(self):
        source = """
        def test_saves(handler, writer):
            handler.save(writer)
            writer.write.assert_called_once()
            assert handler.state == "saved"
        """

        assert _lines(source, "call-only-assertions") == []

    def test_a_context_manager_or_a_qt_wait_is_a_real_check(self):
        source = """
        import pytest

        def test_raises(worker, mock_log):
            with pytest.raises(ValueError):
                worker.run()
            mock_log.assert_called_once()

        def test_signal(qtbot, worker, mock_log):
            with qtbot.waitSignal(worker.done):
                worker.start()
            mock_log.assert_called_once()
        """

        assert _lines(source, "call-only-assertions") == []

    def test_a_helper_that_checks_state_counts_as_a_real_check(self):
        source = """
        def test_rows(model, mock_emit):
            model.reload()
            mock_emit.assert_called_once()
            assert_rows_match(model)
        """

        assert _lines(source, "call-only-assertions") == []

    def test_unittest_style_mock_checks_are_mock_checks(self):
        source = """
        import unittest

        class TestSave(unittest.TestCase):
            def test_saves(self):
                self.writer.write.assert_called_once()
                self.assertEqual(self.writer.write.call_count, 1)
        """

        assert _lines(source, "call-only-assertions") == [5]

    def test_a_test_without_any_assertion_is_another_problem(self):
        source = """
        def test_runs(handler):
            handler.start()
        """

        assert _lines(source, "call-only-assertions") == []

    def test_product_code_is_not_scanned_by_a_test_rule(self):
        source = """
        def test_saves(handler, writer):
            writer.write.assert_called_once()
        """

        assert _lines(source, "call-only-assertions", path="plugins/sample.py") == []


class TestModuleMocking:
    @pytest.mark.parametrize(
        "statement",
        [
            'monkeypatch.setitem(sys.modules, "gpu", fake)',
            'patch.dict(sys.modules, {"gpu": fake})',
            'sys.modules["gpu"] = fake',
            'sys.modules.update({"gpu": fake})',
            'mock.patch.dict("sys.modules", {"gpu": fake})',
        ],
    )
    def test_replacing_modules_is_flagged(self, statement):
        source = f"import sys\n{statement}\n"

        assert _lines(source, "module-mocking") == [2]

    def test_reading_or_cleaning_up_sys_modules_is_not_flagged(self):
        source = """
        import sys

        def test_snapshot():
            before = dict(sys.modules)
            json_module = sys.modules["json"]
            del sys.modules["made_for_the_test"]
            assert json_module is not None and before
        """

        assert _lines(source, "module-mocking") == []


class TestPoorSubstringTests:
    @pytest.mark.parametrize(
        "statement",
        ['assert "4" in text', 'assert "error" in str(exc)', 'assertTrue("ok" in value)', 'assertIn("", output)'],
    )
    def test_a_short_or_generic_substring_is_flagged(self, statement):
        source = f"def test_text(text, exc, value, output):\n    {statement}\n"

        assert _lines(source, "poor-substring-tests") == [2]

    def test_a_full_message_is_not_flagged(self):
        source = """
        def test_text(text):
            assert "Saved 4 files" in text
            assert "fatal" in text
        """

        assert _lines(source, "poor-substring-tests") == []

    def test_the_length_threshold_is_an_option(self):
        source = """
        def test_text(text):
            assert "fatal" in text
        """

        assert _lines(source, "poor-substring-tests", poor_substring_max_length=5) == [3]


class TestRepeatedAssertCall:
    def test_the_same_assertion_twice_in_a_row_is_flagged(self):
        source = """
        def test_count(writer):
            assert writer.count == 1
            assert writer.count == 1
        """

        assert _lines(source, "repeated-assert-call") == [4]

    def test_a_repeated_mock_check_is_flagged(self):
        source = """
        def test_writes(writer):
            writer.write.assert_called_once_with("a")
            writer.write.assert_called_once_with("a")
        """

        assert _lines(source, "repeated-assert-call") == [4]

    def test_the_same_assertion_after_a_change_of_state_is_not_flagged(self):
        source = """
        def test_count(state):
            assert state.value == 0
            state.bump()
            assert state.value == 0
        """

        assert _lines(source, "repeated-assert-call") == []

    def test_a_repeat_with_an_assertion_that_changes_state_between_is_not_flagged(self):
        source = """
        def test_fold(dialog):
            assert dialog.toggle(1)
            assert not dialog.is_folded()
            assert dialog.toggle(1)
        """

        assert _lines(source, "repeated-assert-call") == []


class TestChainedCast:
    @pytest.mark.parametrize(
        "statement",
        ["typing.cast(int, typing.cast(object, value))", "cast(str, cast(Any, value))"],
    )
    def test_a_cast_of_a_cast_is_flagged(self, statement):
        source = f"import typing\nfrom typing import Any, cast\nresult = {statement}\n"

        assert _lines(source, "chained-cast") == [3]

    def test_a_single_cast_is_not_flagged(self):
        source = "from typing import cast\nresult = cast(int, value)\n"

        assert _lines(source, "chained-cast") == []


class TestGetattrLiteral:
    @pytest.mark.parametrize(
        "statement",
        ['value = getattr(obj, "name")', 'setattr(obj, "name", 1)'],
    )
    def test_a_constant_attribute_name_is_flagged(self, statement):
        assert _lines(statement + "\n", "getattr-literal", path="plugins/sample.py") == [1]

    @pytest.mark.parametrize(
        "statement",
        [
            'value = getattr(obj, "name", None)',
            "value = getattr(obj, name)",
            'value = getattr(obj, "not-an-identifier")',
            'value = getattr(obj, "__class__")',
            'value = getattr(obj, "class")',
            'present = hasattr(obj, "name")',
        ],
    )
    def test_defaults_variables_and_probes_are_not_flagged(self, statement):
        assert _lines(statement + "\n", "getattr-literal", path="plugins/sample.py") == []


class TestReduceAccumulatorCopy:
    @pytest.mark.parametrize(
        "statement",
        [
            "reduce(lambda acc, x: acc + [x], xs, [])",
            "functools.reduce(lambda acc, x: {**acc, x: 1}, xs, {})",
            "reduce(lambda acc, x: acc | {x}, xs, set())",
            "reduce(lambda acc, x: [*acc, x], xs, [])",
        ],
    )
    def test_a_reducer_that_copies_the_accumulator_is_flagged(self, statement):
        source = f"import functools\nfrom functools import reduce\nresult = {statement}\n"

        assert _lines(source, "reduce-accumulator-copy") == [3]

    def test_a_reducer_that_adds_numbers_is_not_flagged(self):
        source = "from functools import reduce\nresult = reduce(lambda total, x: total + x, xs, 0)\n"

        assert _lines(source, "reduce-accumulator-copy") == []


class TestFilterMapChain:
    def test_map_over_filter_is_flagged(self):
        assert _lines("out = map(str, filter(None, xs))\n", "filter-map-chain") == [1]

    def test_a_comprehension_over_a_materialised_comprehension_is_flagged(self):
        assert _lines("out = [y for y in [x * 2 for x in xs]]\n", "filter-map-chain") == [1]

    def test_one_pass_and_nested_generators_are_not_flagged(self):
        source = """
        out = map(str, (x for x in xs))
        plain = [x for x in xs]
        pairs = [y for x in xs for y in [x]]
        """

        assert _lines(source, "filter-map-chain") == []


class TestOptInRules:
    def test_any_in_a_public_signature_is_flagged(self):
        source = """
        from typing import Any

        def load(path: str) -> Any:
            return path

        def _private(value: Any):
            return value

        def typed(path: str) -> dict:
            return {}
        """

        assert _lines(source, "any-params-returns") == [4]

    def test_an_alias_that_renames_a_type_is_flagged(self):
        source = "import pathlib\nBoardPath = pathlib.Path\nlimit = 3\nCOLOR_A = COLOR_B\n"

        assert _lines(source, "pass-through-type-alias") == [2]

    def test_redundant_and_needless_import_aliases_are_flagged(self):
        source = """
        import os
        from os import path as path
        from os import sep as separator
        from os import linesep as _linesep
        import numpy as np
        """

        assert _lines(source, "renamed-imports") == [3, 4]

    def test_package_init_files_keep_their_reexports(self):
        source = "from os import path as path\n"

        assert _lines(source, "renamed-imports", path="pkg/__init__.py") == []

    def test_a_type_suffix_in_a_variable_or_argument_is_flagged(self):
        source = """
        def run(name_dict):
            file_list = []
            item = []
            return file_list, item, name_dict

        def to_dict():
            return {}
        """

        assert _lines(source, "shape-in-names") == [2, 3]

    def test_the_same_constant_in_two_modules_is_flagged_once_per_module(self, tmp_path):
        (tmp_path / "a.py").write_text('LABEL = "shared label"\nOTHER = 1\n', encoding="utf-8")
        (tmp_path / "b.py").write_text('LABEL = "shared label"\n', encoding="utf-8")
        (tmp_path / "c.py").write_text('LABEL = "only here"\n', encoding="utf-8")

        result = engine.scan(["."], rule_ids=["duplicate-consts"], excludes=(), root=tmp_path)

        assert [(item.path, item.line) for item in result.violations] == [("a.py", 1), ("b.py", 1)]


class TestSuppression:
    def test_the_named_rule_is_suppressed_on_its_line(self):
        source = 'value = getattr(obj, "name")  # deslop: ignore[getattr-literal]\n'

        assert _lines(source, "getattr-literal", path="plugins/sample.py") == []

    def test_another_rule_name_does_not_suppress(self):
        source = 'value = getattr(obj, "name")  # deslop: ignore[chained-cast]\n'

        assert _lines(source, "getattr-literal", path="plugins/sample.py") == [1]

    def test_a_bare_ignore_suppresses_every_rule_on_its_line(self):
        source = 'value = getattr(obj, "name")  # deslop: ignore\n'

        assert _lines(source, "getattr-literal", path="plugins/sample.py") == []


class TestConfiguration:
    def test_enable_and_disable_change_the_default_set(self):
        settings = {"enable": ["shape-in-names"], "disable": ["chained-cast"]}

        chosen = engine.enabled_rule_ids(settings, extra=["renamed-imports"])

        assert "shape-in-names" in chosen and "renamed-imports" in chosen
        assert "chained-cast" not in chosen and "call-only-assertions" in chosen

    def test_opt_in_rules_are_off_by_default(self):
        chosen = engine.enabled_rule_ids({})

        assert chosen == {rule_id for rule_id, rule in RULES.items() if rule.default_on}

    def test_an_unknown_rule_is_an_error(self):
        with pytest.raises(ValueError, match="unknown deslop rule"):
            engine.enabled_rule_ids({}, extra=["no-such-rule"])

    def test_options_use_dashes_in_the_file_and_underscores_in_code(self):
        options = engine.resolve_options({"poor-substring-max-length": 5, "enable": []})

        assert options["poor_substring_max_length"] == 5

    def test_an_unknown_option_is_an_error(self):
        with pytest.raises(ValueError, match="unknown"):
            engine.resolve_options({"poor-substring-max-lenght": 5})


class TestScanning:
    def test_excluded_and_hidden_folders_are_skipped_before_they_are_read(self, tmp_path):
        for relative in ("keep.py", "venv/skip.py", ".hidden/skip.py", "pkg/__pycache__/skip.py", "build/skip.py", "tools/build/keep.py"):
            target = tmp_path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x = 1\n", encoding="utf-8")

        found = list(engine.iter_python_files(["."], tmp_path, excludes=("venv", "build")))

        assert sorted(path.relative_to(tmp_path).as_posix() for path in found) == ["keep.py", "tools/build/keep.py"]

    def test_the_default_excludes_skip_local_scratch_and_worktree_folders(self, tmp_path):
        for relative in ("keep.py", "scratch/skip.py", "worktrees/skip.py"):
            target = tmp_path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x = 1\n", encoding="utf-8")

        found = list(engine.iter_python_files(["."], tmp_path, excludes=engine.DEFAULT_EXCLUDES))

        assert [path.relative_to(tmp_path).as_posix() for path in found] == ["keep.py"]

    def test_a_named_python_file_is_checked_and_a_named_text_file_is_not(self, tmp_path):
        (tmp_path / "scratch").mkdir()
        (tmp_path / "scratch" / "one.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("x\n", encoding="utf-8")

        found = list(engine.iter_python_files(["scratch/one.py", "notes.txt"], tmp_path, excludes=engine.DEFAULT_EXCLUDES))

        assert [path.relative_to(tmp_path).as_posix() for path in found] == ["scratch/one.py"]

    def test_a_syntax_error_is_reported_and_the_scan_goes_on(self, tmp_path):
        (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
        (tmp_path / "fine.py").write_text('assert "x" in y\n', encoding="utf-8")

        result = engine.scan(["."], rule_ids=["module-mocking"], excludes=(), root=tmp_path)

        assert result.errors and result.errors[0].startswith("broken.py:")
        assert result.files == ["broken.py", "fine.py"]


class TestBaseline:
    def test_growth_is_reported_only_where_a_count_is_higher(self):
        current = {"tests/a.py": {"call-only-assertions": 3, "module-mocking": 1}, "tests/b.py": {"poor-substring-tests": 1}}
        baseline = {"tests/a.py": {"call-only-assertions": 3, "module-mocking": 0}, "tests/b.py": {"poor-substring-tests": 2}}

        assert engine.growth(current, baseline) == [("tests/a.py", "module-mocking", 0, 1)]

    def test_a_new_file_with_violations_grows_from_zero(self):
        assert engine.growth({"tests/new.py": {"chained-cast": 2}}, {}) == [("tests/new.py", "chained-cast", 0, 2)]

    def test_write_replaces_scanned_files_and_keeps_the_rest(self, tmp_path):
        target = tmp_path / "baseline.json"
        target.write_text('{"tests/old.py": {"chained-cast": 1}, "tests/kept.py": {"chained-cast": 2}}', encoding="utf-8")

        engine.write_baseline(target, {"tests/old.py": {"module-mocking": 4}}, ["tests/old.py"])

        assert engine.load_baseline(target) == {"tests/kept.py": {"chained-cast": 2}, "tests/old.py": {"module-mocking": 4}}
        assert target.read_bytes().endswith(b"}\n") and b"\r" not in target.read_bytes()


class TestCommandLine:
    def test_list_rules_prints_every_rule_and_exits_zero(self, capsys):
        assert deslop_cli.main(["--list-rules"]) == 0

        printed = capsys.readouterr().out
        assert all(rule_id in printed for rule_id in RULES)

    def test_an_unknown_rule_exits_with_usage_error(self, capsys):
        assert deslop_cli.main(["--rule", "no-such-rule", "tests/test_tools"]) == 2
        assert "unknown deslop rule" in capsys.readouterr().err
