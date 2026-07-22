"""Single source of truth for "who speaks this line".

Both the editor's Speaker field (``ui/updaters/string_settings_updater.py``) and
the Story Timeline window (``core/story_inspector.py``) must answer this question
identically — a row that shows ``None`` in the editor may not show a speaker in
the timeline, and vice versa.

The resolution order (highest authority first) is:

1. the manual assignment stored in the project block metadata
   (``character_assignments[str(string_idx)]``),
2. the MemePalace cached context speaker for the row's BMG id,
3. a fuzzy lookup of the line in the marked-up script
   (``ScriptSpeakerFinder`` via ``AIPromptComposer._find_speaker_in_script``).

Step 3 must be fed the **original** game text, never the edited/translated text:
the script is in the source language, so matching a translation against it
produces false positives (this was the cause of the editor/timeline mismatch).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from utils.logging_utils import log_debug

_UNKNOWN = ("", "unknown", "none")


@dataclass(frozen=True)
class SpeakerResolution:
    """Resolved speaker for one row. ``name`` is None when nothing is known."""
    name: Optional[str] = None
    source: str = "none"          # 'assignment' | 'mempalace' | 'script' | 'none'
    script_line: Optional[int] = None

    def __bool__(self) -> bool:
        return bool(self.name)


def _is_known(value: Any) -> bool:
    return bool(value) and str(value).strip().lower() not in _UNKNOWN


def get_original_text(mw: Any, block_idx: int, string_idx: int) -> str:
    """The row's ORIGINAL (untranslated) text — what the script is written in."""
    try:
        data = mw.data_store.data
        if data and 0 <= block_idx < len(data):
            block = data[block_idx]
            if 0 <= string_idx < len(block):
                return block[string_idx] or ""
    except Exception:
        pass
    return ""


def _resolve_block_label(mw: Any, block_idx: int, proj_b_idx: int, project: Any) -> str:
    try:
        blocks = project.blocks if project else []
        if proj_b_idx < len(blocks):
            return blocks[proj_b_idx].name
    except Exception:
        pass
    try:
        names = getattr(mw.data_store, "block_names", None) or {}
        desc = names.get(str(block_idx))
        if desc and "Message ID" in desc:
            return desc.partition("(")[0].strip()
    except Exception:
        pass
    return f"Block_{block_idx}"


def resolve_speaker_for_string(
    mw: Any,
    block_idx: int,
    string_idx: int,
    composer: Any = None,
    need_script_line: bool = False,
) -> SpeakerResolution:
    """Resolve the speaker for one row (see module docstring for the order).

    ``composer`` is an ``AIPromptComposer``; when omitted it is taken from
    ``mw.translation_handler.prompt_composer``. Set ``need_script_line`` to also
    run the (more expensive) script lookup when an earlier source already
    answered — the Story Timeline needs the script line for chapter lookup.
    """
    if block_idx in (-1, -2, -3) or string_idx < 0:
        return SpeakerResolution()

    project = None
    try:
        pm = getattr(mw, "project_manager", None)
        project = getattr(pm, "project", None) if pm else None
    except Exception:
        project = None

    name: Optional[str] = None
    source = "none"

    # 1. manual assignment in project metadata
    proj_b_idx = block_idx
    if project is not None:
        try:
            proj_b_idx = (getattr(mw, "block_to_project_file_map", {}) or {}).get(block_idx, block_idx)
            blocks = project.blocks
            if proj_b_idx < len(blocks):
                assigned = (blocks[proj_b_idx].metadata or {}).get(
                    "character_assignments", {}
                ).get(str(string_idx), "")
                if _is_known(assigned):
                    name, source = str(assigned).strip(), "assignment"
        except Exception as exc:
            log_debug(f"speaker_resolution: assignment lookup failed: {exc}")

    if composer is None:
        handler = getattr(mw, "translation_handler", None)
        composer = getattr(handler, "prompt_composer", None) if handler else None

    # 2. MemePalace cached context
    if name is None and composer is not None:
        try:
            client = composer._get_mempalace_client()
            if client is not None:
                label = _resolve_block_label(mw, block_idx, proj_b_idx, project)
                ctx = client.get_cached_context(f"{label}_Str_{string_idx}", None)
                if ctx and _is_known(ctx.get("speaker")):
                    name, source = str(ctx["speaker"]).strip(), "mempalace"
        except Exception as exc:
            log_debug(f"speaker_resolution: mempalace lookup failed: {exc}")

    # 3. marked-up script (ORIGINAL text only)
    script_line: Optional[int] = None
    if composer is not None and (name is None or need_script_line):
        try:
            result = composer._find_speaker_in_script(
                block_idx, string_idx, get_original_text(mw, block_idx, string_idx)
            )
            if isinstance(result, (tuple, list)) and len(result) == 2:
                raw_spk, lines_str = result
                if lines_str and str(lines_str) != "NONE":
                    try:
                        script_line = int(str(lines_str).split(",")[0].strip())
                    except (TypeError, ValueError):
                        script_line = None
                if name is None and _is_known(raw_spk):
                    name, source = str(raw_spk).strip(), "script"
        except Exception as exc:
            log_debug(f"speaker_resolution: script lookup failed: {exc}")

    return SpeakerResolution(name=name, source=source, script_line=script_line)
