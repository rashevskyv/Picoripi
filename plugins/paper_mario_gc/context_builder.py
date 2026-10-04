"""Build ``context.json`` of the Paper Mario: The Thousand-Year Door plugin from the game's own files.

    python -m plugins.paper_mario_gc.context_builder <extracted disc>\\files [--out plugins/paper_mario_gc/context.json]

Speakers: every ``evt_msg_print`` call in the area modules (``rel/<area>.rel``) names the message key and
the NPC whose balloon shows it (``"me"``: the NPC whose talk script runs it; ``"mario"``, ``"party"``; ``""``:
no balloon). The NPC names are the game's Japanese internal names; ``NPC_NAMES`` and the area's Goombella
tattles (keyed by the same Japanese name) turn them into English names. Items: the item table of
``main.dol`` (0x28 bytes per item: Japanese id, name key, description key, menu description key) says
which ``in_*`` name is a key item, an item or a badge. Only the derived names and keys are written.
"""
import argparse
import bisect
import json
import re
import struct
from collections import Counter, defaultdict
from pathlib import Path

from . import msgfile

EVT_MSG_PRINT = 0x800D284C            # main.dol (G8ME01) address of evt_msg_print
ITEM_TABLE_NAME = b"in_unknown_item"  # name key of item 0; the table starts 4 bytes before its pointer
BADGE_FIRST, ITEM_FIRST = 0xF0, 0x7D

# Japanese internal NPC name -> English (the game's English names; generic roles for unnamed NPCs)
NPC_NAMES = {
    "mario": "Mario", "party": "Partner", "extparty": "Partner", "dummy_party": "Partner",
    "(^x^)party": "Partner", "peach": "Princess Peach", "ピーチ姫": "Princess Peach",
    "クリハカセ": "Professor Frankly", "キノシコワ": "Jolene", "マルコ": "Flavio", "シュリョー": "Sir Grodus",
    "ガンス": "Grubba", "マッチョガンス": "Macho Grubba", "ババ": "Kammy Koopa", "ガラの悪い水夫": "Pa-Patch",
    "モニー": "Francesca", "マジョリン": "Beldam", "マリリン": "Marilyn", "ビビアン": "Vivian",
    "ピートン": "Frankie", "ピートン（指輪）": "Frankie", "村長": "Mayor", "マフィアボス": "Don Pianta",
    "マフィアボスカジノ": "Don Pianta", "マフィア１": "Vinny", "マフィア２": "Tony", "マフィア３": "Rocko",
    "ガイド": "Punio", "ガイドsp": "Punio", "プニオ": "Punio", "ガイド妹": "Petuni", "ライバル": "Puniper",
    "ポワン探偵": "Pennington", "プニ族長老": "Puni Elder", "プニ族": "Puni", "プニ情報屋": "Pungry",
    "プニ店員": "Pungent", "オドオド水夫": "Timid Toad sailor", "オドオド水夫兄": "Timid sailor's brother",
    "コルテス": "Cortez", "キノじい": "Toadsworth", "ホワイト": "General White", "サンダース": "Admiral Bobbery",
    "第三勢力幹部": "Lord Crump", "カンブー": "Lord Crump", "幹部": "X-Naut officer",
    "第三勢力部下": "X-Naut", "第三勢力部下Ａ": "X-Naut", "第三部下": "X-Naut", "手下１": "X-Naut",
    "手下２": "X-Naut", "手下３": "X-Naut", "研究員": "X-Naut scientist", "チュチュリーナ": "Ms. Mowz",
    "ブラックピーチ": "Shadow Queen (Peach)", "影の女王": "Shadow Queen", "ナンシー": "Zess T.",
    "ノコタロウ": "Koops", "ノコタロウ父": "Koopley", "ノコリン": "Koopie Koo", "水夫ボム兵Ａ": "Bomberto",
    "マイケル": "King K", "キノピコ": "Toadette", "にせマリオ": "Doopliss", "ランペル": "Doopliss",
    "ペラ魔人": "Black Chest demon", "クリスチーヌ": "Goombella", "クラウダ": "Flurrie", "ヨッシー": "Yoshi",
    "チビヨッシー": "Yoshi kid", "ルイージ": "Luigi", "クッパ": "Bowser", "飛クッパ": "Bowser",
    "カメック": "Kammy Koopa", "ブレッドハート": "Rawk Hawk", "チャンピョン": "Rawk Hawk",
    "めがね水夫": "Four-Eyes", "盗賊団親分": "Ishnail", "クラガリさん": "Darkly", "マダム": "Toodles",
    "バニーテレサ": "Lahla", "パワーアップ屋": "Merlon", "パワーダウン屋": "Chet Rippo",
    "うらない師": "Merluvlee", "まじない師": "Merlee", "星マニア": "Dazzle", "情報屋ケチ": "Wonky",
    "情報屋完璧": "Grifty", "マスター": "Podley", "マスター２": "Herb T.", "ボッタクール": "Charlieton",
    "行商人": "Charlieton", "ナリキンパパ": "Goldbob", "ナリキンママ": "Sylvia", "コナリキン": "Bub",
    "マッキノ": "Pine T.", "トロン": "Zip Toad", "ブロッツ": "Bandy Andy", "コック": "Chef Shimi",
    "グルメキノピオ": "Heff T.", "ファビオ": "Doe T.", "パレッタ": "Parakarry", "ゴンババ": "Hooktail",
    "ボンババ": "Gloomtail", "ゾンババ": "Bonetail", "ボスロボット": "Magnus von Grapple",
    "アトミックテレサ": "Atomic Boo", "トゲノコエース": "The Koopinator", "ポグ": "Sir Swoop",
    "ウラノコ": "Shellshock", "チェリー": "Jerry", "コブロン": "Whacka", "ス・クリーミ": "Luigi's pal",
    "トルク": "Luigi's pal", "キック": "Blooey", "キック２": "Blooey", "ラクガン": "Luigi's pal",
    "レサレサ": "Bow", "キザ野郎": "Dupree", "飛行船係員": "Airship steward", "車掌": "Conductor",
    "運転手": "Engineer", "ウェイトレス": "Waitress", "駅員": "Station worker", "駅員2": "Station worker",
    "土産屋": "Toadia", "門番": "Gatekeeper", "グルメボム兵": "Bob-omb gourmet", "セバスチャン": "Bootler",
    "サラリーマン": "Businessman", "オウム": "Parrot", "クリチェロ": "Goom Goom", "ノッコス": "Koopook",
    "モコリム": "Lumpy", "オクトール": "Master Crash", "ガンガン": "Cleftor", "ニトロ": "Nob",
    "ペントリット": "Rob", "スラリー": "Fred", "ボムヘイE": "Swob", "ボムヘイH": "Gob",
    "盗賊団１": "Gus", "盗賊団２": "Garf", "盗賊団３": "Goose", "ハンマーブロス": "Hamma Jamma",
    "店員": "Shop clerk", "店長": "Shop manager", "店の主人": "Shop owner", "お店の奥さん": "Shopkeeper's wife",
    "宿店員": "Innkeeper", "バッジ店長": "Badge shop manager", "バッジ店員": "Badge shop clerk",
    "おばさん": "Old woman", "ゆうれい": "Ghost", "テレサ": "Boo", "中央テレサ": "Boo",
    "奥扉テレサ": "Boo", "手前扉テレサ": "Boo", "黒カロン": "Dark Bones", "ゴールドチョロボン": "Gold Fuzzy",
    "ゲッソー": "Blooper", "ゲッソーのゲソ": "Blooper's tentacle", "ロボット": "Robot", "たまご": "Egg",
    "ガードマン": "Glitz Pit guard", "ジュゲムＡ": "Laki", "ホットドッグ": "Hot-dog vendor", "パタクリ": "Paragoomba",
    "見張り": "Lookout", "プニコ": "Puni", "ブロッツダミー": "Bandy Andy", "トゲノコＡ": "Spiky Koopa", "敵１": "Enemy", "敵２": "Enemy", "相手": "Opponent",
}
# Generic roles: a Japanese name that starts with the key (and maybe a letter or number) is this role
NPC_ROLES = {
    "クリボー": "Goomba", "ノコノコ": "Koopa", "キノピオ": "Toad", "水夫ボム兵": "Bob-omb sailor",
    "水夫": "Toad sailor", "ボロ水夫": "Shipwrecked Toad", "ボムヘイ": "Bob-omb", "ボロドー": "Bandit",
    "盗賊": "Bandit", "チューさん": "Squeek", "ロテン": "Doogan", "踊り子": "Traveling Sisters 3",
    "３人娘": "Traveling Sisters 3", "村人": "Twilighter", "ブタ": "Pig", "カラス": "Crow",
    "子供": "Kid", "客": "Customer", "kyaku": "Customer", "乗客": "Passenger", "プニ族": "Puni",
    "トゲ族": "Jabbi", "ターくん": "Poshley Heights resident", "ガードマン": "Glitz Pit guard",
    "ハンマー": "Hammer Bro", "ジュゲム": "Lakitu", "アイアン": "Iron Adonis", "シンエモン": "Hamma Bros",
    "カメラマン": "Cameraman", "ピンクボム兵": "Pink Bob-omb", "マフィア": "Pianta", "移動屋": "Mover",
}
_SUFFIX = re.compile(r"[0-9０-９A-ZＡ-Ｚa-z_]*$")


def _rel(data: bytes):
    """``(module id, section offsets, {file position of a 32-bit pointer: (module, section, addend)})``."""
    module_id, count, table = (struct.unpack_from(">I", data, at)[0] for at in (0, 0xC, 0x10))
    sections = [struct.unpack_from(">I", data, table + 8 * i)[0] & ~1 for i in range(count)]
    imp_off, imp_size = struct.unpack_from(">II", data, 0x28)
    pointers = {}
    for j in range(imp_size // 8):
        module, pos = struct.unpack_from(">II", data, imp_off + 8 * j)
        section = where = 0
        while True:
            delta, kind, target, addend = struct.unpack_from(">HBBI", data, pos)
            pos += 8
            if kind == 203:          # R_DOLPHIN_END
                break
            if kind == 202:          # R_DOLPHIN_SECTION
                section, where = target, 0
                continue
            where += delta
            if kind == 1:            # R_PPC_ADDR32
                pointers[sections[section] + where] = (module, target, addend)
    return module_id, sections, pointers


def _cstr(data: bytes, at: int):
    end = data.find(b"\0", at)
    return data[at:end] if end >= 0 else None


def rel_speakers(data: bytes):
    """``{message key: Counter(Japanese speaker name)}`` of one area module."""
    module_id, sections, pointers = _rel(data)

    def target(pos):
        ref = pointers.get(pos)
        if not ref or ref[0] != module_id or not sections[ref[1]]:
            return None
        return sections[ref[1]] + ref[2]

    def string(pos):
        at = target(pos)
        return _cstr(data, at) if at is not None else None

    talk_scripts = {}                 # NPC setup: name pointer, then the talk script pointer 0x14 later
    for pos in pointers:
        name = string(pos)
        if name and len(name) <= 40 and pos + 4 not in pointers and target(pos + 0xC) is not None \
                and target(pos + 0x14) is not None:
            talk_scripts.setdefault(target(pos + 0x14), name)
    starts = sorted({at for at in map(target, pointers) if at is not None})
    found = defaultdict(Counter)
    for pos, (module, _section, addend) in pointers.items():
        if module != 0 or addend != EVT_MSG_PRINT:
            continue
        key, name = string(pos + 8), string(pos + 16)
        if not key:
            continue
        if name == b"me":                 # the NPC whose talk script holds this call
            i = bisect.bisect_right(starts, pos) - 1
            name = next((talk_scripts[starts[j]] for j in range(i, max(-1, i - 40), -1)
                         if starts[j] in talk_scripts), None)
        if name:
            found[key.decode("cp932", "replace")][name.decode("cp932", "replace")] += 1
    return found


def tattle_names(entries):
    """``{Japanese NPC name: English name}`` from the area's tattles ("That's Frankie, ...")."""
    names = {}
    for entry in entries:
        if not any(c >= 0x80 for c in entry.key):
            continue
        text = re.sub(r"\{[^}]*\}", "", msgfile.decode(entry.text)).replace("\n", " ")
        match = re.search(r"(?:That's|This is|That guy's|This guy's) ([A-Z][\w'-]*(?: [A-Z][\w'-]*)*)[,.!]", text)
        if match and match.group(1) not in ("Mario", "That", "This", "Mr", "Ms", "Mrs"):
            names[entry.name] = match.group(1)
    return names


def english_name(jp: str, tattles: dict, enemies: dict):
    if jp in enemies:
        return enemies[jp]
    if jp in NPC_NAMES:
        return NPC_NAMES[jp]
    if jp in tattles:
        return tattles[jp]
    base = _SUFFIX.sub("", jp)
    for role in sorted(NPC_ROLES, key=len, reverse=True):
        if base.startswith(role):
            return NPC_ROLES[role]
    return None if jp.isascii() else jp       # internal ids (T_1, e_bero) say nothing; keep Japanese


def item_kinds(dol: bytes):
    """``{name key: "key_item" | "item" | "badge"}`` from main.dol's item table."""
    offsets, addresses, sizes = (struct.unpack_from(">18I", dol, at) for at in (0, 0x48, 0x90))

    def to_offset(address):
        for off, start, size in zip(offsets, addresses, sizes):
            if size and start <= address < start + size:
                return off + address - start
        return None

    name_at = dol.index(ITEM_TABLE_NAME + b"\0")
    name_address = next(start + name_at - off for off, start, size in zip(offsets, addresses, sizes)
                        if size and off <= name_at < off + size)
    first = dol.index(struct.pack(">I", name_address)) - 4
    kinds = {}
    for index in range(0x200):
        words = struct.unpack_from(">4I", dol, first + index * 0x28)
        at = to_offset(words[1])
        if at is None:
            break
        key = _cstr(dol, at).decode("ascii", "replace")
        if key.startswith("in_") and key != ITEM_TABLE_NAME.decode():
            kinds.setdefault(key, "badge" if index >= BADGE_FIRST else "item" if index >= ITEM_FIRST else "key_item")
    return kinds


def build_context(files: Path) -> dict:
    msg_dir = files / "msg" / "US"
    area_entries = defaultdict(list)
    for path in sorted(msg_dir.glob("*.txt")):
        area_entries[path.stem.split("_")[0]].extend(msgfile.parse(path.read_bytes()))
    enemies = {e.name: msgfile.decode(e.text) for e in area_entries["global"] if e.name.startswith("btl_un_")}
    speakers, unnamed = {}, Counter()
    for rel in sorted((files / "rel").glob("*.rel")):
        area = rel.stem.rstrip("0123456789")
        tattles = tattle_names(area_entries.get(area, []))
        for key, names in sorted(rel_speakers(rel.read_bytes()).items()):
            jp = names.most_common(1)[0][0]
            name = english_name(jp, tattles, enemies)
            if name:
                speakers.setdefault(area, {})[key] = name
                if not name.isascii():
                    unnamed[name] += 1
    return {
        "source": {"game": "G8ME01", "generator": "plugins.paper_mario_gc.context_builder"},
        "speakers": speakers,
        "items": item_kinds((files.parent / "sys" / "main.dol").read_bytes()),
        "unnamed_speakers": dict(unnamed.most_common()),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", type=Path, help="the disc's files folder (has msg/, rel/; ../sys/main.dol)")
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("context.json"))
    args = parser.parse_args(argv)
    context = build_context(args.files)
    args.out.write_text(json.dumps(context, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
    lines = sum(len(v) for v in context["speakers"].values())
    print(f"{args.out}: {lines} messages with a speaker, {len(context['items'])} items")


if __name__ == "__main__":
    main()
