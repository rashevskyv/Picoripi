"""Measure how large the AI translation prompts are.

Runs the real ``AIPromptComposer`` against a small fake project (no MemPalace
database, a fake plugin with flow/addressee data, 12 glossary entries, a
40-string block, two reference languages) and prints the size of every part of
the single-string and batch prompts.

Tokens are estimated: ~4 characters per token for Latin text, ~2.5 for Cyrillic.
The numbers are for comparing one revision with another, not for billing.

    python tools/measure_prompts.py            # human-readable report
    python tools/measure_prompts.py --json     # the headline numbers as JSON
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BLOCK = [
    "Hey, [PLAYER]! Are you heading to\nOrdon Village again?",
    "Link, the goats got loose!\nHelp me round them up!",
    "Rusl asked me to bring the sword\nto Hyrule Castle.",
    "Ilia will be waiting at Ordon Spring.\nDon't be late.",
    "Yes",
    "No",
    "You got a {0}!\nIt's a wooden sword.",
    "The Midna shadow follows you\nwherever you go.",
    "Zelda is the princess of Hyrule.",
    "Welcome to the shop!\nWhat would you like?",
] * 4  # 40 strings

GLOSSARY_MD = """
| Original | Translation | Notes |
|---|---|---|
| Link | Лінк | Головний герой, хлопець 17 років, мовчазний |
| Ordon Village | Село Ордон | Рідне село Лінка |
| Rusl | Русл | Мечник, старший, звертається до Лінка неформально |
| Hyrule Castle | Замок Гайрул | Столиця |
| Ilia | Ілія | Подруга Лінка, донька старости, звертається неформально |
| Ordon Spring | Джерело Ордон | Святе джерело біля села |
| Midna | Мідна | Принцеса сутінків, саркастична |
| Zelda | Зельда | Принцеса Гайрулу, формальна мова |
| Hyrule | Гайрул | Королівство |
| goat | коза | Тварина |
| wooden sword | дерев'яний меч | Предмет |
| Ganondorf | Ґанондорф | Головний злодій |
"""


def tok(text: str) -> int:
    """Rough token count: Cyrillic is about 2.5 chars/token, the rest about 4."""
    cyrillic = len(re.findall(r"[Ѐ-ӿ]", text))
    return int(cyrillic / 2.5 + (len(text) - cyrillic) / 4)


def build_composer():
    """The real composer wired to a fake main window."""
    from PyQt6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])

    from core.glossary_manager import GlossaryManager
    from handlers.translation.prompt_composer import AIPromptComposer

    glossary = GlossaryManager()
    glossary.load_from_text(plugin_name="zelda", glossary_path=None, raw_text=GLOSSARY_MD)

    class Rules:
        def get_display_name(self):
            return "Zelda TP"

        def get_text_representation_for_editor(self, text):
            return text

        def get_translation_context_for_string(self, block, string):
            if string % 5:
                return {"window_type": "TalkBox"}
            return {"window_type": "Choice", "content_role": "Choice"}

        def get_ai_flow_context_for_string(self, block, string):
            return f"conversation Ordon_{string // 5}: line {string % 5 + 1}/5; after player picks 'Yes'"

        def get_ai_flow_overview(self, block, indices):
            outline = "Conversation Ordon_0 (owner: Rusl)\n  1. greeting\n  2. request\n  3. choice Yes/No\n  4. reply\n"
            return outline * max(1, len(indices) // 5)

        def get_addressee_for_string(self, block, string, speaker=None):
            return "Link"

    class DataStore:
        data = [BLOCK]
        reference_languages_data = {
            "German": {(0, i): f"Deutsche Referenz Zeile {i}" for i in range(40)},
            "French": {(0, i): f"Référence française {i}" for i in range(40)},
        }
        reference_data = {}
        block_names = {}
        physical_block_idx = 0
        current_string_idx = 0

    class MainWindow:
        target_language = "Ukrainian"
        current_game_rules = Rules()
        active_game_rules = current_game_rules
        data_store = DataStore()
        default_tag_mappings = {"[PLAYER]": "{Player}", "[Color:Red]": "{C:1}", "[/Color]": "{C:0}"}
        string_metadata = {}
        line_width_warning_threshold_pixels = 280
        game_dialog_max_width_pixels = 300
        lines_per_page = 3
        project_manager = None
        translation_handler = None
        block_to_project_file_map = {}

    class DataProcessor:
        def get_current_string_text(self, block, string):
            return (f"Переклад рядка {string}" if string % 3 == 0 else "", False)

    class MainHandler:
        mw = MainWindow()
        data_processor = DataProcessor()
        ui_updater = None
        _glossary_manager = glossary

    composer = AIPromptComposer(MainHandler())
    composer.story_context.get_mempalace_client = lambda: None  # no MemPalace database
    composer.story_context.fetch_story_context = lambda *args, **kwargs: None
    return composer, glossary


def measure() -> dict:
    """Compose the prompts and return their sizes."""
    composer, glossary = build_composer()
    system = json.loads((ROOT / "translation_prompts" / "prompts.json").read_text(encoding="utf-8"))["translation"]["system_prompt"]
    items = [{"id": i, "text": BLOCK[i]} for i in range(len(BLOCK))]
    chunk = items[:12]

    single_system, single_user = composer.compose_messages(
        system, BLOCK[1], block_idx=0, string_idx=1, expected_lines=2, mode_description="current row"
    )
    batch_system, batch_user, _ = composer.compose_batch_request(
        system, chunk, items, block_idx=0, mode_description="block 1"
    )
    other_system, _, _ = composer.compose_batch_request(
        system, items[12:24], items, block_idx=0, mode_description="block 1"
    )
    retry_system, retry_user, _ = composer.compose_batch_request(
        system, chunk, items, block_idx=0, mode_description="block 1",
        is_retry=True, retry_reason="Line count mismatch in chunk 1",
    )

    payload = json.loads(batch_user.split("JSON DATA TO PROCESS:\n", 1)[1])
    payload_tokens = {
        key: tok(json.dumps(value, ensure_ascii=False, indent=2)) for key, value in payload.items()
    }
    first_item = json.dumps(payload["strings_to_translate"][0], ensure_ascii=False, indent=2)

    block_total = 0
    for start in range(0, len(items), 12):
        chunk_system, chunk_user, _ = composer.compose_batch_request(
            system, items[start:start + 12], items, block_idx=0, mode_description="block 1"
        )
        block_total += tok(chunk_system) + tok(chunk_user)
    source_tokens = tok(" ".join(BLOCK))

    glossary_rows = max(0, str(payload.get("glossary", "")).count("\n") - 1)
    return {
        "single": {
            "system_tok": tok(single_system),
            "user_tok": tok(single_user),
            "total_tok": tok(single_system) + tok(single_user),
        },
        "batch_chunk_12": {
            "system_tok": tok(batch_system),
            "user_tok": tok(batch_user),
            "total_tok": tok(batch_system) + tok(batch_user),
            "payload_tok": payload_tokens,
            "per_item_tok": tok(first_item),
            "glossary_rows": glossary_rows,
            "glossary_rows_in_chunk_text": len(glossary.get_relevant_terms(" ".join(i["text"] for i in chunk))),
            "user_has_instructions_block": "INSTRUCTIONS:" in batch_user,
            "system_identical_across_chunks": batch_system == other_system,
        },
        "batch_retry": {"total_tok": tok(retry_system) + tok(retry_user)},
        "block_40_strings": {
            "requests": (len(items) + 11) // 12,
            "input_tok": block_total,
            "source_tok": source_tokens,
            "overhead_x": round(block_total / max(1, source_tokens), 1),
        },
        "_texts": {
            "single_system": single_system, "single_user": single_user,
            "batch_system": batch_system, "batch_user": batch_user,
            "first_item": first_item,
        },
    }


def _sections(text: str) -> str:
    lines = []
    for section in text.split("\n\n"):
        head = section.split("\n", 1)[0][:60]
        lines.append(f"   [{len(section):5d} ch ~{tok(section):4d} tok] {head}")
    return "\n".join(lines)


def main(argv: list) -> int:
    result = measure()
    texts = result.pop("_texts")
    if "--json" in argv:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    single, batch, block = result["single"], result["batch_chunk_12"], result["block_40_strings"]
    print(f"=== SINGLE (row 1): system ~{single['system_tok']} tok, user ~{single['user_tok']} tok, total ~{single['total_tok']} tok")
    print(_sections(texts["single_user"]))
    print(f"\n=== BATCH chunk 12/40: system ~{batch['system_tok']} tok, user ~{batch['user_tok']} tok, total ~{batch['total_tok']} tok")
    print(_sections(texts["batch_user"]))
    print("\nJSON payload:")
    for key, value in batch["payload_tok"].items():
        print(f"   {key:28s} ~{value:5d} tok")
    print(f"   per item ~{batch['per_item_tok']} tok:\n{texts['first_item']}")
    print(f"   glossary rows sent: {batch['glossary_rows']} | rows matched by the chunk's own text: {batch['glossary_rows_in_chunk_text']}")
    print(f"   system prompt identical for two different chunks: {batch['system_identical_across_chunks']}")
    print(f"   user message carries an INSTRUCTIONS block: {batch['user_has_instructions_block']}")
    print(f"\nretry request: ~{result['batch_retry']['total_tok']} tok")
    print(
        f"whole block: {block['requests']} requests, ~{block['input_tok']} input tok for "
        f"~{block['source_tok']} tok of source text (x{block['overhead_x']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
