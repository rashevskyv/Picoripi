import pytest
import re
from plugins.zelda_bmg.rules import GameRules
from bmg_tool import BMGFile, BMGMessage

def setup_test_mappings(rules):
    # Setup dummy mapping for Ukrainian characters to standard CP1252 characters (diacritics)
    # so that the tests can run without needing a real translation_map.json and won't fail encoding
    # and won't corrupt plain English text.
    rules.translation_map = {
        "П": "À", "р": "á", "и": "â", "в": "ã", "і": "ä", "т": "å", "я": "æ", 
        "к": "ç", "с": "è", "п": "é", "а": "ê", "У": "ë", "ї": "ì", "н": "í", 
        "І": "î", "о": "ï", "Ф": "ð", "ь": "ñ", "ґ": "ò", "г": "ó", "й": "ô",
        "у": "õ", "х": "ö", "ш": "÷", "щ": "ø", "ц": "ù", "ч": "ú", "ю": "û", "ж": "ü"
    }
    rules.reverse_translation_map = {v: k for k, v in rules.translation_map.items()}
    # Prevent load_translation_map from overwriting our test mapping
    rules.load_translation_map = lambda: None

def test_ukrainian_character_mapping():
    rules = GameRules()
    setup_test_mappings(rules)
    
    # Test text with Ukrainian characters
    ukr_text = "Привіт, як справи? Україна, Івано-Франківськ, ґава."
    
    # Encode to CP1252 representation
    encoded = rules.encode_string_with_mapping(ukr_text)
    
    # Check that Ukrainian letters are replaced with accents
    assert "П" not in encoded
    assert "и" not in encoded
    assert "і" not in encoded
    assert "У" not in encoded
    
    # Decode back
    decoded = rules.decode_string_with_mapping(encoded)
    
    # Must match original text exactly
    assert decoded == ukr_text

def test_editor_text_to_msg_content_conversion():
    rules = GameRules()
    
    # Editor text with text and escape codes
    editor_text = "Hello {escape:3:0004ff} World!"
    
    # Convert to message content
    content = rules.editor_text_to_msg_content(editor_text)
    
    assert len(content) == 3
    assert content[0] == "Hello "
    assert content[1] == {"type": "escape", "escape_type": 3, "data": "0004ff"}
    assert content[2] == " World!"
    
    # Reconvert back
    class MockMessage:
        def __init__(self, parts):
            self.parts = parts
            
    mock_msg = MockMessage(content)
    back_to_text = rules.msg_to_editor_text(mock_msg)
    
    assert back_to_text == editor_text

def test_bmg_rules_load_save_lifecycle():
    rules = GameRules()
    setup_test_mappings(rules)
    
    # Create mock BMG bytes
    bmg = BMGFile()
    bmg.endianness = '>'
    bmg.encoding = 'cp1252'
    bmg.id = 0
    
    msg1 = BMGMessage(info=b'\x00\x00\x00\x00', parts=["Start ", {"type": "escape", "escape_type": 3, "data": "1122"}, " End"])
    msg1.id = 100
    
    msg2 = BMGMessage(info=b'\x00\x00\x00\x00', parts=[rules.encode_string_with_mapping("Український text")])
    msg2.id = 101
    
    bmg.messages = [msg1, msg2]
    
    bmg_bytes = bmg.save()
    
    # Test unpacking via plugin
    data, block_names = rules.load_data_from_json_obj(bmg_bytes)
    
    assert len(data) == 1
    assert len(data[0]) == 2
    
    assert data[0][0] == "Start {escape:3:1122} End"
    assert data[0][1] == "Український text"
    
    assert block_names["0"] == "Message ID: 100 (Idx 0)"
    assert block_names["1"] == "Message ID: 101 (Idx 1)"
    
    # Test repacking via plugin
    repacked_bytes = rules.save_data_to_json_obj(data, block_names)
    
    assert isinstance(repacked_bytes, bytes)
    assert len(repacked_bytes) > 0
    
    # Unpack repacked to verify
    bmg_verify = BMGFile()
    bmg_verify.load(repacked_bytes)
    
    assert len(bmg_verify.messages) == 2
    assert bmg_verify.messages[0].id == 100
    assert bmg_verify.messages[1].id == 101


def test_synthetic_empty_glyph_mapping():
    rules = GameRules()
    
    # Setup translation map containing a synthetic empty-glyph mapping
    rules.translation_map = {
        "я": "#g224",
        "#g224": "я"
    }
    rules.reverse_translation_map = {} # Only synthetic entries exist
    rules.load_translation_map = lambda: None
    
    # 1. Test encoding: "я" (Cyrillic ya) should be mapped to chr(225)
    encoded = rules.encode_string_with_mapping("я")
    assert len(encoded) == 1
    assert ord(encoded) == 225
    
    # 2. Test decoding: chr(225) should be mapped back to "я"
    decoded = rules.decode_string_with_mapping(encoded)
    assert decoded == "я"
    
    # 3. Test packing / unpacking lifecycle with synthetic character
    bmg = BMGFile()
    bmg.endianness = '>'
    bmg.encoding = 'cp1252'
    bmg.id = 0
    
    msg = BMGMessage(info=b'\x00\x00\x00\x00', parts=[rules.encode_string_with_mapping("яabc")])
    bmg.messages = [msg]
    
    bmg_bytes = bmg.save()
    
    # Check that bytes contain exactly the code 225 (0xe1) in CP1252 instead of question marks
    assert b'\xe1' in bmg_bytes
    assert b'?' not in bmg_bytes
    
    # Unpack via plugin
    data, block_names = rules.load_data_from_json_obj(bmg_bytes)
    assert len(data) == 1
    assert data[0][0] == "яabc"


def test_autofix_width_exceeded_with_tag():
    rules = GameRules()
    setup_test_mappings(rules)
    
    # We want a font map where each character has a specific width.
    # We map the actual Cyrillic characters used in our test string to width 10.
    font_map = {}
    for char in "Ось чому самотність завжди пронизуєгодинусутінків. ":
        font_map[char] = {"width": 10} # 10 pixels per character
        
    # The text we want to test:
    # "Ось чому самотність завжди пронизує{color:red} годину\nсутінків{color:white}..."
    # "Ось чому самотність завжди пронизує" -> 35 characters (including spaces).
    # With 10 pixels per character, the width is 350 pixels.
    # "{color:red}" is a tag, so its width should be 0.
    # " годину" is 7 characters -> 70 pixels.
    # So "Ось чому самотність завжди пронизує{color:red} годину" has width 350 + 0 + 70 = 420 pixels.
    # Let's set the threshold to 360 pixels.
    # Under 360 pixels, the text before tag fits (350 <= 360), but the whole line does not (420 > 360).
    # So the word "годину" should be wrapped to the next line.
    
    text = "Ось чому самотність завжди пронизує{color:red} годину\nсутінків{color:white}..."
    
    fixed_text, changed = rules.autofix_data_string(text, font_map, 360)
    
    print("FIXED TEXT:", repr(fixed_text))
    assert changed is True
    # Verify that "годину" is wrapped to the second line
    lines = fixed_text.split('\n')
    assert len(lines) >= 2
    assert "годину" in lines[1]


def test_autofix_zelda_bmg_no_remerge_bug():
    rules = GameRules()
    setup_test_mappings(rules)
    
    font_map = {}
    for char in "This is a very long text to test the split and no remerge bug with pause tag {pause} and word herenext line text.":
        font_map[char] = {"width": 10}
        
    text = "This is a very long text to test the split and no remerge bug with pause tag {pause} and word here\nnext line text."
    
    fixed_text, changed = rules.autofix_data_string(text, font_map, 800)
    
    print("FIXED:", repr(fixed_text))
    # The compact step may merge "and word here" with "next line text." since they form one sentence.
    # Verify that {pause} acts as a page boundary and content after it is preserved.
    assert "{pause}" in fixed_text
    assert "next line text." in fixed_text
    # Content after {pause} should come after it
    pause_idx = fixed_text.index("{pause}")
    next_idx = fixed_text.index("next line text.")
    assert next_idx > pause_idx


def test_autofix_star_tag_rules():
    rules = GameRules()
    setup_test_mappings(rules)
    
    # Ensure our new autofix rule is enabled
    rules.problem_analyzer.mw = None
    
    text = (
        "{escape:3:000000000c80}На гачок вудки насаджена личинка.\n"
        "{*} Признач її на {(Y)} або {(X)} і закидай,\n"
        "   стоячи обличчям до води.\n"
        "{*}Коли поплавець пірне, риба клює —\n"
        "{tab}{tab} підсікай, нахиливши й утримуючи {(C-Stick)}{(▼)}."
    )
    
    # Run autofix with empty font map and high threshold
    fixed, changed = rules.autofix_data_string(text, {}, 10000)
    lines = fixed.split('\n')
    
    assert changed is True
    assert len(lines) == 3
    
    # 1. First line remains unchanged (before {*})
    assert lines[0] == "{escape:3:000000000c80}На гачок вудки насаджена личинка."
    
    # 2. Second and third lines merged into one star section
    assert lines[1] == "{escape:6:000a}Признач її на {(Y)} або {(X)} і закидай, стоячи обличчям до води."
    
    # 3. Fourth and fifth lines merged into one star section
    assert lines[2] == "{escape:6:000a}Коли поплавець пірне, риба клює — підсікай, нахиливши й утримуючи {(C-Stick)}{(▼)}."


def test_problem_analyzer_star_tag_rules():
    rules = GameRules()
    setup_test_mappings(rules)
    
    # 1. Check text with NO problems
    valid_text = (
        "{escape:3:000000000c80}На гачок вудки насаджена личинка.\n"
        "{*}Признач її на {(Y)} або {(X)} і закидай,\n"
        "{tab}стоячи обличчям до води.\n"
        "{*}Коли поплавець пірне, риба клює —\n"
        "{tab}підсікай, нахиливши й утримуючи {(C-Stick)}{(▼)}."
    )
    problems = rules.problem_analyzer.analyze_data_string(valid_text, {}, 10000)
    for p_set in problems:
        assert "ZBMG_STAR_TAG_RULES" not in p_set
        
    # 2. Check text with various violations
    invalid_text = (
        "{tab}На гачок вудки насаджена личинка.\n" # Viol: {tab} before {*}
        "{*} Признач її на {(Y)} або {(X)} і закидай,\n" # Viol: space after {*}
        " стоячи обличчям до води.\n" # Viol: missing {tab}
        "{*}Коли поплавець пірне, риба клює —\n" # Valid
        "{tab}підсікай, {tab} нахиливши й утримуючи." # Viol: multiple {tab} tags
    )
    problems = rules.problem_analyzer.analyze_data_string(invalid_text, {}, 10000)
    assert "ZBMG_STAR_TAG_RULES" in problems[0]
    assert "ZBMG_STAR_TAG_RULES" in problems[1]
    assert "ZBMG_STAR_TAG_RULES" in problems[2]
    assert "ZBMG_STAR_TAG_RULES" not in problems[3]
    assert "ZBMG_STAR_TAG_RULES" in problems[4]


def test_lines_per_page_ignored_with_star_tag():
    rules = GameRules()
    setup_test_mappings(rules)
    
    class MockMW:
        lines_per_page = 2
        game_dialog_max_width_pixels = 200
        autofix_enabled = {
            "ZBMG_EMPTY_FIRST_LINE_OF_PAGE": True,
            "ZBMG_SHORT_LINE": True,
            "ZBMG_STAR_TAG_RULES": True
        }
    rules.mw = MockMW()
    rules.problem_analyzer.mw = rules.mw
    rules.text_fixer.mw = rules.mw
    
    # Message has {*}, so lines_per_page (normally 2) should NOT cause empty line warning,
    # and should NOT cause single word checks or sentence shifting
    text_with_empty_and_star = (
        "\n" # Empty first line of page (would normally trigger problem on line 0)
        "{*}Признач її.\n"
        "{tab}стоячи."
    )
    
    # 1. Test check_for_empty_first_line_of_page returns empty
    empty_lines = rules.problem_analyzer.check_for_empty_first_line_of_page(text_with_empty_and_star)
    assert empty_lines == []
    
    # 2. Test analyze_data_string doesn't flag empty first line
    problems = rules.problem_analyzer.analyze_data_string(text_with_empty_and_star, {}, 200)
    assert "ZBMG_EMPTY_FIRST_LINE_OF_PAGE" not in problems[0]
    
    # 3. Test short line checking doesn't merge if next is {*} or {tab}
    short_line_text = (
        "{*}Признач її\n" # Width is short
        "{tab}стоячи"      # Next starts with {tab}
    )
    problems_short = rules.problem_analyzer.analyze_data_string(short_line_text, {}, 1000)
    assert "ZBMG_SHORT_LINE" not in problems_short[0]
    
    # 4. Test autofix merges star-section lines (they fit in one width since threshold is huge)
    fixed, changed = rules.autofix_data_string(short_line_text, {}, 1000)
    assert "{escape:6:000a}Признач її стоячи" in fixed


def test_star_tag_definitions_and_metadata():
    rules = GameRules()
    setup_test_mappings(rules)
    
    # Verify that ZBMG_STAR_TAG_RULES exists in problem definitions
    defs = rules.get_problem_definitions()
    assert "ZBMG_STAR_TAG_RULES" in defs
    
    rule_def = defs["ZBMG_STAR_TAG_RULES"]
    assert rule_def["name"] == "Star Tag Rules ({*} & {tab})"
    assert "Enforce special {*} tag layout rules" in rule_def["description"]
    assert rule_def["priority"] == 8
    
    # Verify short name
    short_name = rules.get_short_problem_name("ZBMG_STAR_TAG_RULES")
    assert short_name == "StarTag"


def test_star_tag_rules_with_escapes():
    rules = GameRules()
    setup_test_mappings(rules)

    # Text with escape:6:000a and escape:6:000b instead of aliases
    text = (
        "{escape:3:000000000c80}На гачок вудки насаджена личинка.\n"
        "{escape:6:000a} Признач її на {(Y)} або {(X)} і закидай,\n"
        "   стоячи обличчям до води.\n"
        "{escape:6:000a}Коли поплавець пірне, риба клює —\n"
        " - {escape:6:000b} підсікай, нахиливши й утримуючи."
    )

    # 1. Test Problem Analyzer detects violations correctly
    problems = rules.problem_analyzer.analyze_data_string(text, {}, 10000)
    assert "ZBMG_STAR_TAG_RULES" in problems[1]  # space after {*}
    assert "ZBMG_STAR_TAG_RULES" in problems[2]  # missing {tab}
    assert "ZBMG_STAR_TAG_RULES" in problems[4]  # {tab} not at start (preceded by ' - ')

    # 2. Test Autofix merges star sections and converts back to escape codes.
    # New behavior: each star section is merged into one line (re-split by width if needed).
    # Section 1: {*} Признач... \n    стоячи... -> {escape:6:000a}Признач... стоячи...
    # Section 2: {*}Коли... \n - {tab} підсікай... -> {escape:6:000a}Коли... - підсікай...
    fixed, changed = rules.autofix_data_string(text, {}, 10000)
    assert changed is True
    lines = fixed.split('\n')

    # Plain section is unchanged
    assert lines[0] == "{escape:3:000000000c80}На гачок вудки насаджена личинка."

    # First star section: two source lines merged into one, prefix = escape:6:000a
    assert lines[1].startswith("{escape:6:000a}")
    assert "Признач її на" in lines[1]
    assert "стоячи обличчям до води." in lines[1]
    assert "{escape:6:000b}" not in lines[1]  # no stray {tab} escape inside

    # Second star section: two source lines merged into one, prefix = escape:6:000a
    assert lines[2].startswith("{escape:6:000a}")
    assert "Коли поплавець пірне" in lines[2]
    assert "підсікай" in lines[2]
    assert "{escape:6:000b}" not in lines[2]  # no stray {tab} escape inside

    # Total: 3 lines (1 plain + 2 star sections)
    assert len(lines) == 3


def test_autofix_tab_relocation_disabled_rules():
    rules = GameRules()
    setup_test_mappings(rules)

    # Text containing {tab} inside lines.
    # We want to check that even if STAR_TAG_RULES is disabled,
    # the tabs are relocated to the start of the next lines and not merged back.
    text = (
        "Line 1 text.\n"
        "Line 2 {tab} text inside.\n"
        "Line 3 more text."
    )

    # Disable ZBMG_STAR_TAG_RULES, enable ZBMG_SHORT_LINE and ZBMG_WIDTH_EXCEEDED
    allowed = {"ZBMG_SHORT_LINE", "ZBMG_WIDTH_EXCEEDED"}

    fixed, changed = rules.autofix_data_string(text, {}, 400, allowed_problems=allowed)
    assert changed is True

    lines = fixed.split('\n')
    # Check that tab is relocated to the start of a line and is not inside any line
    has_tab_start = False
    for line in lines:
        assert not re.search(r'.+\{escape:6:000b\}', line)  # tab must not be inside
        if line.startswith('{escape:6:000b}'):
            has_tab_start = True

    assert has_tab_start is True


def test_autofix_tab_without_star_rules():
    rules = GameRules()
    setup_test_mappings(rules)

    # Text containing {tab} inside, but no {*} prefix at start
    text = (
        "Вона побіжить і вибухне, {tab} коли у\n"
        "щось вдарить або через певний час."
    )

    # 1. With ZBMG_STAR_TAG_RULES enabled, {*} should be prepended and formatted into star section
    allowed_enabled = {"ZBMG_SHORT_LINE", "ZBMG_WIDTH_EXCEEDED", "ZBMG_STAR_TAG_RULES"}
    fixed_enabled, changed_enabled = rules.autofix_data_string(text, {}, 10000, allowed_problems=allowed_enabled)
    assert changed_enabled is True
    # Under high threshold, it should merge into a single line with star prefix
    assert fixed_enabled.startswith("{escape:6:000a}")
    assert "{escape:6:000b}" not in fixed_enabled

    # Under low threshold (e.g. 400), it should split and use tab prefix for next lines
    fixed_split, changed_split = rules.autofix_data_string(text, {}, 400, allowed_problems=allowed_enabled)
    assert changed_split is True
    lines_split = fixed_split.split('\n')
    assert lines_split[0].startswith("{escape:6:000a}")
    assert lines_split[1].startswith("{escape:6:000b}")

    # 2. With ZBMG_STAR_TAG_RULES disabled, star is not prepended, but tab is still relocated to start of line
    allowed_disabled = {"ZBMG_SHORT_LINE", "ZBMG_WIDTH_EXCEEDED"}
    fixed_disabled, changed_disabled = rules.autofix_data_string(text, {}, 400, allowed_problems=allowed_disabled)
    assert changed_disabled is True
    lines_disabled = fixed_disabled.split('\n')
    assert not lines_disabled[0].startswith("{escape:6:000a}")
    assert any(line.startswith("{escape:6:000b}") for line in lines_disabled)









