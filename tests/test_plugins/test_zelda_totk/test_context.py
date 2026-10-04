"""TotK speakers (event flows), reference languages, layouts and the scrambled-font wrapper."""
import struct

import pytest

from core.font_formats import bfotf
from plugins.zelda_totk import event_flow, reference
from plugins.common.msbt import Msbt
from plugins.zelda_totk.rules import CUTSCENE_WIDTH, GameRules

from . import samples


def _rules_with(member, labels):
    rules = GameRules()
    msbt = Msbt(samples.msbt([(label, samples.text("x")) for label in labels]))
    rules._member = lambda block_idx: (member, msbt)
    return rules


class TestSpeakers:
    def test_a_talk_line_gets_the_english_name_of_its_actor(self):
        rules = _rules_with("EventFlowMsg/Npc_Kakariko002.msbt", ["talk0123"])
        assert rules.get_speaker_for_string(0, 0) == "Paya"
        assert not rules.is_placeholder_speaker("Paya")
        context = rules.get_ai_flow_context_for_string(0, 0)
        assert "spoken by Paya" in context and "event flow" in context

    def test_a_cutscene_line_takes_the_speaker_parameter(self):
        rules = _rules_with("EventFlowMsg/DmT_OP_GanonWakeUp.msbt", ["DmT_OP_GanonWakeUp_Text_006_b"])
        assert rules.get_speaker_for_string(0, 0) == "Demon King Ganondorf"

    def test_lines_no_flow_shows_have_no_speaker(self):
        assert _rules_with("LayoutMsg/Title_00.msbt", ["0000"]).get_speaker_for_string(0, 0) is None

    def test_the_speaker_parameter_overrides_the_actor(self):
        params = {"MessageId": "EventFlowMsg/Dm_X:T_00", "Speaker": "Npc_Zelda_Opening"}
        assert list(event_flow._talks("VoicePlayActor", "EventStartVoice", params)) == [
            ("Npc_Zelda_Opening", "EventStartVoice", "EventFlowMsg/Dm_X:T_00")]

    def test_one_character_is_a_speaker_several_are_not(self):
        assert event_flow.speaker_of({"Npc_A": 2, "GameSystemActor": 1}) == "Npc_A"
        assert event_flow.speaker_of({"Npc_A": 1, "Npc_B": 1}) is None
        assert event_flow.message_key("EventFlowMsg/Npc_A:Talk_00") == ("EventFlowMsg/Npc_A.msbt", "Talk_00")


def test_cutscene_subtitles_are_wider_than_the_talk_window(monkeypatch):
    rules = GameRules()
    monkeypatch.setattr(rules, "_archive_member", lambda block: ("USen.Product.140.sarc.zs", "EventFlowMsg/Dm_ZO_0032.msbt"))
    assert rules.get_string_layout(0, 0)["max_width"] == CUTSCENE_WIDTH
    monkeypatch.setattr(rules, "_archive_member", lambda block: ("USen.Product.140.sarc.zs", "EventFlowMsg/Npc_A.msbt"))
    assert rules.get_string_layout(0, 0) is None


def test_other_language_archives_are_references(tmp_path):
    mals = tmp_path / "romfs" / "Mals"
    mals.mkdir(parents=True)

    def archive(text):
        return samples.sarc({"EventFlowMsg/A.msbt": samples.msbt([("T0", samples.text(text)), ("T1", samples.text("2"))])})

    (mals / "USen.Product.140.sarc.zs").write_bytes(archive("Hello"))
    (mals / "EUru.Product.140.sarc.zs").write_bytes(archive("Привет"))
    (mals / "JPja.Product.140.sarc.zs").write_bytes(archive("こんにちは"))

    loaded = reference.load_languages(tmp_path / "romfs", {3: ("USen.Product.140.sarc.zs", "EventFlowMsg/A.msbt")})

    assert set(loaded) == {"Russian (RU)", "Japanese (JA)"}      # the project's own language is not a reference
    assert loaded["Russian (RU)"] == {(3, 0): "Привет", (3, 1): "2"}


def test_a_scrambled_font_unscrambles_and_scrambles_back():
    font = b"OTTO" + struct.pack(">HHHH", 0, 0, 0, 0) + b"data" * 5
    key = 0x028501A6
    scrambled = bfotf.encrypt(font, key)
    assert bfotf.is_bfotf(scrambled)
    assert bfotf.decrypt(scrambled) == (font, key)
    assert not bfotf.is_bfotf(b"SARC" + bytes(28))


@pytest.mark.parametrize("value, shown", [(0.6, "0.6"), (1.5, "1.5"), (5.0, "5")])
def test_floats_show_their_shortest_exact_form(value, shown):
    from plugins.common.lms_tags import float_text as _float_text
    assert _float_text(struct.unpack("<f", struct.pack("<f", value))[0]) == shown
