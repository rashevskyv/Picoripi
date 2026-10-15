"""The European disc as reference languages: file mapping, message pairing, the BMG-only unpack, the worker that runs
it, and (with ``PICORIPI_ROMHACKING``) the owner's real ``reference_eu`` folder. Synthetic files only, except the last."""
import json
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

import romhacking_root
from core.containers import yaz0
from core.reference_manager import ReferenceUnpackWorker
from gc_disc import build_disc
from plugins.base_game_rules import BaseGameRules
from plugins.super_mario_sunshine import reference
from plugins.super_mario_sunshine.rules import GameRules
from rarc_fixture import build_rarc
from ui.main_window.main_window_event_handler import MainWindowEventHandler

LABELS = [label for _lang, label in reference.LANGUAGES]


def bmg(texts, names=False) -> bytes:
    """A BMG of ``texts`` (cp1252). ``names`` adds the European layout: 12-byte INF1 entries and an STR1 section."""
    entry_len = 12 if names else 8
    dat, entries = bytearray(b"\0"), bytearray()
    for text in texts:
        entries += struct.pack(">I", len(dat)) + bytes(entry_len - 4)
        dat += text.encode("cp1252") + b"\0"
    sections = [(b"INF1", struct.pack(">HHI", len(texts), entry_len, 0) + entries), (b"DAT1", bytes(dat))]
    if names:
        sections.append((b"STR1", b"\0" + b"".join(b"m%d\0" % i for i in range(len(texts)))))
    head = bytearray(0x20)
    head[:8] = b"MESGbmg1"
    struct.pack_into(">I", head, 0x0C, len(sections))
    out = bytearray(head)
    for magic, body in sections:
        section = bytearray(magic + bytes(4) + body)
        section += bytes(-len(section) % 32)
        struct.pack_into(">I", section, 4, len(section))
        out += section
    return bytes(out)


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _rules(us_root: Path, sources) -> GameRules:
    blocks = [SimpleNamespace(source_file=rel) for rel in sources]
    manager = SimpleNamespace(project=SimpleNamespace(blocks=blocks), project_dir=None,
                              get_absolute_path=lambda rel: str(us_root / rel))
    return GameRules(SimpleNamespace(project_manager=manager, block_to_project_file_map={}))


@pytest.mark.parametrize("rel,lang,expected", [
    ("files/data/scene/bianco0.szs/map/message.bmg", "fr", "files/data/scene/bianco0.szs/map/message_fr.bmg"),
    ("files/data/option.szs/loadmessage.bmg", "ge", "files/data/option.szs/loadmessage_ge.bmg"),
    ("files/data/scene/test11.szs/map/bianco_0.bmg", "sp", "files/data/scene/test11.szs/map/_sp/bianco_0.bmg"),
    ("files/data/subtitle.szs/bath.bmg", "it", "files/data/subtitle_it.szs/bath.bmg"),
    ("files/data/common.szs/2d/balloon.bmg", "en", "files/data/cmn2d_en.szs/balloon.bmg"),
])
def test_each_us_file_names_its_european_copy(rel, lang, expected):
    assert expected in reference.european_paths(rel, lang)


def test_a_file_outside_an_archive_has_no_european_copy():
    assert reference.european_paths("sys/main_strings.dolstr", "en") == []


def test_an_inserted_message_is_paired_by_the_english_text():
    us = ["Corrupt", "Erase?", "New", "Saving...", "Done"]
    english = ["Corrupt", "Erase?", "New", "Select option", "Saving...", "Done"]
    assert reference.pairing(us, english) == {0: 0, 1: 1, 2: 2, 3: 4, 4: 5}
    assert reference.pairing(["a", "b"], ["x", "y"]) == {0: 0, 1: 1}   # same count: by number


def test_the_five_languages_sit_beside_each_us_message(tmp_path):
    us_root, root = tmp_path / "unpacked", tmp_path / reference.FOLDER
    sources = ["files/data/scene/bianco0.szs/map/message.bmg", "files/data/common.szs/2d/balloon.bmg",
               "files/data/option.szs/loadmessage.bmg", "files/data/title.szs/marisun_stage.bmg"]
    _write(us_root / sources[0], bmg(["Huh?", "Bye"]))
    _write(us_root / sources[1], bmg(["Yes"]))
    _write(us_root / sources[2], bmg(["Corrupt", "New", "Done"]))
    _write(us_root / sources[3], bmg(["Delfino Plaza"]))
    for lang, label in reference.LANGUAGES:
        _write(root / f"files/data/scene/bianco0.szs/map/message_{lang}.bmg",
               bmg([f"{label} 0 é", f"{label} 1"], names=True))
        _write(root / f"files/data/cmn2d_{lang}.szs/balloon.bmg", bmg([f"{label} yes"], names=True))
        loads = ["Corrupt", "New", "Select", "Done"] if lang == "en" else [f"{label} {i}" for i in range(4)]
        _write(root / f"files/data/option.szs/loadmessage_{lang}.bmg", bmg(loads, names=True))

    found = _rules(us_root, sources).load_multi_reference(str(root), {"0": "a", "1": "b", "2": "c", "3": "d"})

    assert list(found) == LABELS
    french = found["French (FR)"]
    assert french[(0, 0)] == "French (FR) 0 é"          # é stays é: the Ukrainian letter map is not applied
    assert french[(0, 1)] == "French (FR) 1"
    assert french[(1, 0)] == "French (FR) yes"
    assert [french[(2, i)] for i in range(3)] == ["French (FR) 0", "French (FR) 1", "French (FR) 3"]
    assert found["English (EU)"][(2, 2)] == "Done"
    assert all((3, 0) not in texts for texts in found.values())   # no European copy: no reference
    assert len(found["German (DE)"]) == 6


def test_a_disc_image_path_gives_no_languages_until_it_is_unpacked(tmp_path):
    image = _write(tmp_path / "eu.iso", b"not a folder")
    assert _rules(tmp_path, []).load_multi_reference(str(image), {}) == {}


def _european_disc(tmp_path: Path, game_id=b"GMSP01") -> Path:
    return _write(tmp_path / "eu.iso", build_disc({
        "data/cmn2d_fr.szs": yaz0.compress(build_rarc({"balloon.bmg": bmg(["Oui"], names=True)})),
        "data/mario.szs": build_rarc({"mario.bmd": b"model"}),
        "data/plain.bin": b"no archive"}, game_id=game_id))


def test_the_unpack_writes_only_the_message_files_and_replaces_an_older_folder(tmp_path):
    project = tmp_path / "project"
    _write(project / reference.FOLDER / "stale.bmg", b"old")
    image = _european_disc(tmp_path)

    folder = GameRules().unpack_reference(str(image), str(project), lambda _p, _t: None, lambda: False)

    assert folder == str(project / reference.FOLDER)
    written = sorted(p.relative_to(folder).as_posix() for p in Path(folder).rglob("*") if p.is_file())
    assert written == ["files/data/cmn2d_fr.szs/balloon.bmg"]
    assert sorted(p.name for p in project.iterdir()) == [reference.FOLDER]   # no temporary folder left


def test_a_cancelled_unpack_keeps_the_older_folder_and_leaves_no_partial_one(tmp_path):
    project = tmp_path / "project"
    _write(project / reference.FOLDER / "kept.bmg", b"old")
    assert reference.unpack(_european_disc(tmp_path), project, lambda _p, _t: None, lambda: True) is None
    assert sorted(p.name for p in project.iterdir()) == [reference.FOLDER]
    assert (project / reference.FOLDER / "kept.bmg").read_bytes() == b"old"


def test_another_disc_is_not_unpacked(tmp_path):
    us_disc = _european_disc(tmp_path, game_id=b"GMSE01")
    assert GameRules().unpack_reference(str(us_disc), str(tmp_path), lambda _p, _t: None, lambda: False) is None
    with pytest.raises(ValueError):
        reference.unpack(us_disc, tmp_path, lambda _p, _t: None, lambda: False)
    assert BaseGameRules().unpack_reference(str(us_disc), str(tmp_path), lambda _p, _t: None, lambda: False) is None


class _UnpackingRules:
    """Unpacks any picked file into ``<project>/ref`` and reads every folder as one language."""

    def __init__(self, fail=False):
        self.fail, self.loaded = fail, []

    def unpack_reference(self, path, project_dir, progress, is_cancelled):
        if self.fail:
            raise ValueError("broken image")
        folder = Path(project_dir) / "ref"
        folder.mkdir(exist_ok=True)
        return str(folder)

    def supports_reference_patch(self):
        return True

    def load_multi_reference(self, patch_path, block_names=None):
        self.loaded.append(patch_path)
        return {"French (FR)": {(0, 0): "Oui"}}


def _window(project_dir: Path, rules) -> SimpleNamespace:
    toasts = []
    return SimpleNamespace(project_manager=SimpleNamespace(project_dir=str(project_dir)), current_game_rules=rules,
                           data_store=SimpleNamespace(block_names={}, reference_languages_data={}, reference_data={}),
                           reference_patch_path="", show_toast=toasts.append, toasts=toasts)


def test_a_picked_image_is_unpacked_on_a_worker_and_its_folder_becomes_the_reference(qtbot, tmp_path):
    rules = _UnpackingRules()
    window = _window(tmp_path, rules)
    handler = MainWindowEventHandler(window)

    handler._apply_reference_path(str(_write(tmp_path / "eu.rvz", b"disc")))

    assert window.reference_patch_path == ""            # nothing is read on the UI thread
    qtbot.waitUntil(lambda: window.reference_patch_path == str(tmp_path / "ref"), timeout=5000)
    assert rules.loaded == [str(tmp_path / "ref")]
    assert window.data_store.reference_languages_data == {"French (FR)": {(0, 0): "Oui"}}
    settings = json.loads((tmp_path / "project_settings.json").read_text(encoding="utf-8"))
    assert settings["reference_patch_path"] == str(tmp_path / "ref")


def test_a_failed_unpack_keeps_the_old_reference_and_says_why(qtbot, tmp_path):
    rules = _UnpackingRules(fail=True)
    window = _window(tmp_path, rules)
    window.reference_patch_path = "old"
    handler = MainWindowEventHandler(window)

    handler._apply_reference_path(str(_write(tmp_path / "eu.rvz", b"disc")))

    qtbot.waitUntil(lambda: any("broken image" in toast for toast in window.toasts), timeout=5000)
    assert window.reference_patch_path == "old" and rules.loaded == []


def test_the_worker_emits_nothing_after_a_cancel(qtbot, tmp_path):
    worker = ReferenceUnpackWorker(_UnpackingRules(), str(tmp_path / "eu.rvz"), str(tmp_path))
    emitted = []
    worker.finished_signal.connect(lambda folder, error: emitted.append((folder, error)))
    worker.cancel()
    with qtbot.waitSignal(worker.finished, timeout=5000):
        worker.start()
    assert emitted == []


PROJECT = ("Super Mario", "Super Mario Sunshine", "GameCube", "picoripi")


@romhacking_root.needs(PROJECT + (reference.FOLDER,), PROJECT + ("unpacked", "files", "data", "scene"))
def test_real_bianco_hills_message_has_the_five_european_languages():
    base = romhacking_root.path(*PROJECT)
    rel = "files/data/scene/bianco0.szs/map/message.bmg"
    found = _rules(base / "unpacked", [rel]).load_multi_reference(str(base / reference.FOLDER), {"0": "message"})
    assert list(found) == LABELS
    assert found["English (EU)"][(0, 0)].startswith("Huh? You're back")
    assert found["French (FR)"][(0, 0)].startswith("Hein ? Tu es de")
    assert all(found[label][(0, 13)] for label in LABELS)
