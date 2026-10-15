"""The owner's Super Mario Galaxy files under ``PICORIPI_ROMHACKING`` (read only); skipped elsewhere.

Checks the facts measured on 2026-10-15: the USA RVZ reads with no key and its main.dol is the one Nebula pins, its
English messages have 2463 labels and write back unchanged, the five Wii fonts save byte for byte, and the Switch
Ukrainian mod matches the Wii English by label.
"""
import hashlib

import pytest

import romhacking_root
from core.containers.rarc_container import RarcContainer
from core.containers.wia import open_disc
from core.containers.wii_disc import WiiImage
from core.font_formats import bcfnt
from core.project_library import images
from plugins.super_mario_galaxy import build, import_mod, messages, unpack

RVZ = ("Super Mario", "Super Mario Galaxy", "Wii", "source", "Super Mario Galaxy (USA) (En,Fr,Es).rvz")
UA_MOD = ("Super Mario", "Super Mario Galaxy", "Switch", "source", "Super Mario Galaxy ukr translate.zip")


@pytest.fixture(scope="module")
def wii_files():
    reason = romhacking_root.missing(*RVZ)
    if reason:
        pytest.skip(reason)
    wanted = ("sys/main.dol", "files/UsEnglish/MessageData/Message.arc", "files/LayoutData/Font.arc")
    with open_disc(romhacking_root.path(*RVZ)) as disc:
        reader = WiiImage(disc, None)
        return {entry.path: reader.read(entry) for entry in reader.entries() if entry.path in wanted}


def test_the_usa_rvz_is_identified_and_needs_no_key():
    reason = romhacking_root.missing(*RVZ)
    if reason:
        pytest.skip(reason)
    path = str(romhacking_root.path(*RVZ))
    assert unpack.identify(path) == {"role": "wii", "platform": "wii", "game": "smg1"}
    assert images.needs_key(path) is None


def test_main_dol_is_the_one_nebula_pins(wii_files):
    assert hashlib.sha1(wii_files["sys/main.dol"]).hexdigest() == build.NEBULA_MAIN_DOL_SHA1


def test_english_messages_have_their_labels_and_write_back_unchanged(wii_files):
    data = wii_files["files/UsEnglish/MessageData/Message.arc"]
    texts = messages.texts_by_label(data)
    assert len(texts) == 2463 and texts["GalaxyName_CosmosGardenGalaxy"] == "Gusty Garden Galaxy"
    out = RarcContainer(messages.apply_texts(data, texts))
    original = RarcContainer(data)
    assert all(out.read_file(name) == original.read_file(name) for name in original.list_files())


def test_the_five_wii_fonts_save_byte_for_byte(wii_files):
    archive = RarcContainer(wii_files["files/LayoutData/Font.arc"])
    names = sorted(archive.list_files())
    assert names == ["cinemafont26.brfnt", "menufont64.brfnt", "messagefont26.brfnt", "numberfont.brfnt",
                     "picturefont.brfnt"]
    for name in names:
        font = archive.read_file(name)
        metadata, sheets = bcfnt.extract(font, {})
        assert bcfnt.pack(metadata, sheets, font, {}) == font, name


def test_the_ukrainian_switch_mod_matches_the_wii_english_by_label(wii_files):
    reason = romhacking_root.missing(*UA_MOD)
    if reason:
        pytest.skip(reason)
    archives, font = import_mod.read_mod(str(romhacking_root.path(*UA_MOD)))
    ua = messages.texts_by_label(archives["Message"])
    wii = messages.texts_by_label(wii_files["files/UsEnglish/MessageData/Message.arc"])
    assert len(ua) == 2247 and len(set(ua) & set(wii)) == 1938 and font is not None
