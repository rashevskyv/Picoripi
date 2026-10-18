"""Control tags across the games of a series: the neutral form, the carry-over per plugin pair, the blocked cases, and the
series lookup of the translation memory (plugins/common/series_tags.py)."""
import importlib

import pytest

from core.saved_translations_manager import SavedTranslationsManager
from core.translation.series_memory import index_neutral_rows, source_hash
from plugins.common import gen5msg, gfmsg
from plugins.common.series_tags import TagMap, body_kind, carry, kind_by_name, neutral_of, tags_of, tag_fields
from test_core.test_translation_memory import _window

GFMSG = gfmsg.SERIES_TAG_MAP
GEN5 = gen5msg.SERIES_TAG_MAP
GEN1 = importlib.import_module("plugins.pokemon_gen1.tag_manager").SERIES_TAG_MAP
GSC = importlib.import_module("plugins.pokemon_gsc.tag_manager").SERIES_TAG_MAP
GEN4 = importlib.import_module("plugins.pokemon_gen4.tag_manager").SERIES_TAG_MAP
BDSP = importlib.import_module("plugins.pokemon_bdsp.tag_manager").SERIES_TAG_MAP
MD3DS = importlib.import_module("plugins.pokemon_md_3ds.tag_manager").SERIES_TAG_MAP
FR = importlib.import_module("plugins.pokemon_fr.rules").SERIES_TAG_MAP


def _row(source, translation, tag_map, project="Other"):
    """A memory row as the game of ``tag_map`` saves it."""
    return {"source": source, "translation": translation, "project": project, **tag_fields(source, tag_map)}


class TestNeutralForm:
    def test_a_tag_becomes_its_kind_and_the_text_is_folded(self):
        assert neutral_of("Hi  {PAGE} There {VAR 0100 0000}!", GFMSG) == "hi⟨page⟩there⟨name⟩!"

    def test_the_same_text_in_two_syntaxes_has_one_neutral_form(self):
        assert neutral_of("Hi {VAR 0101 0000}, {PAGE}!", GEN5) == neutral_of("Hi {VAR 0100 0000}, {PAGE}!", GFMSG)

    def test_a_grammar_branch_has_no_kind_and_no_neutral_form(self):
        assert tags_of("M{GENDER 00FF|aster|iss}", GFMSG) is None
        assert neutral_of("M{GENDER 00FF|aster|iss}", GFMSG) is None
        assert tag_fields("M{GENDER 00FF|aster|iss}", GFMSG) == {}

    def test_a_glyph_keeps_its_code_so_it_matches_no_other_glyph(self):
        assert tags_of("A {CHAR E447}", GEN5) == [("{CHAR E447}", "icon:E447")]
        assert neutral_of("A {CHAR E447}", GEN5) != neutral_of("A {CHAR E305}", GFMSG)

    def test_body_kind_and_kind_by_name(self):
        assert body_kind("{text_ram wStringBuffer}") == body_kind("[text_ram   wStringBuffer]") == "tag:text_ram wStringBuffer"
        assert kind_by_name("{cont}", {"cont": "scroll"}) == "scroll"
        assert kind_by_name("{PLAYER}", {"cont": "scroll"}) == "tag:PLAYER"


class TestCarryAcrossPairs:
    """Each pair of syntaxes with synthetic tags: a translation of one game written in the other game's syntax."""

    @pytest.mark.parametrize("row_map, target_map, row_source, row_translation, target_source, expected", [
        # gen 5 (DS) -> gen 6/7/Switch (gfmsg): a name the game inserts keeps its kind, the page is the same
        (GEN5, GFMSG, "Hi {VAR 0101 0000}, {PAGE}!", "Привіт, {VAR 0101 0000}! {PAGE}Далі.",
         "Hi {VAR 0100 0000}, {PAGE}!", "Привіт, {VAR 0100 0000}! {PAGE}Далі."),
        # gfmsg -> gen 5: the other direction
        (GFMSG, GEN5, "Hi {VAR 0100 0000}{SCROLL}", "Привіт {VAR 0100 0000}{SCROLL}",
         "Hi {VAR 0101 0000}{SCROLL}", "Привіт {VAR 0101 0000}{SCROLL}"),
        # gen 2 (pret [command]) -> gen 1 ({command}): the same text command and the same RAM buffer
        (GSC, GEN1, "Hi [text_ram wStringBuffer][cont]Bye", "Привіт [text_ram wStringBuffer][cont]Бувай",
         "Hi {text_ram wStringBuffer}{cont}Bye", "Привіт {text_ram wStringBuffer}{cont}Бувай"),
        # gen 1 -> gen 2: the other direction
        (GEN1, GSC, "{cont}Hi", "{cont}Привіт", "[cont]Hi", "[cont]Привіт"),
        # gen 4 (DS pret) -> gen 5: a page break is the same kind in both
        (GEN4, GEN5, "{PAGE}Hi", "{PAGE}Привіт", "{PAGE}Hi", "{PAGE}Привіт"),
        # Brilliant Diamond (rich text, {scroll}) -> gen 4 ({SCROLL}): the scroll is the same kind
        (BDSP, GEN4, "Hi{scroll}there", "Привіт{scroll}там", "Hi{SCROLL}there", "Привіт{SCROLL}там"),
        # Fire Red (pret {NAME}) -> gen 4 ({NAME}): a player name is the same kind in both
        (FR, GEN4, "Hi {PLAYER}!", "Привіт, {PLAYER}!", "Hi {PLAYER}!", "Привіт, {PLAYER}!"),
    ])
    def test_a_translation_carries_across_the_syntax(self, row_map, target_map, row_source, row_translation,
                                                     target_source, expected):
        row = _row(row_source, row_translation, row_map)
        assert row["syntax"] == row_map.name
        assert carry(row["translation"], row, target_source, target_map) == (expected, "")

    def test_the_same_syntax_carries_only_with_the_same_tags(self):
        same = _row("Hi {VAR 0100 0000}", "Привіт {VAR 0100 0000}", GFMSG)
        assert carry(same["translation"], same, "Hi {VAR 0100 0000}", GFMSG) == ("Привіт {VAR 0100 0000}", "")
        ok, reason = carry(same["translation"], same, "Hi {VAR 0101 0000}", GFMSG)
        assert ok is None and "not the tags of this text" in reason

    def test_a_kind_that_the_other_game_does_not_have_blocks_the_carry(self):
        # md_3ds [NAME] has the kind tag:NAME; the gen 2 text has another kind here: no pair, no carry
        row = _row("Hi [NAME]", "Привіт [NAME]", MD3DS)
        assert carry(row["translation"], row, "Hi [text_ram wStringBuffer]", GSC)[0] is None


class TestBlockedCarry:
    @pytest.mark.parametrize("row_map, target_map, row_source, row_translation, target_source, phrase", [
        # the translation adds a tag the text does not have
        (GEN5, GFMSG, "Hi there", "Привіт {PAGE}там", "Hi there", "not a tag of the current text"),
        # the translation drops a tag of the text
        (GEN5, GFMSG, "Hi {PAGE}there", "Привіт там", "Hi {PAGE}there", "lacks a tag of the current text"),
        # two different name tags in one text: the pairing is not known
        (GEN5, GFMSG, "{VAR 0101 0000} and {VAR 0101 0001}", "{VAR 0101 0000} і {VAR 0101 0001}",
         "{VAR 0100 0000} and {VAR 0100 0001}", "pairing is not known"),
        # the glyphs of two games are different glyphs: their kinds differ
        (GEN5, GFMSG, "A {CHAR E447}", "А {CHAR E447}", "A {CHAR E305}", "do not have the same kinds"),
        # a tag in the translation that the game does not write
        (GEN5, GFMSG, "Hi", "Привіт [PLAYER]", "Hi", "this game does not have"),
    ])
    def test_a_tag_that_cannot_be_mapped_blocks_the_carry_and_says_why(self, row_map, target_map, row_source,
                                                                       row_translation, target_source, phrase):
        row = _row(row_source, row_translation, row_map)
        text, reason = carry(row["translation"], row, target_source, target_map)
        assert text is None
        assert phrase in reason


class TestPluginDeclarations:
    @pytest.mark.parametrize("plugin, syntax", [
        ("pokemon_gen1", "gen1"), ("pokemon_gsc", "gsc"), ("pokemon_fr", "fr"), ("pokemon_gen4", "gen4"),
        ("pokemon_gen5", "gen5msg"), ("pokemon_gen6", "gfmsg"), ("pokemon_gen7", "gfmsg"), ("pokemon_nx", "gfmsg"),
        ("pokemon_trinity", "gfmsg"), ("pokemon_md_3ds", "md_3ds"), ("pokemon_bdsp", "bdsp"),
    ])
    def test_every_pokemon_plugin_declares_its_tag_kinds(self, plugin, syntax):
        rules = importlib.import_module(f"plugins.{plugin}.rules")
        declared = rules.GameRules.get_series_tag_map(None)
        assert isinstance(declared, TagMap)
        assert declared.name == syntax


class TestSeriesLookup:
    """The translation memory of this game offers what another game of the series saved, in this game's tags."""

    @pytest.fixture
    def manager(self, tmp_path):
        data = [["Hi {VAR 0100 0000}, {PAGE}!", "Hi there"]]
        mw = _window(tmp_path, data)
        mgr: SavedTranslationsManager = mw.saved_translations_manager
        mgr.series_tag_map = GFMSG
        mgr.context_for = lambda block, string, source: {"speaker": "NONE", "speaker_en": "Ann", "addressee": "", "fold": "f"}
        mgr.configure_series_reuse(True, 0, True)  # sentences only are reused (D45); this text is one
        return mgr

    def _set_series(self, mgr, rows):
        memory = {}
        for row in rows:
            row.setdefault("speaker", "NONE")
            row.setdefault("speaker_en", "Ann")
            row.setdefault("addressee", "")
            memory.setdefault(source_hash(row["source"]), []).append(row)
        mgr.series_memory = memory
        mgr.series_neutral = index_neutral_rows(memory)

    def test_a_row_of_another_syntax_is_offered_with_its_tags_converted(self, manager):
        self._set_series(manager, [_row("Hi {VAR 0101 0000}, {PAGE}!", "Привіт, {VAR 0101 0000}! {PAGE}Далі.", GEN5, "BW")])
        own, series = manager.acceptable_rows(0, 0, "Hi {VAR 0100 0000}, {PAGE}!")
        assert own == []
        assert [(row["translation"], row["project"], row["origin"]) for row in series] == [
            ("Привіт, {VAR 0100 0000}! {PAGE}Далі.", "BW", "series_mapped")
        ]

    def test_a_row_that_cannot_be_carried_is_offered_nowhere_and_its_reason_is_known(self, manager):
        self._set_series(manager, [_row("Hi {VAR 0101 0000}, {PAGE}!", "Привіт {PAGE}!", GEN5, "BW")])
        _, series = manager.acceptable_rows(0, 0, "Hi {VAR 0100 0000}, {PAGE}!")
        # the blocked row is listed for its reason, but it has no translation to apply
        assert [row for row in series if row["applicable"]] == []
        project, reason = manager.blocked_series_reason(0, 0, "Hi {VAR 0100 0000}, {PAGE}!")
        assert project == "BW"
        assert "lacks a tag of the current text" in reason

    def test_the_other_speaker_gets_a_doubtful_series_row_that_is_not_ticked(self, manager):
        row = _row("Hi {VAR 0101 0000}, {PAGE}!", "Привіт, {VAR 0101 0000}! {PAGE}Далі.", GEN5, "BW")
        row.update({"speaker": "Someone else", "speaker_en": "Bob", "addressee": ""})
        self._set_series(manager, [row])
        _, series = manager.acceptable_rows(0, 0, "Hi {VAR 0100 0000}, {PAGE}!")
        assert [(c["safe"], c["reason"]) for c in series] == [(False, "The speaker names differ.")]

    def test_a_row_saved_before_the_tag_kinds_is_not_matched_across_syntaxes(self, manager):
        old = {"source": "Hi {VAR 0101 0000}, {PAGE}!", "translation": "Привіт", "project": "BW",
               "speaker": "NONE", "addressee": ""}
        self._set_series(manager, [old])
        _, series = manager.acceptable_rows(0, 0, "Hi {VAR 0100 0000}, {PAGE}!")
        assert series == []
