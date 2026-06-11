# core/saved_translations_manager.py
import json
import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

from utils.logging_utils import log_info, log_error, log_debug

class SavedTranslationsManager:
    def __init__(self, main_window: Any):
        self.mw = main_window

    def _get_saved_translations_path(self) -> Optional[Path]:
        if hasattr(self.mw, 'project_manager') and self.mw.project_manager and self.mw.project_manager.project_dir:
            return Path(self.mw.project_manager.project_dir) / "saved_translations.json"
        elif hasattr(self.mw, 'data_store') and self.mw.data_store.json_path:
            p = Path(self.mw.data_store.json_path)
            return p.parent / f"{p.stem}_saved_translations.json"
        return None

    def _get_string_unique_key(self, block_idx: int, string_idx: int) -> str:
        block_source_file = "single_file"
        block_internal_key = ""
        if hasattr(self.mw, 'block_to_project_file_map') and self.mw.block_to_project_file_map:
            p_b_idx = self.mw.block_to_project_file_map.get(block_idx)
            if p_b_idx is not None and self.mw.project_manager and self.mw.project_manager.project and p_b_idx < len(self.mw.project_manager.project.blocks):
                block = self.mw.project_manager.project.blocks[p_b_idx]
                block_source_file = block.source_file
                block_internal_key = block.internal_key or ""
        elif hasattr(self.mw, 'data_store') and self.mw.data_store.block_names:
            block_source_file = self.mw.data_store.block_names.get(str(block_idx), f"block_{block_idx}")
            
        return f"{block_source_file}::{block_internal_key}::{string_idx}"

    def load_all_saved_translations(self) -> Dict[str, str]:
        path = self._get_saved_translations_path()
        if not path or not path.exists():
            return {}
        try:
            with path.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log_error(f"Failed to load saved translations: {e}")
            return {}

    def save_all_saved_translations(self, data: Dict[str, str]) -> bool:
        path = self._get_saved_translations_path()
        if not path:
            return False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            log_error(f"Failed to save translations to {path}: {e}")
            return False

    def has_saved_translation(self, block_idx: int, string_idx: int) -> bool:
        key = self._get_string_unique_key(block_idx, string_idx)
        translations = self.load_all_saved_translations()
        return key in translations

    def get_saved_translation(self, block_idx: int, string_idx: int) -> Optional[str]:
        key = self._get_string_unique_key(block_idx, string_idx)
        translations = self.load_all_saved_translations()
        return translations.get(key)

    def save_translation(self, block_idx: int, string_idx: int, text: str) -> None:
        if not text or not text.strip():
            return
        key = self._get_string_unique_key(block_idx, string_idx)
        translations = self.load_all_saved_translations()
        translations[key] = text
        self.save_all_saved_translations(translations)
        log_info(f"Saved translation for key {key}")

    def save_translations_bulk(self, block_idx: int, string_indices_and_texts: List[Tuple[int, str]]) -> None:
        translations = self.load_all_saved_translations()
        any_saved = False
        for string_idx, text in string_indices_and_texts:
            if text and text.strip():
                key = self._get_string_unique_key(block_idx, string_idx)
                translations[key] = text
                any_saved = True
        if any_saved:
            self.save_all_saved_translations(translations)
            log_info(f"Bulk saved {len(string_indices_and_texts)} translations for block {block_idx}")
