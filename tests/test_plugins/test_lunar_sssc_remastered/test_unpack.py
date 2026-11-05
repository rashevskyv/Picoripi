"""Lunar SSS Remastered unpack: the PC game folder is recognised by its files (synthetic folders, no game data)."""
from plugins.lunar_sssc_remastered import unpack


def test_pc_folder_with_data_cpk_and_exe_is_pc_base(tmp_path):
    (tmp_path / "data.cpk").write_bytes(b"CPK ")
    (tmp_path / "lunar1.exe").write_bytes(b"MZ")
    assert unpack.identify(str(tmp_path)) == {"role": "base", "platform": "pc", "libraries": []}


def test_folder_without_the_game_files_is_not_recognised(tmp_path):
    (tmp_path / "data.cpk").write_bytes(b"CPK ")
    assert unpack.identify(str(tmp_path)) is None
