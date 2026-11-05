"""Keep the parsed Hunspell dictionary on disk so a later start does not parse it again."""
from __future__ import annotations

import gc
import hashlib
import io
import pickle
import sys
from importlib import metadata
from pathlib import Path

from spylls.hunspell import Dictionary
from spylls.hunspell.data.dic import Dic

from utils import constants
from utils.atomic_io import atomic_write_bytes
from utils.logging_utils import log_debug

_FORMAT = 1
# The words and the indexes go in chunks, one pickle each: a load holds the GIL for its whole call, so one
# 30 MB load would stop the UI thread for ~0.6 s. A chunk of this size holds it for a few milliseconds.
_CHUNK_ITEMS = 5000


def _spylls_version() -> str:
    try:
        return metadata.version("spylls")
    except Exception:
        return "unknown"


def _cache_dir() -> Path:
    return constants.SETTINGS_DIR / "cache" / "spellchecker"


def _cache_path(basename: Path) -> Path:
    digest = hashlib.sha1(str(basename.resolve()).encode("utf-8")).hexdigest()[:12]
    return _cache_dir() / f"{basename.name}-{digest}.pickle"


def _key(basename: Path) -> tuple:
    stats = []
    for suffix in (".dic", ".aff"):
        stat = basename.with_suffix(suffix).stat()
        stats.append((stat.st_size, stat.st_mtime_ns))
    return (_FORMAT, _spylls_version(), sys.version_info[:2], str(basename.resolve()), tuple(stats))


def _read(path: Path, key: tuple) -> Dictionary | None:
    stream = io.BytesIO(path.read_bytes())
    if pickle.load(stream) != key:
        return None
    aff = pickle.load(stream)
    words: list = []
    for _ in range(pickle.load(stream)):
        words.extend(pickle.load(stream))
    # spylls fills both indexes word by word in file order (``Dic.append``); this rebuilds them the same way.
    dic = Dic([])
    for word in words:
        dic.index[word.stem].append(word)
    for _ in range(pickle.load(stream)):
        for lower, positions in pickle.load(stream):
            dic.lowercase_index[lower] = [words[position] for position in positions]
    dic.words = words
    return Dictionary(aff, dic)


def _write(path: Path, key: tuple, dictionary: Dictionary) -> None:
    dic = dictionary.dic
    position = {id(word): number for number, word in enumerate(dic.words)}
    lowercase = [(lower, [position[id(word)] for word in words]) for lower, words in dic.lowercase_index.items()]
    stream = io.BytesIO()
    for part in (key, dictionary.aff):
        pickle.dump(part, stream, pickle.HIGHEST_PROTOCOL)
    # Every chunk is a pickle of its own: a pickle shared by all would grow a memo of millions of entries,
    # and each resize of it stops every thread for ~0.1 s.
    for items in (dic.words, lowercase):
        chunks = range(0, len(items), _CHUNK_ITEMS)
        pickle.dump(len(chunks), stream)
        for start in chunks:
            pickle.dump(items[start:start + _CHUNK_ITEMS], stream, pickle.HIGHEST_PROTOCOL)
    atomic_write_bytes(path, stream.getvalue())


def load_dictionary(basename: Path) -> Dictionary:
    """Return the dictionary ``basename``.dic/.aff: from the disk cache when it is current, else parsed and cached.

    Slow (a second or more): call it from a worker thread or a headless path only.
    """
    basename = Path(basename)
    path = _cache_path(basename)
    key = _key(basename)
    if path.exists():
        # The load makes ~1.5 million objects; with the collector on, its full passes over them stop
        # every thread (the UI thread too) for ~100 ms each.
        collector_was_on = gc.isenabled()
        gc.disable()
        try:
            dictionary = _read(path, key)
            if dictionary is not None:
                return dictionary
            log_debug(f"Spellchecker cache {path} is out of date; parsing the dictionary again.")
        except Exception as exc:
            log_debug(f"Spellchecker cache {path} is unreadable ({exc!r}); parsing the dictionary again.")
        finally:
            if collector_was_on:
                gc.enable()
    dictionary = Dictionary.from_files(str(basename))
    try:
        _write(path, key, dictionary)
    except Exception as exc:
        log_debug(f"Spellchecker cache {path} was not written: {exc!r}")
    return dictionary
