"""Xenoblade Chronicles: Definitive Edition (Switch) plugin: the Xenoblade 2 rules on the DE files (real data when unpacked)."""
import romhacking_root

import pytest

from plugins.common import bdat_legacy
from plugins.testing import check_loads, check_validator, load_rules

PLUGIN = "xenoblade_de"
SOURCE = romhacking_root.under('Xenoblade\\Chronicles\\DE - Switch\\source')


def test_the_plugin_loads_and_validates():
    rules = check_loads(PLUGIN)
    assert rules.get_display_name().startswith("Xenoblade Chronicles: Definitive Edition")
    assert rules.problem_prefix == "XCDE"
    check_validator(PLUGIN)


@pytest.mark.skipif(not (SOURCE / "bdat" / "gb").is_dir(), reason="Xenoblade DE is not unpacked here")
def test_every_english_table_file_round_trips():
    files = sorted((SOURCE / "bdat" / "gb").glob("*.bdat"))
    assert len(files) == 60
    total = 0
    for path in files:
        raw = path.read_bytes()
        assert bdat_legacy.is_bdat(raw)
        texts = bdat_legacy.read(raw)
        assert bdat_legacy.write(raw, texts) == raw
        total += len(texts)
    assert total > 50000
    rules = load_rules(PLUGIN)
    blocks, _names = rules.load_data_from_json_obj(files[0].read_bytes())
    assert blocks and blocks[0]
