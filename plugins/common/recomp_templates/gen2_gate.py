"""Accept one more ROM SHA-1 in a Gen2Recomped checkout (src\\core\\GameVersion.lua), in place.

Usage: python -I set_gen2_gate_UA.py CHECKOUT VERSION CANONICAL_SHA1 ROM_SHA1

VERSION is the block name (gold, silver, crystal). CANONICAL_SHA1 is the block's own sha1 line. The script adds
ROM_SHA1 to the block's sha1Alt list (or adds a sha1Alt line after the sha1 line). It writes GameVersion.lua.bak
first and does nothing when ROM_SHA1 is already accepted. It exits with 1 when the block is not found once.
"""
import pathlib
import re
import shutil
import sys


def main(argv):
    checkout, version, canonical, rom_sha = argv
    path = pathlib.Path(checkout) / "src" / "core" / "GameVersion.lua"
    text = path.read_text(encoding="utf-8")
    # The block runs from its header to the first "  }," line; the sha1 line must be inside it.
    whole = re.compile(r"^  %s = \{\n(?:(?!^  \},).*\n)*" % re.escape(version), re.M)
    found = list(whole.finditer(text))
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
    if "sha1Alt = {" in body:
        new_body = body.replace("sha1Alt = { ", 'sha1Alt = { "%s", ' % rom_sha, 1)
    else:
        line = re.search(r"^    sha1 = \"%s\",[^\n]*\n" % re.escape(canonical), body, re.M)
        new_body = body[:line.end()] + '    sha1Alt = { "%s" },\n' % rom_sha + body[line.end():]
    shutil.copyfile(path, str(path) + ".bak")
    path.write_text(text.replace(body, new_body, 1), encoding="utf-8", newline="\n")
    print("accepted %s in block %s (backup: %s.bak)" % (rom_sha, version, path))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
