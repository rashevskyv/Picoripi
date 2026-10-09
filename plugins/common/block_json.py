"""Text a workspace script exported as JSON blocks: ``{"file": ..., "blocks": [{"name": ..., "strings": [...],
<anything else the build needs>}]}``. The plugin shows each block's ``strings`` and writes them back into the
same JSON; every other key stays as it was. Used where the game's own text format cannot be edited in place
(No More Heroes, MadWorld: each text box carries a picture of its own glyphs, which the build draws anew).
The Wii HOME Menu table (``home.csv``) is handled too."""
import copy
from typing import Any, Dict, List, Optional, Tuple

from plugins.base_game_rules import BaseGameRules
from plugins.common.wii_home_menu import HomeCsv, is_home_csv


def is_block_json(obj: Any) -> bool:
    return isinstance(obj, dict) and isinstance(obj.get("blocks"), list) and all(
        isinstance(b, dict) and isinstance(b.get("strings"), list) for b in obj["blocks"])


class BlockJsonRules(BaseGameRules):
    """Loads and saves block JSON files and the HOME Menu table; the game plugin adds tags and checks."""

    text_extension = ".json"
    text_label = "Text blocks"

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._doc: Optional[dict] = None
        self._home: Optional[HomeCsv] = None

    def get_file_formats(self) -> list:
        from core.formats import FileFormat
        return [FileFormat((self.text_extension,), "json", self.text_label),
                FileFormat((".csv",), "bytes", "Wii HOME Menu messages")]

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[List[List[str]], Dict[str, str]]:
        self._doc, self._home = None, None
        if isinstance(json_obj, (bytes, bytearray)):
            if is_home_csv(bytes(json_obj)):
                self._home = HomeCsv(bytes(json_obj))
                return [self._home.messages], {"0": "HOME Menu"}
            return [[]], {}
        if not is_block_json(json_obj):
            return super().load_data_from_json_obj(json_obj)
        self._doc = copy.deepcopy(json_obj)
        blocks = [[str(s) for s in block["strings"]] for block in json_obj["blocks"]]
        names = {str(i): str(block.get("name") or f"Block {i + 1}") for i, block in enumerate(json_obj["blocks"])}
        return blocks or [[]], names

    def prepare_save_context(self, context) -> None:
        """The file is written over its newest existing version (the translation, else the source)."""
        import json
        for raw in context.existing_versions():
            if is_home_csv(raw):
                self._home, self._doc = HomeCsv(raw), None
            else:
                try:
                    doc = json.loads(bytes(raw).decode("utf-8-sig"))
                except ValueError:
                    return
                if is_block_json(doc):
                    self._doc, self._home = doc, None
            return

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        if self._home is not None:
            texts = data[0] if data and isinstance(data[0], list) else []
            old = self._home.messages
            return self._home.build([str(texts[i]) if i < len(texts) and texts[i] is not None else old[i]
                                     for i in range(len(old))])
        if self._doc is None:
            return super().save_data_to_json_obj(data, block_names)
        doc = copy.deepcopy(self._doc)
        for block, texts in zip(doc["blocks"], data or []):
            old = block["strings"]
            block["strings"] = [str(texts[i]) if i < len(texts) and texts[i] is not None else old[i]
                                for i in range(len(old))]
        return doc

    def reset_runtime_state(self) -> None:
        self._doc, self._home = None, None
