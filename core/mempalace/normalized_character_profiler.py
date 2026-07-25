"""AI character voice profiling from normalized Speaker → Dialogue nodes."""

from __future__ import annotations

import hashlib
import json

from PyQt6.QtCore import QThread, pyqtSignal

from core.translation.providers import ProviderResponse
from utils.logging_utils import log_ai_traffic, log_error


class NormalizedCharacterProfilerWorker(QThread):
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
            speakers = collect_character_dialogues(nodes)
            if not speakers:
                self.finished.emit(False, "No normalized Speaker → Dialogue data was found.")
                return
            if not self.ai_provider:
                self.finished.emit(False, "No AI provider is configured.")
                return

            profiles = []
            ordered = sorted(speakers.items(), key=lambda item: item[0].casefold())
            for index, (speaker_name, lines) in enumerate(ordered, 1):
                if self.is_cancelled:
                    self.finished.emit(False, "Character profiling was cancelled.")
                    return
                self.progress.emit(
                    index - 1,
                    len(ordered),
                    f"Analyzing {speaker_name} ({index}/{len(ordered)})…",
                )
                partial_profiles = []
                chunks = chunk_character_dialogues(lines)
                for chunk_index, chunk in enumerate(chunks, 1):
                    self.progress.emit(
                        index - 1,
                        len(ordered),
                        f"Analyzing {speaker_name}: evidence part "
                        f"{chunk_index}/{len(chunks)}…",
                    )
                    messages = build_character_profile_messages(
                        speaker_name,
                        chunk,
                        self.target_lang,
                        total_dialogue_count=len(lines),
                    )
                    partial_profiles.append(self._request_profile(messages))
                if len(partial_profiles) == 1:
                    profile = partial_profiles[0]
                else:
                    profile = self._request_profile(
                        build_character_profile_synthesis_messages(
                            speaker_name, partial_profiles, self.target_lang
                        )
                    )
                if profile.pop("is_character"):
                    profile["speaker_name"] = speaker_name
                    profile["dialogue_count"] = len(lines)
                    profiles.append(profile)

            source_hash = hashlib.sha256(
                json.dumps(
                    [(node.stable_id, node.title, node.text) for node in nodes],
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
            saved = self.client.replace_character_profiles(
                self.document_id, profiles, source_hash
            )
            self.progress.emit(len(ordered), len(ordered), "Character voices are ready.")
            self.finished.emit(
                True,
                f"Built translation profiles for {saved} characters from "
                f"{sum(len(lines) for lines in speakers.values())} dialogue lines.",
            )
        except Exception as exc:
            log_error(f"Normalized character profiling failed: {exc}", exc_info=True)
            self.finished.emit(False, f"Character profiling failed: {exc}")

    def _request_profile(self, messages) -> dict:
        log_ai_traffic(self.mw, "mempalace_normalized_character_profile", messages)
        response: ProviderResponse = self.ai_provider.translate(messages, session=None)
        log_ai_traffic(
            self.mw,
            "mempalace_normalized_character_profile",
            messages,
            response_text=response.text,
        )
        return parse_character_profile(response.text)


def collect_character_dialogues(nodes) -> dict[str, list[dict]]:
    node_by_id = {node.id: node for node in nodes}
    result: dict[str, list[dict]] = {}
    for node in nodes:
        if node.node_type != "dialogue":
            continue
        speaker = ""
        structures = []
        parent = node_by_id.get(node.parent_id)
        visited = set()
        while parent is not None and parent.id not in visited:
            visited.add(parent.id)
            label = (parent.title or parent.text or "").strip()
            if parent.node_type == "speaker" and not speaker:
                speaker = label
            elif parent.node_type in {"act", "chapter", "scene"} and label:
                structures.append(label)
            parent = node_by_id.get(parent.parent_id)
        text = (node.text or node.title or "").strip()
        if speaker and text:
            result.setdefault(speaker, []).append({
                "text": text,
                "path": " > ".join(reversed(structures)),
            })
    return result


def chunk_character_dialogues(lines: list[dict]) -> list[list[dict]]:
    chunks = []
    current = []
    current_chars = 0
    for line in lines:
        size = len(line.get("text", "")) + len(line.get("path", "")) + 8
        if current and (len(current) >= 60 or current_chars + size > 24000):
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(line)
        current_chars += size
    if current:
        chunks.append(current)
    return chunks


def build_character_profile_messages(
    speaker_name: str,
    lines: list[dict],
    target_lang: str,
    *,
    total_dialogue_count: int | None = None,
):
    evidence = "\n".join(
        f"- [{line['path'] or 'Unstructured'}] {line['text']}" for line in lines
    )
    system = (
        "You are a senior game localization director and character voice editor. "
        "Infer only what the supplied dialogue supports. Produce practical, consistent "
        "translation direction, not generic literary commentary."
    )
    user = f"""Analyze the voice of speaker "{speaker_name}" from all representative lines below.
Write every descriptive field in {target_lang}.

DIALOGUE EVIDENCE ({len(lines)} lines in this part; {total_dialogue_count or len(lines)} total):
{evidence}

Return ONLY one valid JSON object with exactly these fields:
{{
  "is_character": true,
  "role": "Role in the story, only when supported",
  "personality": "Temperament, motives, emotional tendencies",
  "speech_style": "Register, tone, rhythm, sentence construction",
  "vocabulary": "Recurring words, verbal habits, idioms, taboo or preferred vocabulary",
  "relationships": "Social status and how speech changes toward other characters",
  "address_and_grammar": "Forms of address, formality, pronouns and grammar advice for {target_lang}",
  "translation_advice": "Concrete do/don't instructions that keep this voice consistent in {target_lang}",
  "evidence_notes": "Uncertainties or limits caused by sparse/ambiguous dialogue"
}}

Set is_character to false for technical labels such as System or Narrative. Never invent lore, gender,
relationships, dialect, or catchphrases that cannot be inferred from these lines. Even with few lines,
record cautious useful observations and state the evidence limits."""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_character_profile_synthesis_messages(
    speaker_name: str, partial_profiles: list[dict], target_lang: str
):
    evidence = json.dumps(partial_profiles, ensure_ascii=False, indent=2)
    system = (
        "You are a senior game localization director. Merge evidence-based partial "
        "character voice analyses without inventing facts or losing contradictions."
    )
    user = f"""Synthesize the partial dialogue analyses for "{speaker_name}" into one profile.
Write all descriptive fields in {target_lang}. If evidence conflicts, report the uncertainty
in evidence_notes. Return ONLY valid JSON with the same exact fields as the inputs.

PARTIAL ANALYSES:
{evidence}"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_character_profile(text: str) -> dict:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        rows = cleaned.splitlines()[1:]
        if rows and rows[-1].strip().startswith("```"):
            rows.pop()
        cleaned = "\n".join(rows).strip()
    payload = json.loads(cleaned)
    if not isinstance(payload, dict) or not isinstance(payload.get("is_character"), bool):
        raise ValueError("AI returned an invalid character profile")
    fields = (
        "role", "personality", "speech_style", "vocabulary", "relationships",
        "address_and_grammar", "translation_advice", "evidence_notes",
    )
    result = {"is_character": payload["is_character"]}
    for field in fields:
        value = payload.get(field, "")
        if not isinstance(value, str):
            raise ValueError(f"AI returned a non-text character field: {field}")
        result[field] = value.strip()
    if result["is_character"] and not (
        result["personality"] or result["speech_style"] or result["translation_advice"]
    ):
        raise ValueError("AI returned an empty character profile")
    return result
