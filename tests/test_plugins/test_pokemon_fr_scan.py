"""The C-text scanner of the Generation III facts: which source lines the image builds, and why a missing literal is missing."""
from tools import pokemon_fr_c_texts as scan


def _reasons(text, variant="RUBY", revision=0):
    return scan.conditional_reasons(text, variant, revision)


SOURCE = "\n".join([
    "a",
    "#if DEBUG",
    "b",
    "#endif",
    "#if REVISION >= 1",
    "c",
    "#else",
    "d",
    "#endif",
    "#ifdef SAPPHIRE",
    "e",
    "#endif",
])


def test_debug_and_revision_branches_are_left_out_of_the_retail_image():
    assert _reasons(SOURCE) == ["", "debug", "debug", "", "revision", "revision", "", "", "", "other_language",
                                "other_language", ""]


def test_a_revision_one_image_builds_the_revision_branch():
    reasons = _reasons(SOURCE, revision=1)
    assert reasons[5] == ""           # c: REVISION >= 1 holds
    assert reasons[7] == "revision"   # d: the else branch of REVISION >= 1 is left out


def test_a_version_macro_selects_its_own_branch():
    assert _reasons(SOURCE, variant="SAPPHIRE")[10] == ""
    assert _reasons(SOURCE, variant="RUBY")[10] == "other_language"


def test_an_expression_with_a_size_suffix_is_read():
    text = "#if __STDC_VERSION__ < 202311L\nx\n#endif"
    assert _reasons(text) == ["", "", ""]     # an undefined name is 0, so 0 < 202311L holds and the block is built


def test_defined_selects_the_version_branch():
    text = "#if defined(FIRERED)\na\n#elif defined(LEAFGREEN)\nb\n#endif"
    assert _reasons(text, variant="FIRERED") == ["", "", "other_language", "other_language", ""]
    assert _reasons(text, variant="LEAFGREEN") == ["other_language", "other_language", "", "", ""]


def test_missing_literals_are_classed_by_their_cause():
    assert scan.missing_class("debug", "POS:") == "debug_build"
    assert scan.missing_class("revision", "This can't be used") == "other_revision"
    assert scan.missing_class("", "{COLOR WHITE}{HIGHLIGHT TRANSPARENT}      ") == "fill"
    assert scan.missing_class("", "CHERRY") == "missing"
