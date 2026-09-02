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


def test_uk_catalog_covers_main_window_chrome():
    i18n.init("uk")
    assert i18n.tr("Blocks (double-click to rename):").startswith("Блоки")
    assert i18n.tr("Warnings: {0} / {1}").format(0, 11).startswith("Попередження")
    assert i18n.tr("Plugin: {0}").format("Zelda: Twilight Princess BMG").startswith("Плагін")
    assert i18n.tr("None") == "Немає"
    assert i18n.tr("Dialogue") == "Діалог"
    assert i18n.tr("Tag Error") == "Помилка тегу"
    i18n.init("en")


def test_uk_catalog_covers_bfn_editor_chrome():
    i18n.init("uk")
    assert i18n.tr("BFN Font Editor v{0}", "1.0.21").startswith("Редактор шрифтів BFN")
    assert i18n.tr("Font Editor") == "Редактор шрифту"
    assert i18n.tr("Glyph Table") == "Таблиця гліфів"
    assert i18n.tr("Texture Sheets:") == "Текстурні аркуші:"
    assert i18n.tr("Save Changes (Ctrl+S)") == "Зберегти зміни (Ctrl+S)"
    assert i18n.tr("Sync with editor") == "Синхронізувати з редактором"
    i18n.init("en")
    assert i18n.tr("Font Editor") == "Font Editor"


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
