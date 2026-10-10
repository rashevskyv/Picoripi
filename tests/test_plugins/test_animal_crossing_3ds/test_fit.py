"""Animal Crossing 3DS windows without game data: which window a file shows in, line widths in the game font (sizes,
inserted names, look-alike letters), re-wrapping with the game's breaks, answer lines and the two plugin rules."""
from types import SimpleNamespace

from plugins.animal_crossing_3ds import fit
from plugins.animal_crossing_3ds.problems import ChoiceAnswersRule, PageLinesRule
from plugins.animal_crossing_3ds.rules import GameRules
from plugins.common.problem_rules.context import GameProblemProfile, RuleContext

FONT = {**{c: {"width": 10} for c in "abcdefghijklmnopqrstuvwxyzабвгдежзийклмнопрстуфхцчшщьюя.,!?"},
        " ": {"width": 5}, "i": {"width": 4}, "е": {"width": 9}}


def test_files_map_to_their_window():
    assert fit.kind_for_path("romfs/Script/Talk/NPC_Rover_Train.umsbt") == "dialogue"
    assert fit.kind_for_path("romfs/Script/MailN/Mail_AN_Bday.umsbt") == "letter"
    assert fit.kind_for_path("romfs/Script/Bbs/BBS_Event.umsbt") == "board"
    assert fit.kind_for_path("romfs/Script/Str/SYS_2D_Dialog_Text.umsbt") == "dialog"
    assert fit.kind_for_path("romfs/Script/Str/STR_Item_name.umsbt") == "item_name"
    assert fit.kind_for_path("romfs/Layout/x.arc/timg/y.bclim") is None


def test_widths_follow_size_tags_inserted_names_and_look_alikes():
    measure = fit.Measure(FONT, {"playerName": 80})
    assert measure.lines("ab c") == [35]
    assert measure.lines("a{size:200}a\na{size:100}a") == [30, 30]           # a size carries on to the next line
    assert measure.width("a {playerName}!") == 10 + 5 + 80 + 10
    assert measure.width("{delay:8}{anim37}a") == 10                          # other tags draw nothing
    assert measure.width("і є") == 4 + 5 + 9                                  # і as i, є as е until the font has them
    assert measure.lines("ab{pageBreak}c") == [20, 10]


def test_answers_are_split_off_and_kept():
    text = "Will you?{menu5:0}\nYes!\nNo."
    assert fit.split_choice(text) == ("Will you?{menu5:0}", ["Yes!", "No."])
    assert fit.split_choice("No question\nhere") == ("No question\nhere", [])
    measure = fit.Measure(FONT, {})
    long = "aaaa bbbb cccc dddd eeee ffff gggg hhhh{menu5:0}\nYes, a very very long answer\nNo."
    fitted = fit.fit(long, measure, 100, 3)
    assert fitted.endswith("{menu5:0}\nYes, a very very long answer\nNo.")


def test_fit_keeps_fitting_text_and_rewraps_the_rest_with_the_games_breaks():
    measure = fit.Measure(FONT, {})
    assert fit.fit("aa bb\ncc", measure, 100, 3) == "aa bb\ncc"
    wrapped = fit.fit("aaaa bbbb cccc dddd eeee ffff gggg hhhh. iiii jjjj", measure, 100, 2)
    assert all(width <= 100 for width in measure.lines(wrapped))
    assert "{pageBreak}" in wrapped and "\n" in wrapped
    assert all(len(page) <= 2 for page in fit.pages(wrapped))
    five = "a\nb\nc\nd\ne"                      # the dialogue box goes on by itself every 3 lines
    assert fit.fit(five, measure, 100, 3, auto_pages=True) == five
    assert fit.fit(five, measure, 100, 3) != five


def _context(text, original=None, block=None, rules=None):
    profile = GameProblemProfile(main_window=SimpleNamespace(current_game_rules=rules, data_store=None))
    return RuleContext(text=text, font_map={}, width_threshold=320, logical_hard_limit=320, lines_per_page=3,
                       default_tag_mappings={}, icon_sequences=[], original_text=original, block_idx=block,
                       game_profile=profile)


def test_answer_count_must_stay():
    rule = ChoiceAnswersRule()
    original = "Will you?{menu5:0}\nYes!\nNo."
    assert rule.detect(_context("Так?{menu5:0}\nТак!\nНі.", original)) == []
    matches = rule.detect(_context("Так?{menu5:0}\nТак! Ні.", original))
    assert matches and matches[0].line_index == 1


class _Rules:
    def __init__(self, kind):
        self.kind = kind

    def window_spec(self, block_idx):
        return fit.layouts()["kinds"][self.kind]


def test_fixed_row_windows_report_extra_lines_and_the_dialogue_box_does_not():
    seven = "\n".join("abcdefg")
    assert [m.line_index for m in PageLinesRule().detect(_context(seven, block=0, rules=_Rules("letter")))] == [6]
    assert PageLinesRule().detect(_context(seven, block=0, rules=_Rules("dialogue"))) == []


def test_rules_measure_and_wrap_by_the_files_window():
    project = SimpleNamespace(blocks=[SimpleNamespace(source_file="romfs/Script/Talk/x.umsbt"),
                                      SimpleNamespace(source_file="romfs/Script/Str/STR_Misc.umsbt")])
    main = SimpleNamespace(project_manager=SimpleNamespace(project=project), font_map=FONT,
                           block_to_project_file_map={}, data_store=SimpleNamespace(data=[]))
    rules = GameRules(main)
    assert rules.get_string_layout(0, 0) == {"warn_width": 320, "max_width": 320, "lines_per_page": 3,
                                             "font_file": "Garden_msg_size16.json"}
    assert rules.get_string_layout(1, 0) == {"font_file": "Garden_msg_size16.json"}
    text = " ".join(["абвгд"] * 20)
    wrapped = rules.fit_text_to_window(text, 0, 0)
    assert all(width <= 320 for width in rules._measure().lines(wrapped))
    assert rules.fit_text_to_window(text, 1, 0) is None
    assert "strict_tags" in rules.get_capabilities()
    fixed, changed = rules.autofix_data_string(text, FONT, 320, allowed_problems={"AC3DS_WIDTH_EXCEEDED"},
                                               block_idx=0, string_idx=0)
    assert changed and fixed == wrapped
