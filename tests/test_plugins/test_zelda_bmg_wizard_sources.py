"""Twilight Princess in the Project Manager wizard: the GameCube and Wii discs and the Wii U HD title folder.

Synthetic headers and folders only. The real-file checks are in test_zelda_bmg_unpack_real.py.
"""
import struct
from pathlib import Path

import pytest

from core.project_library import build, plugin_facts
from core.project_library.source_folder import validate_source_folder
from plugins.super_mario_sunshine.rules import GameRules as SunshineRules
from plugins.zelda_bmg.bmg_tool import BMGFile, BMGMessage
from rarc_fixture import build_rarc
from plugins.zelda_bmg.rules import GameRules
from plugins.zelda_tww.rules import GameRules as WindWakerRules

HD_META = b'<menu><product_code type="string" length="32">WUP-P-AZAE</product_code></menu>'


def _disc_header(path, game_id, wii):
    """A file the image reader recognises as a disc of ``game_id``: only its header."""
    head = bytearray(0x440)
    head[0:6] = game_id
    struct.pack_into(">I", head, 0x18 if wii else 0x1C, 0x5D1C9EA3 if wii else 0xC2339F3D)
    path.write_bytes(bytes(head))
    return str(path)


def _bmgres():
    """A message archive like the game's: one BMG with one message inside a RARC."""
    bmg = BMGFile()
    bmg.endianness, bmg.encoding, bmg.id = ">", "cp1252", 0
    message = BMGMessage(info=bytes(4), parts=["Hello"])
    message.id = 1
    bmg.messages = [message]
    return build_rarc({"zel_00.bmg": bmg.save()})


def _hd_title(root, slots=("Msguk", "Msgus")):
    (root / "meta").mkdir(parents=True)
    (root / "meta" / "meta.xml").write_bytes(HD_META)
    (root / "code").mkdir()
    for slot in slots:
        (root / "content" / "res" / slot).mkdir(parents=True)
        (root / "content" / "res" / slot / "bmgres.arc").write_bytes(_bmgres())
    return root


@pytest.mark.parametrize("game_id, wii, platform", [(b"GZ2E01", False, "gc"), (b"RZDE01", True, "wii")])
def test_gamecube_and_wii_discs_are_the_base_game_of_their_platform(tmp_path, game_id, wii, platform):
    image = _disc_header(tmp_path / "tp.iso", game_id, wii)

    assert GameRules().identify_source(image) == {"role": "base", "platform": platform}
    assert platform in {item["id"] for item in GameRules().get_platforms()}


def test_another_wii_game_is_not_twilight_princess(tmp_path):
    assert GameRules().identify_source(_disc_header(tmp_path / "x.iso", b"RMGE01", True)) is None


def test_the_wii_disc_asks_for_the_wii_key_and_the_gamecube_disc_for_none(tmp_path, monkeypatch):
    monkeypatch.setattr(plugin_facts.console_keys, "path_for", lambda console: None)
    wii = _disc_header(tmp_path / "wii.iso", b"RZDE01", True)
    gc = _disc_header(tmp_path / "gc.iso", b"GZ2E01", False)

    found = {item["path"]: item for item in plugin_facts.identify_sources(GameRules(), [wii, gc])}

    assert (found[wii]["key"], found[wii]["key_ready"]) == ("wii", False)
    assert found[gc]["key"] == ""


@pytest.mark.parametrize("rules", [WindWakerRules, SunshineRules])
def test_gamecube_only_subclasses_do_not_ask_for_the_wii_key(rules):
    assert rules().unpack_key_consoles() == []


def test_the_hd_title_folder_is_the_wii_u_base_game(tmp_path):
    folder = _hd_title(tmp_path / "TPHD")

    assert GameRules().identify_source(str(folder)) == {"role": "base", "platform": "wiiu"}


def test_a_folder_of_another_wii_u_game_is_not_twilight_princess(tmp_path):
    folder = _hd_title(tmp_path / "Other")
    (folder / "meta" / "meta.xml").write_bytes(HD_META.replace(b"AZAE", b"BEFE"))

    assert GameRules().identify_source(str(folder)) is None
    assert GameRules().identify_source(str(tmp_path / "missing")) is None


def test_the_added_hd_folder_resolves_to_its_msguk_message_folder(tmp_path):
    folder = _hd_title(tmp_path / "TPHD")

    assert validate_source_folder(GameRules(), folder, lambda: False) == str(folder / "content" / "res" / "Msguk")


def test_an_hd_folder_with_only_msgus_uses_that_slot(tmp_path):
    folder = _hd_title(tmp_path / "TPHD", slots=("Msgus",))

    assert validate_source_folder(GameRules(), folder, lambda: False) == str(folder / "content" / "res" / "Msgus")


def test_an_unpacked_disc_keeps_files_res_msgus_as_its_source(tmp_path):
    class Disc(GameRules):
        def unpack_sources(self, sources, target_dir, progress, is_cancelled):
            msgus = Path(target_dir, "files", "res", "Msgus")
            msgus.mkdir(parents=True)
            (msgus / "bmgres.arc").write_bytes(_bmgres())
            return target_dir

    result = build.run_unpack(Disc(), {"base": "x"}, tmp_path / "project", lambda *_: None, lambda: False)

    assert result == str(tmp_path / "project" / "unpacked" / "files" / "res" / "Msgus")


def test_an_archive_without_text_is_not_readable_game_text(tmp_path):
    (tmp_path / "files" / "res" / "Msgus").mkdir(parents=True)
    (tmp_path / "files" / "res" / "Msgus" / "bmgres.arc").write_bytes(b"not an archive")

    with pytest.raises(ValueError, match="No readable game text"):
        validate_source_folder(GameRules(), tmp_path, lambda: False)
