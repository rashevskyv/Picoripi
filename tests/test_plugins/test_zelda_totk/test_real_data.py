"""TotK 1.4.0 on the developer's disk (E:\\...\\TOTK_UA\\romfs, made by 1_unpack.bat); skipped elsewhere."""
from pathlib import Path

import pytest

from core import font_formats
from core.font_formats import bfotf
from plugins.zelda_totk import event_flow, font_glyphs, restbl, sarc
from plugins.common.msbt import Msbt, Tag
from plugins.zelda_totk.tags import from_editor, to_editor

ROMFS = Path(r"E:\Emulators\RomHacking\ZELDA\TOTK_UA\romfs")
pytestmark = pytest.mark.skipif(not (ROMFS / "Pack" / "ZsDic.pack.zs").is_file(), reason="no TotK romfs on disk")


@pytest.fixture(autouse=True)
def dictionaries(monkeypatch):
    pytest.importorskip("compression.zstd")
    monkeypatch.setattr(sarc, "dictionary_dirs", lambda: [ROMFS])


def _archive(name):
    return sarc.SarcContainer((ROMFS / name).read_bytes())


def test_every_english_message_round_trips_through_the_editor():
    container = _archive("Mals/USen.Product.140.sarc.zs")
    raw_tags, count = set(), 0
    for member in container.list_files():
        data = container.read_file(member)
        msbt = Msbt(data)
        messages = [from_editor(to_editor(tokens)) for tokens in msbt.messages]
        assert msbt.build(messages) == data, member
        count += len(messages)
        raw_tags |= {(t.group, t.type) for tokens in msbt.messages for t in tokens
                     if isinstance(t, Tag) and to_editor([t]).startswith("{tag:")}
    assert count == 47799
    assert raw_tags == {(1, 2)}          # the only tag whose meaning the data does not show


def test_an_unchanged_archive_is_written_back_as_the_same_bytes():
    raw = (ROMFS / "Mals" / "USen.Product.140.sarc.zs").read_bytes()
    plain = sarc.decompress(raw)[0]
    assert sarc.Sarc(plain).build() == plain
    assert sarc.SarcContainer(raw).pack() is raw or sarc.SarcContainer(raw).pack() == raw


def test_the_size_table_rule_matches_every_text_and_font_archive():
    table = restbl.Restbl(sarc.decompress(next((ROMFS / "System" / "Resource").glob("*.rsizetable.zs")).read_bytes())[0])
    for path in sorted((ROMFS / "Mals").glob("*.sarc.zs")) + sorted((ROMFS / "Font").glob("*.bfarc.zs")):
        key = f"{path.parent.name}/{path.name[:-3]}"
        kind = ".bfarc" if path.name.endswith(".bfarc.zs") else ".sarc"
        assert table.size(key) == restbl.required_size(len(sarc.decompress(path.read_bytes())[0]), kind), key


def test_every_font_opens_and_packs_back_byte_exact():
    container = _archive("Font/Font.Nin_NX_NVN.bfarc.zs")
    fonts = [name for name in container.list_files() if name.endswith(".bfotf")]
    assert len(fonts) == 10
    for name in fonts:
        data = container.read_file(name)
        assert font_formats.detect(data) == "bfotf"
        metadata, sheets = font_formats.extract("bfotf", data, {"size": 24})
        assert font_formats.char_map(metadata), name
        assert font_formats.pack("bfotf", metadata, sheets, data, {"size": 24}) == data


def test_the_ukrainian_letters_are_added_once_and_render():
    container = _archive("Font/Font.Nin_NX_NVN.bfarc.zs")
    plain, _key = bfotf.decrypt(container.read_file("scft/nintendo_NTLG-DB_DH_002.bfotf"))
    patched, added = font_glyphs.add_ukrainian(plain)
    assert added == ["Ґ", "ґ"]
    assert font_glyphs.add_ukrainian(patched)[1] == []
    font = bfotf.OpenType(patched)
    assert {ord("Ґ"), ord("ґ")} <= set(font.cmap())
    width, contours = font_glyphs.outline(font_glyphs.Cff(patched[font.table("CFF "):]), font.cmap()[ord("Ґ")])
    assert width > 0 and len(contours) >= 2      # Г plus the upturn


def test_talks_and_cutscene_voices_name_their_speakers():
    def talks(name):
        data = sarc.decompress((ROMFS / "Event" / "EventFlow" / f"{name}.bfevfl.zs").read_bytes())[0]
        return [talk for chart in event_flow.flowcharts(data) for talk in chart["talks"]]

    assert ("Npc_EventStarter", "EventTalk", "EventFlowMsg/Npc_Goron018:Talk_00") in talks("Npc_Goron018")
    assert ("Npc_Zelda_Opening", "EventStartVoice", "EventFlowMsg/DmT_OP_GanonWakeUp:DmT_OP_GanonWakeUp_Text_000_b") \
        in talks("DmT_OP_GanonWakeUp_PreRender")
