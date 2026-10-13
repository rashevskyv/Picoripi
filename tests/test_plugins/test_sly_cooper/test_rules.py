"""Sly Cooper plugin: the level text as JSON blocks loads, validates and saves with the ids and other keys kept."""
from plugins.testing import check_loads, check_round_trip, check_validator

PLUGIN = "sly_cooper"

SAMPLE = {"file": "text/Paris.json", "blocks": [
    {"name": "Paris", "level": "Worlds/Paris/Paris/Paris.brx", "strings": ["Bummer. You can't open this vault.", "Really?"]}]}


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert ".json" in {e for f in rules.get_file_formats() for e in f.extensions}
    check_validator(PLUGIN)


def test_sample_survives_load_and_save():
    check_round_trip(PLUGIN, SAMPLE)
