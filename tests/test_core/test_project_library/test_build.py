"""Unpack, build, export, emulator command, project flags and the registry setting of the Project Manager."""
import json
import os
import struct
from pathlib import Path

import pytest

from core.project_library import build, flags, registry
from plugins.base_game_rules import BaseGameRules
from plugins.castlevania_gba.rules import GameRules as GbaRules
from plugins.plain_text.rules import GameRules as PlainTextRules


def _no_cancel():
    return False


class BuildingRules(BaseGameRules):
    """Writes one file per call into the folder it is given; unpacks only when asked to."""

    def __init__(self, unpack_result="source", fail=False):
        super().__init__()
        self.unpack_result = unpack_result
        self.fail = fail

    def unpack_sources(self, sources, target_dir, progress, is_cancelled):
        if self.unpack_result is None:
            return None
        with open(os.path.join(target_dir, "game.bin"), "w", encoding="utf-8") as handle:
            handle.write(",".join(sorted(sources)))
        progress(100, "done")
        return target_dir

    def build_target(self, target_id, source_dir, translation_dir, output_dir, progress, is_cancelled):
        if self.fail:
            raise OSError("disk full")
        if target_id != "patch":
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        result = os.path.join(output_dir, "patch.ips")
        with open(result, "w", encoding="utf-8") as handle:
            handle.write("patched")
        return result


def test_unpack_moves_the_folder_into_place(tmp_path):
    result = build.run_unpack(BuildingRules(), {"base": "x"}, tmp_path, lambda p, t: None, _no_cancel)

    assert result == str(tmp_path / "unpacked")
    assert (tmp_path / "unpacked" / "game.bin").read_text(encoding="utf-8") == "base"
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".unpack-")]


def test_unpack_without_a_recipe_leaves_no_folder(tmp_path):
    result = build.run_unpack(BuildingRules(unpack_result=None), {}, tmp_path, lambda p, t: None, _no_cancel)

    assert result is None
    assert list(tmp_path.iterdir()) == []


def test_cancelled_unpack_removes_only_its_temporary_folder(tmp_path):
    (tmp_path / "keep.txt").write_text("user file", encoding="utf-8")
    with pytest.raises(build.Cancel):
        build.run_unpack(BuildingRules(), {"base": "x"}, tmp_path, lambda p, t: None, lambda: True)

    assert sorted(p.name for p in tmp_path.iterdir()) == ["keep.txt"]


def test_build_replaces_an_earlier_result_and_returns_its_path(tmp_path):
    rules = BuildingRules()
    build_dir = tmp_path / "build" / "patch"
    build_dir.mkdir(parents=True)
    (build_dir / "old.ips").write_text("old", encoding="utf-8")

    result = build.run_build(rules, "patch", tmp_path, "src", "tr", lambda p, t: None, _no_cancel)

    assert result == str(build_dir / "patch.ips")
    assert (build_dir / "patch.ips").read_text(encoding="utf-8") == "patched"
    assert not (build_dir / "old.ips").exists()
    assert [p.name for p in (tmp_path / "build").iterdir()] == ["patch"]


def test_failed_build_keeps_the_earlier_result(tmp_path):
    build_dir = tmp_path / "build" / "patch"
    build_dir.mkdir(parents=True)
    (build_dir / "old.ips").write_text("old", encoding="utf-8")

    with pytest.raises(OSError):
        build.run_build(BuildingRules(fail=True), "patch", tmp_path, "src", "tr", lambda p, t: None, _no_cancel)

    assert (build_dir / "old.ips").read_text(encoding="utf-8") == "old"
    assert [p.name for p in (tmp_path / "build").iterdir()] == ["patch"]


def test_export_copies_into_an_empty_folder_and_refuses_a_used_one(tmp_path):
    source = tmp_path / "build"
    (source / "sub").mkdir(parents=True)
    (source / "sub" / "a.txt").write_text("a", encoding="utf-8")
    destination = tmp_path / "out"

    result = build.export_build(source, destination, lambda p, t: None, _no_cancel)

    assert result == str(destination)
    assert (destination / "sub" / "a.txt").read_text(encoding="utf-8") == "a"
    other = tmp_path / "used"
    other.mkdir()
    (other / "x").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        build.export_build(source, other, lambda p, t: None, _no_cancel)


def test_plain_text_target_copies_translation_files_keeping_folders(tmp_path):
    translation = tmp_path / "tr"
    (translation / "menu").mkdir(parents=True)
    (translation / "menu" / "a.txt").write_text("hello", encoding="utf-8")
    output = tmp_path / "out"
    output.mkdir()

    result = PlainTextRules().build_target("translated_files", "", str(translation), str(output),
                                           lambda p, t: None, _no_cancel)

    assert result == str(output)
    assert (output / "menu" / "a.txt").read_text(encoding="utf-8") == "hello"


def test_emulator_template_keeps_a_spaced_path_as_one_argument():
    template = '"C:\\Emu Dir\\emu.exe" --load {path} --title x'

    assert build.emulator_argv(template, "Z:\\my mods\\build", posix=False) == [
        "C:\\Emu Dir\\emu.exe", "--load", "Z:\\my mods\\build", "--title", "x"]
    assert build.emulator_argv("/Applications/Emu.app/Contents/MacOS/emu {path}", "/tmp/a b",
                               posix=True) == ["/Applications/Emu.app/Contents/MacOS/emu", "/tmp/a b"]


def test_emulator_template_without_placeholder_appends_the_path_and_empty_is_nothing():
    assert build.emulator_argv("emu", "/x", posix=True) == ["emu", "/x"]
    assert build.emulator_argv("   ", "/x", posix=True) == []


def test_build_result_runs_on_the_targets_only_platform_else_the_projects():
    assert build.emulator_platform(["switch"], "3ds") == "switch"
    assert build.emulator_platform(["switch", "3ds"], "3ds") == "3ds"
    assert build.emulator_platform([], "3ds") == "3ds"
    assert build.emulator_platform([], "") == ""


def test_each_platform_uses_its_own_emulator_command_and_the_shared_one_is_the_fallback():
    settings = {"emulator_command": "shared {path}", "emulator_command.3ds": "emu3 {path}",
                "emulator_command.switch": ""}

    assert build.emulator_template_for(settings, "3ds") == "emu3 {path}"
    # an empty platform setting means "no command", even when a shared command exists
    assert build.emulator_template_for(settings, "switch") == ""
    # a platform with no setting of its own uses the shared command
    assert build.emulator_template_for(settings, "wii") == "shared {path}"
    assert build.emulator_template_for({}, "wii") == ""


def test_flags_are_stored_in_metadata_and_other_data_stays(tmp_path):
    project_file = tmp_path / "project.uiproj"
    project_file.write_text(json.dumps({"name": "Aria", "metadata": {"source_path": "src"}}), encoding="utf-8")

    stored = flags.set_flags(project_file, {"built": True})
    flags.set_flags(project_file, {"verified_in_game": True})

    document = json.loads(project_file.read_text(encoding="utf-8"))
    assert stored == {"built": True}
    assert document["metadata"] == {"source_path": "src",
                                    "flags": {"built": True, "verified_in_game": True}}
    assert flags.flags_of(document["metadata"]) == {"built": True, "verified_in_game": True}


def test_unknown_flag_is_refused(tmp_path):
    project_file = tmp_path / "project.uiproj"
    project_file.write_text(json.dumps({"metadata": {}}), encoding="utf-8")

    with pytest.raises(ValueError):
        flags.set_flags(project_file, {"shipped": True})


def test_registry_keeps_only_known_settings(tmp_path):
    def operation(reg):
        assert reg.set_setting("emulator_command", "emu {path}")
        assert not reg.set_setting("openai_key", "secret")

    registry.mutate(tmp_path, operation)

    reloaded = registry.Registry(registry.read(tmp_path))
    assert reloaded.settings() == {"emulator_command": "emu {path}"}
    assert "openai_key" not in json.dumps(registry.read(tmp_path))


def test_registry_keeps_one_emulator_command_per_platform(tmp_path):
    def operation(reg):
        assert reg.set_setting(registry.emulator_setting("switch"), "emus {path}")
        assert reg.set_setting(registry.emulator_setting("3ds"), "emu3 {path}")
        assert not reg.set_setting("emulator_command.bad platform!", "x")
        assert not reg.set_setting("emulator_command.", "x")

    registry.mutate(tmp_path, operation)

    reloaded = registry.Registry(registry.read(tmp_path))
    assert reloaded.settings() == {"emulator_command": "", "emulator_command.3ds": "emu3 {path}",
                                   "emulator_command.switch": "emus {path}"}


class TreeRules(BuildingRules):
    """Writes a disc-like tree: a boot file and the Msgus archives under files/res/Msgus."""

    def unpack_sources(self, sources, target_dir, progress, is_cancelled):
        folder = os.path.join(target_dir, "files", "res", "Msgus")
        os.makedirs(folder)
        with open(os.path.join(folder, "bmgres.arc"), "w", encoding="utf-8") as handle:
            handle.write("arc")
        with open(os.path.join(target_dir, "boot.bin"), "w", encoding="utf-8") as handle:
            handle.write("boot")
        return target_dir

    def get_source_subfolder(self):
        return "files/res/Msgus"


def test_source_subfolder_becomes_the_project_source(tmp_path):
    result = build.run_unpack(TreeRules(), {"base": "x"}, tmp_path, lambda p, t: None, _no_cancel)

    assert result == str(tmp_path / "unpacked" / "files" / "res" / "Msgus")
    assert (Path(result) / "bmgres.arc").read_text(encoding="utf-8") == "arc"
    assert (tmp_path / "unpacked" / "boot.bin").exists()


def test_missing_source_subfolder_fails_and_leaves_no_folder(tmp_path):
    class WrongSubfolder(TreeRules):
        def get_source_subfolder(self):
            return "files/res/Msguk"

    with pytest.raises(ValueError):
        build.run_unpack(WrongSubfolder(), {"base": "x"}, tmp_path, lambda p, t: None, _no_cancel)

    assert list(tmp_path.iterdir()) == []


def _gamecube_image(path: Path) -> Path:
    """A file the image reader recognises as a GameCube disc. It holds only the header, nothing else."""
    head = bytearray(0x440)
    head[0:6] = b"GZ2E01"
    struct.pack_into(">I", head, 0x1C, 0xC2339F3D)
    path.write_bytes(bytes(head))
    return path


def test_game_image_fails_before_writing_when_the_drive_is_too_small(tmp_path, monkeypatch):
    image = _gamecube_image(tmp_path / "disc.iso")
    monkeypatch.setattr(build, "_free_bytes", lambda path: 100 * build.MB)

    with pytest.raises(ValueError, match="Not enough free space"):
        build.run_unpack(BuildingRules(), {"base": str(image)}, tmp_path / "project", lambda p, t: None, _no_cancel)

    assert not (tmp_path / "project").exists()


def test_switch_and_wii_images_count_toward_the_room_check(tmp_path, monkeypatch):
    """Switch and Wii images are unpack inputs, so the room check counts them like GameCube (DECISIONS D30)."""
    disc = tmp_path / "wii.iso"
    head = bytearray(0x20)
    head[0:6] = b"RMCE01"
    struct.pack_into(">I", head, 0x18, 0x5D1C9EA3)   # the Wii disc magic
    disc.write_bytes(bytes(head))
    name = b"game.nca\0"
    body = b"n" * 64
    nsp = tmp_path / "game.nsp"                       # a PFS0 with one entry: recognised as a Switch package
    nsp.write_bytes(b"PFS0" + struct.pack("<III", 1, len(name), 0) + struct.pack("<QQII", 0, len(body), 0, 0)
                    + name + body)
    monkeypatch.setattr(build, "_free_bytes", lambda path: 0)

    for image in (disc, nsp):
        with pytest.raises(ValueError, match="Not enough free space"):
            build._check_free_space(tmp_path / "project", {"base": str(image)})


def test_game_image_passes_when_the_room_covers_the_image_and_its_margin(tmp_path, monkeypatch):
    image = _gamecube_image(tmp_path / "disc.iso")
    needed = image.stat().st_size + build.MIN_MARGIN
    monkeypatch.setattr(build, "_free_bytes", lambda path: needed)

    result = build.run_unpack(BuildingRules(), {"base": str(image)}, tmp_path / "project", lambda p, t: None,
                              _no_cancel)

    assert result == str(tmp_path / "project" / "unpacked")


def test_plain_file_is_not_checked_for_room(tmp_path, monkeypatch):
    rom = tmp_path / "game.gba"
    rom.write_bytes(b"\0" * 0x100)
    monkeypatch.setattr(build, "_free_bytes", lambda path: 0)

    assert build.run_unpack(GbaRules(), {"base": str(rom)}, tmp_path / "project", lambda p, t: None,
                            _no_cancel) is None


def test_gba_rom_is_used_as_it_is_when_the_plugin_unpacks_nothing(tmp_path):
    rom = tmp_path / "game.gba"
    data = bytes(range(256))
    rom.write_bytes(data)
    project = tmp_path / "project"

    result = build.run_unpack(GbaRules(), {"base": str(rom)}, project, lambda p, t: None, _no_cancel)

    assert result is None
    assert rom.read_bytes() == data
    assert list(project.iterdir()) == []
