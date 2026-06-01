import pytest
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
    lines = fixed_text.split('\n')
    # "and word here" must be wrapped to the second line because of threshold 800
    assert len(lines) >= 2
    assert "and word here" in lines[1]




