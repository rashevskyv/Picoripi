"""The owner's disc: every stage rebuilds byte for byte and every script reads and writes back unchanged.

Set ``PICORIPI_ZOE2_ISO`` to the USA disc image (SLUS-20545); the test is skipped without it. About two minutes.
"""
import os

import pytest

from plugins.zoe2_ps2 import disc, scx, stagedat as sd, unpack

ISO = os.environ.get("PICORIPI_ZOE2_ISO", "")

pytestmark = pytest.mark.skipif(not os.path.isfile(ISO), reason="PICORIPI_ZOE2_ISO is not set to the disc image")


def test_every_stage_rebuilds_byte_for_byte_and_every_script_round_trips():
    with open(ISO, "rb") as image:
        entry = disc.find_path(image, disc.STAGE_PATH)
        read = disc.file_reader(image, entry)
        toc = sd.read_toc(read)
        assert len(toc.stages) == 110
        starts = [sector for _name, sector in toc.stages] + [entry.size // sd.SECTOR]
        texts = 0
        for position, (name, sector) in enumerate(toc.stages):
            stage = sd.parse_stage(read, toc, name, sector)
            stored = sd.stage_bytes(read, toc, stage, {})
            assert stored == read(sector * sd.SECTOR, (starts[position + 1] - sector) * sd.SECTOR), name
            found = unpack.find_script(stage)
            assert found is not None, name
            group = stage.groups[found[0]]
            data = sd.member_bytes(read, stage, group, group.members[found[1]])
            strings = scx.read_texts(data)
            assert scx.write_texts(data, strings) == (data, []), name
            texts += len(strings)
        assert texts > 9000
