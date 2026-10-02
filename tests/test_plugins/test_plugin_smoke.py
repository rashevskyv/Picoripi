"""Every shipped plugin passes the checks a generated plugin starts with (WP5 5.4)."""
import pytest

from plugins.testing import check_loads, check_round_trip
from plugins.validate import plugin_names

# A piece of text in the form each plugin loads. Plugins without an entry need a
# real game file to round-trip and are covered by their own tests.
SAMPLES = {
    "default_plugin": "First line\nSecond line\n\nNext block",
    "plain_text": "First line\nSecond line",
    "zelda_mc": [["First {Color:Red}line", "Second line"], ["Next block"]],
    "zelda_ww": [["First [Color:Red]line[/C]", "Second line"], ["Next block"]],
    "pokemon_fr": {"block_a": {"key_1": "First line", "key_2": "Second line"}, "block_b": {"key_3": "Next block"}},
}


@pytest.mark.parametrize("name", plugin_names())
def test_the_plugin_loads(name):
    check_loads(name)


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_a_sample_survives_load_and_save(name):
    check_round_trip(name, SAMPLES[name])
