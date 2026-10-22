"""The default key source: downloads console key files on the user's request, into the data folder.

The source is the ``bios/Nintendo`` folder of one pinned commit of the Abdess/retrobios repository. Picoripi ships no
key bytes. This module holds only the names, sizes and SHA-256 values of the five files it reads, copied from that
commit's ``database.json``. A download runs only after the user confirmed it in the UI (``ui/key_source_download.py``).

Files go to ``SETTINGS_DIR/key_source/<console>/``. Each console's files are checked, then replaced in one step, then
the registered file is stored in the console key store. A key file the user already set for a console always wins:
that console is skipped. Key bytes are never logged or shown.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Sequence, Tuple

from core.containers import n3ds, switch_crypto, wii_disc
from core.containers.image_files import ImageError
from core.i18n import tr
from core.project_library import console_keys
from utils import constants
from utils.atomic_io import atomic_write_json

REPO = "Abdess/retrobios"
DEFAULT_REF = "ccac829b5460a2d2dcaac9a9c5d4e915bb0fd1c3"   # the commit the table below was read from (database.json)
DEFAULT_BASE = f"https://raw.githubusercontent.com/{REPO}/{DEFAULT_REF}/bios/Nintendo/"
CONFIG_NAME = "key_source.json"
DOWNLOAD_DIR = "key_source"
CHUNK = 64 * 1024
TIMEOUT_S = 20          # per socket operation
BUDGET_S = 180          # one whole download run
CUSTOM_LIMIT = 4 * 1024 * 1024   # the largest file a source the user set may send


class SourceFile(NamedTuple):
    console: str     # the console key store slot
    remote: str      # path under bios/Nintendo in the repository
    local: str       # file name in the console's download folder
    size: int        # bytes, from database.json
    sha256: str      # SHA-256, from database.json


# The files each console reads. 3DS: boot9 and the seed database must sit beside aes_keys.txt (n3ds reads them there).
# title.keys (Switch) and every .variants copy are left out: no reader uses them. Wii U has no console slot.
SOURCE_FILES: Tuple[SourceFile, ...] = (
    SourceFile("3ds", "3DS/aes_keys.txt", "aes_keys.txt", 7357,
               "0d866e062cf62275fbb291ba44af253e67fdc5bd76c7640b6c4a9dfe742510d9"),
    SourceFile("3ds", "3DS/boot9.bin", "boot9.bin", 65536,
               "2f88744feed717856386400a44bba4b9ca62e76a32c715d4f309c399bf28166f"),
    SourceFile("3ds", "3DS/Citra/sysdata/seeddb.bin", "seeddb.bin", 53264,
               "ff485c60090185aff05354ece01f86b61f6020332bed0f9090c58d4678e5a180"),
    SourceFile("switch", "Switch/prod.keys", "prod.keys", 16025,
               "039895c6e93a0c6208c3af27da8c3fc408083873a96f2320dc334a6fa252c112"),
    SourceFile("wii", "Wii/keys.bin", "keys.bin", 1024,
               "71b888e41c7d3e6173a131a4b80c4a366a13348e6c1f3c53c8b4635a839a3d2d"),
)
# The file each console's key store entry points at. The other files of the group sit beside it.
REGISTERED = {"3ds": "aes_keys.txt", "switch": "prod.keys", "wii": "keys.bin"}
SOURCE_CONSOLES = tuple(REGISTERED)


class KeySourceError(Exception):
    """A download failed. The message is a ``tr()`` text for the user: no key text, no full path."""


class KeySourceCancelled(Exception):
    """The user cancelled the download."""


class Outcome(NamedTuple):
    downloaded: Tuple[str, ...]   # consoles whose files were fetched and registered
    kept: Tuple[str, ...]         # consoles where the user's own key file stays


class Source(NamedTuple):
    """The source settings as one value: what the consent dialog shows and what the download then reads."""
    enabled: bool
    base: str          # the address, ending with "/"
    pinned: bool       # True for the default address: its files are checked against the record above


def _config_path() -> Path:
    return constants.SETTINGS_DIR / CONFIG_NAME


def config() -> Dict[str, object]:
    """The source settings: ``enabled``, ``base_url`` ("" = default), ``last_ref``, ``last_time``. Damaged file = defaults."""
    data: Dict[str, object] = {"enabled": True, "base_url": "", "last_ref": "", "last_time": ""}
    try:
        stored = json.loads(_config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return data
    if isinstance(stored, dict):
        for key in data:
            if isinstance(stored.get(key), type(data[key])):
                data[key] = stored[key]
    return data


def set_config(**changes: object) -> None:
    """Save the source settings. Atomic. A ``base_url`` that is not an http(s) address is refused."""
    if "base_url" in changes:
        _address(str(changes["base_url"]))   # raises KeySourceError for a bad address
    data = config()
    data.update(changes)
    atomic_write_json(_config_path(), data, indent=2)


def _address(value: str) -> str:
    """``value`` with a trailing slash, or the default when empty. Raises KeySourceError for a non-http(s) address."""
    text = value.strip() or DEFAULT_BASE
    if not text.lower().startswith(("https://", "http://")):
        raise KeySourceError(tr("The source address must start with https:// or http://."))
    return text if text.endswith("/") else text + "/"


def snapshot() -> Source:
    """The current source settings. Reads the settings file: call it on a worker."""
    cfg = config()
    base = _address(str(cfg["base_url"]))
    return Source(bool(cfg["enabled"]), base, base == DEFAULT_BASE)


def files_for(console: str) -> Tuple[SourceFile, ...]:
    return tuple(item for item in SOURCE_FILES if item.console == console)


def download_root() -> Path:
    """The data folder that holds every downloaded key file, one sub-folder per console."""
    return constants.SETTINGS_DIR / DOWNLOAD_DIR


def managed_dir(console: str) -> Path:
    """The folder that holds the files downloaded for ``console``."""
    return download_root() / console


def own_file(console: str) -> bool:
    """True when the console key store points at a key file the user set (not one this module downloaded)."""
    path = console_keys.stored(console)
    if not path or not os.path.isfile(path):
        return False
    try:
        Path(path).resolve().relative_to(managed_dir(console).resolve())
    except ValueError:
        return True
    return False


def download(consoles: Sequence[str], base: str, is_cancelled: Callable[[], bool],
             progress: Callable[[str], None] = lambda _text: None) -> Outcome:
    """Fetch the files of ``consoles`` from ``base`` (the address the user consented to) and register them.

    Runs on a worker, never on the UI thread. Raises ``KeySourceError`` (a message for the user) or
    ``KeySourceCancelled``. A console whose download fails keeps its earlier files; no partial file is left behind.
    """
    if not bool(config()["enabled"]):
        raise KeySourceError(tr("The default key source is turned off in the Console keys tab."))
    base = _address(base)
    pinned = base == DEFAULT_BASE
    deadline = time.monotonic() + BUDGET_S
    downloaded: List[str] = []
    kept: List[str] = []
    for console in consoles:
        if console not in SOURCE_CONSOLES:
            raise ValueError(f"unknown console: {console}")
        if own_file(console):
            kept.append(console)
            continue
        folder = managed_dir(console)
        folder.mkdir(parents=True, exist_ok=True)
        staged: List[Tuple[Path, Path]] = []
        try:
            for item in files_for(console):
                progress(tr("Downloading {0}...", item.local))
                limit = item.size if pinned else CUSTOM_LIMIT
                data = _fetch(base + item.remote, item.local, limit, is_cancelled, deadline)
                if pinned:
                    _check_record(item, data)
                temp = folder / f".{item.local}.{uuid.uuid4().hex}.tmp"
                temp.write_bytes(data)
                staged.append((temp, folder / item.local))
            if not pinned:
                _check_format(console, folder / REGISTERED[console], staged)
            if is_cancelled():
                raise KeySourceCancelled()
            for temp, final in staged:
                os.replace(temp, final)
        except BaseException:
            for temp, _final in staged:
                temp.unlink(missing_ok=True)
            raise
        if own_file(console):   # the user set a file while this ran: theirs wins
            kept.append(console)
            continue
        console_keys.set_path(console, str(folder / REGISTERED[console]))
        downloaded.append(console)
    if downloaded:
        set_config(last_ref=DEFAULT_REF if pinned else "", last_time=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    return Outcome(tuple(downloaded), tuple(kept))


def _fetch(url: str, name: str, limit: int, is_cancelled: Callable[[], bool], deadline: float) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Picoripi"})
    data = bytearray()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            while True:
                if is_cancelled():
                    raise KeySourceCancelled()
                if time.monotonic() > deadline:
                    raise KeySourceError(tr("The source answered too slowly. Try again later."))
                block = response.read(CHUNK)
                if not block:
                    break
                data += block
                if len(data) > limit:
                    raise KeySourceError(tr("The file {0} does not match the source record. It was not kept.", name))
    except urllib.error.HTTPError as exc:
        raise KeySourceError(_http_message(exc.code, name)) from None
    except (OSError, ValueError):
        raise KeySourceError(tr("Picoripi could not reach the source. Check the connection and try again.")) from None
    return bytes(data)


def _http_message(code: int, name: str) -> str:
    if code in (404, 410):
        return tr("The source has no {0}. The source may have moved. Change the source in the Console keys tab.", name)
    if code in (403, 429):
        return tr("The source refused the request (HTTP {0}). Try again later.", code)
    return tr("The source answered with an error (HTTP {0}).", code)


def _check_record(item: SourceFile, data: bytes) -> None:
    """The pinned source: the size and SHA-256 must equal the repository's record."""
    if len(data) != item.size or sha256(data).hexdigest() != item.sha256:
        raise KeySourceError(tr("The file {0} does not match the source record. It was not kept.", item.local))


def _check_format(console: str, registered: Path, staged: List[Tuple[Path, Path]]) -> None:
    """A source the user set has no record: the registered file must parse as that console's key file."""
    temp = next(temp for temp, final in staged if final == registered)
    try:
        if console == "3ds":
            n3ds.Keys3ds.load(str(temp))
        elif console == "switch":
            switch_crypto.load_keys(str(temp))
        else:
            wii_disc.load_common_key(str(temp))
    except ImageError:
        raise KeySourceError(tr("The downloaded {0} file is not a valid key file. It was not kept.",
                                registered.name)) from None
