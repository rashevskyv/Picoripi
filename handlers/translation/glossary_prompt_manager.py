# handlers/translation/glossary_prompt_manager.py
"""
Manages loading, caching, and saving of translation prompts and the glossary file.
Isolated from AI request logic and dialog handling.
"""
import json
from pathlib import Path
from typing import Dict, Optional, Tuple

from utils.logging_utils import log_debug
from core.i18n import tr

_DEFAULT_GLOSSARY_PROMPT = (
    "You are the creative {target_lang} localization lead for {{GAME_NAME}}. "
    "When given a source term (and optional context line), craft a vivid {target_lang} translation that matches the game's universe, tone, and established terminology. "
    "Describe the in-game meaning in one short note – explain what the term represents or how it is used, without grammar labels, part-of-speech hints, or plural/singular remarks. "
    "Respond strictly in JSON with keys \"translation\" and \"notes\"; keep both values in {target_lang}."
)


class GlossaryPromptManager:
    """
    Handles reading/writing of prompts.json and glossary.md.
    Provides caching to avoid repeated file reads.
    """

    def __init__(self, mw, main_handler, glossary_manager) -> None:
        """Initialize a new instance."""
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
        """Internal helper to plugin dir."""
        return Path("plugins", plugin_name, "translation_prompts") if plugin_name else None

    def _fallback_dir(self) -> Path:
        """Internal helper to fallback dir."""
        return Path("translation_prompts")

    def _resolve_file(self, filename: str, plugin_name: Optional[str]) -> Optional[Path]:
        """Internal helper to resolve file."""
        candidates = [
            self._plugin_dir(plugin_name) and self._plugin_dir(plugin_name) / filename,
            Path("plugins", "common", "defaults") / filename,
            self._fallback_dir() / filename,
        ]
        return next((p for p in candidates if p and p.exists()), None)

    def _project_dir(self) -> Optional[Path]:
        """Directory of the open project, or None when no project is open."""
        manager = getattr(self._mw, "project_manager", None)
        project_dir = getattr(manager, "project_dir", None) if manager else None
        if not project_dir:
            return None
        try:
            return Path(project_dir)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _newest_glossary_in(directory: Path) -> Optional[Path]:
        """Existing glossary file in ``directory``; the newer one if both exist."""
        json_p = directory / "glossary.json"
        md_p = directory / "glossary.md"
        if json_p.exists() and md_p.exists():
            return md_p if md_p.stat().st_mtime > json_p.stat().st_mtime else json_p
        if json_p.exists():
            return json_p
        if md_p.exists():
            return md_p
        return None

    def _resolve_glossary_path(self, plugin_name: Optional[str]) -> Optional[Path]:
        """Resolve the glossary path for the open project.

        The glossary belongs to the PROJECT, not to the plugin: it lives in the
        project directory and is looked up **only** there. Two projects never
        share a glossary, and recreating a project starts from an empty one.

        Returns ``<project>/glossary.json`` even when the file does not exist yet
        (it is created on first write). Without an open project there is no
        glossary path at all.
        """
        project_dir = self._project_dir()
        if project_dir is None:
            return None
        return self._newest_glossary_in(project_dir) or (project_dir / "glossary.json")

    # ── Public: load prompts (cached) ───────────────────────────────────

    def load_prompts(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Returns (system_prompt, glossary_text).
        Uses cached values when available. Shows QMessageBox on errors.
        """
        from PyQt6.QtWidgets import QMessageBox

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
            QMessageBox.critical(self._mw, tr('AI Translation'), tr('prompts.json not found.'))
            return None, None

        try:
            prompt_data = json.loads(prompts_path.read_text("utf-8"))
        except Exception as e:
            QMessageBox.critical(self._mw, tr('AI Translation'), f"Failed to load prompts.json: {e}")
            return None, None

        system_prompt = self._extract_system_prompt(prompt_data)
        if not system_prompt:
            QMessageBox.critical(self._mw, tr('AI Translation'), tr('System prompt not defined in prompts.json.'))
            return None, None

        glossary_path = self._resolve_glossary_path(plugin_name)

        glossary_text = ""
        if glossary_path and glossary_path.exists():
            try:
                glossary_text = glossary_path.read_text("utf-8").strip()
            except Exception as e:
                QMessageBox.warning(self._mw, tr('AI Translation'), f"Failed to read glossary: {e}")

        self._current_glossary_path = glossary_path
        self._current_plugin_name = plugin_name
        self._glossary_manager.load_from_text(
            plugin_name=plugin_name, glossary_path=glossary_path, raw_text=glossary_text
        )
        self._update_glossary_highlighting()

        h._cached_system_prompt = system_prompt
        h._cached_glossary = glossary_text
        return system_prompt, glossary_text

    def bind_glossary_for_write(self) -> Optional[Path]:
        """Bind the manager to the project glossary file, creating it if absent.

        For callers about to write a lot of entries (the build pipeline). The
        path is resolved **fresh** rather than taken from ``_current_glossary_path``:
        the cached prompt state may have been filled in at startup, before a
        project was open, in which case it pins ``None`` and every write would be
        kept in memory and lost on the next reload.

        Returns the bound path, or ``None`` when there is no project to bind to.
        """
        plugin_name = getattr(self._mw, "active_game_plugin", None)
        path = self._resolve_glossary_path(plugin_name)
        if path is None:
            return None

        if not path.exists():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("[]\n", encoding="utf-8")
                log_debug(f"GlossaryPromptManager: created project glossary at {path}")
            except OSError as exc:
                log_debug(f"GlossaryPromptManager: cannot create glossary at {path}: {exc}")
                return None

        # Already bound to this exact file: leave the in-memory state alone
        # rather than re-reading and discarding anything not yet flushed.
        if self._glossary_manager.glossary_path == path:
            self._current_glossary_path = path
            self._current_plugin_name = plugin_name
            return path

        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            log_debug(f"GlossaryPromptManager: cannot read glossary at {path}: {exc}")
            return None

        self._current_glossary_path = path
        self._current_plugin_name = plugin_name
        self._main_handler._cached_glossary = text
        self._glossary_manager.load_from_text(
            plugin_name=plugin_name, glossary_path=path, raw_text=text
        )
        self._update_glossary_highlighting()
        return path

    def initialize_highlighting(self) -> None:
        """Pre-load glossary text for syntax highlighting without a full prompts load."""
        plugin_name = getattr(self._mw, "active_game_plugin", None)
        
        glossary_path = self._resolve_glossary_path(plugin_name)

        glossary_text = ""
        if glossary_path and glossary_path.exists():
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

        raw_template = None
        if self._cached_glossary_prompt_template and self._cached_glossary_prompt_plugin == plugin_name:
            raw_template = self._cached_glossary_prompt_template
        else:
            prompts_path = self._resolve_file("prompts.json", plugin_name)
            if prompts_path:
                self.current_prompts_path = prompts_path

            raw_template = _DEFAULT_GLOSSARY_PROMPT
            if prompts_path:
                try:
                    prompt_data = json.loads(prompts_path.read_text("utf-8"))
                    extracted = self._extract_glossary_prompt(prompt_data)
                    if extracted:
                        raw_template = extracted
                except Exception as e:
                    log_debug(f"Glossary prompt template read error: {e}")

            self._cached_glossary_prompt_template = raw_template
            self._cached_glossary_prompt_plugin = plugin_name

        target_lang = getattr(self._mw, 'target_language', 'Ukrainian')
        if not isinstance(target_lang, str):
            target_lang = 'Ukrainian'

        from utils.utils import resolve_target_language_prompt
        resolved_template = resolve_target_language_prompt(raw_template, target_lang)
        return resolved_template, self._current_glossary_path

    # ── Public: save a prompt section ───────────────────────────────────

    def save_prompt_section(self, section: str, field: str, value: str) -> bool:
        """Persists one field of prompts.json and updates local caches."""
        plugin_name = getattr(self._mw, "active_game_plugin", None)
        if not plugin_name:
            return False

        plugin_dir = self._plugin_dir(plugin_name)
        if not plugin_dir:
            return False
        
        target_path = plugin_dir / "prompts.json"

        # If local prompts.json doesn't exist, materialize it from defaults
        if not target_path.exists():
            current_resolved = self._resolve_file("prompts.json", plugin_name)
            if current_resolved and current_resolved.exists():
                try:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    import shutil
                    shutil.copy2(current_resolved, target_path)
                    log_debug(f"Copied default prompts to {target_path} for on-demand writing.")
                except Exception as exc:
                    log_debug(f"Failed to copy default prompts to {target_path}: {exc}")

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            data: Dict = json.loads(target_path.read_text("utf-8")) if target_path.exists() else {}
            if not isinstance(data, dict):
                data = {}
        except Exception as exc:
            log_debug(f"Failed to load prompts file {target_path}: {exc}")
            return False

        section_data = data.setdefault(section, {})
        if not isinstance(section_data, dict):
            section_data = {}
            data[section] = section_data
        section_data[field] = value

        try:
            target_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.current_prompts_path = target_path
        except Exception as exc:
            log_debug(f"Failed to write prompts file {target_path}: {exc}")
            return False

        if section == "glossary" and field == "prompt_template":
            self._cached_glossary_prompt_template = value
        if section == "translation" and field == "system_prompt":
            self._main_handler._cached_system_prompt = value
        return True

    # ── Internal helpers ─────────────────────────────────────────────────

    def _extract_system_prompt(self, payload: Dict) -> Optional[str]:
        """Internal helper to extract system prompt."""
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
        """Internal helper to extract glossary prompt."""
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
        """Internal helper to ensure glossary loaded."""
        if glossary_text is None:
            return
        self._glossary_manager.load_from_text(
            plugin_name=plugin_name, glossary_path=glossary_path, raw_text=glossary_text
        )
        self._update_glossary_highlighting()

    def _update_glossary_highlighting(self) -> None:
        """Internal helper to update the glossary highlighting."""
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
