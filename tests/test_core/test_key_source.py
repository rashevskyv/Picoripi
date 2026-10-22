"""The default key source: download, checks, the user's own file wins, error messages, cancel.

A local HTTP server serves synthetic all-zero key files. Nothing here reaches the network: every test passes its own
loopback address, and the real default address is only checked as a value.
"""
import pytest

from hashlib import sha256

from core.project_library import console_keys, key_source
from test_core.key_source_server import BODIES, PROD_KEYS, serve_all, serve_loopback
from utils import constants


@pytest.fixture
def loopback_source():
    with serve_loopback() as value:
        yield value


def _names(console):
    folder = key_source.managed_dir(console)
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


def test_a_download_registers_the_registered_file_and_keeps_the_others_beside_it(loopback_source):
    base, routes = loopback_source
    serve_all(routes)

    outcome = key_source.download(["3ds"], base, lambda: False)

    assert outcome == key_source.Outcome(downloaded=("3ds",), kept=())
    assert _names("3ds") == ["aes_keys.txt", "boot9.bin", "seeddb.bin"]   # no temporary file left behind
    assert console_keys.path_for("3ds") == str(key_source.managed_dir("3ds") / "aes_keys.txt")
    assert key_source.config()["last_time"] != ""


def test_a_pinned_source_checks_size_and_sha256_and_refuses_a_changed_file(loopback_source, monkeypatch):
    base, routes = loopback_source
    serve_all(routes)
    table = tuple(key_source.SourceFile(item.console, item.remote, item.local, len(BODIES[item.remote]),
                                        sha256(BODIES[item.remote]).hexdigest())
                  for item in key_source.SOURCE_FILES)
    monkeypatch.setattr(key_source, "SOURCE_FILES", table)
    monkeypatch.setattr(key_source, "DEFAULT_BASE", base)
    assert key_source.snapshot().pinned

    key_source.download(["wii"], base, lambda: False)
    assert _names("wii") == ["keys.bin"]

    routes["Wii/keys.bin"] = b"\x01" * 1024   # the same size, other bytes
    with pytest.raises(key_source.KeySourceError, match="does not match the source record"):
        key_source.download(["wii"], base, lambda: False)
    assert _names("wii") == ["keys.bin"]   # the earlier good copy stays in place
    routes["Switch/prod.keys"] = PROD_KEYS + b"x"   # a longer file
    with pytest.raises(key_source.KeySourceError, match="does not match the source record"):
        key_source.download(["switch"], base, lambda: False)
    assert _names("switch") == []


def test_the_users_own_key_file_wins_and_nothing_is_fetched_for_that_console(loopback_source, tmp_path):
    base, routes = loopback_source
    own = tmp_path / "my_prod.keys"
    own.write_bytes(PROD_KEYS)
    console_keys.set_path("switch", str(own))
    serve_all(routes)

    outcome = key_source.download(["switch"], base, lambda: False)

    assert outcome == key_source.Outcome(downloaded=(), kept=("switch",))
    assert console_keys.path_for("switch") == str(own)
    assert _names("switch") == []


def test_a_stored_file_that_is_gone_does_not_count_as_own(loopback_source, tmp_path):
    base, routes = loopback_source
    gone = tmp_path / "moved.keys"
    console_keys.set_path("wii", str(gone))   # the file was never there, or was moved away
    serve_all(routes)

    outcome = key_source.download(["wii"], base, lambda: False)

    assert outcome.downloaded == ("wii",)
    assert console_keys.path_for("wii") == str(key_source.managed_dir("wii") / "keys.bin")


def test_a_missing_file_at_the_source_says_the_source_may_have_moved(loopback_source):
    base, routes = loopback_source   # nothing served: every file is a 404

    with pytest.raises(key_source.KeySourceError, match="may have moved"):
        key_source.download(["wii"], base, lambda: False)
    assert _names("wii") == []


def test_a_refused_request_says_so_with_the_code(loopback_source):
    base, routes = loopback_source
    routes["Wii/keys.bin"] = 429

    with pytest.raises(key_source.KeySourceError, match="HTTP 429"):
        key_source.download(["wii"], base, lambda: False)


def test_an_unreachable_source_says_the_connection_failed(loopback_source):
    base, _routes = loopback_source
    with pytest.raises(key_source.KeySourceError, match="could not reach the source"):
        key_source.download(["wii"], "http://127.0.0.1:1/", lambda: False)   # port 1: nothing listens there


def test_a_stalled_source_stops_at_the_socket_timeout(loopback_source, monkeypatch):
    base, routes = loopback_source
    routes["Wii/keys.bin"] = 5.0
    monkeypatch.setattr(key_source, "TIMEOUT_S", 0.3)

    with pytest.raises(key_source.KeySourceError, match="could not reach the source"):
        key_source.download(["wii"], base, lambda: False)
    assert _names("wii") == []


def test_a_cancel_part_way_keeps_no_file_of_that_console(loopback_source):
    base, routes = loopback_source
    serve_all(routes)
    calls = {"n": 0}

    def cancel_after_a_few_checks():
        calls["n"] += 1
        return calls["n"] >= 3

    with pytest.raises(key_source.KeySourceCancelled):
        key_source.download(["3ds"], base, cancel_after_a_few_checks)
    assert _names("3ds") == []
    assert console_keys.path_for("3ds") is None


def test_a_custom_source_is_checked_by_the_format_of_its_key_file(loopback_source):
    base, routes = loopback_source
    serve_all(routes)
    routes["Switch/prod.keys"] = b"header_key = 00\n"   # a known name with a 1-byte value

    with pytest.raises(key_source.KeySourceError, match="not a valid key file"):
        key_source.download(["switch"], base, lambda: False)
    assert _names("switch") == []


def test_the_source_can_be_turned_off_and_refuses_a_bad_address(loopback_source):
    base, routes = loopback_source
    serve_all(routes)
    key_source.set_config(enabled=False)

    with pytest.raises(key_source.KeySourceError, match="turned off"):
        key_source.download(["wii"], base, lambda: False)
    with pytest.raises(key_source.KeySourceError, match="must start with https://"):
        key_source.set_config(enabled=True, base_url="ftp://example.invalid/")
    assert key_source.config()["enabled"] is False


def test_the_default_address_is_pinned_to_one_commit_and_the_settings_file_is_in_the_data_folder():
    assert key_source.DEFAULT_REF in key_source.DEFAULT_BASE
    assert key_source.DEFAULT_BASE.startswith("https://raw.githubusercontent.com/Abdess/retrobios/")
    assert key_source.snapshot().pinned
    assert key_source._config_path().parent == constants.SETTINGS_DIR
