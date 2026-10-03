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


def test_prompts_stay_inside_the_budget_reached_in_wp2(sizes):
    """A regression gate, not a target: raise a limit only with a reason in the commit."""
    batch = sizes["batch_chunk_12"]
    assert batch["system_identical_across_chunks"] is True
    assert batch["user_has_instructions_block"] is False
    # Raised 2026-10-03 (1400/4500/17500): every reference language for every line again, the owner's call.
    assert batch["user_tok"] <= 1450          # was 3414 before WP2
    assert batch["total_tok"] <= 4650         # was 5520
    assert batch["per_item_tok"] <= 100       # was 156
    assert batch["glossary_rows"] == batch["glossary_rows_in_chunk_text"]
    assert sizes["single"]["user_tok"] <= 450  # was 946
    assert sizes["block_40_strings"]["input_tok"] <= 17800  # was 20615
