"""Accept a translated Gen 2 ROM in a Gen2Recomped checkout (src\\core\\GameVersion.lua, src\\import\\RomImporter.lua).

Usage: python -I set_gen2_gate_UA.py CHECKOUT VERSION CANONICAL_SHA1 ROM_SHA1 [POKE_SYM]

VERSION is the block name (gold, silver, crystal). CANONICAL_SHA1 is the block's own sha1 line. ROM_SHA1 is the
SHA-1 of the translated ROM. POKE_SYM is the .sym of the pret build that wrote that ROM. It is required when ROM_SHA1
is not CANONICAL_SHA1: the importer reads every table at the symbol addresses of the build, so the shipped manifest
of the block only fits the canonical ROM.

For a changed build the script does three things:
  1. adds ROM_SHA1 to sha1Alt of the block (the gate);
  2. writes tools/rom_manifest_<block>_<sha8>.json: the block's shipped manifest with every ROM symbol set to the
     address in POKE_SYM. RAM symbols (bank 0, address C000 and up) keep the shipped values, because the pret .sym
     and the shipped manifest disagree there and a text edit does not move RAM;
  3. adds manifestBySha1 to the block and makes RomImporter load that manifest for that SHA-1.

Each edited file gets a .bak first. A second run does nothing once applied. It exits with 1 when a block or a code
line is not found once, and with 2 on bad arguments.
"""
import json
import pathlib
import re
import shutil
import sys

GAME_VERSION = pathlib.Path("src") / "core" / "GameVersion.lua"
IMPORTER = pathlib.Path("src") / "import" / "RomImporter.lua"
OLD_DECODE = ("local function decodeManifest(version)\n"
              "  local path = GameVersion.info(version).manifest\n")
NEW_DECODE = ("local function decodeManifest(version, sha1)\n"
              "  local info = GameVersion.info(version)\n"
              "  local path = (sha1 and info.manifestBySha1 and info.manifestBySha1[sha1]) or info.manifest\n")
OLD_CALL = "    local manifest = decodeManifest(version)\n"
NEW_CALL = "    local manifest = decodeManifest(version, actualHash)\n"
RAM_START = 0xC000
SYM_LINE = re.compile(r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)$")


def read(path):
    """The text with LF line ends (the patterns use \\n), and the file's own line end for write()."""
    raw = path.read_bytes().decode("utf-8")
    return raw.replace("\r\n", "\n"), ("\r\n" if "\r\n" in raw else "\n")


def write(path, text, eol):
    shutil.copyfile(path, str(path) + ".bak")
    path.write_bytes(text.replace("\n", eol).encode("utf-8"))


def block_span(text, version):
    whole = re.compile(r"^  %s = \{\n(?:(?!^  \},).*\n)*" % re.escape(version), re.M)
    return list(whole.finditer(text))


def load_sym(path):
    table = {}
    for line in pathlib.Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        found = SYM_LINE.match(line.strip())
        if found:
            table.setdefault(found.group(3), [int(found.group(1), 16), int(found.group(2), 16)])
    return table


def remap(manifest, sym):
    """Set every ROM symbol to the pret .sym address. Returns (changed, kept)."""
    changed = kept = 0
    for name, loc in manifest["symbols"].items():
        new = sym.get(name)
        if new is None or (loc[0] == 0 and loc[1] >= RAM_START):
            kept += 1
        elif [loc[0], loc[1]] != new:
            manifest["symbols"][name] = new
            changed += 1
        else:
            kept += 1
    return changed, kept


def remap_text_placeholders(checkout, version, shipped, new_sym):
    """Move the baked {GEN2_TEXT:BB:AAAA:Label} placeholders that still point at the shipped label address.

    The importer reads the name-keyed texts from data/generated_gen2_<version>/text.lua, not from the manifest, so
    a moved label needs its placeholder moved too. A placeholder that points elsewhere is left alone.
    """
    path = checkout / "data" / ("generated_gen2_%s" % version) / "text.lua"
    if not path.is_file():
        return None
    text, eol = read(path)
    moved = 0

    def move(found):
        nonlocal moved
        bank, addr, name = int(found.group(1), 16), int(found.group(2), 16), found.group(3)
        target = new_sym.get(name)
        if target is None or shipped.get(name) != [bank, addr] or target == [bank, addr]:
            return found.group(0)
        moved += 1
        return "{GEN2_TEXT:%02x:%04x:%s}" % (target[0], target[1], name)

    text_new = re.sub(r"\{GEN2_TEXT:([0-9A-Fa-f]+):([0-9A-Fa-f]+):([^}]+)\}", move, text)
    if moved:
        write(path, text_new, eol)
    return moved


def add_sha_alt(body, canonical, rom_sha):
    if "sha1Alt = {" in body:
        return body.replace("sha1Alt = { ", 'sha1Alt = { "%s", ' % rom_sha, 1)
    line = re.search(r"^    sha1 = \"%s\",[^\n]*\n" % re.escape(canonical), body, re.M)
    return body[:line.end()] + '    sha1Alt = { "%s" },\n' % rom_sha + body[line.end():]


def main(argv):
    if len(argv) not in (4, 5):
        print(__doc__)
        return 2
    checkout, version, canonical, rom_sha = pathlib.Path(argv[0]), argv[1], argv[2], argv[3]
    poke_sym = pathlib.Path(argv[4]) if len(argv) == 5 else None
    path = checkout / GAME_VERSION
    text, eol = read(path)
    found = block_span(text, version)
    if len(found) != 1:
        print("block %s not found once (%d matches)" % (version, len(found)))
        return 1
    body = found[0].group(0)
    if canonical not in body:
        print("block %s does not hold the canonical sha1" % version)
        return 1
    if rom_sha in body:
        print("already accepted: %s" % rom_sha)
        return 0
    if poke_sym is None:
        print("a changed ROM needs the pret .sym (POKE_SYM) of its build")
        return 1
    manifest_rel = re.search(r'^    manifest = "([^"]+)",', body, re.M)
    if not manifest_rel:
        print("block %s has no manifest line" % version)
        return 1
    shipped = checkout / manifest_rel.group(1)
    manifest = json.loads(shipped.read_text(encoding="utf-8"))
    new_sym = load_sym(poke_sym)
    shipped_syms = {name: list(loc) for name, loc in manifest["symbols"].items()}
    changed, kept = remap(manifest, new_sym)
    placeholders = remap_text_placeholders(checkout, version, shipped_syms, new_sym)
    manifest["romSha1"] = rom_sha
    sha8 = rom_sha[:8]
    rel = "tools/rom_manifest_%s_%s.json" % (version, sha8)
    target = checkout / rel
    target.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    new_body = add_sha_alt(body, canonical, rom_sha)
    new_body = new_body.replace(manifest_rel.group(0), manifest_rel.group(0) + '\n    manifestBySha1 = { ["%s"] = "%s" },'
                                % (rom_sha, rel), 1)
    write(path, text.replace(body, new_body, 1), eol)
    importer = checkout / IMPORTER
    imp_text, imp_eol = read(importer)
    if NEW_DECODE not in imp_text:
        if imp_text.count(OLD_DECODE) != 1 or imp_text.count(OLD_CALL) != 1:
            print("importer decode lines not found once; GameVersion.lua was changed, RomImporter.lua was not")
            return 1
        write(importer, imp_text.replace(OLD_DECODE, NEW_DECODE, 1).replace(OLD_CALL, NEW_CALL, 1), imp_eol)
    print("accepted %s in block %s; manifest %s (%d symbols moved, %d kept); text placeholders moved: %s"
          % (rom_sha, version, rel, changed, kept, "none (no data/generated_gen2_%s/text.lua)" % version
             if placeholders is None else placeholders))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
