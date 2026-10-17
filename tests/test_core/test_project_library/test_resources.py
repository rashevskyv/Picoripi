"""The resource kinds of a project's source folder: the extension table and the walk that counts them."""
import os

from core.project_library import resources


def test_kind_follows_the_extension_and_unknown_files_are_other():
    assert resources.kind_of("Menu.BMG") == resources.TEXT
    assert resources.kind_of("font.bfn") == resources.FONT
    assert resources.kind_of("title.png") == resources.TEXTURE
    assert resources.kind_of("boot.dol") == resources.OTHER
    assert resources.kind_of("README") == resources.OTHER


def test_count_walks_the_folder_and_totals_files_and_bytes_per_kind(tmp_path):
    (tmp_path / "text").mkdir()
    (tmp_path / "text" / "a.json").write_bytes(b"12345")
    (tmp_path / "fonts").mkdir()
    (tmp_path / "fonts" / "f.bfn").write_bytes(b"123")
    (tmp_path / "tex.png").write_bytes(b"1234567")
    (tmp_path / "exe.bin").write_bytes(b"x")

    counts = resources.count_resources(tmp_path)

    assert counts[resources.TEXT] == {"files": 1, "bytes": 5}
    assert counts[resources.FONT] == {"files": 1, "bytes": 3}
    assert counts[resources.TEXTURE] == {"files": 1, "bytes": 7}
    assert counts[resources.OTHER] == {"files": 1, "bytes": 1}


def test_a_single_file_source_counts_as_one_file(tmp_path):
    game = tmp_path / "game.bfn"
    game.write_bytes(b"abcd")

    counts = resources.count_resources(game)

    assert counts[resources.FONT] == {"files": 1, "bytes": 4}
    assert sum(bucket["files"] for bucket in counts.values()) == 1


def test_a_missing_source_counts_as_empty(tmp_path):
    counts = resources.count_resources(tmp_path / "gone")

    assert all(bucket == {"files": 0, "bytes": 0} for bucket in counts.values())


def test_cancelled_walk_returns_none(tmp_path):
    (tmp_path / "a.json").write_bytes(b"x")

    assert resources.count_resources(tmp_path, is_cancelled=lambda: True) is None


def test_symbolic_links_are_not_followed(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "a.png").write_bytes(b"12")
    link = tmp_path / "link"
    try:
        os.symlink(real, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        return  # symbolic links need a privilege on some Windows accounts; the walk itself is covered above

    counts = resources.count_resources(tmp_path)

    assert counts[resources.TEXTURE] == {"files": 1, "bytes": 2}
