"""Read existing loose tables and ARC0 languages on the reference worker."""
from pathlib import Path
import re

from PyQt6.QtCore import QThread

from utils.logging_utils import log_warning
from .arc0 import Arc0, MAX_MEMBER
from .cfgbin import FormatError
from .textfile import TextFile
from .tags import to_editor

LANGUAGES = {
    "en": "English (EN)", "engb": "English (GB)", "de": "German (DE)",
    "es": "Spanish (ES)", "fr": "French (FR)", "it": "Italian (IT)",
    "ko": "Korean (KO)", "ja": "Japanese (JA)", "ru": "Russian (RU)",
}
_SUFFIX = re.compile(r"_(en|engb|de|es|fr|it|ko|ja|ru)\.cfg\.bin$")


def _cancelled():
    return QThread.currentThread().isInterruptionRequested()


def _variant(rel, code):
    match = _SUFFIX.search(rel)
    if match is None:
        return None
    source = match.group(1)
    return rel[:match.start()].replace(f"/{source}/", f"/{code}/") + f"_{code}.cfg.bin"


def load_references(patch_path, source_root, sources, block_names=None):
    """Align by entry identity; missing files and blank rows never create a language."""
    patch = Path(patch_path)
    roots = list(dict.fromkeys([patch, patch / "reference", patch / "source", source_root,
                              source_root.parent / "reference"]))
    archive_dirs = list(dict.fromkeys([patch, patch / "romfs", source_root, source_root.parent / "romfs"]))
    archives = []
    seen = set()
    for folder in archive_dirs:
        if _cancelled():
            return {}
        paths = [folder] if folder.suffix.lower() == ".fa" and folder.is_file() else sorted(folder.glob("*.fa"))
        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            try:
                archives.append(Arc0(path, _cancelled))
            except (OSError, ValueError, IndexError, UnicodeError) as error:
                log_warning(f"yokai_watch: reference archive {path.name}: {error}")
    out = {}
    japanese = (source_root.joinpath("data/common/text/ja").is_dir()
                or source_root.joinpath("data/res/text/system_text_ja.cfg.bin").is_file())
    for block, (rel, source_path) in sources.items():
        if _cancelled():
            return {}
        if isinstance(block_names, dict) and str(block) not in block_names and block not in block_names:
            continue
        if isinstance(block_names, list) and block >= len(block_names):
            continue
        try:
            if source_path.stat().st_size > MAX_MEMBER:
                continue
            source = TextFile(source_path.read_bytes(), source_path.name, japanese=japanese)
        except (OSError, ValueError, FormatError, IndexError, UnicodeError):
            continue
        for code, label in LANGUAGES.items():
            member = _variant(rel, code)
            if member is None or member == rel:
                continue
            raw = None
            try:
                for root in roots:
                    candidate = root / member
                    if candidate.is_file() and candidate.stat().st_size <= MAX_MEMBER:
                        raw = candidate.read_bytes()
                        break
                if raw is None:
                    for archive in archives:
                        if member in archive.files:
                            raw = archive.read(member)
                            break
                if raw is None:
                    continue
                rows = TextFile(raw, member, japanese=True).rows
            except (OSError, ValueError, FormatError, IndexError, UnicodeError) as error:
                log_warning(f"yokai_watch: reference table {member}: {error}")
                continue
            texts = {(r.kind, r.text_id, r.number, r.param): r.text for r in rows}
            for string, row in enumerate(source.rows):
                text = texts.get((row.kind, row.text_id, row.number, row.param), "")
                if text.strip():
                    out.setdefault(label, {})[(block, string)] = to_editor(text)
    return out
