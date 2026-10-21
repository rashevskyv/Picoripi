#!/bin/bash
# Re-recompile an EmeraldRecomp checkout for a translated pret ROM (WSL). Written by Picoripi into the package;
# __ROM__, __CODE__ and __SHA1__ are filled in there.
# Usage: bash recompile_UA.sh ELF CHECKOUT GBARECOMP GBA_RECOMPILE BUILD_DIR
#   ELF           pokeemerald.elf of the 2_build.bat build (WSL path)
#   CHECKOUT      the EmeraldRecomp checkout (WSL path); its variants/emerald/ is rewritten
#   GBARECOMP     the gbarecomp checkout that the port pins (WSL path)
#   GBA_RECOMPILE the built gba_recompile binary (WSL path)
#   BUILD_DIR     a work folder for logs and the port build (WSL path)
# Steps: 1 readelf the ELF, 2 import its symbols against this ROM (the port's importer), 3 derive a base config for
# this ROM (game.toml with the new [identity] sha1; the USA file is not edited), 4 regenerate the C with
# gba_recompile, 5 build EmeraldRecomp against the gbarecomp checkout.
set -euo pipefail
# cmake's find_program scans PATH; WSL's Windows entries (/mnt/*) make every scan a slow Windows-mount round trip.
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ELF="$1"; CHECKOUT="$2"; GB="$3"; GBRC="$4"; BUILD="$5"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROM="$HERE/__ROM__"
CODE="__CODE__"
SHA="__SHA1__"
OLD="f3ae088181bf583e55daf962a92bb46f4f1d07b7"
VAR="$CHECKOUT/variants/emerald"
SYM="$VAR/symbols"
mkdir -p "$SYM" "$BUILD"
readelf -sW "$ELF" > "$SYM/pokeemerald_emerald_syms.txt"
readelf -SW "$ELF" > "$SYM/pokeemerald_emerald_sections.txt"
python3 "$GB/tools/symbol_import/import_decomp_symbols.py" \
  --id "$CODE" --name "Pokemon Emerald Version (USA)" \
  --syms "$SYM/pokeemerald_emerald_syms.txt" \
  --sections "$SYM/pokeemerald_emerald_sections.txt" \
  --rom "$ROM" \
  --code-copy-pair "IntrMain_Buffer=IntrMain:arm" \
  --code-copy-pair "SoundMainRAM_Buffer=SoundMainRAM:thumb" \
  --out "$SYM" > "$BUILD/import.log" 2>&1 || { echo IMPORT_FAILED; tail -20 "$BUILD/import.log"; exit 1; }
echo "IMPORT_OK sha1=$SHA"
BASE="$VAR/game_${SHA:0:8}.toml"
sed "s/$OLD/$SHA/g" "$VAR/game.toml" > "$BASE"
"$GBRC" --rom "$ROM" \
  --config "$BASE" \
  --config "$SYM/${CODE}_symbols.toml" \
  --symbols "$SYM/imported_symbols.tsv" \
  --data-symbols "$SYM/imported_data_symbols.tsv" \
  --out "$VAR/generated" --max-functions 65536 > "$BUILD/recompile.log" 2>&1 || { echo RECOMPILE_FAILED; tail -30 "$BUILD/recompile.log"; exit 1; }
echo "RECOMPILE_OK"
cmake -S "$CHECKOUT" -B "$BUILD/port" -G Ninja -DCMAKE_BUILD_TYPE=Release -DGBARECOMP_ROOT="$GB" > "$BUILD/port_configure.log" 2>&1 || { echo PORT_CONFIG_FAILED; tail -30 "$BUILD/port_configure.log"; exit 1; }
cmake --build "$BUILD/port" --target EmeraldRecomp -j16 > "$BUILD/port_build.log" 2>&1 || { echo PORT_BUILD_FAILED; tail -30 "$BUILD/port_build.log"; exit 1; }
echo "PORT_BUILD_OK"
find "$BUILD/port" -maxdepth 2 -name "EmeraldRecomp" -type f
