"""Tests for pass-3 translate driver (core/glossary_build/translate_driver.py)."""
from core.glossary_build.translate_driver import propose_translations
from core.glossary_manager import TranslationVariant


class TestVariants:
    def test_single_variant_not_flagged_multiple(self):
        result = propose_translations(
            "Ordon", "a village", lambda t, d: [{"translation": "Ордон", "rationale": "translit"}]
        )
        assert len(result.variants) == 1
        assert result.active == "Ордон"
        assert result.multiple is False

    def test_multiple_variants_flagged(self):
        result = propose_translations(
            "Spring Goron",
            "runs the hot spring",
            lambda t, d: [
                {"translation": "Ґорон Джерела", "rationale": "spring = bath"},
                {"translation": "Весняний Ґорон", "rationale": "spring = season"},
            ],
        )
        assert len(result.variants) == 2
        assert result.multiple is True
        assert result.active == "Ґорон Джерела"  # first is active

    def test_capped_to_max(self):
        raws = [{"translation": f"v{i}"} for i in range(10)]
        result = propose_translations("X", "", lambda t, d: raws, max_variants=3)
        assert len(result.variants) == 3

    def test_dedup_by_casefold(self):
        raws = [{"translation": "Link"}, {"translation": "link"}, {"translation": "LINK"}]
        result = propose_translations("Link", "", lambda t, d: raws)
        assert len(result.variants) == 1

    def test_custom_normalizer_dedup(self):
        from core.glossary_manager import GlossaryManager

        raws = [{"translation": "Ордон"}, {"translation": "ордон "}]
        result = propose_translations(
            "Ordon", "", lambda t, d: raws, normalize=GlossaryManager.normalize_term
        )
        assert len(result.variants) == 1


class TestInputForms:
    def test_accepts_translation_variant_objects(self):
        raws = [TranslationVariant("Мідна", "name")]
        result = propose_translations("Midna", "", lambda t, d: raws)
        assert result.variants[0].translation == "Мідна"
        assert result.variants[0].rationale == "name"

    def test_accepts_bare_strings(self):
        result = propose_translations("Midna", "", lambda t, d: ["Мідна"])
        assert result.active == "Мідна"

    def test_blank_translations_dropped(self):
        raws = [{"translation": "  "}, {"translation": "Real"}]
        result = propose_translations("X", "", lambda t, d: raws)
        assert [v.translation for v in result.variants] == ["Real"]


class TestEdgeCases:
    def test_empty_result(self):
        result = propose_translations("X", "", lambda t, d: [])
        assert result.variants == []
        assert result.active == ""
        assert result.multiple is False

    def test_none_result(self):
        result = propose_translations("X", "", lambda t, d: None)
        assert result.active == ""
