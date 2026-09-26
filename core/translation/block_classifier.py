"""Block and string classifier for phased translation.

Distinguishes chronological story dialogue (mapped via MemePalace or categorized as story)
from remaining semantic blocks (system menus, shops, item descriptions, UI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from utils.logging_utils import log_debug
from core.tag_utils import iter_all_strings


@dataclass
class ClassifiedProjectItems:
    """Container for partitioned project items ready for phased AI translation."""
    story_items: List[Dict[str, Any]] = field(default_factory=list)
    semantic_items: List[Dict[str, Any]] = field(default_factory=list)
    story_temp_id_map: Dict[int, Tuple[int, int]] = field(default_factory=dict)
    semantic_temp_id_map: Dict[int, Tuple[int, int]] = field(default_factory=dict)

    @property
    def total_count(self) -> int:
        return len(self.story_items) + len(self.semantic_items)

    @property
    def has_story(self) -> bool:
        return bool(self.story_items)

    @property
    def has_semantic(self) -> bool:
        return bool(self.semantic_items)


def _is_semantic_name(name: str) -> bool:
    """Check if a block or folder name suggests system/shop/utility content."""
    lowered = (name or "").lower()
    semantic_keywords = (
        "system", "shop", "menu", "ui", "hud", "option", "setting",
        "inventory", "item", "item_desc", "prompt", "save", "title",
        "credit", "manual", "tutorial", "misc", "sound", "debug"
    )
    return any(keyword in lowered for keyword in semantic_keywords)


def _is_story_name(name: str) -> bool:
    """Check if a block or folder name explicitly suggests story/script content."""
    lowered = (name or "").lower()
    story_keywords = (
        "story", "script", "event", "dialogue", "cutscene", "chapter",
        "scenario", "quest", "main", "intro", "prologue", "epilogue"
    )
    return any(keyword in lowered for keyword in story_keywords)


def classify_project_items(data_source: list, mw: Any = None) -> ClassifiedProjectItems:
    """Classify all strings in the project into story items and semantic items.

    Story items are ordered chronologically based on MemePalace script lines when available.
    Semantic items are grouped for parallel block translation.
    """
    if not isinstance(data_source, list) or not data_source:
        return ClassifiedProjectItems()

    client = None
    wing_name = ""
    block_names_map: Dict[int, str] = {}

    if mw:
        try:
            translator = getattr(mw, "translation_handler", None)
            if translator and hasattr(translator, "prompt_composer"):
                composer = translator.prompt_composer
                client = composer._get_mempalace_client()
                wing_name = composer._get_wing_name()
                for b_idx in range(len(data_source)):
                    lbl = composer._get_block_label(b_idx)
                    if isinstance(lbl, str) and lbl.strip():
                        block_names_map[b_idx] = lbl
        except Exception as exc:
            log_debug(f"classify_project_items: failed to obtain MemePalace client: {exc}")

    ds = getattr(mw, "data_store", None) if mw else None
    ds_names = getattr(ds, "block_names", {}) if ds else {}
    for b_idx in range(len(data_source)):
        if b_idx not in block_names_map:
            name_val = ds_names.get(str(b_idx)) or ds_names.get(b_idx) if isinstance(ds_names, dict) else None
            if isinstance(name_val, str) and name_val.strip():
                block_names_map[b_idx] = name_val
            else:
                block_names_map[b_idx] = f"Block_{b_idx + 1}"

    # Check virtual folder names if available
    block_folder_names: Dict[int, str] = {}
    if mw and hasattr(mw, "project") and getattr(mw.project, "virtual_folders", None):
        try:
            for folder in mw.project.virtual_folders:
                folder_name = getattr(folder, "name", "")
                for b_id in getattr(folder, "block_ids", []):
                    # Resolve block id to physical index if possible
                    for idx, blk in enumerate(getattr(mw.project, "blocks", [])):
                        if getattr(blk, "id", None) == b_id or getattr(blk, "name", "") == b_id:
                            block_folder_names[idx] = folder_name
        except Exception:
            pass

    story_scored: List[Tuple[Dict[str, Any], int, Tuple[int, int]]] = []
    semantic_raw: List[Tuple[Dict[str, Any], Tuple[int, int]]] = []

    has_any_script_line = False

    for b_idx, s_idx, original_text in iter_all_strings(data_source):
        text_str = str(original_text or "")
        block_label = block_names_map.get(b_idx, f"Block_{b_idx + 1}")
        folder_label = block_folder_names.get(b_idx, "")
        bmg_id = f"{block_label}_Str_{s_idx}"

        script_line = 999999
        if client and wing_name:
            try:
                mapping = client.get_script_mapping(wing_name, bmg_id)
                if mapping and mapping.get("script_line") is not None:
                    script_line = int(mapping["script_line"])
                    has_any_script_line = True
            except Exception:
                pass

        item_payload = {
            "block_idx": b_idx,
            "string_idx": s_idx,
            "text": text_str,
        }

        # Decision rule:
        # 1. If script mapping exists and is < 999999, it belongs to chronological Story.
        if script_line < 999999:
            story_scored.append((item_payload, script_line, (b_idx, s_idx)))
        elif _is_semantic_name(block_label) or _is_semantic_name(folder_label):
            # Explicitly semantic by name/folder
            semantic_raw.append((item_payload, (b_idx, s_idx)))
        elif _is_story_name(block_label) or _is_story_name(folder_label):
            # Explicitly story by name/folder (assign default order based on index)
            pseudo_line = (b_idx * 10000) + s_idx
            story_scored.append((item_payload, pseudo_line, (b_idx, s_idx)))
        else:
            # Fallback: if project has script lines, unmapped lines are non-story/semantic
            if has_any_script_line or client:
                semantic_raw.append((item_payload, (b_idx, s_idx)))
            else:
                # If project has no script lines at all, treat all as story in original order
                pseudo_line = (b_idx * 10000) + s_idx
                story_scored.append((item_payload, pseudo_line, (b_idx, s_idx)))

    # Sort story items chronologically
    story_scored.sort(key=lambda item: item[1])

    story_items: List[Dict[str, Any]] = []
    story_temp_id_map: Dict[int, Tuple[int, int]] = {}
    for temp_id, (payload, _, coords) in enumerate(story_scored):
        item_copy = dict(payload)
        item_copy["id"] = temp_id
        story_items.append(item_copy)
        story_temp_id_map[temp_id] = coords

    semantic_items: List[Dict[str, Any]] = []
    semantic_temp_id_map: Dict[int, Tuple[int, int]] = {}
    for temp_id, (payload, coords) in enumerate(semantic_raw):
        item_copy = dict(payload)
        item_copy["id"] = temp_id
        semantic_items.append(item_copy)
        semantic_temp_id_map[temp_id] = coords

    return ClassifiedProjectItems(
        story_items=story_items,
        semantic_items=semantic_items,
        story_temp_id_map=story_temp_id_map,
        semantic_temp_id_map=semantic_temp_id_map,
    )
