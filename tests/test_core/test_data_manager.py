import pytest
import json
from pathlib import Path
from unittest.mock import patch, mock_open
from core.data_manager import load_json_file, save_json_file, load_text_file, save_text_file

def test_load_json_file(tmp_path):
    # File not found
    data, err = load_json_file(tmp_path / "nonexistent.json")
    assert data is None
    assert "not found" in err
    
    # Valid JSON
    f = tmp_path / "valid.json"
    f.write_text('{"key": "value"}', encoding='utf-8')
    data, err = load_json_file(f)
    assert data == {"key": "value"}
    assert err is None
    
    # Invalid JSON
    f2 = tmp_path / "invalid.json"
    f2.write_text('{invalid_json: 1}', encoding='utf-8')
    data, err = load_json_file(f2)
    assert data is None
    assert "Failed to load" in err
    assert "Check the file format" in err

def test_save_json_file(tmp_path):
    f = tmp_path / "save.json"
    assert save_json_file(f, {"test": 123}) is True
    assert json.loads(f.read_text(encoding='utf-8')) == {"test": 123}
    
    # Simulate error saving (e.g. read-only dir or type error)
    # MagicMock trick to throw error
    with patch('core.data_manager.Path.open', side_effect=PermissionError("Denied")):
        assert save_json_file(tmp_path / "fail.json", {}) is False

def test_load_text_file(tmp_path):
    # File not found
    content, err = load_text_file(tmp_path / "none.txt")
    assert content is None
    assert "not found" in err
    
    # Valid UTF-8
    f = tmp_path / "utf8.txt"
    f.write_text("Hello Укр", encoding='utf-8')
    content, err = load_text_file(f)
    assert content == "Hello Укр"
    assert err is None
    
    # UTF-16 Fallback
    f16 = tmp_path / "utf16.txt"
    f16.write_bytes("Hello UTF16".encode('utf-16'))
    content, err = load_text_file(f16)
    assert content == "Hello UTF16"
    assert err is None
    
    # Invalid completely
    fbad = tmp_path / "bad.txt"
    fbad.write_bytes(b'\xff\xfe\x00\x00\x00\x00\x00') # random garbage
    content, err = load_text_file(fbad)
    # The actual result might be content or None depending on how python tries to decode it.
    # But let's mock it to ensure Exception is hit for unknown error.
    with patch('core.data_manager.Path.open', side_effect=Exception("Unknown Error!")):
        c, e = load_text_file(fbad)
        assert c is None
        assert "An unknown error occurred" in e

def test_save_text_file(tmp_path):
    f = tmp_path / "savetext.txt"
    assert save_text_file(f, "Line 1") is True
    assert f.read_text(encoding='utf-8') == "Line 1"
    
    with patch('core.data_manager.Path.open', side_effect=PermissionError("Denied")):
        assert save_text_file(tmp_path / "fail.txt", "abc") is False

