"""Reference languages come from actual loose or archived rows, matched by entry identity."""
import struct
from types import SimpleNamespace

import pytest
import romhacking_root

from core.containers.level5 import compress, STORED
from core.reference_manager import ReferenceManager
from core.settings.plugin_settings import PluginSettings
from plugins.yokai_watch.arc0 import Arc0
from plugins.yokai_watch.rules import GameRules
from .samples import cfg_file, text_info


def _arc0(members):
    names = bytearray(b"\0")
    entries, payload = bytearray(), bytearray()
    for name, raw in members.items():
        struct_entry = struct.pack("<4I", 0, len(names), len(payload), len(raw))
        entries.extend(struct_entry)
        names.extend(name.encode("shift-jis") + b"\0")
        payload.extend(raw)
    dirs = struct.pack("<IHhHhii", 0, 0, 0, 0, len(members), 0, 0)
    tables = [compress(data, STORED) for data in (dirs, b"", bytes(entries), bytes(names))]
    offsets, cursor = [], 0x48
    for table in tables:
        offsets.append(cursor)
        cursor += len(table)
    head = bytearray(0x48)
    head[:4] = b"ARC0"
    struct.pack_into("<5I", head, 4, *offsets, cursor)
    struct.pack_into("<HHi", head, 0x18, 1, 0, len(members))
    return bytes(head) + b"".join(tables) + payload


def _write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _rules(root, relatives):
    source = root / "source"
    project = SimpleNamespace(metadata={"source_path": str(source)},
                              blocks=[SimpleNamespace(source_file=rel) for rel in relatives])
    manager = SimpleNamespace(project=project, get_absolute_path=lambda rel: str(source / rel))
    window = SimpleNamespace(project_manager=manager, block_to_project_file_map={})
    return GameRules(window), window


def test_archive_languages_align_ids_and_skip_blank_rows(tmp_path):
    rel = "data/res/text/menu_text_en.cfg.bin"
    _write(tmp_path / "source" / rel, cfg_file([text_info(4, 0, "First"), text_info(5, 0, "Second")]))
    members = {
        rel.replace("_en.", "_de."): cfg_file([text_info(5, 0, "Zwei"), text_info(4, 0, " ")]),
        rel.replace("_en.", "_fr."): cfg_file([text_info(4, 0, "Un"), text_info(99, 0, "Unrelated")]),
        rel.replace("_en.", "_ru."): cfg_file([text_info(4, 0, "  ")]),
    }
    _write(tmp_path / "romfs/yw1_a.fa", _arc0(members))
    rules, _window = _rules(tmp_path, [rel])
    worker_rules, worker_window = rules.reference_worker_rules()
    assert worker_rules.mw is None and worker_window is None
    assert worker_rules.load_multi_reference(str(tmp_path / "source"), {"0": "menu"}) == {
        "German (DE)": {(0, 1): "Zwei"}, "French (FR)": {(0, 0): "Un"}}


def test_private_snapshot_does_not_follow_a_later_project(tmp_path):
    rel = "data/res/text/menu_text_en.cfg.bin"
    _write(tmp_path / "source" / rel, cfg_file([text_info(4, 0, "First")]))
    _write(tmp_path / "reference" / rel.replace("_en.", "_ru."), cfg_file([text_info(4, 0, "Reference")]))
    rules, window = _rules(tmp_path, [rel])
    copy, _window = rules.reference_worker_rules()
    window.project_manager.project.blocks.clear()
    assert copy.load_multi_reference(str(tmp_path / "source"), {"0": "menu"}) == {
        "Russian (RU)": {(0, 0): "Reference"}}


def test_automatic_reference_load_uses_worker_without_persisting_a_path(qtbot, tmp_path):
    rel = "data/res/text/menu_text_en.cfg.bin"
    _write(tmp_path / "source" / rel, cfg_file([text_info(4, 0, "First")]))
    _write(tmp_path / "source" / rel.replace("_en.", "_it."), cfg_file([text_info(4, 0, "Uno")]))
    rules, window = _rules(tmp_path, [rel])
    window.current_game_rules = rules
    window.reference_patch_path = None
    window.data_store = SimpleNamespace(block_names={"0": "menu"}, reference_languages_data={})
    settings = PluginSettings(window)
    settings.load_reference()
    qtbot.waitUntil(lambda: bool(window.data_store.reference_languages_data), timeout=5000)
    assert window.data_store.reference_languages_data == {"Italian (IT)": {(0, 0): "Uno"}}
    assert window.reference_patch_path is None
    assert ReferenceManager.has_worker_rules(rules)


@pytest.mark.parametrize("member", ["../unsafe.cfg.bin", "/absolute.cfg.bin", "C:/unsafe.cfg.bin"])
def test_archive_rejects_unsafe_member_paths(tmp_path, member):
    path = tmp_path / "bad.fa"
    path.write_bytes(_arc0({member: b"table"}))
    with pytest.raises(ValueError, match="Invalid ARC0 member path"):
        Arc0(path)


def test_archive_rejects_out_of_bounds_payload(tmp_path):
    raw = bytearray(_arc0({"table.cfg.bin": b"table"}))
    files = struct.unpack_from("<I", raw, 0x0C)[0]
    struct.pack_into("<I", raw, files + 4 + 8, 0xFFFFFFFF)
    path = tmp_path / "bad.fa"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="Invalid ARC0 member range"):
        Arc0(path)


REAL = ("Yo-kai Watch", "Yo-kai Watch", "3DS")


@romhacking_root.needs((*REAL, "romfs", "yw1_a.fa"))
def test_real_3ds_archive_exposes_six_nonempty_languages():
    root = romhacking_root.path(*REAL)
    rel = "data/res/map/t103i25/t103i25_npc_text_en.cfg.bin"
    rules, _window = _rules(root, [rel])
    worker, _window = rules.reference_worker_rules()
    languages = worker.load_multi_reference(str(root / "source"), {"0": "npc"})
    assert set(languages) == {"English (GB)", "German (DE)", "Spanish (ES)", "French (FR)",
                              "Italian (IT)", "Korean (KO)"}
    assert all(set(rows) == {(0, 0), (0, 1)} for rows in languages.values())
    assert all(text.strip() for rows in languages.values() for text in rows.values())
