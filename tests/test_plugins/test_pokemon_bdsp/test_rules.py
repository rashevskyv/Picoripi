"""Pokémon BDSP message tables: words <-> editor text, unedited labels kept, edited labels rebuilt."""
import json

from plugins.pokemon_bdsp import msg
from plugins.pokemon_bdsp.rules import GameRules
from plugins.pokemon_bdsp.tag_manager import TagManager


def _w(pattern, event, text="", tag=-1, value=0.0, width=-1.0):
    return {"patternID": pattern, "eventID": event, "tagIndex": tag, "tagValue": value, "str": text,
            "strWidth": width}


def _tag(slot, group, tag_id, param=0, words=(), pattern=None):
    return {"tagIndex": slot, "groupID": group, "tagID": tag_id,
            "tagPatternID": {1: 0, 2: 1, 19: 5}[group] if pattern is None else pattern, "forceArticle": 0,
            "tagParameter": param, "tagWordArray": list(words), "forceGrmID": 0}


LABEL = {"labelIndex": 0, "arrayIndex": 0, "labelName": "msg_test_01",
         "styleInfo": {"styleIndex": 1, "colorIndex": -1, "fontSize": 42, "maxWidth": 900, "controlID": 0},
         "attributeValueArray": [-1, 0, 0, -1, 0],
         "tagDataArray": [_tag(0, 1, 0), _tag(1, 2, 1, 205), _tag(0, 19, 1, 0, ("Candy", "Candies"))],
         "wordDataArray": [_w(7, 1, "Hello, ", width=80.0), _w(5, 0, tag=0), _w(0, 0, "! You have ", width=90.0),
                           _w(5, 0, tag=1), _w(0, 0, " ", width=8.0), _w(5, 0, tag=2),
                           _w(7, 3, ".", width=5.0), _w(2, 0, "<color=#F01E1EFF>"), _w(0, 0, "Red", width=30.0),
                           _w(2, 0, "</color>"), _w(7, 2, "...", value=0.5), _w(0, 7, " Bye", width=40.0)]}
TEXT = ("Hello, \n{tag:0:1:0}! You have {tag:1:2:1:205} {tag:0:19:1:0|Candy|Candies}.{scroll}\n"
        "<color=#F01E1EFF>Red</color>...{wait:0.5} Bye")


def _table() -> bytes:
    pad = {"labelIndex": 0, "arrayIndex": 0, "labelName": "", "styleInfo": LABEL["styleInfo"],
           "attributeValueArray": [], "tagDataArray": [], "wordDataArray": []}
    return msg.dump_table({"m_Name": "english_test", "langID": 2, "labelDataArray": [LABEL, pad]})


def test_label_text_and_back():
    assert msg.label_text(LABEL) == TEXT
    words, tags = msg.text_words(TEXT, msg.end_pattern(LABEL))
    assert tags == LABEL["tagDataArray"]
    assert [{k: v for k, v in w.items() if k != "strWidth"} for w in words] == \
           [{k: v for k, v in w.items() if k != "strWidth"} for w in LABEL["wordDataArray"]]
    measured = [w["strWidth"] >= 0 for w in words]
    assert measured == [w["strWidth"] >= 0 for w in LABEL["wordDataArray"]]


def test_closing_event_word_and_empty_text():
    words, _tags = msg.text_words("Line\nlast", end_pattern=7)
    assert [(w["patternID"], w["eventID"], w["str"]) for w in words] == [(7, 1, "Line"), (7, 7, "last")]
    words, _tags = msg.text_words("")
    assert [(w["patternID"], w["eventID"]) for w in words] == [(7, 7)]
    words, _tags = msg.text_words("{tag:0:1:0}")
    assert [(w["patternID"], w["eventID"]) for w in words] == [(5, 7)]


def test_rules_save_unedited_table_byte_for_byte_and_rebuild_an_edit():
    raw = _table()
    rules = GameRules()
    blocks, names = rules.load_data_from_json_obj(raw)
    assert blocks == [[TEXT]]
    assert rules.save_data_to_json_obj(blocks, names) == raw
    blocks[0][0] = "UA TEST {tag:0:1:0}"
    saved = rules.save_data_to_json_obj(blocks, names)
    label = json.loads(saved)["labelDataArray"][0]
    assert [w["str"] for w in label["wordDataArray"]] == ["UA TEST ", ""]
    assert label["tagDataArray"] == [_tag(0, 1, 0)]
    assert GameRules().load_data_from_json_obj(saved)[0] == [["UA TEST {tag:0:1:0}"]]


def test_tags_are_legitimate_only_when_they_encode():
    manager = TagManager(None) if TagManager.__init__.__code__.co_argcount > 1 else TagManager()
    assert manager.is_tag_legitimate("{tag:0:19:1:0|he|she}")
    assert manager.is_tag_legitimate("{scroll}")
    assert manager.is_tag_legitimate("<color=#FF0000FF>")
    assert not manager.is_tag_legitimate("{tag:1}")
