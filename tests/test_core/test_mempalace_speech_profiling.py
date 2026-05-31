import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.mempalace_worker import MemePalaceCharacterProfilerWorker
from core.glossary_manager import GlossaryManager, GlossaryEntry

def test_mempalace_speech_profiling_sera_and_trill_integration(tmp_path):
    # 1. Create a temporary glossary file
    glossary_file = tmp_path / "glossary.json"
    
    # Initial glossary content resembling the user's state (short notes)
    initial_data = [
        {
            "original": "TRILL",
            "translation": "Тріл",
            "notes": "📌 **Хто цей персонаж (Загальний опис та роль)**:",
            "section": "Characters"
        },
        {
            "original": "SERA",
            "translation": "Сера",
            "notes": "📌 **Хто цей персонаж (Загальний опис та роль)**:",
            "section": "Characters"
        }
    ]
    
    with open(glossary_file, "w", encoding="utf-8") as f:
        json.dump(initial_data, f, indent=4, ensure_ascii=False)
        
    # Initialize GlossaryManager and load data from disk
    glossary_manager = GlossaryManager()
    glossary_manager.load_from_text(
        plugin_name="zelda_tp",
        glossary_path=glossary_file,
        raw_text=glossary_file.read_text(encoding="utf-8")
    )
    
    # 2. Mock MemePalace client with character dialogue lines
    client = MagicMock()
    client.get_all_character_lines.return_value = {
        "SERA": [
            "Beth? Are you OK?",
            "You didn't happen to see my little cat out there, did you?",
            "Welcome, m'dear."
        ],
        "TRILL": [
            "If not, stop at Trill's!",
            "TRILL'S SHOP.",
            "Trill's Shop is straight ahead!"
        ]
    }
    
    # 3. Mock AI Provider to return specific profiles & synthesis results
    ai_provider = MagicMock()
    
    # Detailed character profiles and synthesis text
    sera_profile = "Сера — енергійна та турботлива власниця магазину в селищі Ордон. Її мовлення тепле, емоційне та сповнене ласкавих звертань до Лінка."
    trill_profile = "Тріл — незвичайний персонаж, який поєднує комічного продавця та величного наставника. Його мовлення дуже контрастне."
    
    sera_synthesized = "📌 **Хто цей персонаж (Загальний опис та роль)**:\n\nСера — енергійна та турботлива власниця магазину в селищі Ордон. Її мовлення тепле, емоційне та сповнене ласкавих звертань до Лінка."
    trill_synthesized = "📌 **Хто цей персонаж (Загальний опис та роль)**:\n\nТріл — незвичайний персонаж, який поєднує комічного продавця та величного наставника. Його мовлення дуже контрастне."

    def mock_translate(messages, session=None):
        # Accumulate all content from messages to inspect prompts
        prompt_content = ""
        for msg in messages:
            if msg.get("role") == "user":
                prompt_content += msg.get("content", "")
                
        resp = MagicMock()
        
        # Check if this is a Wikipedia translation request
        if "Перекладіть наступний опис персонажа" in prompt_content:
            if "SERA" in prompt_content:
                resp.text = "Сера — опис з Вікіпедії."
            else:
                resp.text = "Трілл — опис з Вікіпедії."
            return resp
            
        # Check if the prompt is for SERA or TRILL
        if "SERA" in prompt_content:
            # Detect if it's a Synthesis request or Profiling request
            if "Синтезуйте" in prompt_content or "existing notes" in prompt_content.lower():
                resp.text = sera_synthesized
            else:
                resp.text = json.dumps({
                    "name_translation": "Сера",
                    "speech_profile": sera_profile
                }, ensure_ascii=False)
        elif "TRILL" in prompt_content:
            if "Синтезуйте" in prompt_content or "existing notes" in prompt_content.lower():
                resp.text = trill_synthesized
            else:
                resp.text = json.dumps({
                    "name_translation": "Тріл",
                    "speech_profile": trill_profile
                }, ensure_ascii=False)
        else:
            resp.text = '{"name_translation": "Unknown", "speech_profile": ""}'
            
        return resp
        
    ai_provider.translate.side_effect = mock_translate
    
    # 4. Create MemePalaceCharacterProfilerWorker with our managers
    worker = MemePalaceCharacterProfilerWorker(
        client=client,
        ai_provider=ai_provider,
        wing_name="Zelda_TP",
        glossary_manager=glossary_manager,
        target_lang="Ukrainian"
    )
    
    # Mock progress signal
    worker.progress = MagicMock()
    
    # 5. Run the worker synchronously
    worker.run()
    
    # 6. Verify client and ai_provider calls
    client.get_all_character_lines.assert_called_once_with("Zelda_TP")
    assert ai_provider.translate.call_count == 6  # 2 characters * (1 wiki translation + 1 profiling + 1 synthesis)
    
    # 7. Reload glossary from disk to verify incremental saves
    saved_glossary = GlossaryManager()
    saved_glossary.load_from_text(
        plugin_name="zelda_tp",
        glossary_path=glossary_file,
        raw_text=glossary_file.read_text(encoding="utf-8")
    )
    
    # 8. Check that entries are successfully updated and saved on disk!
    trill_entry = saved_glossary.get_entry("TRILL")
    assert trill_entry is not None
    assert trill_entry.translation == "Тріл"
    assert trill_entry.notes.strip() == trill_synthesized.strip()
    
    sera_entry = saved_glossary.get_entry("SERA")
    assert sera_entry is not None
    assert sera_entry.translation == "Сера"
    assert sera_entry.notes.strip() == sera_synthesized.strip()
    
    print("SUCCESS: Integration test verified character profiling and glossary updates perfectly!")


def test_mempalace_speech_profiling_incremental_resume(tmp_path):
    # 1. Create a temporary glossary file with one already-profiled character (TRILL) and one non-profiled (SERA)
    glossary_file = tmp_path / "glossary.json"
    
    initial_data = [
        {
            "original": "TRILL",
            "translation": "Тріл",
            "notes": "📌 **Хто цей персонаж**:\n🗣️ **Особливості мовлення**:\n💡 **Рекомендації**:",
            "section": "Characters"
        },
        {
            "original": "SERA",
            "translation": "Сера",
            "notes": "Some basic pre-existing note.",
            "section": "Characters"
        }
    ]
    
    with open(glossary_file, "w", encoding="utf-8") as f:
        json.dump(initial_data, f, indent=4, ensure_ascii=False)
        
    glossary_manager = GlossaryManager()
    glossary_manager.load_from_text(
        plugin_name="zelda_tp",
        glossary_path=glossary_file,
        raw_text=glossary_file.read_text(encoding="utf-8")
    )
    
    client = MagicMock()
    client.get_all_character_lines.return_value = {
        "SERA": ["Beth? Are you OK?", "Cat out there?", "Welcome, m'dear."],
        "TRILL": ["If not, stop at Trill's!", "TRILL'S SHOP.", "Trill's Shop is straight ahead!"]
    }
    
    ai_provider = MagicMock()
    resp = MagicMock()
    resp.text = json.dumps({
        "name_translation": "Сера",
        "speech_profile": "📌 **Хто цей персонаж**:\n🗣️ **Особливості мовлення**:\n💡 **Рекомендації**:"
    }, ensure_ascii=False)
    ai_provider.translate.return_value = resp
    
    worker = MemePalaceCharacterProfilerWorker(
        client=client,
        ai_provider=ai_provider,
        wing_name="Zelda_TP",
        glossary_manager=glossary_manager,
        target_lang="Ukrainian"
    )
    worker.progress = MagicMock()
    
    # Run profiling
    worker.run()
    
    # Verify that TRILL was skipped, so translate was NOT called for TRILL at all.
    # It was only called for SERA (1 profiling call, and since it fell back/mocked synthesis, or synthesis was skipped because we mocked simple return).
    # Since we mocked a single return, translate was called only for SERA.
    # Specifically, it was called for SERA profiling, and SERA synthesis (or Wikipedia lookup if any).
    # Let's inspect the translate calls.
    called_terms = []
    for call in ai_provider.translate.call_args_list:
        messages = call[0][0]
        prompt_content = "".join(m.get("content", "") for m in messages)
        called_terms.append(prompt_content)
        
    # None of the calls should contain "TRILL" because TRILL is skipped!
    for p in called_terms:
        assert "TRILL" not in p
        
    # Check that SERA notes are now updated with the completed profile structure
    sera_entry = glossary_manager.get_entry("SERA")
    assert sera_entry is not None
    assert "📌 **Хто цей персонаж**:" in sera_entry.notes


def test_mempalace_speech_profiling_short_profile_reprofiling(tmp_path):
    # 1. Create a temporary glossary file with a short profile that has BOTH marker and emojis but is < 3 lines
    glossary_file = tmp_path / "glossary.json"
    
    initial_data = [
        {
            "original": "TRILL",
            "translation": "Тріл",
            "notes": "📌 🗣️ 💡", # 1 line only, but contains all emojis -> has_profile=True, line_count=1 (<3)
            "section": "Characters",
            "profiled": True
        }
    ]
    
    with open(glossary_file, "w", encoding="utf-8") as f:
        json.dump(initial_data, f, indent=4, ensure_ascii=False)
        
    glossary_manager = GlossaryManager()
    glossary_manager.load_from_text(
        plugin_name="zelda_tp",
        glossary_path=glossary_file,
        raw_text=glossary_file.read_text(encoding="utf-8")
    )
    
    client = MagicMock()
    client.get_all_character_lines.return_value = {
        "TRILL": [
            "If not, stop at Trill's!",
            "TRILL'S SHOP.",
            "Trill's Shop is straight ahead!"
        ]
    }
    
    ai_provider = MagicMock()
    resp = MagicMock()
    resp.text = json.dumps({
        "name_translation": "Тріл",
        "speech_profile": "📌 **Хто цей персонаж**:\n🗣️ **Особливості мовлення**:\n💡 **Рекомендації**:\nДетальний опис Тріла."
    }, ensure_ascii=False)
    ai_provider.translate.return_value = resp
    
    worker = MemePalaceCharacterProfilerWorker(
        client=client,
        ai_provider=ai_provider,
        wing_name="Zelda_TP",
        glossary_manager=glossary_manager,
        target_lang="Ukrainian"
    )
    worker.progress = MagicMock()
    
    # Run profiling
    worker.run()
    
    # Verify that TRILL was NOT skipped because of the short description!
    assert ai_provider.translate.called
    
    # Reload from disk and check that TRILL is updated and marked as profiled=True again!
    saved_glossary = GlossaryManager()
    saved_glossary.load_from_text(
        plugin_name="zelda_tp",
        glossary_path=glossary_file,
        raw_text=glossary_file.read_text(encoding="utf-8")
    )
    
    trill_entry = saved_glossary.get_entry("TRILL")
    assert trill_entry is not None
    assert trill_entry.profiled is True
    assert "Детальний опис Тріла" in trill_entry.notes


