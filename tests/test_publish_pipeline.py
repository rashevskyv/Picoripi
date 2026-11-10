"""Publish translation: the built files go into a translation repository clone, commit vN: description, push, and
one Telegram message when there is a description and a bot."""
import json
import subprocess

import pytest

from core.project_library import publish
from plugins.zelda_tww import disc

POST = "https://t.me/zelda_ukr/3228/4892"
TARGET = {"id": "iso", "label": "Disc", "publish": publish.spec("origin", "main", "Zelda Test", POST)}


def _git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


class _Rules:
    """A plugin whose target publishes every file of the build folder under files/."""

    def publish_files(self, target_id, source_dir, translation_dir, build_path, work_dir):
        from pathlib import Path
        assert Path(work_dir).is_dir() and not any(Path(work_dir).iterdir())
        return publish.files_under(Path(build_path), "files/")


class _Sent:
    """Stands in for the Telegram call; records what would be sent."""

    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def __call__(self, token, chat, thread, text):
        if self.fail:
            raise OSError("no network")
        self.calls.append((token, chat, thread, text))


@pytest.fixture
def origin(tmp_path):
    """A bare repository on branch main with manifest.json and one old translation file."""
    seed = tmp_path / "seed"
    (seed / "files").mkdir(parents=True)
    (seed / "files" / "old.bin").write_bytes(b"old")
    (seed / "manifest.json").write_text(json.dumps({"translation_version": "2026-11-10"}), encoding="utf-8")
    _git("init", "-q", "-b", "main", cwd=seed)
    _git("add", "-A", cwd=seed)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "seed", cwd=seed)
    bare = tmp_path / "origin.git"
    _git("clone", "-q", "--bare", str(seed), str(bare))
    return bare


@pytest.fixture
def setup(tmp_path, origin, monkeypatch):
    """Git identity, a user settings file that names a Telegram config, the target of ``origin``; returns
    (target, built folder, clones root, settings file)."""
    for name in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(name, "t")
    for name in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(name, "t@t")
    telegram = tmp_path / "telegram.json"
    telegram.write_text(json.dumps({"telegram_bot_token": "TOKEN", "telegram_chat_id": "-100", "telegram_thread_id": "7"}),
                        encoding="utf-8")
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"theme": "auto", publish.TELEGRAM_SETTING: str(telegram)}), encoding="utf-8")
    built = tmp_path / "build" / "content"
    built.mkdir(parents=True)
    (built / "a.arc").write_bytes(b"\r\nnew")
    target = {"id": "iso", "label": "Disc", "publish": publish.spec(str(origin), "main", "Zelda Test", POST)}
    return target, tmp_path / "build", tmp_path / "clones", str(settings)


def test_publish_replaces_files_bumps_the_version_pushes_and_posts(origin, setup):
    target, built, clones, settings = setup
    sent = _Sent()

    text = publish.publish_build(_Rules(), target, "src", "tr", str(built), "New dialogues", lambda *_: None,
                                 root=clones, send=sent, settings_file=settings)

    assert _git("log", "-1", "--format=%s", "main", cwd=origin).strip() == "v1: New dialogues"
    listed = _git("ls-tree", "-r", "--name-only", "main", cwd=origin).split()
    assert listed == ["files/content/a.arc", "manifest.json"]   # files/old.bin left with the old tree
    shown = subprocess.run(["git", "show", "main:files/content/a.arc"], cwd=origin, check=True, capture_output=True)
    assert shown.stdout == b"\r\nnew"   # no line-ending conversion
    assert json.loads(_git("show", "main:manifest.json", cwd=origin))["translation_version"] == 1
    assert sent.calls == [("TOKEN", "-100", "7", "📢 Zelda Test translation updated to v1!\n\nWhat's new:\nNew dialogues"
                                               f"\n\nЯк патчити - {POST}")]
    assert "v1" in text and "sent" in text and "TOKEN" not in text

    again = publish.publish_build(_Rules(), target, "src", "tr", str(built), "Again", lambda *_: None,
                                  root=clones, send=sent, settings_file=settings)
    assert "Nothing to publish" in again and len(sent.calls) == 1


def test_no_description_pushes_without_a_message_and_the_next_version_counts_on(origin, setup):
    target, built, clones, settings = setup
    sent = _Sent()
    publish.publish_build(_Rules(), target, "src", "tr", str(built), "first", lambda *_: None, root=clones,
                          send=sent, settings_file=settings)
    (built / "content" / "a.arc").write_bytes(b"changed")

    text = publish.publish_build(_Rules(), target, "src", "tr", str(built), "", lambda *_: None, root=clones,
                                 send=sent, settings_file=settings)

    assert _git("log", "-1", "--format=%s", "main", cwd=origin).strip() == "Update translation assets - v2"
    assert len(sent.calls) == 1 and "No description" in text


def test_a_missing_bot_or_a_failed_call_leaves_the_push_done(origin, setup, tmp_path):
    target, built, clones, settings = setup
    no_bot = tmp_path / "plain.json"
    no_bot.write_text("{}", encoding="utf-8")
    sent = _Sent()
    text = publish.publish_build(_Rules(), target, "src", "tr", str(built), "d", lambda *_: None, root=clones,
                                 send=sent, settings_file=str(no_bot))
    assert sent.calls == [] and "Settings" in text and _git("rev-list", "--count", "main", cwd=origin).strip() == "2"

    (built / "content" / "a.arc").write_bytes(b"changed")
    text = publish.publish_build(_Rules(), target, "src", "tr", str(built), "d", lambda *_: None, root=clones,
                                 send=_Sent(fail=True), settings_file=settings)
    assert "not sent (OSError)" in text and _git("rev-list", "--count", "main", cwd=origin).strip() == "3"


def test_a_target_without_a_publish_entry_or_a_path_outside_the_files_folder_is_refused(tmp_path):
    with pytest.raises(ValueError, match="does not publish"):
        publish.publish_build(_Rules(), {"id": "iso"}, "s", "t", str(tmp_path), "", lambda *_: None, root=tmp_path)

    class Outside:
        def publish_files(self, *args):
            return {"manifest.json": tmp_path}

    with pytest.raises(ValueError, match="outside"):
        publish.publish_build(Outside(), TARGET, "s", "t", str(tmp_path), "", lambda *_: None, root=tmp_path)


def test_telegram_config_reads_the_file_named_in_the_settings(tmp_path):
    settings = tmp_path / "settings.json"
    assert publish.telegram_config(str(settings)) is None            # no settings file yet
    publish.save_telegram_config_path(str(tmp_path / "tg.json"), str(settings))
    assert publish.telegram_config(str(settings)) is None            # the named file does not exist
    (tmp_path / "tg.json").write_text(json.dumps({"telegram_bot_token": "T", "telegram_chat_id": "C"}), encoding="utf-8")
    assert publish.telegram_config(str(settings)) == {"token": "T", "chat": "C", "thread": ""}
    assert json.loads(settings.read_text(encoding="utf-8")) == {publish.TELEGRAM_SETTING: str(tmp_path / "tg.json")}


def test_wind_waker_dol_goes_as_a_byte_run_patch(tmp_path):
    source, translation = tmp_path / "source", tmp_path / "translation"
    (source / "sys").mkdir(parents=True)
    (translation / "sys").mkdir(parents=True)
    (translation / "files" / "res" / "Msg").mkdir(parents=True)
    (source / "sys" / "main.dol").write_bytes(bytes(64))
    (translation / "sys" / "main.dol").write_bytes(bytes(10) + b"\x01\x02" + bytes(52))
    (translation / "files" / "res" / "Msg" / "bmgres.arc").write_bytes(b"arc")

    found = disc.publish_files(source, translation, tmp_path / "work")

    assert sorted(found) == ["patcher/files/res/Msg/bmgres.arc", "patcher/files/sys/main.dol.dolpatch.json"]
    runs = json.loads(found["patcher/files/sys/main.dol.dolpatch.json"].read_text(encoding="utf-8"))
    assert runs == [[10, "0000", "0102"]]


def test_the_four_games_publish_from_their_build_targets():
    from core.project_library import plugin_facts
    expected = {"zelda_tww": {"iso", "bluewake"}, "zelda_ww": {"cemu"}, "zelda_bmg": {"wiiu_mod"},
                "zelda_oot_switch2": {"nup", "hookshot"}}
    for plugin, ids in expected.items():
        targets = plugin_facts.targets_of(plugin_facts.default_load_rules(plugin))
        publishing = {t["id"]: publish.spec_of(t) for t in targets if publish.spec_of(t)}
        assert set(publishing) == ids, plugin
        for entry in publishing.values():
            assert entry["repo"].startswith("https://github.com/rashevskyv/") and entry["post"].startswith("https://t.me/")
