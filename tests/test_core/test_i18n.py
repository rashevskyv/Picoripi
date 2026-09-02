import json

from core import i18n


def test_menu_lists_catalogs_that_have_translations():
    codes = i18n.available_languages()
    assert codes[0] == "en"
    assert "uk" in codes
    assert "ru" not in codes


def test_language_name_comes_from_the_catalog_file():
    assert i18n.language_display_name("en") == "English"
    assert i18n.language_display_name("uk") == "Українська"
    assert i18n.language_names()["uk"] == "Українська"


def test_tr_english_is_the_source_key():
    i18n.init("en")
    assert i18n.tr("&Language") == "&Language"


def test_uk_catalog_overrides_when_present():
    i18n.init("uk")
    assert i18n.tr("&Language") == "&Мова"
    assert "перезапуск" in i18n.tr("A restart is required to apply the new interface language.")
    i18n.init("en")
    assert i18n.tr("&Language") == "&Language"


def test_missing_string_stays_english():
    i18n.init("uk")
    missing = "This UI string is not in any catalog"
    assert i18n.tr(missing) == missing


def test_empty_translation_falls_back_to_english(tmp_path, monkeypatch):
    (tmp_path / "en.json").write_text(
        json.dumps({"@language_name": "English", "Save Changes": "Save Changes"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "xx.json").write_text(
        json.dumps({"@language_name": "Testish", "Save Changes": ""}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(i18n, "LOCALES_DIR", tmp_path)
    # Empty value does not count as a translation, so xx stays off the menu.
    assert "xx" not in i18n.available_languages()
    (tmp_path / "xx.json").write_text(
        json.dumps({"@language_name": "Testish", "Save Changes": "Savex"}, ensure_ascii=False),
        encoding="utf-8",
    )
    assert "xx" in i18n.available_languages()
    i18n.set_language("xx")
    assert i18n.tr("Save Changes") == "Savex"
    assert i18n.tr("Unknown chrome") == "Unknown chrome"


def test_unknown_or_russian_falls_back_to_english():
    assert i18n.set_language("zz-missing") == "en"
    assert i18n.set_language("ru") == "en"
