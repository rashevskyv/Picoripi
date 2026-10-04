"""Skyward Sword's own translations as reference languages, matched by MSBT file and label.

A reference folder is a romfs (HD: ``<REGION>/Object/<lang>/<area>.arc``, ``Layout/<name>.arc``) or the Wii
disc's files (``US/Object/<lang>/...``, ``US/Layout/<name>.arc``). Story text is member ``<area>/<file>.msbt``
of ``<lang>/<area>.arc``; interface text is member ``text/<lang>_<name>.msbt`` of the layout archive.
Lines are matched by label, so the HD's official Russian also fills a Wii project (HD 1.0.1 against Wii
USA: 7,690 of the Wii's 7,707 story labels exist on HD).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, Tuple

from core.containers.u8_container import U8Container
from plugins.common.msbt import Msbt
from utils.logging_utils import log_warning

from .tags import to_editor

# Language folder -> reference label. Russian keeps "Russian (RU)" and comes first.
LANGUAGES = {
    "ru_RU": "Russian (RU)", "en_US": "English (US)", "en_GB": "English (EU)", "de_DE": "German (DE)",
    "fr_FR": "French (EU)", "fr_US": "French (US)", "es_ES": "Spanish (EU)", "es_US": "Spanish (US)",
    "it_IT": "Italian (IT)", "nl_NL": "Dutch (NL)", "ja_JP": "Japanese (JA)", "ko_KR": "Korean (KO)",
    "zh_CN": "Chinese, simplified (CN)", "zh_TW": "Chinese, traditional (TW)",
}
_LANG = re.compile(r"^[a-z]{2}_[A-Z]{2}$")


def locate(rel_path: str) -> Tuple[str, str, str, str]:
    """``(kind, archive name, member template, own language)`` of a project file path.

    ``US/Object/en_US/1-Town/100-Town.msbt`` -> ("object", "1-Town", "1-Town/100-Town.msbt", "en_US");
    ``Layout/Title2D/text/en_US_titleBG_00.msbt`` -> ("layout", "Title2D", "text/{lang}_titleBG_00.msbt", "en_US").
    """
    parts = Path(rel_path).as_posix().split("/")
    if "Object" in parts:
        at = parts.index("Object")
        if len(parts) > at + 3 and _LANG.match(parts[at + 1]):
            return "object", parts[at + 2], "/".join(parts[at + 2:]), parts[at + 1]
    if "Layout" in parts:
        at = parts.index("Layout")
        if len(parts) > at + 2:
            name = parts[-1]
            own = name[:5] if _LANG.match(name[:5]) else ""
            member = "/".join(parts[at + 2:-1] + ["{lang}" + name[5:] if own else name])
            return "layout", parts[at + 1], member, own
    return "", "", "", ""


def _object_archives(root: Path, area: str) -> Iterable[Tuple[str, Path]]:
    for path in sorted(root.glob(f"*/Object/*/{area}.arc")):
        if _LANG.match(path.parent.name):
            yield path.parent.name, path


def _layout_archives(root: Path, name: str) -> Iterable[Path]:
    yield from (p for p in [root / "Layout" / f"{name}.arc", *sorted(root.glob(f"*/Layout/{name}.arc"))]
                if p.is_file())


def load_languages(root: Path, blocks: Dict[int, Tuple[str, Dict[int, str]]]) -> Dict[str, Dict[Tuple[int, int], str]]:
    """``{label: {(block, line): text}}`` for every other language under ``root``.

    ``blocks`` maps a project block to ``(project file path, {line: MSBT label})``.
    """
    texts: Dict[str, Dict[Tuple[int, int], str]] = {}
    cache: Dict[Path, U8Container] = {}

    def member(path: Path, name: str):
        try:
            if path not in cache:
                cache[path] = U8Container(path.read_bytes())
            return Msbt(cache[path].read_file(name)) if name in cache[path].list_files() else None
        except (OSError, ValueError, KeyError) as error:
            log_warning(f"zelda_sshd: reference {path.name}/{name}: {error}")
            return None

    for block, (rel_path, labels) in blocks.items():
        kind, archive, template, own = locate(rel_path)
        sources = []
        if kind == "object":
            sources = [(lang, path, template) for lang, path in _object_archives(root, archive) if lang != own]
        elif kind == "layout" and own:
            for path in _layout_archives(root, archive):
                for lang in LANGUAGES:
                    if lang != own:
                        sources.append((lang, path, template.replace("{lang}", lang)))
        for lang, path, name in sources:
            msbt = member(path, name)
            if msbt is None:
                continue
            by_label = {label: index for index, label in msbt.labels.items()}
            target = texts.setdefault(LANGUAGES.get(lang, lang), {})
            for line, label in labels.items():
                if label in by_label:
                    target[(block, line)] = to_editor(msbt.messages[by_label[label]], msbt.little)
    ordered = {label: texts[label] for label in LANGUAGES.values() if texts.get(label)}
    ordered.update({label: found for label, found in texts.items() if found and label not in ordered})
    return ordered
