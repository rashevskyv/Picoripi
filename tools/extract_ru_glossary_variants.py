"""
Extract Russian translation variants from an aligned reference patch (e.g. Zelda TP RU patch)
and populate `translation_variants` in `glossary.json`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from core.reference_manager import ReferenceManager
from utils.logging_utils import log_info, log_warning, log_error


TAG_RE = re.compile(r'\{[^}]+\}')
# Matches any escape:255 color/formatting tag or friendly alias
COLOR_SPAN_RAW_RE = re.compile(r'\{escape:255:[0-9a-fA-F]{2,6}\}([^{]+)\{escape:255:000000\}')
COLOR_SPAN_ALIAS_RE = re.compile(r'\{(?:Color|color):[A-Za-z0-9_]+\}([^{]+)\{(?:Color|color):(?:Default|white|0)\}')


def clean_tags(text: str) -> str:
    """Remove all {tag} markers and normalize whitespace."""
    return " ".join(TAG_RE.sub(" ", text).split())


def extract_variants_from_aligned_corpus(
    glossary_entries: List[Dict[str, Any]],
    eng_blocks: List[List[str]],
    ru_data: Dict[Tuple[int, int], str],
) -> Dict[str, Tuple[str, str]]:
    """
    Extract Russian translations for glossary terms from aligned English and Russian texts.
    Returns {original_term: (ru_translation, method_used)}.
    """
    extracted: Dict[str, Tuple[str, str]] = {}

    # Build glossary lookup maps
    term_to_entry = {e["original"]: e for e in glossary_entries if e.get("original")}
    term_lower_to_orig = {e["original"].lower().strip(): e["original"] for e in glossary_entries if e.get("original")}

    # Pass 1: Standalone strings (menus, items, UI prompts, inventory)
    for b_idx, block in enumerate(eng_blocks):
        for s_idx, eng_str in enumerate(block):
            eng_clean = clean_tags(eng_str)
            if not eng_clean:
                continue
            ru_str = ru_data.get((b_idx, s_idx), "")
            ru_clean = clean_tags(ru_str)
            if not ru_clean:
                continue

            orig = term_lower_to_orig.get(eng_clean.lower())
            if orig and orig not in extracted:
                extracted[orig] = (ru_clean, "exact_standalone")

    # Pass 2: Tagged / highlighted spans (items, quest objectives, key names)
    for b_idx, block in enumerate(eng_blocks):
        for s_idx, eng_str in enumerate(block):
            ru_str = ru_data.get((b_idx, s_idx), "")
            if not ru_str:
                continue

            # Try raw escape tags
            e_spans = COLOR_SPAN_RAW_RE.findall(eng_str) or COLOR_SPAN_ALIAS_RE.findall(eng_str)
            r_spans = COLOR_SPAN_RAW_RE.findall(ru_str) or COLOR_SPAN_ALIAS_RE.findall(ru_str)

            if len(e_spans) == len(r_spans) and len(e_spans) >= 1:
                for esp, rsp in zip(e_spans, r_spans):
                    esp_clean = clean_tags(esp).strip()
                    rsp_clean = clean_tags(rsp).strip()
                    if not esp_clean or not rsp_clean:
                        continue
                    orig = term_lower_to_orig.get(esp_clean.lower())
                    if orig and orig not in extracted:
                        extracted[orig] = (rsp_clean, "tagged_span")

    # Pass 3: Character names & capitalized single-word terms
    for orig, entry in term_to_entry.items():
        if orig in extracted:
            continue
        words = orig.strip().split()
        if len(words) == 1 and words[0].isalpha() and words[0][0].isupper():
            term = words[0]
            term_pattern = re.compile(r'\b' + re.escape(term) + r'\b')
            candidates = Counter()
            for b_idx, block in enumerate(eng_blocks):
                for s_idx, eng_str in enumerate(block):
                    if term_pattern.search(eng_str):
                        ru_str = ru_data.get((b_idx, s_idx), "")
                        ru_clean = clean_tags(ru_str)
                        # Find capitalized Cyrillic words
                        ru_words = re.findall(r'\b[А-ЯЁ][а-яё]+\b', ru_clean)
                        for rw in ru_words:
                            candidates[rw] += 1
            if candidates:
                best_rw, count = candidates.most_common(1)[0]
                if count >= 2:
                    extracted[orig] = (best_rw, f"name_freq_{count}")

    # Pass 4: Multi-word phrase matches for locations and items
    for orig, entry in term_to_entry.items():
        if orig in extracted:
            continue
        words = orig.strip().split()
        if len(words) >= 2:
            term_pattern = re.compile(r'\b' + re.escape(orig) + r'\b', re.IGNORECASE)
            candidates = Counter()
            for b_idx, block in enumerate(eng_blocks):
                for s_idx, eng_str in enumerate(block):
                    if term_pattern.search(eng_str):
                        ru_str = ru_data.get((b_idx, s_idx), "")
                        ru_clean = clean_tags(ru_str)
                        if ru_clean:
                            candidates[ru_clean] += 1
            # If the entire line was a short phrase that appeared consistently
            if candidates:
                for phrase, count in candidates.most_common(3):
                    if len(phrase.split()) <= len(words) + 2:
                        extracted[orig] = (phrase, f"phrase_freq_{count}")
                        break

    return extracted


def update_glossary_with_ru_variants(
    glossary_path: str | Path,
    extracted_variants: Dict[str, Tuple[str, str]],
    rationale_label: str = "RU патч v2.0",
) -> Tuple[int, int]:
    """
    Update glossary.json with extracted Russian variants.
    Returns (added_count, updated_count).
    """
    gpath = Path(glossary_path)
    with open(gpath, "r", encoding="utf-8") as f:
        glossary: List[Dict[str, Any]] = json.load(f)

    # Backup existing file
    bak_path = gpath.with_suffix(".json.bak")
    try:
        bak_path.write_bytes(gpath.read_bytes())
        log_info(f"Created backup: {bak_path}")
    except Exception as e:
        log_warning(f"Failed to create backup: {e}")

    added_count = 0
    updated_count = 0

    for entry in glossary:
        orig = entry.get("original", "")
        if orig in extracted_variants:
            ru_text, method = extracted_variants[orig]
            variants = entry.get("translation_variants", [])
            if not isinstance(variants, list):
                variants = []

            # Check if variant already exists
            existing_idx = -1
            for idx, v in enumerate(variants):
                if isinstance(v, dict) and v.get("rationale", "").startswith("RU"):
                    existing_idx = idx
                    break

            new_var = {
                "translation": ru_text,
                "rationale": rationale_label
            }

            if existing_idx >= 0:
                variants[existing_idx] = new_var
                updated_count += 1
            else:
                variants.append(new_var)
                added_count += 1

            entry["translation_variants"] = variants

    with open(gpath, "w", encoding="utf-8") as f:
        json.dump(glossary, f, ensure_ascii=False, indent=2)

    log_info(f"Saved {gpath}: added {added_count} variants, updated {updated_count} variants.")
    return added_count, updated_count


def run_extraction(
    project_dir: str | Path,
    patch_dir: str | Path,
    glossary_file: Optional[str | Path] = None,
) -> None:
    """Main execution flow for extracting Russian variants and updating glossary."""
    pdir = Path(project_dir)
    gpath = Path(glossary_file) if glossary_file else pdir / "glossary.json"

    if not gpath.exists():
        log_error(f"Glossary file not found: {gpath}")
        return

    # Load session for English strings
    session_file = pdir / ".picoripi_session.json"
    if not session_file.exists():
        log_error(f"Session file not found: {session_file}")
        return

    with open(session_file, "r", encoding="utf-8") as f:
        session_data = json.load(f)

    eng_blocks = session_data.get("data", [])
    block_names = session_data.get("block_names", {})

    with open(gpath, "r", encoding="utf-8") as f:
        glossary = json.load(f)

    # Determine active plugin from project_settings.json
    plugin_name = "zelda_bmg"
    settings_file = pdir / "project_settings.json"
    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as sf:
                sdata = json.load(sf)
                plugin_name = sdata.get("active_game_plugin", plugin_name)
        except Exception:
            pass

    game_rules = None
    try:
        import importlib
        mod = importlib.import_module(f"plugins.{plugin_name}.rules")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if isinstance(attr, type) and attr.__name__.endswith("Rules") and attr_name != "BaseGameRules":
                game_rules = attr()
                break
    except Exception as e:
        log_warning(f"Could not instantiate plugin rules for '{plugin_name}': {e}")

    log_info(f"Loading reference data from {patch_dir} via plugin '{plugin_name}'...")
    ru_data = ReferenceManager.load_reference(patch_dir, block_names, game_rules=game_rules)

    log_info(f"Extracting variants for {len(glossary)} glossary terms...")
    extracted = extract_variants_from_aligned_corpus(glossary, eng_blocks, ru_data)
    log_info(f"Successfully extracted Russian variants for {len(extracted)} terms.")

    added, updated = update_glossary_with_ru_variants(gpath, extracted)
    print(f"Done: {added} variants added, {updated} updated in {gpath.name}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract Russian variants for glossary terms from aligned patch.")
    parser.add_argument("--project-dir", required=True, help="Path to project directory containing glossary.json and session")
    parser.add_argument("--patch-dir", required=True, help="Path to Russian patch directory (e.g. RU_patch_2.0)")
    parser.add_argument("--glossary", default=None, help="Optional explicit path to glossary.json")
    args = parser.parse_args()

    run_extraction(args.project_dir, args.patch_dir, args.glossary)
