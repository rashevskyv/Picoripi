"""Silent Hill 2 (PC; the same data files serve the Switch homebrew port) plugin: the game's message files.

Each ``data\\etc\\message\\*.mes`` file is one project block; its messages are the block's lines. A line is the
message as text in the PC font charset (byte b shows the character b + 0x20 in Windows-1252): 0x00 is a space, 0x07 an
apostrophe, the bytes the font has no character for are tags ``{XX}``
(kept as it is). Saving rebuilds the file: the messages are encoded again and the table is rewritten, so a
longer message is allowed. A line that cannot be encoded keeps its original bytes (a warning is logged).
"""
from typing import Any, Callable, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug, log_info, log_warning

from . import mes, mes_legacy
from .config import PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .tag_manager import TagManager

# Layout of the message rows a session holds. 2: the rows read the table's word 1 (the message table fix). A session
# without this layout was written before the fix; migrate_session_snapshot maps its rows.
SESSION_DATA_LAYOUT = 2


class GameRules(BaseGameRules):
    """Silent Hill 2 (PC data, Enhanced Edition packs or the retail data; Switch homebrew reads the same files)."""

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS
    tag_manager_class = TagManager
    tag_style = "curly"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Silent Hill 2 (PC / Switch data)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".mes",), "bytes", "Silent Hill 2 message files"), *DEFAULT_FORMATS]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        try:
            messages = mes.split(data)
        except ValueError as error:
            log_debug(f"silent_hill2_pc: not a message file ({error})")
            return [[]], {}
        return [[mes.decode(m) for m in messages]], {"0": "messages"}

    def prepare_save_context(self, context) -> None:
        """Every save is built from the source file (the last version offered)."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        source = self._save_source if self._save_source is not None else self._last_loaded
        if source is None:
            return super().save_data_to_json_obj(data, block_names)
        originals = mes.split(source)
        lines = (data[0] if data else []) or []
        if len(lines) != len(originals):
            log_warning(f"silent_hill2_pc: message count changed ({len(lines)} for {len(originals)}); file not saved")
            return source
        out = []
        for index, (original, text) in enumerate(zip(originals, lines)):
            if text == mes.decode(original):
                out.append(original)
                continue
            try:
                out.append(mes.encode(text))
            except ValueError as error:
                log_warning(f"silent_hill2_pc: message {index} kept as it was: {error}")
                out.append(original)
        return mes.build(out)

    def _legacy_codec(self) -> Tuple[Callable[[str], bytes], Callable[[bytes], str]]:
        """(encode the old rows, decode the new messages) for this plugin's role."""
        return mes_legacy.legacy_encode, mes.decode

    def session_data_layout(self) -> Optional[int]:
        return SESSION_DATA_LAYOUT

    def migrate_session_snapshot(self, snapshot: dict) -> dict:
        """Maps a session saved before the message table fix (another or no data_layout) to the current rows.

        Each block's rows are re-read from their bytes (mes_legacy.migrate_block). Edits move with their message.
        An edit to the merged row is kept only when its byte count did not change; otherwise it is dropped, with a
        log line. Selection, undo and problem marks of a migrated block are cleared. Returns the snapshot.
        """
        snapshot["data_layout"] = self.session_data_layout()
        data = snapshot.get("data")
        if not isinstance(data, list):
            return snapshot
        old_encode, new_decode = self._legacy_codec()
        edits = dict(snapshot.get("edited_data") or {})
        moved: Dict[Tuple[int, int], str] = {}
        migrated = set()
        for b, rows in enumerate(data):
            if not isinstance(rows, list) or not rows or not all(isinstance(r, str) for r in rows):
                continue
            try:
                new_rows, row_map, notes, cut = mes_legacy.migrate_block(rows, old_encode, new_decode)
            except ValueError as error:
                log_warning(f"silent_hill2: block {b} kept its rows (not migrated): {error}")
                continue
            migrated.add(b)
            data[b] = new_rows
            log_info(f"silent_hill2: block {b} migrated to the current message table ({', '.join(notes)})")
            for (eb, r), text in edits.items():
                if eb != b:
                    continue
                targets = row_map.get(r, [])
                if not targets:
                    log_warning(f"silent_hill2: block {b} edit on the offset row {r} dropped")
                elif len(targets) == 1:
                    moved[(b, targets[0])] = text
                else:
                    try:
                        edited_bytes = old_encode(text)
                    except ValueError:
                        edited_bytes = None
                    if edited_bytes is None or cut is None or len(edited_bytes) != len(old_encode(rows[r])):
                        log_warning(f"silent_hill2: block {b} merged-row edit dropped (its length changed)")
                    else:
                        moved[(b, targets[0])] = new_decode(edited_bytes[:cut])
                        moved[(b, targets[1])] = new_decode(edited_bytes[cut:])
        if migrated:
            snapshot["edited_data"] = {k: v for k, v in edits.items() if k[0] not in migrated}
            snapshot["edited_data"].update(moved)
            snapshot["undo_stack"] = []
            snapshot["redo_stack"] = []
            snapshot["problems_per_subline"] = {
                k: v for k, v in (snapshot.get("problems_per_subline") or {}).items()
                if str(k).split(",")[0] not in {str(b) for b in migrated}
            }
            if snapshot.get("current_block_idx") in migrated:
                snapshot["current_string_idx"] = -1
                snapshot["selected_string_indices"] = []
                snapshot["last_selected_string_index"] = -1
        return snapshot

    def get_editor_page_size(self) -> int:
        return 1

    def get_spellcheck_ignore_pattern(self) -> str:
        return r"\{[0-9A-Fa-f]{2}\}"

    def get_tag_tooltip(self, tag: str) -> str:
        return "Game code (byte) kept as it is." if tag.startswith("{") else ""
