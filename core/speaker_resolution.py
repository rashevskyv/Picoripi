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

import os
import re
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


def _glossary_translator(composer: Any):
    """Build a fast raw->display speaker translator from the active glossary.

    The editor Speaker field translates a script-derived speaker through the
    glossary (``AIPromptComposer._translate_speaker``); the virtual folders must
    use the identical mapping so a row's folder label matches its field value.
    Returns an idempotent function: names that are not glossary originals (e.g. a
    projection heading or an already-translated manual name) pass through.
    """
    table: dict[str, str] = {}
    try:
        main_handler = getattr(composer, "main_handler", None)
        glossary_manager = getattr(main_handler, "_glossary_manager", None)
        entries = glossary_manager.get_entries() if glossary_manager else []
        for entry in entries or ():
            original = str(getattr(entry, "original", "") or "").strip()
            translation = str(getattr(entry, "translation", "") or "").split(";")[0].strip()
            if original and translation:
                table.setdefault(original.casefold(), translation)
    except Exception as exc:
        log_debug(f"speaker_resolution: glossary translator unavailable: {exc}")

    def translate(name: str) -> str:
        if not name:
            return name
        return table.get(name.strip().casefold(), name)

    return translate


def _projection_speaker_rows(mw: Any, projection: Any) -> dict:
    """Map every projection speaker relation to its physical ``(block, string)``."""
    rows: dict = {}
    speakers = getattr(projection, "speakers", ()) or ()
    data = getattr(getattr(mw, "data_store", None), "data", []) or []
    handler = getattr(mw, "list_selection_handler", None)
    for speaker in speakers:
        name = str(getattr(speaker, "name", "") or "").strip()
        if not name:
            continue
        for mapping in getattr(speaker, "mappings", ()) or ():
            row = None
            try:
                b_idx = int(mapping.game_block_id)
                s_idx = int(mapping.string_index)
                if 0 <= b_idx < len(data) and 0 <= s_idx < len(data[b_idx]):
                    row = (b_idx, s_idx)
            except (TypeError, ValueError, IndexError):
                row = None
            if row is None and handler is not None:
                try:
                    row = handler.resolve_bmg_id_to_indices(mapping.game_string_id)
                except Exception:
                    row = None
            if row is not None:
                rows.setdefault(row, name)
    return rows


def _legacy_assignment_rows(mw: Any) -> dict:
    """Map legacy ``character_assignments`` to physical ``(block, string)`` rows."""
    rows: dict = {}
    pm = getattr(mw, "project_manager", None)
    project = getattr(pm, "project", None) if pm else None
    blocks = getattr(project, "blocks", None)
    if not isinstance(blocks, list):
        return rows
    block_map = getattr(mw, "block_to_project_file_map", {}) or {}
    project_to_data = {proj_idx: data_idx for data_idx, proj_idx in block_map.items()}
    for proj_idx, block in enumerate(blocks):
        assignments = getattr(block, "metadata", {}).get("character_assignments", {})
        if not isinstance(assignments, dict):
            continue
        data_idx = project_to_data.get(proj_idx, proj_idx)
        for s_idx_str, name in assignments.items():
            if _is_known(name):
                try:
                    rows[(data_idx, int(s_idx_str))] = str(name).strip()
                except (TypeError, ValueError):
                    continue
    return rows


def _script_line_to_speaker(composer: Any) -> dict:
    """Parse the marked script once into ``{line_number: SPEAKER heading}``."""
    find_path = getattr(composer, "_find_script_path", None)
    script_path = find_path() if callable(find_path) else None
    if not script_path or not os.path.exists(script_path):
        return {}
    cached = getattr(composer, "_line_to_speaker_cache", None)
    if cached and getattr(composer, "_line_to_speaker_path", None) == script_path:
        return cached
    lines = getattr(composer, "_script_lines_cache", None)
    if not lines:
        try:
            with open(script_path, "r", encoding="cp1252", errors="replace") as fh:
                lines = fh.readlines()
        except Exception:
            with open(script_path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
    line_to_speaker: dict = {}
    current = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            continue
        if stripped.isupper() and len(stripped) >= 2 and re.match(r"^[A-Z0-9\s#]+$", stripped):
            current = stripped
        if current:
            line_to_speaker[idx + 1] = current
    try:
        composer._line_to_speaker_cache = line_to_speaker
        composer._line_to_speaker_path = script_path
    except Exception:
        pass
    return line_to_speaker


def _stored_script_speaker_rows(mw: Any, composer: Any) -> dict:
    """Cheap batch: rows with a stored ``script_line`` mapping -> raw speaker.

    One query for the whole ``script_mappings`` table (including chapterless
    rows, which the editor field also sees via ``get_script_mapping``), joined
    against the parsed speaker headings. This is the fast, always-on marked-script
    source; the per-row fuzzy match (``resolve_script_speaker_raw_rows``) is the
    deeper, opt-in fallback for rows that have no stored mapping.
    """
    rows: dict = {}
    if composer is None or not hasattr(composer, "_get_mempalace_client"):
        return rows
    try:
        line_to_speaker = _script_line_to_speaker(composer)
        if not line_to_speaker:
            return rows
        client = composer._get_mempalace_client()
        if client is None or not hasattr(client, "get_all_script_mappings"):
            return rows
        wing_name = composer._get_wing_name() if hasattr(composer, "_get_wing_name") else ""
        mappings = client.get_all_script_mappings(wing_name)
        if not isinstance(mappings, list):
            return rows
        handler = getattr(mw, "list_selection_handler", None)
        for mapping in mappings:
            if not hasattr(mapping, "get"):
                continue
            bmg_id = mapping.get("bmg_id")
            script_line = mapping.get("script_line")
            if not bmg_id or not script_line:
                continue
            raw = line_to_speaker.get(script_line)
            if not _is_known(raw):
                continue
            row = None
            if handler is not None:
                try:
                    row = handler.resolve_bmg_id_to_indices(bmg_id)
                except Exception:
                    row = None
            if row is not None and row not in rows:
                rows[row] = str(raw).strip()
    except Exception as exc:
        log_debug(f"speaker_resolution: stored-script pool failed: {exc}")
    return rows


def resolve_script_speaker_raw_rows(
    mw: Any, composer: Any, skip_rows: Any = None
) -> dict:
    """Map every non-empty row to its marked-script speaker (raw, untranslated).

    Uses the exact same per-row resolver the editor Speaker field uses
    (``AIPromptComposer._find_speaker_in_script``, which consults the stored
    ``script_line`` mapping first and falls back to a fuzzy text match), so the
    virtual Speaker folders resolve a row to the identical speaker the field
    shows. Returns the raw source-language name; the caller applies the glossary.

    This is the expensive step (one lookup per row), so the result is meant to be
    cached by the block-list updater and only recomputed when the marked script
    or its mappings change (see ``invalidate_mempalace_story_cache``). ``skip_rows``
    lets the caller omit rows already resolved by a higher-authority source
    (e.g. the projection) to save work.
    """
    rows: dict = {}
    if composer is None or not hasattr(composer, "_find_speaker_in_script"):
        return rows
    skip = skip_rows if isinstance(skip_rows, (set, frozenset)) else set(skip_rows or ())
    data = getattr(getattr(mw, "data_store", None), "data", []) or []
    for b_idx, block in enumerate(data):
        for s_idx, text in enumerate(block or ()):
            if (b_idx, s_idx) in skip:
                continue
            if not isinstance(text, str) or not text.strip():
                continue
            try:
                result = composer._find_speaker_in_script(b_idx, s_idx, text)
            except Exception:
                result = None
            if isinstance(result, (tuple, list)) and len(result) >= 1:
                raw = result[0]
                if isinstance(raw, str) and _is_known(raw) and raw != "NONE":
                    rows[(b_idx, s_idx)] = raw.strip()
    return rows


def build_speaker_pool(
    mw: Any,
    composer: Any = None,
    projection: Any = None,
    script_raw_rows: Any = None,
) -> dict:
    """The single source of truth mapping every row to its resolved speaker.

    Both the editor's Speaker field and the virtual Speaker/Story folders must
    read from this one pool so they can never disagree (a row that shows a
    speaker in the editor must live in that speaker's folder, not in ``None``).

    Resolution priority per row (highest authority first):

    1. manual override (``story_context_assignments`` speaker; an explicit
       ``None`` forces the row out of every speaker folder),
    2. normalized marked-script speaker relations (the ``StoryVirtualProjection``),
    3. legacy ``character_assignments``,
    4. the row's stored marked-script ``script_line`` speaker (cheap batch), then
    5. a deep per-row fuzzy match for rows still unresolved (``script_raw_rows``),
       the same ``_find_speaker_in_script`` the editor field uses.

    Steps 1-4 are cheap and always run. Step 5 is expensive (one script lookup
    per row) so it is opt-in: pass ``script_raw_rows`` (a precomputed
    ``{row: raw_name}`` from ``resolve_script_speaker_raw_rows``) only from the
    user-triggered "rebuild virtual folders" action, and cache it. All script
    speaker names are glossary-translated to match the editor field's display.

    Returns ``{(block_idx, string_idx): display_name}`` for every resolved row.
    Rows absent from the result belong to the ``None`` folder.
    """
    if composer is None:
        handler = getattr(mw, "translation_handler", None)
        composer = getattr(handler, "prompt_composer", None) if handler else None

    translate = _glossary_translator(composer)

    # Highest authority first; a row keeps the first source that claims it.
    resolved: dict = {}

    # Every source is glossary-translated to one canonical DISPLAY name so the
    # editor field and the folders show the identical string for a row (e.g. a
    # projection heading "TWILIGHT PRINCESS" and a script match both become
    # "Сутінкова Принцеса" and merge into one folder). Translating an already
    # translated or non-glossary name is a no-op.

    # 1. manual overrides (an explicit "None" blocks every lower source).
    from core.story_context_overrides import iter_story_context_overrides
    for block_idx, string_idx, assignment in iter_story_context_overrides(mw):
        if "speaker" not in assignment:
            continue
        name = str(assignment.get("speaker") or "").strip()
        resolved[(block_idx, string_idx)] = translate(name) if _is_known(name) else None

    def fill(source_rows: dict) -> None:
        for row, name in source_rows.items():
            if row not in resolved and name:
                resolved[row] = translate(name)

    # 2. normalized marked-script speakers.
    if projection is not None:
        fill(_projection_speaker_rows(mw, projection))
    # 3. legacy assignments.
    fill(_legacy_assignment_rows(mw))
    # 4. stored marked-script line mappings (cheap batch).
    fill(_stored_script_speaker_rows(mw, composer))
    # 5. deep per-row fuzzy match (opt-in via the ⟳ button).
    if script_raw_rows:
        fill(script_raw_rows)
    # 6. the game's own data, for rows nothing above claimed. Last on purpose:
    # it is authoritative about the game but knows nothing of the user's
    # corrections, and those must win.
    fill(_plugin_speaker_rows(mw))

    return {row: name for row, name in resolved.items() if name}


def _plugin_speaker_rows(mw: Any) -> dict:
    """Speakers the active plugin can read out of the game's own data.

    Optional: a plugin without such a source answers nothing and the pool is
    exactly what it was before.
    """
    rules = getattr(mw, "current_game_rules", None)
    getter = getattr(rules, "get_speaker_for_string", None)
    if not callable(getter):
        return {}
    data = getattr(getattr(mw, "data_store", None), "data", None)
    if not isinstance(data, list):
        return {}

    # A code the script has already been merged onto becomes that name here, so
    # every consumer -- editor field, folders, prompts -- sees the same one.
    aliases = _speaker_aliases(mw)

    rows: dict = {}
    for block_idx, block in enumerate(data):
        if not isinstance(block, (list, tuple)):
            continue
        for string_idx, value in enumerate(block):
            # A blank row says nothing and belongs to nobody. Attributing one
            # inflates every speaker's count with padding.
            if not str(value or "").strip():
                continue
            try:
                name = getter(block_idx, string_idx)
            except Exception:
                continue
            # Only a real string counts: a plugin that answers with something
            # else must not be able to fill the pool with nonsense.
            if isinstance(name, str) and name.strip():
                resolved_name = name.strip()
                rows[(block_idx, string_idx)] = aliases.get(resolved_name, resolved_name)
    return rows


def _speaker_aliases(mw: Any) -> dict:
    """The project's code -> name map, if one has been merged from a script."""
    from core.speaker_alias_merge import load_speaker_aliases

    manager = getattr(mw, "project_manager", None)
    return load_speaker_aliases(getattr(manager, "project_dir", None) if manager else None)


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
