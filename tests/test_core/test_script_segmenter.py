import os
from core.script_segmenter import clean_chapter_title, segment_script_file

def test_clean_chapter_title():
    # Spaced-out letters with double spaces separating words
    assert clean_chapter_title("S u b s e r v i e n t  T w i l i g h t") == "Subservient Twilight"
    assert clean_chapter_title("C a t  H a n d l e r") == "Cat Handler"
    assert clean_chapter_title("O f  W o r l d s  L e f t  B e h i n d") == "Of Worlds Left Behind"
    
    # Dash prefixes
    assert clean_chapter_title("- Ordon Village") == "Ordon Village"
    assert clean_chapter_title("? Subservient Twilight") == "Subservient Twilight"
    assert clean_chapter_title("– Forgotten Hero") == "Forgotten Hero"
    
    # Normal titles
    assert clean_chapter_title("The Forest Temple") == "The Forest Temple"

def test_segment_script_file():
    # Create a mock script file
    script_content = (
        "ACT ONE\n"
        "Some intro text\n"
        "Act One\n"
        "Chapter I - S u b s e r v i e n t  T w i l i g h t\n"
        "~~~~~~~~~~~~~~~~~~~~~~~~~~\n"
        "RUSL\n"
        "Tell me... Do you feel sad?\n"
        "\n"
        "Chapter II ? C a t  H a n d l e r\n"
        "~~~~~~~~~~~~~~~~~~~~~~~~~~\n"
        "FADO\n"
        "Hey! Link!\n"
    )
    
    temp_path = "temp_test_script.txt"
    try:
        with open(temp_path, "w", encoding="cp1252") as f:
            f.write(script_content)
        
        chapters = segment_script_file(temp_path)
        
        assert len(chapters) == 2
        
        # Chapter I
        assert chapters[0]["num"] == "Act 1, Ch I"
        assert chapters[0]["title"] == "Subservient Twilight"
        assert chapters[0]["start_line"] == 4
        assert chapters[0]["end_line"] == 8
        assert "RUSL\nTell me..." in chapters[0]["content"]
        
        # Chapter II
        assert chapters[1]["num"] == "Act 1, Ch II"
        assert chapters[1]["title"] == "Cat Handler"
        assert chapters[1]["start_line"] == 9
        assert chapters[1]["end_line"] == 12
        assert "FADO\nHey! Link!" in chapters[1]["content"]
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    print("Running segmenter tests...")
    test_clean_chapter_title()
    test_segment_script_file()
    print("ALL TESTS PASSED SUCCESSFULLY!")
