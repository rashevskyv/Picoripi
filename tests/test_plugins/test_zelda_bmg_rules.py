import pytest
from plugins.zelda_bmg.rules import GameRules
from bmg_tool import BMGFile, BMGMessage

def test_ukrainian_character_mapping():
    rules = GameRules()
    
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

