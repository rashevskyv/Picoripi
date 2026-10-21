"""Silent Hill 2 (Switch port data): the PC message files, with the Ukrainian glyph table for the translation.

The source file (English) keeps the PC charset (byte b shows b + 0x20, Windows-1252). The translation file uses the
glyph table of the Switch font atlas: byte = atlas cell, so Cyrillic is 0x80..0x9F and so on (``mes.decode_uk``).
Saving writes the translation, so it always uses the Ukrainian table.
"""
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.i18n import tr
from plugins.silent_hill2_pc import mes
from plugins.silent_hill2_pc.rules import GameRules as PcGameRules
from utils.logging_utils import log_debug, log_warning

SH23DS_TARGET = "sh23ds"


HEADER = b"\x00\x80"  # every message starts with it; it is not text


TAILS = (b"\x00\x80", b"\x00\x90")  # the next header, or the end marker before the next message


def _split(message: bytes):
    """(head, body, tail): the bytes shown as text are the body; head and tail come back on save."""
    head = HEADER if message[:2] == HEADER else b""
    body = message[len(head):]
    tail = b""
    if len(body) >= 2 and body[-2:] in TAILS:
        tail, body = body[-2:], body[:-2]
    return head, body, tail


class GameRules(PcGameRules):
    """Silent Hill 2 (Switch port, Ukrainian translation)."""

    def __init__(self, main_window_ref=None):
        super().__init__(main_window_ref)
        self._role = "source"
        self._save_copy: Optional[bytes] = None

    def get_display_name(self) -> str:
        return "Silent Hill 2 (Switch, Ukrainian)"

    def get_platforms(self) -> List[Dict[str, str]]:
        return [{"id": "3ds", "label": tr("Nintendo 3DS")}]

    def get_build_targets(self) -> List[Dict[str, Any]]:
        return [{"id": SH23DS_TARGET, "label": tr("sh23ds 3DS port: Ukrainian messages and font"),
                 "platforms": ["3ds"], "kind": "files"}]

    def build_target(self, target_id: str, source_dir: str, translation_dir: str, output_dir: str,
                     progress: Callable[[int, str], None], is_cancelled: Callable[[], bool]) -> str:
        if target_id != SH23DS_TARGET:
            return super().build_target(target_id, source_dir, translation_dir, output_dir, progress, is_cancelled)
        from . import sh23ds
        return sh23ds.build(translation_dir, output_dir, progress, is_cancelled)

    def set_load_role(self, role: str) -> None:
        self._role = role

    def migrate_session_snapshot(self, snapshot: dict) -> dict:
        """Not migrated: the Switch rows are the message bodies (the head and tail bytes are not shown), so an old
        row cannot be mapped back to its bytes from the session alone. Returned without the layout marker, so the
        session is not restored and the project opens from its files (the bytes there are unchanged)."""
        return snapshot

    def load_data_from_json_obj(self, json_obj: Any) -> Tuple[list, dict]:
        if not isinstance(json_obj, (bytes, bytearray)):
            return super().load_data_from_json_obj(json_obj)
        data = bytes(json_obj)
        self._last_loaded = data
        try:
            messages = mes.split(data)
        except ValueError as error:
            log_debug(f"silent_hill2_switch: not a message file ({error})")
            return [[]], {}
        decode = mes.decode_uk if self._role == "translation" else mes.decode
        return [[decode(_split(m)[1]) for m in messages]], {"0": "messages"}

    def prepare_save_context(self, context) -> None:
        """The translation copy (newest version) gives the bytes of a message that cannot be encoded."""
        versions = list(context.existing_versions())
        self._save_source = versions[-1] if versions else None
        self._save_copy = versions[0] if len(versions) > 1 else None

    def save_data_to_json_obj(self, data: list, block_names: dict) -> Any:
        template = self._save_copy if self._save_copy is not None else self._save_source
        if template is None:
            template = self._last_loaded
        if template is None:
            return super().save_data_to_json_obj(data, block_names)
        originals = mes.split(template)
        lines = (data[0] if data else []) or []
        if len(lines) != len(originals):
            log_warning(f"silent_hill2_switch: message count changed ({len(lines)} for {len(originals)}); file not saved")
            return template
        out = []
        for index, (original, text) in enumerate(zip(originals, lines)):
            head, _, tail = _split(original)
            try:
                out.append(head + mes.encode_uk(text) + tail)
            except ValueError as error:
                log_warning(f"silent_hill2_switch: message {index} kept as it was: {error}")
                out.append(original)
        return mes.build(out)
