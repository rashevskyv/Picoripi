"""Disk cache of decoded textures and of a project's texture list, plus a process pool that fills it.

A texture is decoded once per change of its files: the key holds the size and time of the source and the translation
file, so a write or a new unpack makes a new entry. Decoding is pure Python, so a pool of processes (not threads)
makes it parallel.
"""
from __future__ import annotations

import hashlib
import os
import pickle
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple

from PIL import Image

from core.texture_formats import sources as texture_sources
from core.texture_formats.sources import TextureSource
from utils.atomic_io import atomic_write_bytes

Pair = Tuple[Optional[Image.Image], Optional[Image.Image], str]
POOL_MIN = 8   # fewer uncached textures than this decode in the calling thread: a pool takes longer to start


def _stamp(path: str) -> str:
    try:
        info = os.stat(path)
    except OSError:
        return "-"
    return f"{info.st_mtime_ns}:{info.st_size}"


def _digest(*parts: Any) -> str:
    return hashlib.sha1(repr(parts).encode("utf-8")).hexdigest()


def _pair_base(source: TextureSource, cache_dir: str) -> Path:
    current = source._current_path()
    return Path(cache_dir) / "decoded" / _digest(source.key, source.format, source.member, source.index,
                                                  sorted(source.params.items(), key=repr),
                                                  _stamp(source.source_path), _stamp(current), current)


def _decode(source: TextureSource) -> Pair:
    try:
        return source.read_original().image, source.read_current().image, ""
    except (OSError, ValueError, KeyError, IndexError) as error:
        return None, None, str(error)


def _png(image: Image.Image) -> bytes:
    import io
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def read_pair(source: TextureSource, cache_dir: str = "") -> Pair:
    """``(original, current, error)`` of a texture, from the cache when its files are unchanged."""
    if not cache_dir or source.original_bytes is not None:
        return _decode(source)
    base = _pair_base(source, cache_dir)
    original_file, current_file = base.with_suffix(".o.png"), base.with_suffix(".c.png")
    try:
        with Image.open(original_file) as a, Image.open(current_file) as b:
            return a.convert("RGBA"), b.convert("RGBA"), ""
    except (OSError, ValueError):
        pass
    original, current, error = _decode(source)
    if not error:
        try:
            base.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(str(original_file), _png(original))
            atomic_write_bytes(str(current_file), _png(current))
        except OSError:
            pass   # a cache that cannot be written only costs the next open some time
    return original, current, error


def read_pairs(sources: Iterable[TextureSource], cache_dir: str,
               cancelled: Callable[[], bool]) -> Iterator[Tuple[TextureSource, Pair]]:
    """Every texture's pair as it is ready. Many uncached textures decode in a pool of processes."""
    sources = list(sources)
    uncached = [s for s in sources if s.original_bytes is not None or not cache_dir
                or not _pair_base(s, cache_dir).with_suffix(".c.png").is_file()]
    if len(uncached) < POOL_MIN:
        for source in sources:
            if cancelled():
                return
            yield source, read_pair(source, cache_dir)
        return
    cached = [s for s in sources if s not in uncached]
    for source in cached:
        if cancelled():
            return
        yield source, read_pair(source, cache_dir)
    with ProcessPoolExecutor(max_workers=max(1, min(8, (os.cpu_count() or 2) - 1))) as pool:
        futures = {pool.submit(read_pair, s, cache_dir): s for s in uncached}
        try:
            for future in as_completed(futures):
                if cancelled():
                    return
                try:
                    pair = future.result()
                except Exception as error:   # a worker that died: this texture shows no picture
                    pair = (None, None, str(error))
                yield futures[future], pair
        finally:
            pool.shutdown(wait=False, cancel_futures=True)


def _list_key(descriptors: List[Dict[str, Any]], metadata: Dict[str, Any]) -> str:
    source_root = str(metadata.get("source_path") or "")
    translation_root = str(metadata.get("translation_path") or "")
    directory_mode = metadata.get("is_directory_mode", True)
    files = []
    for descriptor in descriptors or []:
        try:
            for source_path, translation_path in texture_sources._match_files(descriptor, source_root,
                                                                               translation_root, directory_mode):
                files.append((source_path, _stamp(source_path), _stamp(translation_path)))
        except (OSError, ValueError, TypeError):
            continue
    return _digest(descriptors, source_root, translation_root, directory_mode, files)


def resolve(descriptors: Iterable[Dict[str, Any]], metadata: Dict[str, Any], cache_dir: str) -> List[TextureSource]:
    """``texture_sources.resolve``, but a list whose files are unchanged comes from the cache."""
    descriptors = list(descriptors or [])
    if not cache_dir:
        return texture_sources.resolve(descriptors, metadata)
    key = _list_key(descriptors, metadata)
    path = Path(cache_dir) / "list.pickle"
    try:
        stored_key, found = pickle.loads(path.read_bytes())
        if stored_key == key:
            return found
    except (OSError, pickle.PickleError, EOFError, ValueError, TypeError, AttributeError, IndexError):
        pass
    found = texture_sources.resolve(descriptors, metadata)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(str(path), pickle.dumps((key, found)))
    except OSError:
        pass
    return found
