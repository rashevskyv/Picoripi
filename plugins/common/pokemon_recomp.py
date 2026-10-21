"""Recomp packages of the Pokemon ROM projects: one folder per dump with the ROM, a manifest and a README per PC port.

The ports read the cartridge at run time. EmeraldRecomp and FireRedLeafGreenRecomp take the ROM and its SHA-1 on the
command line. Gen2Recomp imports the ROM once into its own cache, and its gate lists the accepted dumps. This module
writes files only: it copies no port code and patches no runtime.

A translated ROM can change code addresses. Emerald then needs its port re-recompiled: the package copies
``recomp_templates/emerald_resym.sh``, which runs the port's own importer and ``gba_recompile`` on this ROM and the
new build's ELF (WSL). A Gen 2 package copies ``recomp_templates/gen2_gate.py``, which adds the ROM's SHA-1 to the
gate of the user's Gen2Recomp checkout.

Two kinds of project: a ROM-mode project (``rom\\base.*`` beside the source; the ROM is written by Picoripi) and a
pret workspace (``ISO\\`` holds the dumps; each ROM is the one ``2_build.bat`` wrote into ``build\\``).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core.i18n import tr

TARGET_ID = "recomp"
Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]
MakeRom = Callable[[str, str, str], str]          # (source_dir, translation_dir, output_dir) -> ROM path
ROM_SUFFIXES = (".gba", ".gbc")
TEMPLATES = Path(__file__).with_name("recomp_templates")
EMERALD_RESYM = "emerald_resym.sh"
GEN2_GATE = "gen2_gate.py"

GBA_RELEASE = "https://github.com/mstan/{repo}/releases/tag/v{version}"
# Base ROM SHA-1 -> the port that runs a translated copy of it. Only the dumps each port accepts.
# "built" is the ROM the pret workspace's 2_build.bat writes into build\; "canonical" is the Gen2Recomp block's own
# sha1 line (the gate script adds the ROM beside it); "zip" is the official release asset.
PORTS_BY_BASE_SHA1: Dict[str, Dict[str, str]] = {
    "f3ae088181bf583e55daf962a92bb46f4f1d07b7": {
        "id": "emerald", "kind": "gba", "folder": "EmeraldRecomp", "exe": "EmeraldRecomp.exe",
        "game": "Pokemon Emerald (USA)", "built": "pokeemerald.gba", "code": "BPEE",
        "zip": "EmeraldRecomp-windows-x64-v0.1.2.zip", "version": "0.1.2",
        "release": GBA_RELEASE.format(repo="EmeraldRecomp", version="0.1.2")},
    "41cb23d8dccc8ebd7c649cd8fbb58eeace6e2fdc": {
        "id": "firered", "kind": "gba", "folder": "FireRedLeafGreenRecomp", "exe": "FireRedRecomp.exe",
        "game": "Pokemon FireRed v1.0 (USA)", "built": "pokefirered.gba",
        "zip": "FireRedRecomp-windows-x64-v0.0.4.zip", "version": "0.0.4",
        "release": GBA_RELEASE.format(repo="FireRedLeafGreenRecomp", version="0.0.4")},
    "574fa542ffebb14be69902d1d36f1ec0a4afd71e": {
        "id": "leafgreen", "kind": "gba", "folder": "FireRedLeafGreenRecomp", "exe": "LeafGreenRecomp.exe",
        "game": "Pokemon LeafGreen (USA)", "built": "pokeleafgreen.gba",
        "zip": "LeafGreenRecomp-windows-x64-v0.0.4.zip", "version": "0.0.4",
        "release": GBA_RELEASE.format(repo="FireRedLeafGreenRecomp", version="0.0.4")},
    "d8b8a3600a465308c9953dfa04f0081c05bdcb94": {
        "id": "gold", "kind": "gen2", "folder": "Gen2Recomped", "game": "Pokemon Gold (USA)",
        "built": "pokegold.gbc", "block": "gold", "canonical": "d8b8a3600a465308c9953dfa04f0081c05bdcb94"},
    "49b163f7e57702bc939d642a18f591de55d92dae": {
        "id": "silver", "kind": "gen2", "folder": "Gen2Recomped", "game": "Pokemon Silver (USA)",
        "built": "pokesilver.gbc", "block": "silver", "canonical": "49b163f7e57702bc939d642a18f591de55d92dae"},
    "f2f52230b536214ef7c9924f483392993e226cfb": {
        "id": "crystal", "kind": "gen2", "folder": "Gen2Recomped", "game": "Pokemon Crystal (USA, Rev 1)",
        "built": "pokecrystal11.gbc", "block": "crystal", "canonical": "f2f52230b536214ef7c9924f483392993e226cfb"},
    "f4cd194bdee0d04ca4eac29e09b8e4e9d818c133": {
        "id": "crystal10", "kind": "gen2", "folder": "Gen2Recomped", "game": "Pokemon Crystal (USA, Rev 0)",
        "built": "pokecrystal.gbc", "block": "crystal", "canonical": "f2f52230b536214ef7c9924f483392993e226cfb"},
}

RUN_BAT = """@echo off
rem Starts {exe} with this translated ROM. Put {exe} and gba_bios.bin (your own BIOS dump) in this folder.
cd /d "%~dp0"
if not exist "{exe}" (echo {exe} is not in this folder & pause & exit /b 1)
if not exist gba_bios.bin (echo gba_bios.bin is not in this folder & pause & exit /b 1)
"{exe}" --bios gba_bios.bin --rom "{rom}" --rom-sha1 {rom_sha1}
"""

GBA_README = """{game}: українська збірка для {exe_family}

Що є в цій папці
  {rom}         перекладений ROM (SHA-1 {rom_sha1})
  recomp.json   маніфест: SHA-1 перекладеного ROM, розмір
  run_UA.bat    запускає {exe} з цим ROM
{resym_line}
Кроки
  1. Завантажте {zip} з офіційного релізу {release}.
     Розпакуйте архів у цю папку.
  2. Покладіть свій дамп GBA BIOS у цю папку під назвою gba_bios.bin
     (SHA-1 300c20df6731a33952ded8c436f7f186d25d3492).
{resym_steps}  3. Запустіть run_UA.bat. Порт перевіряє SHA-1 з командного рядка (--rom-sha1).

Обмеження
  Порт виконує ROM через статичну рекомпіляцію. Якщо збірка змінила розкладку коду, порт потребує
  нової рекомпіляції (recompile_UA.sh). Перевірте текст на тих екранах, які ви використовуєте.
"""

RESYM_LINE = "  recompile_UA.sh  перерекомпіляція порту під цей ROM (WSL, див. нижче)\n"
RESYM_STEPS = """  Якщо цей ROM відрізняється від оригіналу (зміна тексту в pret-збірці), виконайте один раз у WSL:
     bash recompile_UA.sh <ELF> <папка EmeraldRecomp> <папка gbarecomp> <gba_recompile> <папка збірки>
     <ELF>  pokeemerald.elf з 2_build.bat (WSL: ~/pk/work/pokeemerald/pokeemerald.elf)
     <gba_recompile>  зібраний з gbarecomp (WSL-шлях до бінарника)
     Скрипт імпортує символи, знову рекомпілює ROM у generated\\ порту і збирає EmeraldRecomp.
     Перед ним зберіть gba_recompile з gbarecomp (cmake --build <папка> --target gba_recompile).
"""

GEN2_README = """{game}: українська збірка для Gen2Recomp (LÖVE2D, джерело)

Що є в цій папці
  {rom}         перекладений ROM (SHA-1 {rom_sha1})
  recomp.json   маніфест: SHA-1 перекладеного ROM, розмір
  set_gen2_gate_UA.py  додає SHA-1 цього ROM до перевірки в копії Gen2Recomp

Кроки
  1. Завантажте Gen2Recomped-0.8.41.love з офіційного релізу UNDERdecoded/Gen2Recomped (тег v0.8.41).
     Розпакуйте його в нову папку, наприклад Gen2Recomped-src. Виконуваний .exe цю зміну не прийме.
  2. Завантажте середовище LÖVE 11.5 з love2d.org. Запускайте папку гри цим середовищем.
  3. Запустіть: python -I set_gen2_gate_UA.py "<папка Gen2Recomped-src>" {block} {canonical} {rom_sha1}
     Скрипт додає SHA-1 до sha1Alt у блоці "{block}" файлу src\\core\\GameVersion.lua і
     зберігає резервну копію GameVersion.lua.bak. Повторний запуск нічого не змінює.
  4. У папці гри створіть порожній файл portable.txt (тоді кеш лежить у самій папці).
  5. Скопіюйте {rom} у папку гри й один раз імпортуйте його з командного рядка:
         set POKEPORT_VERSION={block}
         set POKEPORT_IMPORT_ROM=<повний шлях до {rom}>
         set POKEPORT_IMPORT_ONLY=1
         "<папка LÖVE 11.5>\\love.exe" .
  6. Запустіть гру без POKEPORT_IMPORT_ONLY: "<папка LÖVE 11.5>\\love.exe" .

Обмеження
  Імпортер читає ROM за адресами оригінальної збірки. Пакет створено для ROM проєкту (rom\\base.*), у якому
  розкладка не змінюється. Перевірте текст на тих екранах, які ви використовуєте.
"""


def _sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    """Write through a temporary file in the same folder, then replace (AGENTS rule 9)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _is_rom_mode(ws: Path) -> bool:
    return (ws / "rom").is_dir()


def _dumps(ws: Path) -> List[Path]:
    """The dumps of the project: ``rom\\base.*`` in ROM mode, else the ROM files in the workspace ``ISO\\``."""
    if _is_rom_mode(ws):
        return sorted((ws / "rom").glob("base.*"))
    iso = ws / "ISO"
    return sorted(p for p in iso.iterdir() if p.suffix.lower() in ROM_SUFFIXES) if iso.is_dir() else []


def ports_for_source(source_dir: str) -> List[Dict[str, str]]:
    """Every port that runs a dump of this project, one entry per recognized dump (each with its ``base_sha1``)."""
    ws = Path(source_dir).parent
    dumps = _dumps(ws)
    if not dumps:
        raise ValueError(tr("This project was not unpacked from a ROM."))
    found = []
    for dump in dumps:
        sha = _sha1(dump)
        if sha in PORTS_BY_BASE_SHA1:
            found.append(dict(PORTS_BY_BASE_SHA1[sha], base_sha1=sha))
    if not found:
        raise ValueError(tr("No recomp port runs this ROM: {0}", _sha1(dumps[0])))
    return found


def port_for_source(source_dir: str) -> Dict[str, str]:
    """The first port of :func:`ports_for_source`."""
    return ports_for_source(source_dir)[0]


def _built_rom(ws: Path, port: Dict[str, str]) -> Path:
    path = ws / "build" / port["built"]
    if not path.is_file():
        raise ValueError(tr("The ROM is not built yet: run 2_build.bat in the project first ({0} is missing).",
                            str(path)))
    return path


def _write_gba(folder: Path, port: Dict[str, str], rom: str, rom_sha1: str, resym: bool) -> None:
    fields = {"game": port["game"], "exe_family": port["folder"], "rom": rom, "rom_sha1": rom_sha1,
              "exe": port["exe"], "zip": port["zip"], "release": port["release"]}
    _atomic_write(folder / "run_UA.bat", RUN_BAT.format(exe=port["exe"], rom=rom, rom_sha1=rom_sha1).encode("ascii"))
    _atomic_write(folder / "README_UA.txt", GBA_README.format(
        resym_line=RESYM_LINE if resym else "", resym_steps=RESYM_STEPS if resym else "", **fields).encode("utf-8"))
    if resym:
        script = (TEMPLATES / EMERALD_RESYM).read_text(encoding="utf-8")
        script = script.replace("__ROM__", rom).replace("__CODE__", port["code"]).replace("__SHA1__", rom_sha1)
        _atomic_write(folder / "recompile_UA.sh", script.encode("utf-8"))


def _write_gen2(folder: Path, port: Dict[str, str], rom: str, rom_sha1: str) -> None:
    shutil.copyfile(TEMPLATES / GEN2_GATE, folder / "set_gen2_gate_UA.py")
    _atomic_write(folder / "README_UA.txt", GEN2_README.format(
        game=port["game"], rom=rom, rom_sha1=rom_sha1, block=port["block"],
        canonical=port["canonical"]).encode("utf-8"))


def _check_changed_build(port: Dict[str, str], rom_sha1: str, base_sha1: str) -> bool:
    """Whether this pret build needs the Emerald re-recompile. Refuses the routes that are not built or verified."""
    if rom_sha1 == base_sha1:
        return False
    if port["id"] == "emerald":
        return True
    if port["kind"] == "gen2":
        raise ValueError(tr("The pret build of {0} changed the ROM. The Gen 2 importer reads the original "
                            "addresses, so package a ROM project for it.", port["game"]))
    raise ValueError(tr("The pret build of {0} changed the ROM. Its re-recompilation is not built yet; "
                        "package a ROM project for it.", port["game"]))


def build_package(source_dir: str, translation_dir: str, output_dir: str, make_rom: MakeRom,
                  progress: Progress, is_cancelled: Cancelled,
                  port: Optional[Dict[str, str]] = None) -> str:
    """Write one dump's package into ``output_dir/<port folder>/<port id>`` and return that folder ("" when cancelled).

    A ROM-mode project gets its ROM from ``make_rom``. A pret workspace gets the ROM ``2_build.bat`` built, for the
    given (or first) dump.
    """
    ws = Path(source_dir).parent
    port = port or port_for_source(source_dir)
    work = Path(output_dir) / "_rom"
    resym = False
    if _is_rom_mode(ws):
        progress(10, tr("Building the translated ROM"))
        rom = Path(make_rom(source_dir, translation_dir, str(work)))
    else:
        rom = _built_rom(ws, port)
        resym = _check_changed_build(port, _sha1(rom), port["base_sha1"])
    if is_cancelled():
        return ""
    folder = Path(output_dir) / port["folder"] / port["id"]
    folder.mkdir(parents=True, exist_ok=True)
    rom_sha1, rom_bytes = _sha1(rom), rom.stat().st_size
    shutil.copyfile(rom, folder / rom.name)
    shutil.rmtree(work, ignore_errors=True)
    manifest = {"port": port["id"], "game": port["game"], "rom": rom.name, "rom_sha1": rom_sha1,
                "rom_bytes": rom_bytes, "base_sha1": port["base_sha1"], "re_recompile": resym}
    _atomic_write(folder / "recomp.json", (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    if port["kind"] == "gen2":
        _write_gen2(folder, port, rom.name, rom_sha1)
    else:
        _write_gba(folder, port, rom.name, rom_sha1, resym)
    progress(100, tr("Done"))
    return str(folder)


def build_packages(source_dir: str, translation_dir: str, output_dir: str, make_rom: MakeRom,
                   progress: Progress, is_cancelled: Cancelled) -> str:
    """One package per recognized dump, under ``output_dir/recomp``. Returns that folder."""
    root = Path(output_dir) / "recomp"
    ports = ports_for_source(source_dir)
    for index, port in enumerate(ports):
        if is_cancelled():
            break
        build_package(source_dir, translation_dir, str(root), make_rom,
                      lambda p, m, i=index: progress(int(100 * (i + p / 100) / len(ports)), m),
                      is_cancelled, port)
    return str(root)
