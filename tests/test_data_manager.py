"""
Tests for core/data_manager.py — JSON/text file loading and saving.
These tests act as a safety net for refactoring Issue #9 (removing QMessageBox from core).
"""
from pathlib import Path
import json
import pytest

from core.data_manager import load_json_file, save_json_file, load_text_file, save_text_file


# ── load_json_file ──────────────────────────────────────────────────

class TestLoadJsonFile:
    def test_load_valid_file(self, sample_json_path, sample_json_data):
        """Load a valid JSON file and verify data matches."""
        data, error = load_json_file(sample_json_path)
        assert data == sample_json_data
        assert error is None

    def test_load_nonexistent_file(self, temp_dir):
        """Non-existent file should return None data and an error message."""
        path = Path(temp_dir) / "does_not_exist.json"
        data, error = load_json_file(str(path))
        assert data is None
        assert error is not None
        assert "not found" in error.lower()

    def test_load_invalid_json(self, invalid_json_path):
        """Malformed JSON should return None data and an error message."""
        data, error = load_json_file(invalid_json_path)
        assert data is None
        assert error is not None

    def test_load_empty_json_object(self, temp_dir):
        """An empty JSON object {} should load as an empty dict."""
        path = Path(temp_dir) / "empty.json"
        with open(path, 'w') as f:
            f.write("{}")
        data, error = load_json_file(str(path))
        assert data == {}
        assert error is None

    def test_load_json_array(self, temp_dir):
        """A JSON array should load correctly."""
        path = Path(temp_dir) / "array.json"
        with open(path, 'w') as f:
            json.dump(["a", "b", "c"], f)
        data, error = load_json_file(str(path))
        assert data == ["a", "b", "c"]
        assert error is None

    def test_load_json_with_cyrillic(self, temp_dir):
        """JSON with Cyrillic text should load correctly (UTF-8)."""
        path = Path(temp_dir) / "cyrillic.json"
        expected = {"text": "Привіт, світе!"}
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(expected, f, ensure_ascii=False)
        data, error = load_json_file(str(path))
        assert data == expected
        assert error is None


# ── save_json_file ──────────────────────────────────────────────────

class TestSaveJsonFile:
    def test_save_and_reload(self, temp_dir, sample_json_data):
        """Save data to a file and reload it — data should match."""
        path = Path(temp_dir) / "output.json"
        result = save_json_file(str(path), sample_json_data)
        assert result is True

        data, error = load_json_file(path)
        assert data == sample_json_data
        assert error is None

    def test_save_creates_parent_dirs(self, temp_dir):
        """Saving to a nested path should create parent directories."""
        path = Path(temp_dir) / "sub" / "deep" / "output.json"
        result = save_json_file(str(path), {"key": "value"})
        assert result is True
        assert path.exists()

    def test_save_with_cyrillic(self, temp_dir):
        """Saved JSON should preserve Cyrillic characters (ensure_ascii=False)."""
        path = Path(temp_dir) / "cyrillic_out.json"
        data = {"text": "Зельда: Мініш Кап"}
        save_json_file(str(path), data)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "Зельда" in content  # Not escaped as \u...


# ── load_text_file ──────────────────────────────────────────────────

class TestLoadTextFile:
    def test_load_utf8(self, sample_text_path, sample_text_content):
        """Load a UTF-8 text file."""
        content, error = load_text_file(sample_text_path)
        assert content == sample_text_content
        assert error is None

    def test_load_utf16_fallback(self, sample_utf16_path):
        """UTF-16 file should be loaded via fallback when UTF-8 fails."""
        content, error = load_text_file(sample_utf16_path)
        assert content is not None
        assert "Тестовий текст UTF-16" in content
        assert error is None

    def test_load_nonexistent(self, temp_dir):
        """Non-existent text file should return None content and error."""
        path = Path(temp_dir) / "nope.txt"
        content, error = load_text_file(str(path))
        assert content is None
        assert error is not None


# ── save_text_file ──────────────────────────────────────────────────

class TestSaveTextFile:
    def test_save_and_reload(self, temp_dir):
        """Save text and reload — content should match."""
        path = Path(temp_dir) / "output.txt"
        text = "Рядок 1\nРядок 2\n"
        result = save_text_file(str(path), text)
        assert result is True

        content, error = load_text_file(str(path))
        assert content == text

    def test_save_creates_parent_dirs(self, temp_dir):
        """Saving text to a nested path should create parent directories."""
        path = Path(temp_dir) / "a" / "b" / "c.txt"
        result = save_text_file(str(path), "test")
        assert result is True
        assert path.exists()
