"""tools/measure_prompts.py keeps working and the prompts stay inside their budget."""
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "picoripi_measure_prompts", Path(__file__).parents[2] / "tools" / "measure_prompts.py"
)
measure_prompts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(measure_prompts)


@pytest.fixture(scope="module")
def sizes(qapp):
    result = measure_prompts.measure()
    result.pop("_texts")
    return result


def test_harness_reports_every_headline_number(sizes):
    assert sizes["single"]["total_tok"] > 0
    assert sizes["batch_chunk_12"]["total_tok"] > 0
    assert sizes["block_40_strings"]["requests"] == 4
    assert set(sizes["batch_chunk_12"]["payload_tok"]) >= {"strings_to_translate", "glossary"}
