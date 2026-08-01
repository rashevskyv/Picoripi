"""Aggregate every available piece of per-line story context into one bundle.

This powers the Story Timeline window (the editor's "S" button). It is
game-agnostic: it talks to the MemePalace client and the AI prompt composer for
narrative data, and reaches the active game only through the plugin hooks
``get_scene_context_for_string`` / ``get_ai_flow_context_for_string`` on
``mw.current_game_rules``.

The single entry point is :func:`build_timeline_inspection`, which returns a
plain dict (see its docstring) that the dialog renders. All heavy queries are
wrapped so a failure in one source never sinks the rest of the bundle.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from core.speaker_resolution import SpeakerResolution, resolve_speaker_for_string
from utils.logging_utils import log_debug


# --- composer acquisition (mirrors ui/main_window/mempalace_actions.py) --------

def _get_composer(mw: Any):
    handler = getattr(mw, "translation_handler", None)
    composer = getattr(handler, "prompt_composer", None) if handler else None
    if composer is not None:
        return composer
    try:
        from handlers.translation.ai_prompt_composer import AIPromptComposer

        class _DummyHandler:
            def __init__(self, mw):
                self.mw = mw
                self.data_processor = getattr(mw, "data_processor", None)
                self.ui_updater = getattr(mw, "ui_updater", None)
                self._glossary_manager = None
                h = getattr(mw, "translation_handler", None)
                if h:
                    self._glossary_manager = getattr(h, "_glossary_manager", None)

            def __getattr__(self, name):
                return getattr(self.mw, name)

        return AIPromptComposer(_DummyHandler(mw))
    except Exception as exc:  # pragma: no cover - defensive
        log_debug(f"story_inspector: composer unavailable: {exc}")
        return None


def _relation_display(relation: str) -> str:
    return {
        "addresses_informally": "addresses informally (ти)",
        "addresses_respectfully": "addresses respectfully (ви)",
        "addresses_formally": "addresses formally (ви)",
    }.get(relation, relation.replace("_", " "))


def _parse_chapter_events(ai_summary: str) -> Optional[List[dict]]:
    if not ai_summary:
        return None
    cleaned = ai_summary.strip()
    if cleaned.startswith("```"):
        rows = cleaned.splitlines()
        if rows and rows[0].startswith("```"):
            rows = rows[1:]
        if rows and rows[-1].startswith("```"):
            rows = rows[:-1]
        cleaned = "\n".join(rows).strip()
    try:
        parsed = json.loads(cleaned)
    except Exception:
        return None
    return parsed if isinstance(parsed, list) else None


def _character_lookup_variants(name: str) -> List[str]:
    """Progressively relaxed forms of a character label for glossary lookup.

    ``"SPRING GORON #3"`` -> ``["SPRING GORON #3", "SPRING GORON"]``.
    """
    base = (name or "").strip()
    if not base:
        return []
    variants = [base]
    without_number = re.sub(r"\s*#\s*\d+\s*$", "", base).strip()
    if without_number and without_number not in variants:
        variants.append(without_number)
    without_parens = re.sub(r"\([^)]*\)", "", without_number or base).strip()
    if without_parens and without_parens not in variants:
        variants.append(without_parens)
    return variants


def _event_summary(ev: dict) -> str:
    return (
        ev.get("summary_translated")
        or ev.get("summary_ukrainian")
        or ev.get("summary")
        or ""
    )


def build_timeline_inspection(
    mw: Any, block_idx: int, string_idx: int
) -> Dict[str, Any]:
    """Assemble the full context bundle for one editor row.

    Returns a dict with (all optional / best-effort):
        block_idx, string_idx, block_label, text, window_type
        speaker: {raw, translated, line}
        source: 'mempalace' | 'chapter' | 'flow' | 'none'
        timeline: [{title, summary, location, order, current}]
        current_index: int | None
        event: {title, summary, location, participants, interactions} | None
        character_voices: [{name, personality, speech_style, advice}]
        relations: [{source, target, relation, display}]
        addressees: [{name, relation}]         # speaker -> X
        scene: {game-truth dict from the plugin}
        flow_summary: str | None
        chapter: {title, current_event, events} | None
        story_context: str | None
        empty: bool
    """
    bundle: Dict[str, Any] = {
        "block_idx": block_idx,
        "string_idx": string_idx,
        "source": "none",
        "timeline": [],
        "current_index": None,
        "character_voices": [],
        "relations": [],
        "addressees": [],
        "scene": {},
        "empty": True,
    }

    composer = _get_composer(mw)
    if composer is None:
        return bundle

    # --- current line text -----------------------------------------------------
    text = ""
    try:
        text, _ = mw.data_processor.get_current_string_text(block_idx, string_idx)
    except Exception:
        text = ""
    bundle["text"] = text or ""

    def _call(fn, *a, default=None, **kw):
        try:
            return fn(*a, **kw)
        except Exception as exc:
            log_debug(f"story_inspector: {getattr(fn, '__name__', fn)} failed: {exc}")
            return default

    block_label = _call(composer._get_block_label, block_idx, default=str(block_idx))
    wing_name = _call(composer._get_wing_name, default="")
    bundle["block_label"] = block_label

    client = _call(composer._get_mempalace_client)

    # --- speaker -------------------------------------------------------------
    # Resolved through the SAME chain the editor's Speaker field uses, so the two
    # can never disagree (assignment -> MemePalace -> marked script).
    # NB: a resolution with no speaker is falsy but may still carry the script
    # line the chapter lookup needs, so test for None explicitly.
    resolution = _call(
        resolve_speaker_for_string, mw, block_idx, string_idx,
        composer=composer, need_script_line=True,
    )
    if resolution is None:
        resolution = SpeakerResolution()
    raw_speaker = resolution.name
    line_num = resolution.script_line
    if raw_speaker:
        bundle["speaker"] = {
            "raw": raw_speaker,
            "translated": _call(composer._translate_speaker, raw_speaker, default=raw_speaker),
            "line": line_num,
            "source": resolution.source,
        }

    # --- addressee (plugin hook) ----------------------------------------------
    # Who the line is spoken TO. The speaker resolved just above is handed over
    # so the plugin does not repeat that work.
    rules = getattr(mw, "current_game_rules", None)
    get_addressee = getattr(rules, "get_addressee_for_string", None)
    if callable(get_addressee):
        addressee = _call(get_addressee, block_idx, string_idx, speaker=raw_speaker)
        if addressee:
            bundle["addressee"] = {
                "raw": addressee,
                "translated": _call(
                    composer._translate_speaker, addressee, default=addressee
                ),
            }

    # --- game-truth scene (plugin hook) ---------------------------------------
    if rules is not None:
        scene = _call(rules.get_scene_context_for_string, block_idx, string_idx, default={})
        if isinstance(scene, dict) and scene:
            bundle["scene"] = scene
            if scene.get("flow_summary"):
                bundle["flow_summary"] = scene["flow_summary"]

    # --- window type (game-truth attribute) -----------------------------------
    if rules is not None:
        ctx = _call(rules.get_translation_context_for_string, block_idx, string_idx, default={})
        if isinstance(ctx, dict) and ctx.get("window_type"):
            bundle["window_type"] = ctx["window_type"]

    # --- narrative timeline: MemePalace first ---------------------------------
    event = None
    if client is not None:
        event = _call(client.get_story_event_for_game_string, str(block_idx), string_idx)
    if event is not None:
        bundle["source"] = "mempalace"
        bundle["empty"] = False
        bundle["event"] = {
            "title": getattr(event, "event_title", ""),
            "summary": getattr(event, "summary", ""),
            "location": getattr(event, "location", ""),
            "participants": list(getattr(event, "participants", []) or []),
            "interactions": list(getattr(event, "interactions", []) or []),
        }
        doc_id = getattr(event, "document_id", None)
        cur_order = getattr(event, "event_order", None)
        events = _call(client.get_story_events, doc_id, default=[]) or []
        timeline = []
        current_index = None
        for i, item in enumerate(sorted(events, key=lambda e: getattr(e, "event_order", 0))):
            is_cur = getattr(item, "event_order", None) == cur_order
            if is_cur:
                current_index = i
            timeline.append({
                "title": getattr(item, "event_title", ""),
                "summary": getattr(item, "summary", ""),
                "location": getattr(item, "location", ""),
                "order": getattr(item, "event_order", i),
                "current": is_cur,
            })
        bundle["timeline"] = timeline
        bundle["current_index"] = current_index

        # character voices for the speaker(s)
        voices = _call(client.get_character_profiles_for_game_string,
                       str(block_idx), string_idx, doc_id, default=[]) or []
        bundle["character_voices"] = [
            {
                "name": getattr(p, "speaker_name", ""),
                "personality": getattr(p, "personality", ""),
                "speech_style": getattr(p, "speech_style", ""),
                "advice": getattr(p, "translation_advice", ""),
            }
            for p in voices
        ]

    # --- fallback narrative timeline: chapter ai_summary ----------------------
    chapter = None
    if line_num is not None and client is not None:
        chapter_info = _call(client.get_chapter_for_line, wing_name, line_num)
        if chapter_info:
            events_list = _parse_chapter_events(chapter_info.get("ai_summary") or "")
            current_event = None
            ch_events = []
            if events_list:
                for ev in events_list:
                    if not isinstance(ev, dict) or "event_name" not in ev:
                        continue
                    is_cur = (
                        isinstance(ev.get("start_line"), int)
                        and isinstance(ev.get("end_line"), int)
                        and ev["start_line"] <= line_num <= ev["end_line"]
                    )
                    row = {
                        "name": ev.get("event_name", "Untitled"),
                        "summary": _event_summary(ev),
                        "start_line": ev.get("start_line"),
                        "end_line": ev.get("end_line"),
                        "current": is_cur,
                    }
                    if is_cur:
                        current_event = row
                    ch_events.append(row)
            chapter = {
                "title": chapter_info.get("title", ""),
                "num": chapter_info.get("num"),
                "current_event": current_event,
                "events": ch_events,
            }
            bundle["chapter"] = chapter
            # If MemePalace had no event, drive the timeline from the chapter.
            if bundle["source"] == "none" and ch_events:
                bundle["source"] = "chapter"
                bundle["empty"] = False
                bundle["timeline"] = [
                    {
                        "title": e["name"],
                        "summary": e["summary"],
                        "location": "",
                        "order": idx,
                        "current": e["current"],
                    }
                    for idx, e in enumerate(ch_events)
                ]
                bundle["current_index"] = next(
                    (i for i, e in enumerate(ch_events) if e["current"]), None
                )

    # --- relations + addressee (from the marked speaker) ----------------------
    if raw_speaker and raw_speaker != "NONE" and client is not None:
        detected = [s.strip().upper() for s in raw_speaker.split(",") if s.strip()]
        relations = _call(client.get_relations, wing_name, default=[]) or []
        rel_out, addressees = [], []
        for r in relations:
            src = (r.get("source") or "").strip()
            tgt = (r.get("target") or "").strip()
            rel = r.get("relation") or ""
            if any(spk in src.upper() or spk in tgt.upper() for spk in detected):
                rel_out.append({
                    "source": src, "target": tgt,
                    "relation": rel, "display": _relation_display(rel),
                    "source_tr": _call(composer._translate_speaker, src, default=src),
                    "target_tr": _call(composer._translate_speaker, tgt, default=tgt),
                })
                if rel.startswith("addresses") and any(spk in src.upper() for spk in detected):
                    addressees.append({
                        "name": _call(composer._translate_speaker, tgt, default=tgt),
                        "raw": tgt,
                        "relation": _relation_display(rel),
                    })
        bundle["relations"] = rel_out
        bundle["addressees"] = addressees

    # --- raw story context string (BMG/flow blend from the composer) ----------
    story_context = _call(composer._fetch_story_context, block_idx, string_idx, text)
    if story_context:
        bundle["story_context"] = story_context

    # --- glossary matches -----------------------------------------------------
    glossary_entries: List[dict] = []
    seen_originals = set()
    glossary_manager = None
    h = getattr(mw, "translation_handler", None)
    if h:
        glossary_manager = getattr(h, "_glossary_manager", None)

    def _add_entry(entry) -> None:
        if entry is None:
            return
        original = getattr(entry, "original", None)
        if not original or original in seen_originals:
            return
        seen_originals.add(original)
        glossary_entries.append({
            "original": original,
            "translation": getattr(entry, "translation", "") or "",
            "notes": getattr(entry, "notes", "") or "",
        })

    def _lookup_character(name: str) -> None:
        """Glossary lookup for a character label.

        Script speaker labels carry disambiguating suffixes the glossary does not
        (``SPRING GORON #3`` vs the ``Spring Goron`` entry), so retry with those
        stripped — otherwise the character's notes silently never show up.
        """
        for variant in _character_lookup_variants(name):
            entry = _call(glossary_manager.get_entry, variant)
            if entry is not None:
                _add_entry(entry)
                return

    if glossary_manager is not None:
        if text:
            for entry in _call(glossary_manager.get_relevant_terms, text, default=[]) or []:
                _add_entry(entry)
        if raw_speaker:
            for spk in str(raw_speaker).split(","):
                if spk.strip():
                    _lookup_character(spk)
        if event is not None:
            for part in getattr(event, "participants", []) or []:
                if str(part).strip():
                    _lookup_character(str(part))
    bundle["glossary_entries"] = glossary_entries

    # empty only if truly nothing useful surfaced
    if any(bundle.get(k) for k in ("timeline", "event", "chapter", "scene",
                                   "story_context", "flow_summary", "glossary_entries")):
        bundle["empty"] = False
    return bundle
