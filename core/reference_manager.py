"""Reference translation manager for loading and mapping external reference texts.

This module provides the general engine-level facade for reference translation patches.
Concrete archive extraction, binary parsing, and game-specific block mappings are
delegated to the active plugin via the BaseGameRules contract:
- game_rules.supports_reference_patch()
- game_rules.get_reference_language_label()
- game_rules.load_reference_patch(patch_path, block_names)
"""
from __future__ import annotations
from utils.atomic_io import atomic_write_json

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.logging_utils import log_error, log_info, log_warning

# Reference languages the prompt trusts least: they go last, after every other one. Russian wording leaks into
# Ukrainian translations as calques (live run 2026-10-03: «Уговори Линка» taken from the Russian line).
LEAST_TRUSTED_REFERENCE_LANGUAGES = ("russian",)


def least_trusted_last(references):
    """``(label, text)`` pairs in their order, the least trusted languages moved to the end."""
    return sorted(references, key=lambda pair: str(pair[0]).casefold().startswith(LEAST_TRUSTED_REFERENCE_LANGUAGES))


class ReferenceManager:
    """Manages loading, persisting settings, and coordinating reference translations."""

    @staticmethod
    def get_reference_patch_path(project_dir: str | Path) -> Optional[str]:
        """Read reference_patch_path from project_settings.json."""
        try:
            settings_path = Path(project_dir) / "project_settings.json"
            if settings_path.exists():
                with open(settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("reference_patch_path")
        except Exception as e:
            log_warning(f"ReferenceManager: failed to read reference_patch_path: {e}")
        return None

    @staticmethod
    def set_reference_patch_path(project_dir: str | Path, patch_path: str) -> None:
        """Persist reference_patch_path into project_settings.json."""
        try:
            settings_path = Path(project_dir) / "project_settings.json"
            data: Dict[str, Any] = {}
            if settings_path.exists():
                with open(settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["reference_patch_path"] = str(patch_path)
            atomic_write_json(settings_path, data, ensure_ascii=False, indent=2)
            log_info(f"ReferenceManager: saved reference_patch_path='{patch_path}'")
        except Exception as e:
            log_error(f"ReferenceManager: failed to save reference_patch_path: {e}")

    @classmethod
    def get_reference_language_label(cls, game_rules: Optional[Any] = None) -> str:
        """Return the UI display label for the reference translation tab from the plugin.

        Defaults to 'Reference (RU)' if not specified by the active plugin.
        """
        if game_rules and hasattr(game_rules, "get_reference_language_label"):
            try:
                return game_rules.get_reference_language_label()
            except Exception as e:
                log_warning(f"ReferenceManager: failed to get language label from plugin: {e}")
        return "Reference (RU)"

    @classmethod
    def load_multi_reference(
        cls,
        patch_path: str | Path,
        block_names: Optional[Dict[str, str] | List[str]] = None,
        game_rules: Optional[Any] = None,
    ) -> Dict[str, Dict[Tuple[int, int], str]]:
        """Load and parse reference translation files for multiple languages.

        Delegates concrete parsing, archive extraction, and language identification
        to the active game plugin via BaseGameRules.load_multi_reference().

        Returns:
            A mapping of language_label -> {(block_idx, string_idx): reference_text}.
        """
        p = Path(patch_path)
        if not p.exists():
            log_warning(f"ReferenceManager: patch path does not exist: {p}")
            return {}

        if not game_rules:
            log_warning("ReferenceManager: no game rules provided for loading reference.")
            return {}

        if hasattr(game_rules, "supports_reference_patch") and not game_rules.supports_reference_patch():
            log_warning(
                f"ReferenceManager: active plugin {type(game_rules).__name__} does not support reference patches."
            )
            return {}

        if hasattr(game_rules, "load_multi_reference"):
            try:
                log_info(
                    f"ReferenceManager: delegating multi-reference loading to {type(game_rules).__name__}..."
                )
                return game_rules.load_multi_reference(str(p), block_names=block_names)
            except Exception as e:
                log_error(f"ReferenceManager: plugin failed to load multi-reference: {e}", exc_info=True)
                return {}

        if hasattr(game_rules, "load_reference_patch"):
            try:
                single = game_rules.load_reference_patch(str(p), block_names=block_names)
                if single:
                    label = cls.get_reference_language_label(game_rules)
                    return {label: single}
            except Exception as e:
                log_error(f"ReferenceManager: fallback single reference load failed: {e}", exc_info=True)
                return {}

        log_warning(
            f"ReferenceManager: active plugin {type(game_rules).__name__} lacks load_reference implementation."
        )
        return {}

    @classmethod
    def load_reference(
        cls,
        patch_path: str | Path,
        block_names: Optional[Dict[str, str] | List[str]] = None,
        game_rules: Optional[Any] = None,
    ) -> Dict[Tuple[int, int], str]:
        """Load and parse reference translation files for the current project.

        Returns:
            A mapping of (block_idx, string_idx) -> reference_text for the primary reference language.
        """
        multi = cls.load_multi_reference(patch_path, block_names=block_names, game_rules=game_rules)
        if not multi:
            return {}
        return multi.get("Russian (RU)") or next(iter(multi.values()))
