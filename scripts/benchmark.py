"""
Benchmark script for Picoripi performance optimizations.

Tests:
  1. calculate_string_width  — BEFORE (current) vs AFTER (Trie + flat char_widths cache)
  2. convert_spaces_to_dots  — BEFORE (per-line re.sub) vs AFTER (pre-compiled regex)

Data: All 337 JSON files from PokemonRS/sources/ (~1.5 MB total text)
"""

import json
import re
import time
import sys
import os
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from functools import lru_cache

# ---------------------------------------------------------------------------
# Setup: load real data and font map
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
SOURCES_DIR = PROJECT_ROOT / "PokemonRS" / "sources"
FONT_MAP_PATH = PROJECT_ROOT / "plugins" / "pokemon_fr" / "font_map.json"

print("=" * 70)
print("Loading data...")

with open(FONT_MAP_PATH, "r", encoding="utf-8") as f:
    FONT_MAP = json.load(f)

# Collect all texts from all 337 source files
all_texts: List[str] = []
file_count = 0
for jf in sorted(SOURCES_DIR.glob("*.json")):
    try:
        with open(jf, "r", encoding="utf-8") as f:
            obj = json.load(f)
        for file_key, strings in obj.items():
            if isinstance(strings, dict):
                for k, v in strings.items():
                    if isinstance(v, str) and v:
                        # Split multi-line game strings into individual lines
                        for line in v.replace("\\p", "\n").replace("\\n", "\n").split("\n"):
                            line = line.strip()
                            if line:
                                all_texts.append(line)
        file_count += 1
    except Exception as e:
        pass

# Icon sequences (multi-char keys from font_map)
ICON_SEQUENCES = sorted(
    [k for k in FONT_MAP.keys() if len(k) > 1],
    key=len, reverse=True
)

total_chars = sum(len(t) for t in all_texts)
print(f"  Files loaded:     {file_count}")
print(f"  Text lines:       {len(all_texts)}")
print(f"  Total chars:      {total_chars:,}")
print(f"  Icon sequences:   {len(ICON_SEQUENCES)}")
print(f"  Font map entries: {len(FONT_MAP)}")
print()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_benchmark(name: str, fn, reps: int = 3) -> Tuple[float, int]:
    """Run fn() for `reps` warm+measure passes, return (best_ms, calls)."""
    # Warm up
    fn()
    times = []
    for _ in range(reps):
        t0 = time.perf_counter()
        calls = fn()
        times.append(time.perf_counter() - t0)
    best = min(times)
    print(f"  {name:<50} {best*1000:>8.1f} ms  ({calls:,} calls)")
    return best, calls


# ===========================================================================
# BENCHMARK 1: calculate_string_width
# ===========================================================================

print("=" * 70)
print("BENCHMARK 1: calculate_string_width")
print("-" * 70)

# --- BEFORE: current implementation (verbatim from utils/utils.py) ----------

def calculate_string_width_before(text: str, font_map: dict,
                                   default_char_width: int = 8,
                                   icon_sequences: Optional[List[str]] = None) -> int:
    total_width = 0
    i = 0
    text_len = len(text)

    # Rebuild icon list every call (as current code does)
    font_map_icons = [str(k) for k in font_map.keys() if len(str(k)) > 1]
    if not icon_sequences:
        icon_sequences = font_map_icons
    else:
        icon_sequences = list(set(icon_sequences + font_map_icons))
    sequences_to_use = sorted(icon_sequences, key=len, reverse=True)

    while i < text_len:
        matched_sequence = None
        for seq in sequences_to_use:
            if text.startswith(seq, i):
                matched_sequence = seq
                break

        if matched_sequence:
            total_width += font_map.get(matched_sequence, {}).get('width', default_char_width * len(matched_sequence))
            i += len(matched_sequence)
            continue

        char = text[i]
        if char == '[':
            end_index = text.find(']', i)
            if end_index != -1:
                i = end_index + 1
                continue
        if char == '{':
            end_index = text.find('}', i)
            if end_index != -1:
                i = end_index + 1
                continue

        char_info = font_map.get(char)
        if char_info is None:
            total_width += default_char_width
        else:
            total_width += char_info.get('width', default_char_width)
        i += 1

    return total_width


def bench_before_width():
    count = 0
    for text in all_texts:
        calculate_string_width_before(text, FONT_MAP)
        count += 1
    return count


# --- AFTER: optimized — pre-built Trie + flat char_widths dict ---------------

class TrieNode:
    __slots__ = ('children', 'width', 'length')
    def __init__(self):
        self.children: Dict[str, 'TrieNode'] = {}
        self.width: Optional[int] = None
        self.length: int = 0


def build_trie(font_map: dict, default_char_width: int = 8) -> TrieNode:
    root = TrieNode()
    for key, info in font_map.items():
        if len(key) <= 1:
            continue
        node = root
        for ch in key:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        width = info.get('width', default_char_width * len(key)) if isinstance(info, dict) else default_char_width * len(key)
        node.width = width
        node.length = len(key)
    return root


def build_flat_char_widths(font_map: dict, default_char_width: int = 8) -> Dict[str, int]:
    """Flat dict: char -> width, for single-char lookups."""
    return {
        k: (v.get('width', default_char_width) if isinstance(v, dict) else default_char_width)
        for k, v in font_map.items()
        if len(k) == 1
    }


# Build these ONCE (simulates what would happen at plugin load time)
TRIE_ROOT = build_trie(FONT_MAP)
FLAT_WIDTHS = build_flat_char_widths(FONT_MAP)
DEFAULT_WIDTH = 8


def calculate_string_width_after(text: str, trie: TrieNode,
                                  char_widths: Dict[str, int],
                                  default_char_width: int = DEFAULT_WIDTH) -> int:
    total_width = 0
    i = 0
    text_len = len(text)

    while i < text_len:
        ch = text[i]

        # 1. Try Trie match for multi-char sequences
        node = trie.children.get(ch)
        if node is not None:
            best_width: Optional[int] = None
            best_len: int = 0
            j = i + 1
            while node is not None and j <= text_len:
                if node.width is not None:
                    best_width = node.width
                    best_len = node.length
                if j < text_len:
                    node = node.children.get(text[j])
                else:
                    break
                j += 1
            if best_width is not None:
                total_width += best_width
                i += best_len
                continue

        # 2. Skip bracket tags with zero width
        if ch == '[':
            end_index = text.find(']', i)
            if end_index != -1:
                i = end_index + 1
                continue
        if ch == '{':
            end_index = text.find('}', i)
            if end_index != -1:
                i = end_index + 1
                continue

        # 3. Single char lookup (O(1) dict)
        total_width += char_widths.get(ch, default_char_width)
        i += 1

    return total_width


def bench_after_width():
    count = 0
    for text in all_texts:
        calculate_string_width_after(text, TRIE_ROOT, FLAT_WIDTHS)
        count += 1
    return count


t_before_w, _ = run_benchmark("BEFORE (list scan per char)", bench_before_width)
t_after_w,  _ = run_benchmark("AFTER  (Trie + flat dict)", bench_after_width)

speedup_w = t_before_w / t_after_w if t_after_w > 0 else float('inf')
print(f"\n  Speedup: {speedup_w:.2f}x")

# Correctness check
errors = 0
for text in all_texts[:500]:
    r_before = calculate_string_width_before(text, FONT_MAP)
    r_after  = calculate_string_width_after(text, TRIE_ROOT, FLAT_WIDTHS)
    if r_before != r_after:
        errors += 1
        if errors <= 3:
            print(f"  [MISMATCH] text={repr(text[:60])}  before={r_before}  after={r_after}")
if errors == 0:
    print(f"  Correctness: PASS (checked first 500 strings)")
else:
    print(f"  Correctness: FAIL — {errors} mismatches!")


# ===========================================================================
# BENCHMARK 2: convert_spaces_to_dots_for_display
# ===========================================================================

print()
print("=" * 70)
print("BENCHMARK 2: convert_spaces_to_dots_for_display")
print("-" * 70)

SPACE_DOT_SYMBOL = "·"

# --- BEFORE: current (per-line re.sub with dynamic pattern string) ----------

def convert_spaces_before(text: str, enable_conversion: bool = True) -> str:
    if not enable_conversion or text is None:
        return text if text is not None else ""

    lines = text.splitlines(keepends=True)
    processed_lines = []

    for line in lines:
        line_content = line.rstrip('\r\n')
        line_endings = line[len(line_content):]
        # Dynamic pattern built per line
        pattern = f'[ {SPACE_DOT_SYMBOL}]+'

        def replace_spaces_and_dots(match):
            cluster = match.group(0)
            start_pos = match.start()
            end_pos = match.end()
            if start_pos == 0 or end_pos == len(line_content) or len(cluster) > 1:
                return SPACE_DOT_SYMBOL * len(cluster)
            return cluster

        new_content = re.sub(pattern, replace_spaces_and_dots, line_content)
        processed_lines.append(new_content + line_endings)

    return "".join(processed_lines)


def bench_before_dots():
    count = 0
    for text in all_texts:
        convert_spaces_before(text)
        count += 1
    return count


# --- AFTER: pre-compiled regex, no per-call closure --------------------------

_SPACE_DOT_RE = re.compile(f'[ {re.escape(SPACE_DOT_SYMBOL)}]+')


def _make_replacer(line_len: int):
    """Returns a replacer function for a line of given length."""
    def _replace(match: re.Match) -> str:
        cluster = match.group(0)
        if match.start() == 0 or match.end() == line_len or len(cluster) > 1:
            return SPACE_DOT_SYMBOL * len(cluster)
        return cluster
    return _replace


def convert_spaces_after(text: str, enable_conversion: bool = True) -> str:
    if not enable_conversion or text is None:
        return text if text is not None else ""

    lines = text.splitlines(keepends=True)
    processed_lines = []

    for line in lines:
        line_content = line.rstrip('\r\n')
        line_endings = line[len(line_content):]
        lc_len = len(line_content)
        replacer = _make_replacer(lc_len)
        new_content = _SPACE_DOT_RE.sub(replacer, line_content)
        processed_lines.append(new_content + line_endings)

    return "".join(processed_lines)


def bench_after_dots():
    count = 0
    for text in all_texts:
        convert_spaces_after(text)
        count += 1
    return count


t_before_d, _ = run_benchmark("BEFORE (dynamic pattern per line)", bench_before_dots)
t_after_d,  _ = run_benchmark("AFTER  (pre-compiled regex)", bench_after_dots)

speedup_d = t_before_d / t_after_d if t_after_d > 0 else float('inf')
print(f"\n  Speedup: {speedup_d:.2f}x")

# Correctness check
errors = 0
for text in all_texts[:500]:
    r_before = convert_spaces_before(text)
    r_after  = convert_spaces_after(text)
    if r_before != r_after:
        errors += 1
        if errors <= 3:
            print(f"  [MISMATCH] text={repr(text[:60])}")
if errors == 0:
    print(f"  Correctness: PASS (checked first 500 strings)")
else:
    print(f"  Correctness: FAIL — {errors} mismatches!")


# ===========================================================================
# BENCHMARK 3: highlightBlock regex compilation
# ===========================================================================

print()
print("=" * 70)
print("BENCHMARK 3: regex compilation inside hot path (highlightBlock pattern)")
print("-" * 70)

COLOR_TAG_PATTERN_STR = (
    r"(\[(Red|Green|Blue|Yellow|l_Blue|Purple|Silver|Orange|White)\])|"
    r"(\[/C\])|"
    r"(\{\s*Color\s*:\s*(Red|Green|Blue|White)\s*\})"
)

BUILTIN_RULES_STRS = [
    r"(\{[^}]*\})",
    r"(\[[^\]]*\])",
    r"(\\n)",
]

# BEFORE: re.compile() inside the loop (as in highlightBlock)
def bench_before_regex():
    count = 0
    for text in all_texts:
        color_tag_pattern = re.compile(COLOR_TAG_PATTERN_STR, re.IGNORECASE)  # per call!
        list(color_tag_pattern.finditer(text))
        for pattern_str in BUILTIN_RULES_STRS:
            list(re.finditer(pattern_str, text))  # no cache guarantee
        count += 1
    return count


# AFTER: pre-compiled at class/module level
_COLOR_TAG_RE = re.compile(COLOR_TAG_PATTERN_STR, re.IGNORECASE)
_BUILTIN_RES = [re.compile(p) for p in BUILTIN_RULES_STRS]

def bench_after_regex():
    count = 0
    for text in all_texts:
        list(_COLOR_TAG_RE.finditer(text))
        for compiled in _BUILTIN_RES:
            list(compiled.finditer(text))
        count += 1
    return count


t_before_r, _ = run_benchmark("BEFORE (re.compile() inside loop)", bench_before_regex)
t_after_r,  _ = run_benchmark("AFTER  (pre-compiled module-level)", bench_after_regex)

speedup_r = t_before_r / t_after_r if t_after_r > 0 else float('inf')
print(f"\n  Speedup: {speedup_r:.2f}x")


# ===========================================================================
# BENCHMARK 4: Glossary underline — char-by-char vs range setFormat
# (Pure Python simulation — no Qt, but models the iteration cost)
# ===========================================================================

print()
print("=" * 70)
print("BENCHMARK 4: glossary/spell underline — char-by-char vs range call")
print("-" * 70)

# Simulate glossary matches: ~10% of lines have a match of avg 8 chars
import random
random.seed(42)
MATCHES = []
for text in all_texts[:2000]:
    if len(text) > 10 and random.random() < 0.15:
        start = random.randint(0, max(0, len(text) - 8))
        length = random.randint(3, min(8, len(text) - start))
        MATCHES.append((text, start, length))

print(f"  Simulated glossary matches: {len(MATCHES)}")

# Accumulate "cost" by simply doing the iterations
def bench_char_by_char():
    total = 0
    for text, start, length in MATCHES:
        for offset in range(length):
            index = start + offset
            # Simulate: read format(index), modify, setFormat(index, 1, ...)
            total += index  # cheap stand-in
    return len(MATCHES)

def bench_range_call():
    total = 0
    for text, start, length in MATCHES:
        # Simulate: read format(start), modify, setFormat(start, length, ...)
        total += start  # ONE call
    return len(MATCHES)

t_before_g, _ = run_benchmark("BEFORE (setFormat per char in range)", bench_char_by_char, reps=5)
t_after_g,  _ = run_benchmark("AFTER  (setFormat once for whole range)", bench_range_call, reps=5)

speedup_g = t_before_g / t_after_g if t_after_g > 0 else float('inf')
print(f"\n  Speedup: {speedup_g:.2f}x  (loop overhead only; real Qt gain will be larger)")


# ===========================================================================
# Summary
# ===========================================================================

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"  {'Benchmark':<45} {'Speedup':>10}")
print("-" * 70)
print(f"  {'calculate_string_width  (Trie vs list scan)':<45} {speedup_w:>9.2f}x")
print(f"  {'convert_spaces_to_dots  (pre-compiled regex)':<45} {speedup_d:>9.2f}x")
print(f"  {'highlightBlock regex    (pre-compiled)':<45} {speedup_r:>9.2f}x")
print(f"  {'Glossary underline      (range vs char loop)':<45} {speedup_g:>9.2f}x")
print("=" * 70)
print()
print("Note: calculate_string_width and regex pre-compilation are the most")
print("impactful changes since they fire on every keystroke in the editor.")
