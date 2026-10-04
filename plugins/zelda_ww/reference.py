"""The Wind Waker HD's other languages as reference languages, matched by MSBT file and label.

A reference folder (searched with its subfolders) holds packs named like the game's own:
``permanent_2d_<Region><Language>.pack`` -- ``UsFrench``, ``UsSpanish``, ``EuGerman``... A message file
``X.msbt`` is pack member ``X_msbt.szs`` (a Yaz0 SARC holding ``X.msbt``). A fan translation keeps its
language in the name the same way: the Russian patch's ``permanent_2d_UsEnglish.pack`` is copied as
``permanent_2d_RuRussian.pack``. English packs are the project's own language and are skipped.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Tuple

from core.containers import yaz0
from core.containers.sarc import Sarc
from plugins.common.msbt import Msbt
from utils.logging_utils import log_warning

from .tags import to_editor

RUSSIAN = "Russian (RU)"
_PACK = re.compile(r"^permanent_2d_([A-Z][a-z])([A-Z][a-z]+)\.pack$")


def label(pack_name: str) -> str:
    """``permanent_2d_UsFrench.pack`` -> ``French (US)``; '' for any other file and for English."""
    match = _PACK.match(pack_name)
    if not match or match.group(2) == "English":
        return ""
    return f"{match.group(2)} ({match.group(1).upper()})"


def load_languages(root: Path, blocks: Dict[int, Tuple[str, Dict[int, str]]]) -> Dict[str, Dict[Tuple[int, int], str]]:
    """``{label: {(block, line): text}}`` for every reference pack under ``root``, Russian first.

    ``blocks`` maps a project block to ``(MSBT file name, {line: MSBT label})``.
    """
    texts: Dict[str, Dict[Tuple[int, int], str]] = {}
    for path in sorted(root.rglob("permanent_2d_*.pack")):
        name = label(path.name)
        if not name or name in texts:
            continue
        try:
            pack = Sarc(path.read_bytes())
        except (OSError, ValueError) as error:
            log_warning(f"zelda_ww: reference {path}: {error}")
            continue
        found = texts.setdefault(name, {})
        for block, (file_name, labels) in blocks.items():
            stem = Path(file_name).stem
            member = pack.files.get(f"{stem}_msbt.szs")
            if member is None:
                continue
            try:
                msbt = Msbt(Sarc(yaz0.decompress(member)).files[f"{stem}.msbt"])
            except (KeyError, ValueError) as error:
                log_warning(f"zelda_ww: reference {path.name}/{stem}: {error}")
                continue
            by_label = {msbt_label: index for index, msbt_label in msbt.labels.items()}
            for line, line_label in labels.items():
                if line_label in by_label:
                    found[(block, line)] = to_editor(msbt.messages[by_label[line_label]])
    ordered = {RUSSIAN: texts[RUSSIAN]} if texts.get(RUSSIAN) else {}
    ordered.update({name: found for name, found in texts.items() if found and name != RUSSIAN})
    return ordered
