"""Tests for tools.extract_ru_glossary_variants."""
import json
from pathlib import Path
from tools.extract_ru_glossary_variants import (
    extract_variants_from_aligned_corpus,
    update_glossary_with_ru_variants,
)


def test_extract_variants_standalone_and_tagged():
    """Test extracting variants via exact standalone match and tagged span."""
    glossary = [
        {"original": "green Rupee", "translation": "зелена рупія"},
        {"original": "Master Sword", "translation": "меч Майстра"},
        {"original": "Midna", "translation": "Мідна"},
    ]

    eng_blocks = [
        [
            "green Rupee",  # exact standalone
            "You got the {escape:255:000001}Master Sword{escape:255:000000}!",  # tagged span
            "Talk to Midna now.",  # name mention 1
            "Where is Midna?",  # name mention 2
        ]
    ]

    ru_data = {
        (0, 0): "зелёная рупия",
        (0, 1): "Ты получил {escape:255:000001}меч Героев{escape:255:000000}!",
        (0, 2): "Поговори с Мидна сейчас.",
        (0, 3): "Где Мидна?",
    }

    extracted = extract_variants_from_aligned_corpus(glossary, eng_blocks, ru_data)

    assert "green Rupee" in extracted
    assert extracted["green Rupee"][0] == "зелёная рупия"

    assert "Master Sword" in extracted
    assert extracted["Master Sword"][0] == "меч Героев"

    assert "Midna" in extracted
    assert extracted["Midna"][0] == "Мидна"


def test_update_glossary_with_ru_variants(tmp_path: Path):
    """Test persisting extracted Russian variants to glossary.json."""
    gfile = tmp_path / "glossary.json"
    initial_data = [
        {
            "original": "green Rupee",
            "translation": "зелена рупія",
            "translation_variants": [
                {"translation": "зелена рупія", "rationale": "UK rationale"}
            ],
        }
    ]
    gfile.write_text(json.dumps(initial_data, ensure_ascii=False), encoding="utf-8")

    extracted = {
        "green Rupee": ("зелёная рупия", "exact_standalone")
    }

    added, updated = update_glossary_with_ru_variants(gfile, extracted)
    assert added == 1
    assert updated == 0

    # Verify backup exists
    assert (tmp_path / "glossary.json.bak").exists()

    # Verify updated content
    updated_data = json.loads(gfile.read_text(encoding="utf-8"))
    variants = updated_data[0]["translation_variants"]
    assert len(variants) == 2
    assert variants[0]["translation"] == "зелена рупія"
    assert variants[1]["translation"] == "зелёная рупия"
    assert variants[1]["rationale"] == "RU патч v2.0"

    # Running update again should update existing RU variant, not append duplicate
    extracted2 = {
        "green Rupee": ("одна рупия", "exact_standalone")
    }
    added2, updated2 = update_glossary_with_ru_variants(gfile, extracted2)
    assert added2 == 0
    assert updated2 == 1

    updated_data2 = json.loads(gfile.read_text(encoding="utf-8"))
    variants2 = updated_data2[0]["translation_variants"]
    assert len(variants2) == 2
    assert variants2[1]["translation"] == "одна рупия"
