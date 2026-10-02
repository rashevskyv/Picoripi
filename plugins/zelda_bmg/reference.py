"""Reference translation patch loader for Zelda BMG (Twilight Princess / Wind Waker).

Handles loading, extracting RARC archives (e.g. bmgres*.arc), parsing BMG binary files
with cp1251 single-byte encoding, and mapping them to project block indices.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.logging_utils import log_error, log_info, log_warning



def load_zelda_bmg_reference_patch(
    patch_path: str | Path,
    block_names: Optional[Dict[str, str] | List[str]] = None,
    game_rules: Optional[Any] = None,
    encoding: str = "cp1251",
) -> Dict[Tuple[int, int], str]:
    """Load and parse reference translation files from a folder or file for Zelda BMG games.

    Supports RARC archives containing BMG files (e.g. bmgres*.arc) and standalone .bmg files.
    Decodes strings using the specified encoding (default cp1251 for GameCube/Wii RU patches)
    and maps them to project blocks.

    Returns:
        Mapping of (block_idx, string_idx) -> formatted_reference_text.
    """
    p = Path(patch_path)
    if not p.exists():
        log_warning(f"ZeldaBMG reference: patch path does not exist: {p}")
        return {}

    log_info(f"ZeldaBMG reference: loading patch from '{p}'...")
    ref_data: Dict[Tuple[int, int], str] = {}

    name_to_idx: Dict[str, int] = {}
    if block_names:
        if isinstance(block_names, dict):
            for idx_str, name in block_names.items():
                try:
                    b_idx = int(idx_str)
                    name_to_idx[name.lower()] = b_idx
                    stem = Path(name).stem.lower()
                    name_to_idx[stem] = b_idx
                except (ValueError, TypeError):
                    continue
        elif isinstance(block_names, list):
            for b_idx, name in enumerate(block_names):
                name_to_idx[name.lower()] = b_idx
                stem = Path(name).stem.lower()
                name_to_idx[stem] = b_idx

    search_dirs = [p]
    msg_sub = p / "Msg"
    if msg_sub.is_dir():
        search_dirs.insert(0, msg_sub)

    # 1. Look for .arc archives (RARC)
    arc_files: List[Path] = []
    for sdir in search_dirs:
        if sdir.is_dir():
            arc_files.extend(sorted(sdir.glob("*.arc")))
            arc_files.extend(sorted(sdir.glob("*.ARC")))

    if arc_files:
        _load_from_arcs(arc_files, name_to_idx, ref_data, game_rules, encoding)

    # 2. Look for standalone .bmg files if no arcs or in addition
    bmg_files: List[Path] = []
    for sdir in search_dirs:
        if sdir.is_dir():
            bmg_files.extend(sorted(sdir.glob("*.bmg")))
            bmg_files.extend(sorted(sdir.glob("*.BMG")))
    if bmg_files:
        _load_from_bmgs(bmg_files, name_to_idx, ref_data, game_rules, encoding)

    # 3. If patch_path itself is a direct file (.arc or .bmg)
    if p.is_file():
        if p.suffix.lower() == ".arc":
            _load_from_arcs([p], name_to_idx, ref_data, game_rules, encoding)
        elif p.suffix.lower() == ".bmg":
            _load_from_bmgs([p], name_to_idx, ref_data, game_rules, encoding)

    log_info(f"ZeldaBMG reference: loaded {len(ref_data)} strings across {len(name_to_idx)} blocks.")
    return ref_data


def _load_from_arcs(
    arc_files: List[Path],
    name_to_idx: Dict[str, int],
    ref_data: Dict[Tuple[int, int], str],
    game_rules: Optional[Any],
    encoding: str,
) -> None:
    """Parse BMG files from RARC archives."""
    from core.containers.rarc_container import RarcContainer
    from .bmg_tool import BMGFile

    for arc_path in arc_files:
        try:
            raw_bytes = arc_path.read_bytes()
            if not RarcContainer.can_handle(raw_bytes):
                continue
            arc = RarcContainer(raw_bytes)
            import re
            for inner_file in arc.list_files():
                if inner_file.lower().endswith(".bmg"):
                    stem = Path(inner_file).stem.lower()
                    block_idx = name_to_idx.get(stem)
                    if block_idx is None:
                        block_idx = name_to_idx.get(inner_file.lower())
                    if block_idx is None:
                        # Match by substring e.g. zel_01 in zel_01_bmg
                        for k, v in name_to_idx.items():
                            if k in stem or stem in k:
                                block_idx = v
                                break
                    if block_idx is None:
                        m = re.search(r"zel_(\d+)", stem)
                        if m:
                            try:
                                block_idx = int(m.group(1))
                            except ValueError:
                                pass
                    if block_idx is None:
                        continue

                    bmg_data = arc.read_file(inner_file)
                    bmg = BMGFile()
                    bmg.load(bmg_data, override_encoding=encoding)
                    _extract_bmg_messages(bmg, block_idx, ref_data, game_rules, encoding)
        except Exception as e:
            log_error(f"ZeldaBMG reference: error processing {arc_path.name}: {e}")


def _load_from_bmgs(
    bmg_files: List[Path],
    name_to_idx: Dict[str, int],
    ref_data: Dict[Tuple[int, int], str],
    game_rules: Optional[Any],
    encoding: str,
) -> None:
    """Parse standalone BMG files."""
    from .bmg_tool import BMGFile
    import re

    for bmg_path in bmg_files:
        try:
            stem = bmg_path.stem.lower()
            block_idx = name_to_idx.get(stem)
            if block_idx is None:
                for k, v in name_to_idx.items():
                    if k in stem or stem in k:
                        block_idx = v
                        break
            if block_idx is None:
                m = re.search(r"zel_(\d+)", stem)
                if m:
                    try:
                        block_idx = int(m.group(1))
                    except ValueError:
                        pass
            if block_idx is None:
                continue
            bmg = BMGFile()
            bmg.load(bmg_path.read_bytes(), override_encoding=encoding)
            _extract_bmg_messages(bmg, block_idx, ref_data, game_rules, encoding)
        except Exception as e:
            log_error(f"ZeldaBMG reference: error processing {bmg_path.name}: {e}")


def _extract_bmg_messages(
    bmg: Any,
    block_idx: int,
    ref_data: Dict[Tuple[int, int], str],
    game_rules: Optional[Any],
    encoding: str,
) -> None:
    """Extract and format messages from a parsed BMGFile."""
    for str_idx, msg in enumerate(bmg.messages):
        if getattr(msg, "is_null", False):
            ref_data[(block_idx, str_idx)] = ""
            continue

        parts = []
        for item in msg.parts:
            if isinstance(item, str):
                bmg_enc = getattr(bmg, "encoding", "").lower()
                if bmg_enc and bmg_enc != encoding.lower() and encoding.lower() in ("cp1251", "utf-8"):
                    try:
                        # Re-decode bytes from latin1 to target encoding losslessly
                        raw_bytes = item.encode("latin1", errors="replace")
                        text_part = raw_bytes.decode(encoding, errors="replace")
                    except Exception:
                        text_part = item
                else:
                    text_part = item
                parts.append(text_part)
            elif isinstance(item, dict) and item.get("type") == "escape":
                esc_type = item.get("escape_type", 0)
                hex_data = item.get("data", "")
                parts.append(f"{{escape:{esc_type}:{hex_data}}}")

        raw_text = "".join(parts)
        if game_rules and hasattr(game_rules, "get_text_representation_for_editor"):
            try:
                formatted_text = game_rules.get_text_representation_for_editor(raw_text)
            except Exception:
                formatted_text = raw_text
        else:
            formatted_text = raw_text

        ref_data[(block_idx, str_idx)] = formatted_text


def _try_extract_iso_messages(iso_path: Path) -> Optional[Path]:
    """If wit (Wiimms ISO Tool) is available, extract message archives from an ISO image."""
    import shutil
    import subprocess
    wit_exe = None

    # Check configured wit_tool_path from global settings
    try:
        from utils.constants import SETTINGS_FILE_PATH
        import json
        if SETTINGS_FILE_PATH.is_file():
            with open(SETTINGS_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                cfg_wit = data.get("wit_tool_path", "").strip()
                if cfg_wit and Path(cfg_wit).is_file():
                    wit_exe = cfg_wit
    except Exception:
        pass

    if not wit_exe:
        wit_exe = shutil.which("wit")
    if not wit_exe:
        candidates = [
            Path("E:/Emulators/RomHacking/ZELDA/TP_UA/soft/wit-v3.05a-r8638-cygwin64/bin/wit.exe"),
            iso_path.parent / "soft" / "wit-v3.05a-r8638-cygwin64" / "bin" / "wit.exe",
            iso_path.parent.parent / "soft" / "wit-v3.05a-r8638-cygwin64" / "bin" / "wit.exe",
        ]
        for c in candidates:
            if c.is_file():
                wit_exe = str(c)
                break
    if not wit_exe:
        return None

    target_dir = iso_path.parent / "PAL_RU"
    if not target_dir.is_dir() or not any(target_dir.glob("**/Msg*")):
        target_dir = iso_path.parent / f"extracted_{iso_path.stem}"

    if target_dir.is_dir() and any(target_dir.glob("**/Msg*")):
        return target_dir

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        log_info(f"ZeldaBMG: extracting message files from {iso_path.name} to {target_dir}...")
        cmd = [wit_exe, "extract", str(iso_path), "--dest", str(target_dir), "--files", "+*Msg*"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode == 0:
            log_info(f"ZeldaBMG: successfully extracted message files from {iso_path.name}")
            return target_dir
        else:
            log_warning(f"ZeldaBMG: wit extraction returned code {res.returncode}: {res.stderr}")
    except Exception as e:
        log_warning(f"ZeldaBMG: failed to run wit extract on {iso_path}: {e}")
    return None


def load_zelda_bmg_multi_reference(
    patch_path: str | Path,
    block_names: Optional[Dict[str, str] | List[str]] = None,
    game_rules: Optional[Any] = None,
) -> Dict[str, Dict[Tuple[int, int], str]]:
    """Load reference translation files for multiple languages from an unpacked ROM or patch folder.

    Scans the provided directory (or standard subdirectories such as root/res, files/res, res)
    for localized message folders:
    - English directories (Msguk, Msgus, Msgen, Msge) where Russian replaced English:
      loaded with cp1251 single-byte encoding as 'Russian (RU)'.
    - Other language directories (Msgde, Msgfr, Msgit, Msgsp, Msgjp):
      loaded with cp1252 / standard encoding as 'German (DE)', 'French (FR)', etc.
    - If an ISO file is provided and wit is available, extracts Msg archives automatically.
    - If no multi-language directories are found, loads the directory as a single reference
      patch under the plugin's default reference label (e.g. 'Russian (RU)').

    Returns:
        Mapping of language_label -> {(block_idx, string_idx): reference_text}.
    """
    p = Path(patch_path)
    if not p.exists():
        log_warning(f"ZeldaBMG multi-reference: path does not exist: {p}")
        return {}

    # If patch_path is an ISO image or directory containing an ISO without extracted Msg files, try extraction
    if p.is_file() and p.suffix.lower() == ".iso":
        extracted = _try_extract_iso_messages(p)
        if extracted:
            p = extracted
    elif p.is_dir():
        has_msg = any(p.glob("**/Msg*")) or any(p.glob("**/msg*"))
        if not has_msg:
            for iso_file in sorted(p.glob("*.iso")):
                extracted = _try_extract_iso_messages(iso_file)
                if extracted:
                    p = extracted
                    break

    # Language directory identification map: folder_name_lower -> (label, encoding)
    lang_map: Dict[str, Tuple[str, str]] = {
        # Russian / replaced English folders
        "msg": ("Russian (RU)", "cp1251"),
        "msguk": ("Russian (RU)", "cp1251"),
        "msgus": ("Russian (RU)", "cp1251"),
        "msgen": ("Russian (RU)", "cp1251"),
        "msge": ("Russian (RU)", "cp1251"),
        "msgru": ("Russian (RU)", "cp1251"),
        "msg_ru": ("Russian (RU)", "cp1251"),
        "msg_uk": ("Russian (RU)", "cp1251"),
        "msg_us": ("Russian (RU)", "cp1251"),
        "msg_en": ("Russian (RU)", "cp1251"),
        "msg_e": ("Russian (RU)", "cp1251"),
        "ru": ("Russian (RU)", "cp1251"),
        "rus": ("Russian (RU)", "cp1251"),
        "russian": ("Russian (RU)", "cp1251"),
        # German
        "msgde": ("German (DE)", "cp1252"),
        "msg_de": ("German (DE)", "cp1252"),
        "de": ("German (DE)", "cp1252"),
        "ger": ("German (DE)", "cp1252"),
        "german": ("German (DE)", "cp1252"),
        # French
        "msgfr": ("French (FR)", "cp1252"),
        "msg_fr": ("French (FR)", "cp1252"),
        "fr": ("French (FR)", "cp1252"),
        "fra": ("French (FR)", "cp1252"),
        "french": ("French (FR)", "cp1252"),
        # Italian
        "msgit": ("Italian (IT)", "cp1252"),
        "msg_it": ("Italian (IT)", "cp1252"),
        "it": ("Italian (IT)", "cp1252"),
        "ita": ("Italian (IT)", "cp1252"),
        "italian": ("Italian (IT)", "cp1252"),
        # Spanish
        "msgsp": ("Spanish (ES)", "cp1252"),
        "msg_sp": ("Spanish (ES)", "cp1252"),
        "msges": ("Spanish (ES)", "cp1252"),
        "msg_es": ("Spanish (ES)", "cp1252"),
        "es": ("Spanish (ES)", "cp1252"),
        "spa": ("Spanish (ES)", "cp1252"),
        "spanish": ("Spanish (ES)", "cp1252"),
        # Japanese
        "msgjp": ("Japanese (JA)", "shift_jis"),
        "msg_jp": ("Japanese (JA)", "shift_jis"),
        "msgja": ("Japanese (JA)", "shift_jis"),
        "msg_ja": ("Japanese (JA)", "shift_jis"),
        "jp": ("Japanese (JA)", "shift_jis"),
        "ja": ("Japanese (JA)", "shift_jis"),
        "japanese": ("Japanese (JA)", "shift_jis"),
    }

    # Preferred presentation order
    sort_order = [
        "Russian (RU)",
        "German (DE)",
        "French (FR)",
        "Spanish (ES)",
        "Italian (IT)",
        "Japanese (JA)",
    ]

    discovered_dirs: List[Path] = []
    if p.is_dir():
        # 1. Search recursively for all Msg* / msg* folders
        for pat in ("**/Msg*", "**/msg*"):
            try:
                for match in sorted(p.glob(pat)):
                    if match.is_dir() and match not in discovered_dirs:
                        discovered_dirs.append(match)
            except Exception:
                pass

        # 2. Add standard direct candidate directories
        candidate_res_dirs = [
            p / "DATA" / "files" / "res",
            p / "files" / "res",
            p / "root" / "res",
            p / "res",
            p,
        ]
        # If user picked a specific language folder (e.g. res/Msg or res/Msgde), include parent
        p_name = p.name.lower()
        if p_name.startswith("msg") or p_name in lang_map:
            candidate_res_dirs.append(p.parent)
            if p.parent.parent.is_dir():
                candidate_res_dirs.append(p.parent.parent)

        for cdir in candidate_res_dirs:
            if cdir.is_dir():
                try:
                    for entry in sorted(cdir.iterdir()):
                        if entry.is_dir() and entry not in discovered_dirs:
                            discovered_dirs.append(entry)
                except Exception:
                    pass

    found_msg_dirs: Dict[str, Tuple[Path, str]] = {}  # label -> (dir_path, encoding)

    for entry in discovered_dirs:
        name_lower = entry.name.lower()
        if name_lower.startswith("msg") or name_lower in lang_map:
            if name_lower in lang_map:
                label, enc = lang_map[name_lower]
            else:
                code = entry.name[3:].strip("_- ").upper() if name_lower.startswith("msg") else entry.name.strip("_- ").upper()
                if not code:
                    code = "REF"
                label = f"Reference ({code})"
                enc = "cp1252"

            # Verify that the folder actually contains .arc or .bmg
            has_content = (
                any(entry.glob("*.arc"))
                or any(entry.glob("*.bmg"))
                or any(entry.glob("*.ARC"))
                or any(entry.glob("*.BMG"))
            )
            if not has_content:
                continue

            # Prioritize Msguk over Msgus when in a PAL multi-language release (Msgde, Msgfr etc.)
            if label == "Russian (RU)":
                if name_lower in ("msguk", "msg_uk"):
                    found_msg_dirs[label] = (entry, enc)  # PAL RU always takes precedence
                elif label not in found_msg_dirs:
                    found_msg_dirs[label] = (entry, enc)
            elif label not in found_msg_dirs:
                found_msg_dirs[label] = (entry, enc)

    multi_ref: Dict[str, Dict[Tuple[int, int], str]] = {}

    # If we found localized Msg* folders, load each one
    if found_msg_dirs:
        log_info(
            f"ZeldaBMG multi-reference: discovered {len(found_msg_dirs)} language folders: {list(found_msg_dirs.keys())}"
        )
        for label in sorted(
            found_msg_dirs.keys(),
            key=lambda k: sort_order.index(k) if k in sort_order else 999,
        ):
            dir_path, enc = found_msg_dirs[label]
            lang_data = load_zelda_bmg_reference_patch(
                dir_path,
                block_names=block_names,
                game_rules=game_rules,
                encoding=enc,
            )
            if lang_data:
                multi_ref[label] = lang_data

    # Fallback: if no multi-language directories were found, load patch_path as single reference
    if not multi_ref:
        single_data = load_zelda_bmg_reference_patch(
            p,
            block_names=block_names,
            game_rules=game_rules,
            encoding="cp1251",
        )
        if single_data:
            label = (
                game_rules.get_reference_language_label()
                if (game_rules and hasattr(game_rules, "get_reference_language_label"))
                else "Russian (RU)"
            )
            multi_ref[label] = single_data

    log_info(
        f"ZeldaBMG multi-reference: loaded {len(multi_ref)} languages "
        f"({', '.join(f'{k}: {len(v)} strings' for k, v in multi_ref.items())})"
    )
    return multi_ref
