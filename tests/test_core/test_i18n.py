from core import i18n


def test_shipped_languages_are_english_and_ukrainian_only():
    assert i18n.SHIPPED_UI_LANGUAGES == ("en", "uk")
    assert i18n.available_languages() == ["en", "uk"]
    assert "ru" not in i18n.available_languages()


def test_tr_english_is_the_source_key():
    i18n.init("en")
    assert i18n.tr("&Language") == "&Language"
    assert i18n.tr("Save Changes") in ("Save Changes", i18n._catalog.get("Save Changes", "Save Changes"))


def test_uk_catalog_overrides_when_present():
    i18n.init("uk")
    assert i18n.tr("&Language") == "&Мова"
    assert "перезапуск" in i18n.tr("A restart is required to apply the new interface language.")
    i18n.init("en")
    assert i18n.tr("&Language") == "&Language"


def test_unknown_or_russian_falls_back_to_english():
    assert i18n.set_language("de") == "en"
    assert i18n.set_language("ru") == "en"
