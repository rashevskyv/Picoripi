"""Publish a translation: put the changed game files of a build into the game's translation-only Git repository,
commit, push and tell the Telegram test-builds thread. The model is the owner's Twilight Princess ``upload.py``:
version + 1, commit ``vN: description``, push, then one Telegram message that links the patcher post. No
description: push only, no message.

A plugin opts in by putting ``"publish": spec(...)`` on a build target and implementing ``publish_files``, which
maps the built files to their paths in the repository. The repository is a local clone under
``SETTINGS_DIR/publish/<name>``, cloned without line-ending conversion so game files stay byte-exact; the user's own
Git credentials push it. The ``files_root`` folder is replaced as a whole, so a file the translation no longer
changes leaves the repository too. ``manifest.json`` beside that folder holds ``translation_version``, the counter.

The Telegram bot token, chat and thread come from a JSON file the user names in Settings
(``publish_telegram_config_path``: the same ``config.json`` the Twilight Princess uploader reads). The token is
never logged. Everything here runs on a worker thread.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from core.i18n import tr
from utils.atomic_io import atomic_write_json
from utils.constants import SETTINGS_DIR, SETTINGS_FILE_PATH
from utils.logging_utils import log_info, log_warning

Progress = Callable[[int, str], None]
Sender = Callable[[str, str, str, str], None]   # token, chat id, thread id, text
PUBLISH_KEY = "publish"
PUBLISH_DIR = "publish"
MANIFEST = "manifest.json"
TELEGRAM_SETTING = "publish_telegram_config_path"
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
MESSAGE = "📢 {game} translation updated to v{version}!\n\nWhat's new:\n{description}\n\nЯк патчити - {link}"


def spec(repo: str, branch: str, game: str, post: str, files_root: str = "files") -> Dict[str, str]:
    """The ``publish`` entry of a build target: the repository, its branch, the folder of the game files in it,
    the game's name in the Telegram message and the link of the patcher post."""
    return {"repo": repo, "branch": branch, "game": game, "post": post, "files_root": files_root}


def spec_of(target: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """The publish entry of a build target, or None when the target does not publish."""
    found = target.get(PUBLISH_KEY)
    return dict(found) if isinstance(found, dict) and found.get("repo") else None


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                            errors="replace")
    if result.returncode:
        raise ValueError(tr("git {0} failed: {1}", args[0], (result.stderr or result.stdout).strip()))
    return result.stdout


def clone_dir(repo_url: str, root: Optional[Path] = None) -> Path:
    """Where the local clone of ``repo_url`` lives."""
    name = repo_url.rstrip("/").removesuffix(".git").split("/")[-1]
    return Path(root or Path(SETTINGS_DIR) / PUBLISH_DIR) / name


def files_under(folder: Path, prefix: str = "") -> Dict[str, Path]:
    """``{prefix + path relative to folder: file}`` for every file under ``folder``."""
    return {prefix + path.relative_to(folder).as_posix(): path for path in sorted(folder.rglob("*")) if path.is_file()}


def telegram_config(settings_file: str = "") -> Optional[Dict[str, str]]:
    """``{"token", "chat", "thread"}`` from the JSON file named in the user settings, or None when not set up."""
    try:
        settings = json.loads(Path(settings_file or SETTINGS_FILE_PATH).read_text(encoding="utf-8"))
        path = str(settings.get(TELEGRAM_SETTING) or "")
        if not path:
            return None
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    token, chat = str(data.get("telegram_bot_token") or ""), str(data.get("telegram_chat_id") or "")
    if not token or not chat:
        return None
    return {"token": token, "chat": chat, "thread": str(data.get("telegram_thread_id") or "")}


def save_telegram_config_path(path: str, settings_file: str = "") -> None:
    """Store the path of the Telegram JSON file in the user settings (the other keys stay)."""
    file = Path(settings_file or SETTINGS_FILE_PATH)
    try:
        settings = json.loads(file.read_text(encoding="utf-8")) if file.is_file() else {}
    except (OSError, ValueError):
        settings = {}
    settings[TELEGRAM_SETTING] = path
    atomic_write_json(file, settings, indent=2, ensure_ascii=False)


def _send(token: str, chat: str, thread: str, text: str) -> None:
    """One ``sendMessage`` call. Raises on an HTTP or network error; the token is in the URL, so the URL never
    reaches a log or a message."""
    params = {"chat_id": chat, "text": text}
    if thread:
        params["message_thread_id"] = thread
    request = urllib.request.Request(TELEGRAM_API.format(token=token),
                                     data=urllib.parse.urlencode(params).encode("utf-8"))
    with urllib.request.urlopen(request, timeout=15) as response:
        answer = json.loads(response.read().decode("utf-8"))
    if not answer.get("ok"):
        raise ValueError(str(answer.get("description") or "not ok"))


def _bump_version(manifest: Path) -> int:
    """``translation_version`` + 1 in the manifest (a value that is not a whole number starts at 1)."""
    data = json.loads(manifest.read_text(encoding="utf-8"))
    try:
        version = int(data.get("translation_version")) + 1
    except (TypeError, ValueError):
        version = 1
    data["translation_version"] = version
    atomic_write_json(manifest, data, indent=2, ensure_ascii=False)
    return version


def publish_build(rules: Any, target: Dict[str, Any], source_dir: str, translation_dir: str, build_path: str,
                  description: str, progress: Progress, root: Optional[Path] = None, push: bool = True,
                  send: Sender = _send, settings_file: str = "") -> str:
    """Publish the files of one built target and return a sentence for the user.

    ``description`` is the commit text and the Telegram "What's new"; empty means push only. ``root`` replaces the
    default clone folder and ``push=False`` commits only (tests); ``send`` posts the Telegram message. Raises
    ValueError when the target does not publish, git fails or a file path is outside ``files_root``.
    """
    entry = spec_of(target)
    if entry is None:
        raise ValueError(tr("The build target {0} does not publish.", str(target.get("id"))))
    repo_url, branch, files_root = entry["repo"], entry["branch"], entry["files_root"]
    repo = clone_dir(repo_url, root)
    work = repo.with_name(f".{repo.name}-work")
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    files = rules.publish_files(target["id"], source_dir, translation_dir, build_path, str(work))
    if not files:
        raise ValueError(tr("The build has no files to publish."))
    outside = [rel for rel in files if not rel.startswith(files_root + "/") or ".." in rel.split("/")]
    if outside:
        raise ValueError(tr("{0} is outside the folder {1} of the repository.", outside[0], files_root))
    if not (repo / ".git").is_dir():
        progress(5, tr("Cloning {0}", repo_url))
        _git(repo.parent, "clone", "--config", "core.autocrlf=false", "--branch", branch, repo_url, repo.name)
    elif push:
        _git(repo, "pull", "--ff-only", "origin", branch)
    progress(30, tr("Updating the translation files"))
    shutil.rmtree(repo / files_root, ignore_errors=True)
    for rel, source in files.items():
        target_file = repo / rel
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target_file)
    shutil.rmtree(work, ignore_errors=True)
    if not _git(repo, "status", "--porcelain"):
        progress(100, "")
        return tr("Nothing to publish: the repository already holds these files.")
    version = _bump_version((repo / files_root).parent / MANIFEST)
    progress(60, tr("Committing"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"v{version}: {description}" if description else f"Update translation assets - v{version}")
    if push:
        progress(80, tr("Pushing to {0}", repo_url))
        _git(repo, "push", "-q", "origin", f"HEAD:{branch}")
    commit = _git(repo, "rev-parse", "--short", "HEAD").strip()
    log_info(f"Published v{version} ({commit}) to {repo_url}")
    text = tr("Published v{0} ({1}) to {2}.", str(version), commit, repo_url)
    return text + " " + _notify(entry, version, description, send, settings_file)


def _notify(entry: Dict[str, str], version: int, description: str, send: Sender, settings_file: str) -> str:
    """Post the Telegram message when there is a description and a configured bot; returns what happened."""
    if not description:
        return tr("No description, so no Telegram message.")
    config = telegram_config(settings_file)
    if config is None:
        return tr("No Telegram message: name the Telegram settings file in Settings.")
    text = MESSAGE.format(game=entry["game"], version=version, description=description, link=entry["post"])
    try:
        send(config["token"], config["chat"], config["thread"], text)
    except Exception as exc:   # the push is done; the message is the only thing that failed
        log_warning(f"Telegram message not sent: {type(exc).__name__} {getattr(exc, 'code', '')}".strip())
        return tr("The Telegram message was not sent ({0}).", type(exc).__name__)
    return tr("The Telegram message was sent.")
