"""Hades text codec: SJSON strings and subtitle CSV lines, on synthetic files (no game data in the repo)."""
from plugins.hades import text

SJSON = (b'{\r\n  /* note */\r\n  lang = "en"\r\n  Texts = [\r\n'
         b'    {\r\n      Id = "Hades_Line01"\r\n      DisplayName = "Synthetic line one."\r\n    }\r\n'
         b'    {\r\n      Id = "Hades_Line02"\r\n      DisplayName = "Quote \\"here\\""\r\n'
         b'      Description = """Raw "one" line"""\r\n    }\r\n  ]\r\n}\r\n')

CSV = (b'"Synthetic","ID","ID","ID","","","","Line","","","Notes"\r\n'
       b'"Integrated","Hades_","0002","Hades_0002","","","","Synthetic line two, with a comma.","","",""\r\n'
       b'"Integrated","Hades_","0003","Hades_0003","","","","Plain line","","",""\r\n')


def test_sjson_rows_are_the_display_and_description_strings():
    assert text.read_sjson(SJSON) == ["Synthetic line one.", 'Quote \\"here\\"', 'Raw "one" line']


def test_sjson_unchanged_rows_keep_every_byte():
    rows = text.read_sjson(SJSON)
    out, warnings = text.write_sjson(SJSON, rows)
    assert out == SJSON and warnings == []


def test_sjson_changed_row_writes_over_its_span_only():
    rows = text.read_sjson(SJSON)
    rows[0] = "Changed row one."
    out, warnings = text.write_sjson(SJSON, rows)
    assert warnings == []
    assert text.read_sjson(out) == rows
    assert out.count(b"\r\n") == SJSON.count(b"\r\n")
    assert b'Id = "Hades_Line02"' in out


def test_sjson_row_with_a_quote_is_escaped():
    rows = text.read_sjson(SJSON)
    rows[0] = 'Changed "quoted" row'
    out, _ = text.write_sjson(SJSON, rows)
    assert text.read_sjson(out)[0] == r'Changed \"quoted\" row'


def test_sjson_row_count_change_keeps_the_file():
    out, warnings = text.write_sjson(SJSON, ["only one"])
    assert out == SJSON and warnings


def test_csv_rows_are_the_line_column_after_the_header():
    assert text.read_csv(CSV) == ["Synthetic line two, with a comma.", "Plain line"]


def test_csv_changed_row_changes_one_cell_and_keeps_line_endings():
    rows = text.read_csv(CSV)
    rows[1] = "Changed csv row, with a comma"
    out, warnings = text.write_csv(CSV, rows)
    assert warnings == []
    assert text.read_csv(out) == rows
    assert out.count(b"\r\n") == CSV.count(b"\r\n")
    assert out.endswith(b"\r\n")


def test_csv_unchanged_file_keeps_every_byte():
    out, warnings = text.write_csv(CSV, text.read_csv(CSV))
    assert out == CSV and warnings == []
