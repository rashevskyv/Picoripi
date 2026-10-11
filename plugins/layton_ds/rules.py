"""Professor Layton DS plugin (Curious Village, Pandora's Box, Lost Future, Spectre's Call).

The project's source folder is the workspace's ``source``: the game's own text files at their paths in the
cartridge's file system (compressed as the game keeps them): ``.pcm`` / ``.plz`` / ``.cpck`` packs of texts and
scripts, loose ``.gds`` / ``.txt`` files, Level-5 ``.cb`` scripts in Spectre's Call. Saving writes the same
file, compressed again, into the translation folder; the workspace's build puts them into the ROM.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug

from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .formats import Document, FormatError, Row

# Japanese speaker labels of Lost Future and Spectre's Call -> English names (the main cast; any other label is
# shown as it is). A leading "OP" marks the opening movie's lines.
SPEAKERS = {
    "レイトン": "Layton", "ルーク": "Luke", "レミ": "Emmy", "フローラ": "Flora", "チェルミー": "Chelmey",
    "バートン": "Barton", "ナレーション": "Narrator", "ドン・ポール": "Don Paolo", "デスコール": "Descole",
    "ジャン": "Jean", "クレア": "Claire", "ランドール": "Randall", "ブレア": "Bloom", "ダルストン": "Dalston",
    "ローザ": "Rosa", "ビル": "Bill", "ステラ": "Stella", "ヘンリー": "Henry", "シャロア": "Angela",
    "ジェイク": "Jake", "ミ○": "Mystery", "手紙": "Letter",
}


class GameRules(BaseGameRules):
    """Professor Layton (DS): the plugin reads each file by what it holds (see ``formats``)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._located: Dict[int, Optional[Tuple[str, Document]]] = {}
        self._utf8_for: Optional[Tuple[str, bool]] = None

    def get_display_name(self) -> str:
        return "Professor Layton (DS)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".pcm", ".plz", ".dlz", ".cpck", ".gds", ".cbin", ".cdat", ".lbin", ".cb", ".txt"), "bytes",
                           "Professor Layton (DS) texts"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def _utf8(self) -> bool:
        """True for the Android HD ports (the source folder has ``data-en``): their text is UTF-8."""
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        source = ((getattr(getattr(pm, "project", None), "metadata", None) or {}).get("source_path") or "")
        if self._utf8_for is None or self._utf8_for[0] != source:
            self._utf8_for = (source, bool(source) and (Path(source) / "data-en").is_dir())
        return self._utf8_for[1]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            return [Document(self._last_loaded, "", self._utf8()).texts()], {}
        except (FormatError, ValueError, IndexError, UnicodeDecodeError) as error:
            log_debug(f"layton_ds: no texts in this file ({error})")
            return [[]], {}

    def prepare_save_context(self, context) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        strings = data[0] if data else []
        return Document(source, "", self._utf8()).build([str(s) for s in strings])

    def reset_runtime_state(self) -> None:
        self._located.clear()
        self._save_source = self._last_loaded = None
        self._utf8_for = None

    # -- where a string comes from ---------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[str, Document]]:
        """``(relative path, parsed source file)``, cached."""
        if block_idx in self._located:
            return self._located[block_idx]
        found = None
        try:
            pm = getattr(self.mw, "project_manager", None) if self.mw else None
            block_map = getattr(self.mw, "block_to_project_file_map", None) or {}
            block = pm.project.blocks[block_map.get(block_idx, block_idx)]
            rel = str(block.source_file).replace("\\", "/")
            path = Path(pm.get_absolute_path(block.source_file))
            found = (rel, Document(path.read_bytes(), rel))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError, FormatError) as error:
            log_debug(f"layton_ds: no file behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def _row(self, block_idx: int, string_idx: int) -> Optional[Tuple[str, Row]]:
        located = self._locate(block_idx)
        if not located:
            return None
        rel, document = located
        try:
            return rel, document.rows[int(string_idx)]
        except (IndexError, TypeError, ValueError):
            return None

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._row(block_idx, string_idx)
        if not found:
            return None
        rel, row = found
        return {"file": rel, "member": row.member, "label": row.speaker or row.label, "kind": row.kind}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._row(block_idx, string_idx)
        if not found:
            return {}
        _rel, row = found
        if row.kind == "dialogue":
            return {"content_role": "Dialogue",
                    "role_instruction": "A line said in the message window; the speaker is named. Layton is a "
                                        "courteous English gentleman, Luke his eager apprentice. Keep the game's "
                                        "markup (<T>, <W>, @p, <'e>) as it is."}
        return {"content_role": "Game text",
                "role_instruction": "A text the game shows: a puzzle title or question, a hint, an item or a menu "
                                    "line. Keep the game's markup as it is."}

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._row(block_idx, string_idx)
        if not found or not found[1].speaker:
            return None
        label = found[1].speaker
        return SPEAKERS.get(label[2:] if label.startswith("OP") else label, label)

    def is_placeholder_speaker(self, name: str) -> bool:
        return False

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._row(block_idx, string_idx)
        if not found:
            return {}
        rel, row = found
        return {"resource": rel, "label": row.member or Path(rel).stem}

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution"}

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
