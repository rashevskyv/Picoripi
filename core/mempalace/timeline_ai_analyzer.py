"""AI analysis of the normalized marked script into dialogue-addressable events."""

from __future__ import annotations

import hashlib
import json

from PyQt6.QtCore import QThread, pyqtSignal

from core.translation.providers import ProviderResponse
from utils.logging_utils import log_ai_traffic, log_error


class StoryTimelineAIAnalyzerWorker(QThread):
    progress = pyqtSignal(int, int, str)
    log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, client, ai_provider, document_id: int, target_lang="Ukrainian", mw=None):
        super().__init__()
        self.client = client
        self.ai_provider = ai_provider
        self.document_id = int(document_id)
        self.target_lang = target_lang or "Ukrainian"
        self.mw = mw
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        try:
            nodes = self.client.get_story_timeline(self.document_id)
            dialogues = [node for node in nodes if node.node_type == "dialogue"]
            if not dialogues:
                self.finished.emit(False, "No marked dialogue nodes were found.")
                return
            if not self.ai_provider:
                self.finished.emit(False, "No AI provider is configured.")
                return

            aliases = {node.id: f"d{index:05d}" for index, node in enumerate(dialogues, 1)}
            node_by_id = {node.id: node for node in nodes}
            chunks = [dialogues[i:i + 40] for i in range(0, len(dialogues), 40)]
            events = []
            for chunk_index, chunk in enumerate(chunks):
                if self.is_cancelled:
                    self.finished.emit(False, "Timeline analysis was cancelled.")
                    return
                current = chunk_index + 1
                self.progress.emit(current - 1, len(chunks), f"Analyzing story part {current} of {len(chunks)}…")
                prompt = _build_prompt(
                    chunk, aliases, node_by_id, nodes, self.target_lang
                )
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a game narrative analyst. Infer sequential story events from a "
                            "marked script. Preserve the supplied dialogue IDs exactly and cover every ID."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ]
                log_ai_traffic(self.mw, "mempalace_semantic_timeline", messages)
                response: ProviderResponse = self.ai_provider.translate(messages, session=None)
                log_ai_traffic(
                    self.mw, "mempalace_semantic_timeline", messages,
                    response_text=response.text,
                )
                parsed = parse_timeline_response(response.text, {aliases[node.id] for node in chunk})
                events.extend(parsed)

            alias_to_node = {alias: node_id for node_id, alias in aliases.items()}
            contexts = []
            for event_order, event in enumerate(events):
                previous_title = events[event_order - 1]["event_title"] if event_order else ""
                next_title = events[event_order + 1]["event_title"] if event_order + 1 < len(events) else ""
                for alias in event["dialogue_ids"]:
                    contexts.append({
                        "dialogue_node_id": alias_to_node[alias],
                        "event_order": event_order,
                        "event_title": event["event_title"],
                        "summary": event["summary"],
                        "location": event["location"],
                        "participants": event["participants"],
                        "interactions": event["interactions"],
                        "previous_event": previous_title,
                        "next_event": next_title,
                    })
            source_hash = hashlib.sha256(
                json.dumps(
                    [(node.stable_id, node.text, node.title) for node in nodes],
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
            saved = self.client.replace_story_event_contexts(
                self.document_id, contexts, source_hash
            )
            self.progress.emit(len(chunks), len(chunks), "Timeline is ready.")
            self.finished.emit(
                True,
                f"Built {len(events)} story events for {saved} marked dialogue lines.",
            )
        except Exception as exc:
            log_error(f"Story timeline analysis failed: {exc}", exc_info=True)
            self.finished.emit(False, f"Timeline analysis failed: {exc}")


def _build_prompt(dialogues, aliases, node_by_id, ordered_nodes, target_lang: str) -> str:
    lines = []
    node_positions = {node.id: index for index, node in enumerate(ordered_nodes)}
    for node in dialogues:
        ancestors = []
        parent = node_by_id.get(node.parent_id)
        speaker = ""
        while parent is not None:
            label = (parent.title or parent.text or "").strip()
            if parent.node_type == "speaker" and not speaker:
                speaker = label
            elif parent.node_type in {"act", "chapter", "scene"} and label:
                ancestors.append(label)
            parent = node_by_id.get(parent.parent_id)
        path = " > ".join(reversed(ancestors)) or "Unstructured"
        text = (node.text or node.title or "").strip().replace("\n", " ")
        position = node_positions[node.id]
        directions = []
        for nearby in ordered_nodes[max(0, position - 5):position]:
            if nearby.node_type in {"action", "context", "narrator"}:
                detail = (nearby.text or nearby.title or "").strip().replace("\n", " ")
                if detail:
                    directions.append(detail[:300])
        direction_text = " / ".join(directions[-2:]) or "None"
        lines.append(
            f"[{aliases[node.id]}] PATH={path} | SPEAKER={speaker or 'Unknown'} "
            f"| RECENT DIRECTIONS={direction_text} | DIALOGUE={text}"
        )
    return f"""Divide these consecutive marked dialogues into coherent story events.
Write event_title and summary in {target_lang}. Infer location only when supported; otherwise use an empty string.
Return ONLY valid JSON with this shape:
{{"events":[{{"event_title":"...","summary":"1-3 useful context sentences","location":"...","participants":["..."],"interactions":[{{"source":"...","target":"...","dynamic":"warns / trusts / commands / teases / etc."}}],"dialogue_ids":["d00001"]}}]}}

Rules:
- Every supplied dialogue ID must occur exactly once.
- Keep events in story order and IDs in their original order.
- Do not invent plot facts; summarize goals, actions, stakes, and immediate situation.
- Participants are character names actually present or clearly involved in the event.

MARKED DIALOGUE:
{chr(10).join(lines)}"""


def parse_timeline_response(text: str, expected_ids: set[str]) -> list[dict]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        rows = cleaned.splitlines()[1:]
        if rows and rows[-1].strip().startswith("```"):
            rows.pop()
        cleaned = "\n".join(rows).strip()
    payload = json.loads(cleaned)
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list) or not events:
        raise ValueError("AI returned no timeline events")
    seen = []
    normalized = []
    for raw in events:
        if not isinstance(raw, dict):
            raise ValueError("AI returned an invalid timeline event")
        dialogue_ids = [str(value) for value in raw.get("dialogue_ids") or []]
        if not dialogue_ids:
            raise ValueError("A timeline event contains no dialogue IDs")
        seen.extend(dialogue_ids)
        title = str(raw.get("event_title") or "").strip()
        if not title:
            raise ValueError("A timeline event has no title")
        normalized.append({
            "event_title": title,
            "summary": str(raw.get("summary") or "").strip(),
            "location": str(raw.get("location") or "").strip(),
            "participants": [
                str(value).strip() for value in raw.get("participants") or []
                if str(value).strip()
            ],
            "interactions": _normalize_interactions(raw.get("interactions")),
            "dialogue_ids": dialogue_ids,
        })
    if len(seen) != len(set(seen)) or set(seen) != expected_ids:
        missing = sorted(expected_ids - set(seen))
        unknown = sorted(set(seen) - expected_ids)
        raise ValueError(f"AI did not cover dialogue IDs exactly (missing={missing}, unknown={unknown})")
    return normalized


def _normalize_interactions(raw) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("AI returned invalid event interactions")
    result = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
            continue
        if not isinstance(item, dict):
            raise ValueError("AI returned an invalid event interaction")
        source = str(item.get("source") or "").strip()
        target = str(item.get("target") or "").strip()
        dynamic = str(item.get("dynamic") or "").strip()
        if source and target and dynamic:
            result.append(f"{source} → {target}: {dynamic}")
    return result
