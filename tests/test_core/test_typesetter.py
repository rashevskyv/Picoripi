"""The typesetter: fill to the target, no hanging function word, no lone word on the last line, pages."""
from core.typesetter import typeset_page, typeset_text


def ten_px(line: str) -> int:
    """One pixel per character times ten, tags count as nothing."""
    import re
    return len(re.sub(r"\{[^}]*\}|\[[^\]]*\]", "", line)) * 10


class TestPage:
    def test_words_fill_up_to_the_target(self):
        assert typeset_page("один два три чотири п'ять", ten_px, 100) == ["один два", "три чотири", "п'ять"]

    def test_a_preposition_or_conjunction_never_ends_a_line(self):
        # "в" would end the first line at the target; it goes down with the next word.
        assert typeset_page("Лінк іде в ліс", ten_px, 110) == ["Лінк іде", "в ліс"]
        assert typeset_page("Він сказав, що і ти підеш", ten_px, 150) == ["Він сказав,", "що і ти підеш"]

    def test_no_single_word_alone_on_the_last_line(self):
        # Greedy would give "один два три" / "ліс": one word is pulled down instead.
        assert typeset_page("один два три ліс", ten_px, 120) == ["один два", "три ліс"]
        # ...but not when the line above would be left with one word itself.
        assert typeset_page("один два три", ten_px, 100) == ["один два", "три"]

    def test_the_limit_is_used_only_when_a_rule_asks_for_it(self):
        # Pulling "три" down makes a 16-character line: allowed by a limit of 160, not by the target of 150.
        assert typeset_page("один два три чотирнадцять", ten_px, 150, 160) == ["один два", "три чотирнадцять"]
        assert typeset_page("один два три чотирнадцять", ten_px, 150, 150) == ["один два три", "чотирнадцять"]

    def test_tags_belong_to_their_word_and_cost_nothing(self):
        assert typeset_page("{color:red}Рупія{/color} коштує [icon 3] сто", ten_px, 110) == [
            "{color:red}Рупія{/color}", "коштує [icon 3] сто"]

    def test_a_word_wider_than_the_limit_stays_alone(self):
        assert typeset_page("надзвичайнодовгеслово і", ten_px, 50) == ["надзвичайнодовгеслово", "і"]
        assert typeset_page("", ten_px, 50) == []


class TestText:
    def test_pages_are_kept_and_reflowed_inside(self):
        text, added = typeset_text("один\nдва три\n\nчотири п'ять\n", ten_px, 100)
        assert text == "один два\nтри\n\nчотири\nп'ять\n" and added == 0

    def test_a_page_that_needs_too_many_lines_becomes_two(self):
        text, added = typeset_text("один два три чотири п'ять шість", ten_px, 100, lines_per_page=2)
        assert text == "один два\nтри чотири\n\nп'ять\nшість" and added == 1
