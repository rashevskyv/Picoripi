"""``prompts.json``, read key by key.

Prompts come from up to four files, each later one overriding the earlier ones
*per key*, not per file:

1. ``translation_prompts/prompts.json`` -- the application's own,
2. ``plugins/common/defaults/prompts.json`` -- shared by all plugins,
3. ``plugins/<name>/translation_prompts/prompts.json`` -- the plugin's,
4. the user's or project's override copy (see ``GlossaryPromptManager.override_dir``).

A plugin file used to *replace* the lower files as a whole. Every shipped plugin
holds only a ``translation`` section, so their glossary, editor-review and
MemPalace prompts were never read: the code fell back to built-in constants or
switched the feature off without saying so.
"""
from __future__ import annotations
from utils.constants import plugins_root

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from utils.logging_utils import log_debug

FILE_NAME = "prompts.json"


def deep_merge(base: Dict[str, Any], top: Dict[str, Any]) -> Dict[str, Any]:
    """``base`` with ``top`` laid over it; nested dicts are merged, anything else is replaced."""
    merged = dict(base)
    for key, value in top.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def prompt_layers(plugin_name: Optional[str], override_dirs: Iterable[Optional[Path]] = ()) -> List[Path]:
    """The prompt files that exist for this plugin, lowest priority first."""
    candidates = [
        Path("translation_prompts") / FILE_NAME,
        plugins_root() / "common" / "defaults" / FILE_NAME,
    ]
    if plugin_name:
        candidates.append(plugins_root() / plugin_name / "translation_prompts" / FILE_NAME)
    candidates += [Path(directory) / FILE_NAME for directory in override_dirs if directory]
    return [path for path in candidates if path.exists()]


def load_merged_prompts(plugin_name: Optional[str], override_dirs: Iterable[Optional[Path]] = ()) -> Dict[str, Any]:
    """All prompt sections for this plugin. An unreadable file is skipped and logged."""
    merged: Dict[str, Any] = {}
    for path in prompt_layers(plugin_name, override_dirs):
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError) as error:
            log_debug(f"prompt_files: skipping unreadable {path}: {error}")
            continue
        if isinstance(data, dict):
            merged = deep_merge(merged, data)
    return merged
