import os
from core.markdown_script_parser import parse_markdown_script

def test_parse_markdown_script():
    # Construct a sample markdown script following the template
    md_content = """# Game Translation Script & Context Template

## 1. Global Plot & Synopsis
This is a test game about a hero saving a kingdom from darkness.
It spans multiple acts and chapters.

## 2. Character Cast & Profiles
- **HERO** (Name in Game: `Link`)
  - **Translation**: `Лінк`
  - **Gender**: `male`
  - **Age Group**: `child`
  - **Address Style**: `informal`
  - **Relationship**: `Friend of Zelda`
  - **Description**: `The protagonist who wields the Master Sword.`

- **ZELDA** (Name in Game: `Zelda`)
  - **Translation**: `Зельда`
  - **Gender**: `female`
  - **Age Group**: `adult`
  - **Address Style**: `formal`
  - **Relationship**: `Princess of Hyrule`
  - **Description**: `The princess of the kingdom.`

## 3. Terms & Glossary
- **MASTER_SWORD** (Original: `Master Sword`)
  - **Translation**: `Вищий Меч`
  - **Description**: `The blade of evil's bane.`

## 4. Chronological Dialogue Timeline

# Chapter I: The Forest Meetup
The journey begins here in the Kokiri forest.

### Location: Kokiri Forest

{Action: Hero walks up to the great tree, looking determined}

HERO: We must protect the kingdom.
ZELDA: I agree, Hero. We have no time to lose.

{Action: Zelda turns away, weeping silently}

ZELDA: But the danger is too great.
"""

    temp_path = "temp_test_markdown_script.md"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        data = parse_markdown_script(temp_path)

        # 1. Verify synopsis
        assert "This is a test game about a hero" in data["synopsis"]
        assert "It spans multiple acts and chapters." in data["synopsis"]

        # 2. Verify characters
        chars = data["characters"]
        assert len(chars) == 2
        
        link = chars[0]
        assert link["name"] == "HERO"
        assert link["display_name"] == "Link"
        assert link["translation"] == "Лінк"
        assert link["gender"] == "male"
        assert link["age_group"] == "child"
        assert link["address_type"] == "informal"
        assert link["relationship_summary"] == "Friend of Zelda"
        assert link["description"] == "The protagonist who wields the Master Sword."

        zelda = chars[1]
        assert zelda["name"] == "ZELDA"
        assert zelda["display_name"] == "Zelda"
        assert zelda["translation"] == "Зельда"
        assert zelda["gender"] == "female"
        assert zelda["age_group"] == "adult"
        assert zelda["address_type"] == "formal"
        assert zelda["relationship_summary"] == "Princess of Hyrule"
        assert zelda["description"] == "The princess of the kingdom."

        # 3. Verify terms
        terms = data["terms"]
        assert len(terms) == 1
        sword = terms[0]
        assert sword["name"] == "MASTER_SWORD"
        assert sword["original"] == "Master Sword"
        assert sword["translation"] == "Вищий Меч"
        assert sword["description"] == "The blade of evil's bane."

        # 4. Verify dialogues
        dias = data["dialogues"]
        assert len(dias) == 3
        
        assert dias[0]["speaker"] == "HERO"
        assert dias[0]["text"] == "We must protect the kingdom."
        assert dias[0]["timestamp"] == "Action: Hero walks up to the great tree, looking determined"
        assert dias[0]["room"] == "The Forest Meetup"

        assert dias[1]["speaker"] == "ZELDA"
        assert dias[1]["text"] == "I agree, Hero. We have no time to lose."
        assert dias[1]["timestamp"] == "Action: Hero walks up to the great tree, looking determined"

        assert dias[2]["speaker"] == "ZELDA"
        assert dias[2]["text"] == "But the danger is too great."
        assert dias[2]["timestamp"] == "Action: Zelda turns away, weeping silently"

        # 5. Verify chapters
        chaps = data["chapters"]
        assert len(chaps) == 1
        assert chaps[0]["num"] == "Chapter I"
        assert chaps[0]["title"] == "The Forest Meetup"
        assert chaps[0]["start_line"] > 0
        assert chaps[0]["end_line"] > chaps[0]["start_line"]
        assert "HERO: We must protect the kingdom." in chaps[0]["content"]

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    print("Running markdown parser tests...")
    test_parse_markdown_script()
    print("ALL TESTS PASSED SUCCESSFULLY!")
