# handlers/translation/glossary_prompt_manager.py
"""
Manages loading, caching, and saving of translation prompts and the glossary file.
Isolated from AI request logic and dialog handling.
"""
import json
from pathlib import Path
from typing import Dict, Optional, Tuple

from utils.logging_utils import log_debug

_DEFAULT_GLOSSARY_PROMPT = (
    "You are the creative Ukrainian localization lead for {game_name}. "
    "When given a source term (and optional context line), craft a vivid Ukrainian translation that matches the game's universe, tone, and established terminology. "
    "Describe the in-game meaning in one short note – explain what the term represents or how it is used, without grammar labels, part-of-speech hints, or plural/singular remarks. "
    "Respond strictly in JSON with keys \"translation\" and \"notes\"; keep both values in Ukrainian."
)


class GlossaryPromptManager:
    """
    Handles reading/writing of prompts.json and glossary.md.
    Provides caching to avoid repeated file reads.
    """

    def __init__(self, mw, main_handler, glossary_manager) -> None:
        self._mw = mw
        self._main_handler = main_handler
        self._glossary_manager = glossary_manager

        self.current_prompts_path: Optional[Path] = None
        self._current_glossary_path: Optional[Path] = None
        self._current_plugin_name: Optional[str] = None

        self._cached_glossary_prompt_template: Optional[str] = None
        self._cached_glossary_prompt_plugin: Optional[str] = None

    # ── Prompt directory resolution ─────────────────────────────────────

    def _plugin_dir(self, plugin_name: Optional[str]) -> Optional[Path]:
        return Path("plugins", plugin_name, "translation_prompts") if plugin_name else None

    def _fallback_dir(self) -> Path:
        return Path("translation_prompts")

    def _resolve_file(self, filename: str, plugin_name: Optional[str]) -> Optional[Path]:
        candidates = [
            self._plugin_dir(plugin_name) and self._plugin_dir(plugin_name) / filename,
            self._fallback_dir() / filename,
        ]
        return next((p for p in candidates if p and p.exists()), None)

    # ── Public: load prompts (cached) ───────────────────────────────────

    def load_prompts(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Returns (system_prompt, glossary_text).
        Uses cached values when available. Shows QMessageBox on errors.
        """
        from PyQt5.QtWidgets import QMessageBox

        h = self._main_handler
        if h._cached_system_prompt and h._cached_glossary is not None:
            self._ensure_glossary_loaded(
                glossary_text=h._cached_glossary,
                plugin_name=self._current_plugin_name,
                glossary_path=self._current_glossary_path,
            )
            return h._cached_system_prompt, h._cached_glossary

        plugin_name = getattr(self._mw, "active_game_plugin", None)
        prompts_path = self._resolve_file("prompts.json", plugin_name)
        self.current_prompts_path = prompts_path

        if not prompts_path:
            QMessageBox.critical(self._mw, "AI Translation", "prompts.json not found.")
            return None, None

        try:
            prompt_data = json.loads(prompts_path.read_text("utf-8"))
        except Exception as e:
            QMessageBox.critical(self._mw, "AI Translation", f"Failed to load prompts.json: {e}")
            return None, None

        system_prompt = self._extract_system_prompt(prompt_data)
        if not system_prompt:
            QMessageBox.critical(self._mw, "AI Translation", "System prompt not defined in prompts.json.")
            return None, None

        glossary_path = self._resolve_file("glossary.md", plugin_name)
        glossary_text = ""
        if glossary_path:
            try:
                glossary_text = glossary_path.read_text("utf-8").strip()
            except Exception as e:
                QMessageBox.warning(self._mw, "AI Translation", f"Failed to read glossary.md: {e}")

        self._current_glossary_path = glossary_path
        self._current_plugin_name = plugin_name
        self._glossary_manager.load_from_text(
            plugin_name=plugin_name, glossary_path=glossary_path, raw_text=glossary_text
        )
        self._update_glossary_highlighting()

        h._cached_system_prompt = system_prompt
        h._cached_glossary = glossary_text
        return system_prompt, glossary_text

    def initialize_highlighting(self) -> None:
        """Pre-load glossary text for syntax highlighting without a full prompts load."""
        plugin_name = getattr(self._mw, "active_game_plugin", None)
        glossary_path = self._resolve_file("glossary.md", plugin_name)
        glossary_text = ""
        if glossary_path:
            try:
                glossary_text = glossary_path.read_text(encoding="utf-8")
            except Exception as exc:
                log_debug(f"Glossary preload error: {exc}")

        self._current_plugin_name = plugin_name
        self._current_glossary_path = glossary_path
        self._main_handler._cached_glossary = glossary_text
        self._ensure_glossary_loaded(
            glossary_text=glossary_text, plugin_name=plugin_name, glossary_path=glossary_path
        )

    # ── Public: glossary prompt template ────────────────────────────────

    def get_glossary_prompt_template(self) -> Tuple[str, Optional[Path]]:
        """Returns (template_string, prompts_path). Uses cache if plugin unchanged."""
        plugin_name = getattr(self._mw, "active_game_plugin", None)
        if self._cached_glossary_prompt_template and self._cached_glossary_prompt_plugin == plugin_name:
            return self._cached_glossary_prompt_template, self._current_glossary_path

        prompts_path = self._resolve_file("prompts.json", plugin_name)
        if prompts_path:
            self.current_prompts_path = prompts_path

        template = _DEFAULT_GLOSSARY_PROMPT
        if prompts_path:
            try:
                prompt_data = json.loads(prompts_path.read_text("utf-8"))
                extracted = self._extract_glossary_prompt(prompt_data)
                if extracted:
                    template = extracted
            except Exception as e:
                log_debug(f"Glossary prompt template read error: {e}")

        self._cached_glossary_prompt_template = template
        self._cached_glossary_prompt_plugin = plugin_name
        return template, self._current_glossary_path

    # ── Public: save a prompt section ───────────────────────────────────

    def save_prompt_section(self, section: str, field: str, value: str) -> bool:
        """Persists one field of prompts.json and updates local caches."""
        path = self.current_prompts_path
        if not path:
            return False
        try:
            data: Dict = json.loads(path.read_text("utf-8")) if path.exists() else {}
            if not isinstance(data, dict):
                data = {}
        except Exception as exc:
            log_debug(f"Failed to load prompts file {path}: {exc}")
            return False

        section_data = data.setdefault(section, {})
        if not isinstance(section_data, dict):
            section_data = {}
            data[section] = section_data
        section_data[field] = value

        try:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception as exc:
            log_debug(f"Failed to write prompts file {path}: {exc}")
            return False

        if section == "glossary" and field == "prompt_template":
            self._cached_glossary_prompt_template = value
        if section == "translation" and field == "system_prompt":
            self._main_handler._cached_system_prompt = value
        return True

    # ── Internal helpers ─────────────────────────────────────────────────

    def _extract_system_prompt(self, payload: Dict) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        translation_section = payload.get("translation")
        if isinstance(translation_section, dict):
            candidate = translation_section.get("system_prompt")
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        candidate = payload.get("translation_system_prompt")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        return None

    def _extract_glossary_prompt(self, payload: Dict) -> Optional[str]:
        if not isinstance(payload, dict):
            return None
        glossary_section = payload.get("glossary")
        if isinstance(glossary_section, dict):
            candidate = glossary_section.get("prompt_template")
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        candidate = payload.get("glossary_prompt")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        return None

    def _ensure_glossary_loaded(
        self,
        *,
        glossary_text: Optional[str],
        plugin_name: Optional[str],
        glossary_path: Optional[Path],
    ) -> None:
        if glossary_text is None:
            return
        self._glossary_manager.load_from_text(
            plugin_name=plugin_name, glossary_path=glossary_path, raw_text=glossary_text
        )
        self._update_glossary_highlighting()

    def _update_glossary_highlighting(self) -> None:
        manager = self._glossary_manager if self._glossary_manager.get_entries() else None
        
        # Update all three editors
        editors = [
            getattr(self._mw, "original_text_edit", None),
            getattr(self._mw, "edited_text_edit", None),
            getattr(self._mw, "preview_text_edit", None)
        ]
        
        for editor in editors:
            if editor and hasattr(editor, "set_glossary_manager"):
                editor.set_glossary_manager(manager)
                
                # Special case: Enable translation-side glossary bridge for edited_text_edit
                if editor == getattr(self._mw, "edited_text_edit", None):
                    original_editor = getattr(self._mw, "original_text_edit", None)
                    if hasattr(editor, "highlighter") and editor.highlighter:
                        editor.highlighter.set_translation_mode(manager is not None, original_editor)
