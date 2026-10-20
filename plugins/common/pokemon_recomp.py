"""Recomp package of the Pokemon ROM projects: the translated ROM, a manifest and a README per PC port.

The ports read the cartridge at run time. EmeraldRecomp and FireRedLeafGreenRecomp take the ROM and its SHA-1 on the
command line. Gen2Recomp imports the ROM once into its own cache, and its gate lists the accepted dumps. This module
writes files only: it copies no port code and patches no runtime. A Gen 2 package names the one line the owner adds
to the port's own checkout.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Callable, Dict

from core.i18n import tr

TARGET_ID = "recomp"
Progress = Callable[[int, str], None]
Cancelled = Callable[[], bool]
MakeRom = Callable[[str, str, str], str]          # (source_dir, translation_dir, output_dir) -> ROM path

GBA_RELEASE = "https://github.com/mstan/{repo}/releases/tag/v{version}"
# Base ROM SHA-1 -> the port that runs a translated copy of it. Only the dumps each port accepts.
PORTS_BY_BASE_SHA1: Dict[str, Dict[str, str]] = {
    "f3ae088181bf583e55daf962a92bb46f4f1d07b7": {
        "id": "emerald", "kind": "gba", "folder": "EmeraldRecomp", "exe": "EmeraldRecomp.exe",
        "game": "Pokemon Emerald (USA)", "release": GBA_RELEASE.format(repo="EmeraldRecomp", version="0.1.2")},
    "41cb23d8dccc8ebd7c649cd8fbb58eeace6e2fdc": {
        "id": "firered", "kind": "gba", "folder": "FireRedLeafGreenRecomp", "exe": "FireRedRecomp.exe",
        "game": "Pokemon FireRed v1.0 (USA)",
        "release": GBA_RELEASE.format(repo="FireRedLeafGreenRecomp", version="0.0.4")},
    "574fa542ffebb14be69902d1d36f1ec0a4afd71e": {
        "id": "leafgreen", "kind": "gba", "folder": "FireRedLeafGreenRecomp", "exe": "LeafGreenRecomp.exe",
        "game": "Pokemon LeafGreen (USA)",
        "release": GBA_RELEASE.format(repo="FireRedLeafGreenRecomp", version="0.0.4")},
    "d8b8a3600a465308c9953dfa04f0081c05bdcb94": {
        "id": "gold", "kind": "gen2", "folder": "Gen2Recomped", "game": "Pokemon Gold (USA)"},
    "49b163f7e57702bc939d642a18f591de55d92dae": {
        "id": "silver", "kind": "gen2", "folder": "Gen2Recomped", "game": "Pokemon Silver (USA)"},
    "f2f52230b536214ef7c9924f483392993e226cfb": {
        "id": "crystal", "kind": "gen2", "folder": "Gen2Recomped", "game": "Pokemon Crystal (USA, Rev 1)"},
    "f4cd194bdee0d04ca4eac29e09b8e4e9d818c133": {
        "id": "crystal", "kind": "gen2", "folder": "Gen2Recomped", "game": "Pokemon Crystal (USA, Rev 0)"},
}

RUN_BAT = """@echo off
rem Starts {exe} with this translated ROM. Put {exe} and gba_bios.bin (your own BIOS dump) in this folder.
cd /d "%~dp0"
if not exist "{exe}" (echo {exe} is not in this folder & pause & exit /b 1)
if not exist gba_bios.bin (echo gba_bios.bin is not in this folder & pause & exit /b 1)
"{exe}" --bios gba_bios.bin --rom "{rom}" --rom-sha1 {rom_sha1}
"""

GBA_README = """{game}: українська збірка для {folder}

Що є в цій папці
  {rom}         перекладений ROM (SHA-1 {rom_sha1})
  recomp.json   маніфест: SHA-1 перекладеного ROM, розмір
  run_UA.bat    запускає {exe} з цим ROM

Кроки
  1. Завантажте {folder} v{version} для Windows x64 з офіційного релізу:
     {release}
     Розпакуйте архів у цю папку.
  2. Покладіть свій дамп GBA BIOS у цю папку під назвою gba_bios.bin
     (SHA-1 300c20df6731a33952ded8c436f7f186d25d3492).
  3. Запустіть run_UA.bat. Порт перевіряє SHA-1 з командного рядка (--rom-sha1),
     тому сам порт змінювати не треба.

Обмеження
  Порт виконує ROM через статичну рекомпіляцію, зібрану для оригінальної розкладки ROM.
  Текст, який збірка перенесла, читається з нового місця тільки там, де гра бере текст з даних ROM.
  Якщо на екрані лишився старий текст, ця частина коду потребує нової рекомпіляції цього ROM.
  Перевірте текст на тих екранах, які ви використовуєте.
"""

GEN2_README = """{game}: українська збірка для Gen2Recomp (LÖVE2D, джерело)

Що є в цій папці
  {rom}         перекладений ROM (SHA-1 {rom_sha1})
  recomp.json   маніфест: SHA-1 перекладеного ROM, розмір

Кроки
  1. Завантажте Gen2Recomped-0.8.41.love з офіційного релізу UNDERdecoded/Gen2Recomped (тег v0.8.41).
     Розпакуйте його в нову папку, наприклад Gen2Recomped-src. Виконуваний .exe цю зміну не прийме.
  2. Завантажте середовище LÖVE 11.5 з love2d.org. Запускайте папку гри цим середовищем.
  3. У файлі Gen2Recomped-src\\src\\core\\GameVersion.lua, у блоці "{version} = {{",
     одразу після рядка "sha1 = ..." додайте рядок:
         sha1Alt = {{ "{rom_sha1}" }},
     Це єдина зміна в порту. Вона лише дозволяє цей ROM.
  4. У папці гри створіть порожній файл portable.txt (тоді кеш лежить у самій папці).
  5. Скопіюйте {rom} у папку гри й один раз імпортуйте його з командного рядка:
         set POKEPORT_VERSION={version}
         set POKEPORT_IMPORT_ROM=<повний шлях до {rom}>
         set POKEPORT_IMPORT_ONLY=1
         "<папка LÖVE 11.5>\\love.exe" .
  6. Запустіть гру без POKEPORT_IMPORT_ONLY: "<папка LÖVE 11.5>\\love.exe" .

Обмеження
  Імпортер читає ROM за адресами оригінальної збірки. Якщо розкладка змінилася, потрібен новий
  список символів (див. розділ Gen2 у вікі Picoripi). Перевірте текст на тих екранах, які ви використовуєте.
"""


def _sha1(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    """Write through a temporary file in the same folder, then replace (AGENTS rule 9)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def port_for_source(source_dir: str) -> Dict[str, str]:
    """The port that runs the base ROM of this project (its ``rom/`` folder beside the source root)."""
    bases = sorted((Path(source_dir).parent / "rom").glob("base.*"))
    if not bases:
        raise ValueError(tr("This project was not unpacked from a ROM."))
    sha = _sha1(bases[0])
    port = PORTS_BY_BASE_SHA1.get(sha)
    if port is None:
        raise ValueError(tr("No recomp port runs this ROM: {0}", sha))
    return port


def _write_files(folder: Path, port: Dict[str, str], rom: str, rom_sha1: str) -> None:
    fields = {"game": port["game"], "folder": port["folder"], "rom": rom, "rom_sha1": rom_sha1}
    if port["kind"] == "gen2":
        _atomic_write(folder / "README_UA.txt",
                      GEN2_README.format(version=port["id"], **fields).encode("utf-8"))
        return
    exe = port["exe"]
    _atomic_write(folder / "run_UA.bat", RUN_BAT.format(exe=exe, rom=rom, rom_sha1=rom_sha1).encode("ascii"))
    _atomic_write(folder / "README_UA.txt", GBA_README.format(
        exe=exe, release=port["release"], version=port["release"].rsplit("v", 1)[1], **fields).encode("utf-8"))


def build_package(source_dir: str, translation_dir: str, output_dir: str, make_rom: MakeRom,
                  progress: Progress, is_cancelled: Cancelled) -> str:
    """Write the port's folder into ``output_dir`` and return its path (empty when cancelled)."""
    port = port_for_source(source_dir)
    progress(10, tr("Building the translated ROM"))
    work = Path(output_dir) / "_rom"
    rom = Path(make_rom(source_dir, translation_dir, str(work)))
    if is_cancelled():
        return ""
    folder = Path(output_dir) / port["folder"]
    folder.mkdir(parents=True, exist_ok=True)
    rom_sha1, rom_bytes = _sha1(rom), rom.stat().st_size
    shutil.copyfile(rom, folder / rom.name)
    shutil.rmtree(work, ignore_errors=True)
    manifest = {"port": port["id"], "game": port["game"], "rom": rom.name, "rom_sha1": rom_sha1,
                "rom_bytes": rom_bytes}
    _atomic_write(folder / "recomp.json", (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    _write_files(folder, port, rom.name, rom_sha1)
    progress(100, tr("Done"))
    return str(folder)

