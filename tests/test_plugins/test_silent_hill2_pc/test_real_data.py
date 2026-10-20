"""Silent Hill 2 (PC and Switch data): the message codec on the real files, byte-exact.

The tests read the installed English PC data and the Switch workspace translation folder. They skip when the
files are missing.
"""
import romhacking_root

import pytest

from plugins.silent_hill2_pc import mes, mes_legacy

EN_MESSAGES = romhacking_root.under("Silent Hill\\Silent Hill 2\\PC\\ISO\\data\\etc\\message")
UA_MESSAGES = romhacking_root.under("Silent Hill\\Silent Hill 2\\Switch\\translation\\data\\etc\\message")
needs_en = pytest.mark.skipif(not EN_MESSAGES.is_dir(), reason="Silent Hill 2 PC data not installed here")
needs_ua = pytest.mark.skipif(not UA_MESSAGES.is_dir(), reason="Silent Hill 2 Switch translation not here")


def _check_folder(folder):
    files = sorted(folder.glob("*_e.mes"))
    assert files, "no English message files found"
    for path in files:
        raw = path.read_bytes()
        parts = mes.split(raw)
        assert mes.build(parts) == raw, path.name
        for part in parts:
            assert mes.encode(mes.decode(part)) == part, path.name


@needs_en
def test_english_message_files_round_trip_byte_exact():
    _check_folder(EN_MESSAGES)


@needs_ua
def test_ukrainian_message_files_round_trip_byte_exact():
    _check_folder(UA_MESSAGES)


def _check_legacy_migration(folder, encode, decode):
    for path in sorted(folder.glob("*.mes")):
        raw = path.read_bytes()
        old_rows = [decode(row) for row in mes_legacy.legacy_split(raw)]
        migrated, _notes = mes_legacy.migrate_rows(old_rows, encode)
        assert migrated == mes.split(raw), path.name
        assert mes.build(migrated) == raw, path.name


@needs_en
def test_legacy_rows_migrate_to_the_current_messages_english():
    _check_legacy_migration(EN_MESSAGES, mes_legacy.legacy_encode, mes_legacy.legacy_decode)


@needs_ua
def test_legacy_rows_migrate_to_the_current_messages_ukrainian():
    _check_legacy_migration(UA_MESSAGES, mes.encode_uk, mes.decode_uk)
