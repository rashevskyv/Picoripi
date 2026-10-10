"""MSBT Editor game configs (.gcf): the YAML subset reads, tags expand (type, typeMap, discard), and the names lay
over a plugin catalogue while its argument layout stays."""
from plugins.common import gcf
from plugins.common.lms_tags import TagCodec
from plugins.common.msbt import Tag

CONFIG = """game: "Test Game"

msbt:
  tags:
    - name: color
      description: changes the colour
      group: 0
      type: 3
      arguments:
        - name: id
          dataType: s16
          valueMap:
            -1: Reset
            0: Default
    - name: anim
      description: an animation
      group: 3
      discard: true
    - name: string
      group: 5
      typeMap:
        0: PlayerName
        7: Catchphrase
    - name: delay
      group: 7
      type: 0
      arguments:
        - name: frames
          dataType: u16
"""


def test_a_config_parses_and_its_tags_expand():
    entries = {(e["group"], e["type"]): e for e in gcf.tag_entries(gcf.parse(CONFIG))}
    assert entries[(0, 3)]["value_names"] == {0: {-1: "Reset", 0: "Default"}}
    assert entries[(3, None)]["name"] == "anim"
    assert entries[(5, 7)]["name"] == "string_Catchphrase"
    assert entries[(7, 0)]["arg_names"] == ["frames"]


def test_names_lay_over_a_catalogue_and_old_names_still_read():
    catalogue = {(3, 37): ("G3_37", (), "x"), (5, 7): ("G5_7", (), "x"), (7, 0): ("G7_0", ("u32",), "x"),
                 (9, 1): ("G9_1", (), "x")}
    tags, names, renamed = gcf.overlay(catalogue, {}, gcf.tag_entries(gcf.parse(CONFIG)))
    assert tags[(3, 37)][0] == "anim37" and tags[(5, 7)][0] == "string_Catchphrase"
    assert tags[(7, 0)][:2] == ("delay", ("u32",))          # the verified layout wins over the config's u16
    assert tags[(9, 1)][0] == "G9_1"                        # a tag the config does not know keeps its name
    codec = TagCodec(tags, names, renamed)
    delay = Tag(7, 0, bytes([8, 0, 0, 0]))
    assert codec.to_editor([delay]) == "{delay:8}"
    assert codec.from_editor("{G7_0:8}{G5_7}") == [delay, Tag(5, 7, b"")]
