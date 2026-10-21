#!/bin/bash
# Re-recompile a GBA recomp port checkout for a translated pret ROM (WSL). Written by Picoripi into the package;
# __ROM__, __CODE__, __SHA1__, __OLD_SHA1__, __VARIANT__, __TARGET__, __NAME__ and __RF_OLD__ are filled in there.
# Usage: bash recompile_UA.sh ELF CHECKOUT GBARECOMP GBA_RECOMPILE BUILD_DIR
#   ELF           the pret build's ELF (WSL path), e.g. pokeemerald.elf from the 2_build.bat build
#   CHECKOUT      the port checkout (WSL path); its variants/<variant>/ is rewritten
#   GBARECOMP     the gbarecomp checkout that the port pins (WSL path)
#   GBA_RECOMPILE the built gba_recompile binary (WSL path)
#   BUILD_DIR     a work folder for logs and the port build (WSL path)
# Steps: 1 readelf the ELF, 2 import its symbols against this ROM (gbarecomp's importer), 3 derive a base config
# for this ROM (game_<sha8>.toml: the new [identity] sha1; the ReadFlash1 stack copy source when the port has one),
# 4 regenerate the C with gba_recompile, 5 configure and build the port against the gbarecomp checkout.
set -euo pipefail
# cmake's find_program scans PATH; WSL's Windows entries (/mnt/*) make every scan a slow Windows-mount round trip.
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ELF="$1"; CHECKOUT="$2"; GB="$3"; GBRC="$4"; BUILD="$5"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROM="$HERE/__ROM__"
CODE="__CODE__"
SHA="__SHA1__"
OLD="__OLD_SHA1__"
VARIANT="__VARIANT__"
TARGET="__TARGET__"
NAME="__NAME__"
RF_OLD="__RF_OLD__"
VAR="$CHECKOUT/variants/$VARIANT"
SYM="$VAR/symbols"
mkdir -p "$SYM" "$BUILD"
readelf -sW "$ELF" > "$BUILD/syms.txt"
readelf -SW "$ELF" > "$BUILD/sections.txt"
python3 "$GB/tools/symbol_import/import_decomp_symbols.py" \
  --id "$CODE" --name "$NAME" \
  --syms "$BUILD/syms.txt" \
  --sections "$BUILD/sections.txt" \
  --rom "$ROM" \
  --code-copy-pair "IntrMain_Buffer=IntrMain:arm" \
  --code-copy-pair "SoundMainRAM_Buffer=SoundMainRAM:thumb" \
  --out "$SYM" > "$BUILD/import.log" 2>&1 || { echo IMPORT_FAILED; tail -20 "$BUILD/import.log"; exit 1; }
echo "IMPORT_OK sha1=$SHA"
BASE="$VAR/game_${SHA:0:8}.toml"
sed "s/$OLD/$SHA/g" "$VAR/game.toml" > "$BASE"
# A port that stack-copies a helper keeps its ROM address in the base config. The ROM moved, so take the new one.
if [ -n "$RF_OLD" ]; then
  # awk reads to the end: an early exit would close the pipe and, under pipefail, stop the script.
  RF_NEW=$(readelf -sW "$ELF" | awk '$8=="ReadFlash1" {v=$2} END {print v}')
  if [ -n "$RF_NEW" ]; then
    RF_SRC=$(printf "0x%08x" $(( 0x$RF_NEW & ~1 )))
    sed -i "s/source_start  = $RF_OLD/source_start  = $RF_SRC/" "$BASE"
    echo "READFLASH1_SOURCE=$RF_SRC"
  fi
fi
rm -f "$VAR/generated"/*.c "$VAR/generated"/*.cpp "$VAR/generated"/*.h
"$GBRC" --rom "$ROM" \
  --config "$BASE" \
  --config "$SYM/${CODE}_symbols.toml" \
  --symbols "$SYM/imported_symbols.tsv" \
  --data-symbols "$SYM/imported_data_symbols.tsv" \
  --out "$VAR/generated" --max-functions 65536 > "$BUILD/recompile.log" 2>&1 || { echo RECOMPILE_FAILED; tail -30 "$BUILD/recompile.log"; exit 1; }
echo "RECOMPILE_OK"
tail -5 "$BUILD/recompile.log"
cmake -S "$CHECKOUT" -B "$BUILD/port" -G Ninja -DCMAKE_BUILD_TYPE=Release -DGBAGAME_RECOMP_UI=OFF -DGBARECOMP_ROOT="$GB" > "$BUILD/port_configure.log" 2>&1 || { echo PORT_CONFIG_FAILED; tail -30 "$BUILD/port_configure.log"; exit 1; }
cmake --build "$BUILD/port" --target "$TARGET" -j16 > "$BUILD/port_build.log" 2>&1 || { echo PORT_BUILD_FAILED; tail -30 "$BUILD/port_build.log"; exit 1; }
echo "PORT_BUILD_OK"
find "$BUILD/port" -maxdepth 2 -name "$TARGET*" -type f
