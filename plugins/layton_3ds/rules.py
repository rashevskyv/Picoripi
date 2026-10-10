"""Professor Layton 3DS plugin (Miracle Mask, Azran Legacy, vs. Phoenix Wright): XSCR scripts, XF fonts, IMGC images."""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from plugins.base_game_rules import BaseGameRules
from utils.logging_utils import log_debug

from .config import DEFAULT_LINES_PER_PAGE, PLUGIN_PREFIX, PROBLEM_DEFINITIONS
from .xscr import FormatError, Script, parse

# Japanese speaker labels of the scripts -> the English names (the main cast; any other label is shown as it is).
SPEAKERS = {
    "レイトン": "Layton", "ルーク": "Luke", "レミ": "Emmy", "ランド": "Randall", "シャロア": "Angela", "ヘンリー": "Henry",
    "ダルストン": "Dalston", "ブルーマイル": "Bloom", "グロスキー": "Grosky", "デスコール": "Descole", "奇跡の紳士": "Masked Gentleman",
    "ヤングレイトン": "Young Layton", "ヤングランド": "Young Randall", "ヤングシャロア": "Young Angela", "ヤングヘンリー": "Young Henry",
    "ナレーション中": "Narrator", "ナレーション": "Narrator", "コイン": "Hint coin", "アイテム": "Item", "手紙": "Letter",
    "サーハイマン": "Sycamore", "アーリア": "Aurora", "ブロネフ": "Bronev", "レイモンド": "Raymond",
    "ナルホド": "Phoenix", "マヨイ": "Maya", "サイバンチョ": "Judge", "マホーネ": "Espella", "ジーケン": "Barnham",
    "ジョドーラ検事": "Darklaw", "ジョドーラ": "Darklaw", "ストーリーテラー": "Storyteller", "チェルミー": "Chelmey",
    "司書": "Librarian", "騎士": "Knight", "ロンドンサイバンチョ": "Judge (London)", "ロンドン検事": "Prosecutor (London)",
    "カトリー": "Katrielle", "ノア": "Ernest", "シャーロ": "Sherl",
    "10倍コイン": "Hint coin x10", "スペシャルコイン": "Special coin",
}
# folder of txt/<lang>/ -> (role, instruction); every other folder holds dialogue
_ROLES = {
    "30": ("System message", "A short system message or prompt (save, hint coins, items found)."),
    "40": ("Journal entry", "A journal entry: a title row, then the entry text."),
    "50": ("Puzzle text", "A puzzle: its title, the task, the hints, the answer and the correct / wrong replies."),
    "52": ("Puzzle help", "How to enter the answer of a puzzle on the touch screen."),
    "80": ("Minigame text", "Text of a minigame: names, descriptions, instructions."),
    "81": ("Minigame text", "Text of a minigame: names, descriptions, instructions."),
    "82": ("Minigame text", "Text of a minigame: names, descriptions, instructions."),
    "83": ("Minigame text", "Text of a minigame: names, descriptions, instructions."),
}
_DIALOGUE = ("Dialogue", "A line said in the message window; the speaker is named. Layton is a courteous English "
             "gentleman, Luke his eager apprentice. Keep the game's markup (<T>, <W8>, <M.../...>, {'e}) as it is.")
_NAME = ("Name", "A name the game shows on its own: a puzzle title or type, a minigame name, the game title.")


def folder_of(rel_path: str) -> str:
    """``50`` for ``txt/uk/50/50_000001.xs``, ``res`` for the definitions file."""
    parts = rel_path.replace("\\", "/").split("/")
    return parts[2] if len(parts) > 3 and parts[0] == "txt" else parts[0]


class GameRules(BaseGameRules):
    """Professor Layton on 3DS: Miracle Mask and Azran Legacy (Level-5 ``lt5`` / ``lt6`` engine), vs. Phoenix Wright
    (the same engine with Capcom's trial scripts) and Layton's Mystery Journey (the ``lt6`` engine again, English in
    ``txt/en`` and UTF-8). The project's source folder is the workspace's ``source``: the English XSCR scripts
    ``txt/<uk|en>/<chapter>/*.xs`` and the definitions file ``res/uk/*_def*.xs`` at their paths in the game archive,
    the fonts ``fnt/[eu]/*.xf`` and the language image packs. Saving writes the same files into the translation folder;
    the workspace's build puts them into the archive.
    """

    problem_prefix = PLUGIN_PREFIX
    problem_definitions = PROBLEM_DEFINITIONS

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._save_source: Optional[bytes] = None
        self._last_loaded: Optional[bytes] = None
        self._located: Dict[int, Optional[Tuple[str, Script]]] = {}
        self._utf8_for: Optional[Tuple[str, bool]] = None

    def get_display_name(self) -> str:
        return "Professor Layton (3DS)"

    def get_file_formats(self) -> list:
        from core.formats import DEFAULT_FORMATS, FileFormat
        return [FileFormat((".xs",), "bytes", "Level-5 XSCR scripts"), *DEFAULT_FORMATS]

    # -- load and save ---------------------------------------------------------

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        self._last_loaded = bytes(json_obj)
        try:
            return [parse(self._last_loaded, self._encoding()).texts()], {}
        except (FormatError, UnicodeDecodeError, ValueError) as error:
            log_debug(f"layton_3ds: not an XSCR script ({error})")
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
        return parse(source, self._encoding()).build([str(s) for s in strings])

    def reset_runtime_state(self) -> None:
        self._located.clear()
        self._save_source = self._last_loaded = None
        self._utf8_for = None

    def _encoding(self) -> Optional[str]:
        """``utf-8`` for Mystery Journey (its English is ``txt/en``), else detected per file (Shift-JIS). Once per
        source folder: a plain-ASCII file of Mystery Journey must still be written as UTF-8."""
        pm = getattr(self.mw, "project_manager", None) if self.mw else None
        source = ((getattr(getattr(pm, "project", None), "metadata", None) or {}).get("source_path") or "")
        if self._utf8_for is None or self._utf8_for[0] != source:
            self._utf8_for = (source, bool(source) and (Path(source) / "txt" / "en").is_dir())
        return "utf-8" if self._utf8_for[1] else None

    # -- where a string comes from ---------------------------------------------

    def _locate(self, block_idx: int) -> Optional[Tuple[str, Script]]:
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
            found = (rel, parse(path.read_bytes(), self._encoding()))
        except (AttributeError, IndexError, KeyError, OSError, TypeError, ValueError) as error:
            log_debug(f"layton_3ds: no script behind block {block_idx}: {error}")
        self._located[block_idx] = found
        return found

    def _row(self, block_idx: int, string_idx: int):
        located = self._locate(block_idx)
        if not located:
            return None
        rel, script = located
        try:
            return rel, script.rows[int(string_idx)]
        except (IndexError, TypeError, ValueError):
            return None

    def get_message_attributes(self, block_idx: int, string_idx: int) -> Optional[Dict[str, Any]]:
        found = self._row(block_idx, string_idx)
        if not found:
            return None
        rel, row = found
        return {"file": rel, "opcode": row.opcode, "line_id": row.line_id, "label": row.speaker, "kind": row.kind}

    def get_translation_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._row(block_idx, string_idx)
        if not found:
            return {}
        rel, row = found
        role, instruction = _NAME if row.kind == "name" else _ROLES.get(folder_of(rel), _DIALOGUE)
        return {"content_role": role, "role_instruction": instruction}

    def get_speaker_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._row(block_idx, string_idx)
        if not found or not found[1].speaker:
            return None
        return SPEAKERS.get(found[1].speaker, found[1].speaker)

    def is_placeholder_speaker(self, name: str) -> bool:
        return False

    def get_scene_context_for_string(self, block_idx: int, string_idx: int) -> Dict[str, Any]:
        found = self._row(block_idx, string_idx)
        if not found:
            return {}
        rel = found[0]
        return {"resource": rel, "label": Path(rel).stem, "chapter": folder_of(rel)}

    def get_ai_flow_group_for_string(self, block_idx: int, string_idx: int) -> Optional[str]:
        found = self._row(block_idx, string_idx)
        return f"{found[0]}#{found[1].line_id}" if found else None

    def get_capabilities(self) -> Set[str]:
        return {"speaker_attribution"}

    def get_editor_page_size(self) -> int:
        return DEFAULT_LINES_PER_PAGE
