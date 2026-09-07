#!/usr/bin/env python3
"""
Benchmark utility for Picoripi glossary variant confirmation.

Provides:
1. --profile <path.prof>: Inspects top cumulative functions from real in-app
   cProfile runs (PICORIPI_PROFILE_GLOSSARY_VARIANT=1).
2. Live project SHA-256 integrity verification (read-only safety guarantee).
3. Optional CORE CALLBACK SIMULATION on isolated temporary copies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import pstats
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.data_store import AppDataStore
from core.glossary.models import (
    OCC_MENTION,
    OCC_SPOKEN,
    STATUS_CONFIRMED,
    GlossaryEntry,
    GlossaryOccurrence,
)
from core.glossary_manager import GlossaryManager
from core.project_manager import ProjectManager
from core.speaker_resolution import build_speaker_pool


MONITORED_BASENAMES = [
    "project.uiproj",
    "glossary.json",
    "project_settings.json",
    ".picoripi_session",
    ".picoripi_session.clean",
    ".picoripi_session.json",
]


def calculate_sha256(path: Path) -> Optional[str]:
    """Calculate SHA-256 for a file if it exists, otherwise return None."""
    if not path.exists() or not path.is_file():
        return None
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_monitored_live_files(project_path: Path) -> List[Path]:
    """Collect paths of all live files that could potentially be affected."""
    project_dir = project_path if project_path.is_dir() else project_path.parent
    files = [project_dir / name for name in MONITORED_BASENAMES]

    # Global user settings
    home_settings = Path.home() / ".picoripi" / "settings.json"
    files.append(home_settings)

    admin_settings = Path(r"C:\Users\Administrator\.picoripi\settings.json")
    if admin_settings not in files:
        files.append(admin_settings)

    return files


def record_initial_hashes(files: Sequence[Path]) -> Dict[Path, Optional[str]]:
    """Record initial SHA-256 hashes of all monitored files."""
    return {f: calculate_sha256(f) for f in files}


def verify_live_hashes(initial: Dict[Path, Optional[str]]) -> Tuple[bool, List[str]]:
    """Verify that all monitored live files remain byte-for-byte unchanged."""
    mismatches: List[str] = []
    for path, expected_hash in initial.items():
        current_hash = calculate_sha256(path)
        if expected_hash is None:
            if current_hash is not None:
                mismatches.append(f"File unexpectedly created: {path}")
        else:
            if current_hash is None:
                mismatches.append(f"File unexpectedly deleted: {path}")
            elif current_hash != expected_hash:
                mismatches.append(
                    f"File modified: {path} (expected {expected_hash[:12]}..., got {current_hash[:12]}...)"
                )
    return (len(mismatches) == 0, mismatches)


def inspect_profile(prof_path: Path, top_n: int = 30) -> None:
    """Print top cumulative functions from a cProfile .prof dump using stdlib pstats."""
    if not prof_path.exists():
        print(f"Error: Profile file not found: {prof_path}", file=sys.stderr)
        return

    print("=" * 80)
    print(f"CPROFILE INSPECTION (top {top_n} cumulative functions): {prof_path}")
    print("=" * 80)
    stats = pstats.Stats(str(prof_path))
    stats.strip_dirs()
    stats.sort_stats("cumulative")
    stats.print_stats(top_n)
    print("=" * 80)


def calc_percentile(data: Sequence[float], p: float) -> float:
    """Calculate p-th percentile (0.0 <= p <= 1.0) using linear interpolation."""
    if not data:
        return 0.0
    if len(data) == 1:
        return data[0]
    sorted_data = sorted(data)
    idx = (len(sorted_data) - 1) * p
    low = int(idx)
    high = low + 1
    if high >= len(sorted_data):
        return sorted_data[-1]
    weight = idx - low
    return sorted_data[low] * (1.0 - weight) + sorted_data[high] * weight


def load_game_rules(plugin_name: str) -> Any:
    """Instantiate GameRules for the project's plugin."""
    if plugin_name == "zelda_bmg":
        from plugins.zelda_bmg.rules import GameRules
        return GameRules()
    try:
        import importlib
        mod = importlib.import_module(f"plugins.{plugin_name}.rules")
        cls = getattr(mod, "GameRules")
        return cls()
    except Exception:
        from plugins.base_game_rules import BaseGameRules
        return BaseGameRules()


class CoreCallbackBenchmark:
    """Runs isolated core callback simulations on temporary copies with SHA-256 verification."""

    def __init__(self, live_project_path: Path, runs: int = 5, target_term: Optional[str] = None):
        self.live_project_path = live_project_path.resolve()
        self.live_project_dir = (
            self.live_project_path if self.live_project_path.is_dir() else self.live_project_path.parent
        )
        self.runs = max(1, runs)
        self.target_term = target_term

    def run(self) -> None:
        """Execute core callback simulation safely."""
        monitored_files = get_monitored_live_files(self.live_project_path)
        initial_hashes = record_initial_hashes(monitored_files)

        try:
            with tempfile.TemporaryDirectory(prefix="picoripi_sim_") as tmp_dir_str:
                tmp_dir = Path(tmp_dir_str)
                self._run_simulation(tmp_dir)
        finally:
            intact, mismatches = verify_live_hashes(initial_hashes)
            if not intact:
                msg = "CRITICAL SAFETY FAILURE: Live files were modified!\n" + "\n".join(mismatches)
                print(msg, file=sys.stderr)
                raise RuntimeError(msg)
            print("LIVE INPUT HASHES: UNCHANGED")

    def _copy_files(self, tmp_dir: Path) -> None:
        for item in self.live_project_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, tmp_dir / item.name)
        gloss_path = tmp_dir / "glossary.json"
        if gloss_path.exists():
            shutil.copy2(gloss_path, tmp_dir / "glossary.json.pristine")

    def _run_simulation(self, tmp_dir: Path) -> None:
        self._copy_files(tmp_dir)

        # 1. Project / session load
        t0 = time.perf_counter()
        pm = ProjectManager()
        pm.load(str(tmp_dir / "project.uiproj"))

        session_pickle = tmp_dir / ".picoripi_session"
        store = AppDataStore()
        if session_pickle.exists():
            import pickle
            with session_pickle.open("rb") as f:
                store.restore_from_snapshot(pickle.load(f))
        t_proj_sess = time.perf_counter() - t0

        block_count = len(store.data)
        string_count = sum(len(b) for b in store.data) if store.data else 0

        # 2. Glossary load
        t0 = time.perf_counter()
        gm = GlossaryManager()
        gloss_path = tmp_dir / "glossary.json"
        raw_text = gloss_path.read_text(encoding="utf-8")
        plugin_name = getattr(pm.project, "plugin_name", "zelda_bmg") or "zelda_bmg"
        gm.load_from_text(plugin_name=plugin_name, glossary_path=gloss_path, raw_text=raw_text)
        t_gloss_load = time.perf_counter() - t0

        rules = load_game_rules(plugin_name)

        class DummyMW:
            def __init__(self, st, p, r):
                self.data_store = st
                self.project_manager = p
                self.current_game_rules = r
                self.settings_manager = None
                self.translation_handler = None
                self.ui_updater = None

        dummy_mw = DummyMW(store, pm, rules)
        pool = build_speaker_pool(dummy_mw, raw=True)

        aliases = {}
        aliases_path = tmp_dir / "speaker_aliases.json"
        if aliases_path.exists():
            try:
                aliases = json.loads(aliases_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        gm.bind_project_rows(store, rules, speaker_aliases=aliases, speaker_pool=pool)

        # 3. Occurrence index build (cold)
        t0 = time.perf_counter()
        gm.build_occurrence_index(store.data)
        t_cold_index = time.perf_counter() - t0

        occ_map = gm.get_occurrence_map()
        total_occurrences = sum(len(v) for v in occ_map.values())

        # Select candidate term
        candidate = self._select_candidate(gm, occ_map)
        term_len = len(candidate.original)
        cand_occs = occ_map.get(candidate.original, [])
        mentions = sum(1 for o in cand_occs if o.kind == OCC_MENTION)
        spoken = sum(1 for o in cand_occs if o.kind == OCC_SPOKEN)

        print("=" * 75)
        print("CORE CALLBACK SIMULATION (Isolated Copy)")
        print("NOTE: Real UI latency (user-facing freeze) must be profiled in-app via:")
        print('  $env:PICORIPI_PROFILE_GLOSSARY_VARIANT = "1"')
        print("  .\\venv\\Scripts\\python.exe main.py")
        print("and inspected with:")
        print("  .\\venv\\Scripts\\python.exe tools\\benchmark_glossary_variant.py --profile <file>")
        print("=" * 75)
        print(f"Platform:       {platform.platform()}")
        print(f"Python version: {platform.python_version()}")
        print(f"Plugin:         {plugin_name}")
        print(f"Dataset:        {block_count} blocks, {string_count} strings, {len(gm.get_entries())} entries")
        print(f"Total index:    {total_occurrences} occurrences")
        print(f"Selected term:  term_length={term_len}, occs={len(cand_occs)} (mentions={mentions}, spoken={spoken})")
        print("-" * 75)
        print(f"Cold index build:   {t_cold_index:.4f}s")
        print(f"Project/sess load:  {t_proj_sess:.4f}s")
        print(f"Glossary load/init: {t_gloss_load:.4f}s")
        print("-" * 75)
        print(f"Warm runs ({self.runs} runs, unchanged section):")

        persist_times: List[float] = []
        update_occ_times: List[float] = []
        callback_times: List[float] = []

        new_trans = (
            candidate.translation_variants[1].translation
            if len(candidate.translation_variants or []) >= 2
            else "ConfirmedVariant"
        )

        for run_i in range(self.runs):
            # Restore pristine copy
            pristine = tmp_dir / "glossary.json.pristine"
            shutil.copy2(pristine, gloss_path)
            gm.load_from_text(plugin_name=plugin_name, glossary_path=gloss_path, raw_text=pristine.read_text(encoding="utf-8"))
            gm.bind_project_rows(store, rules, speaker_aliases=aliases, speaker_pool=pool)
            gm.build_occurrence_index(store.data)

            prev_entry = gm.get_entry(candidate.original)

            # Measure update_entry (with persist)
            t0 = time.perf_counter()
            upd_entry = gm.update_entry(
                candidate.original, new_trans, candidate.notes, section=candidate.section, status=STATUS_CONFIRMED
            )
            t_persist = time.perf_counter() - t0
            persist_times.append(t_persist)

            # Measure update_occurrences_for_entry
            t0 = time.perf_counter()
            gm.update_occurrences_for_entry(store.data, candidate.original, upd_entry, previous_entry=prev_entry)
            t_occ = time.perf_counter() - t0
            update_occ_times.append(t_occ)

            t_cb_total = t_persist + t_occ
            callback_times.append(t_cb_total)

            print(f"  Run #{run_i + 1:02d}: callback={t_cb_total:.4f}s (persist={t_persist:.4f}s, update_occ={t_occ:.6f}s)")

        print("-" * 75)
        print("SUMMARY (seconds):")
        print(f"{'Phase':<32} | {'Min':<8} | {'Median':<8} | {'Mean':<8} | {'P95':<8} | {'Max':<8}")
        print("-" * 80)
        for label, times in [
            ("update_entry / persist", persist_times),
            ("update_occurrences_for_entry", update_occ_times),
            ("core callback total", callback_times),
        ]:
            v_min = min(times)
            v_med = statistics.median(times)
            v_mean = statistics.mean(times)
            v_p95 = calc_percentile(times, 0.95)
            v_max = max(times)
            print(f"{label:<32} | {v_min:8.4f} | {v_med:8.4f} | {v_mean:8.4f} | {v_p95:8.4f} | {v_max:8.4f}")
        print("=" * 75)

    def _select_candidate(
        self, gm: GlossaryManager, occ_map: Dict[str, List[GlossaryOccurrence]]
    ) -> GlossaryEntry:
        entries = gm.get_entries()
        if self.target_term:
            matched = next((e for e in entries if e.original == self.target_term), None)
            if matched:
                return matched
            raise ValueError("Requested term not found in glossary.")

        for e in entries:
            variants = e.translation_variants or []
            if len(variants) >= 2 and len(occ_map.get(e.original, [])) >= 1:
                return e
        for e in entries:
            if len(e.translation_variants or []) >= 2:
                return e
        if entries:
            return entries[0]
        raise ValueError("Glossary has no entries.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark utility for Picoripi glossary variant confirmation."
    )
    parser.add_argument(
        "project_path",
        type=Path,
        nargs="?",
        default=None,
        help="Path to .uiproj file or project directory.",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=None,
        help="Path to .prof file captured from PICORIPI_PROFILE_GLOSSARY_VARIANT=1 run.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=30,
        help="Number of top functions to show when inspecting profile (default: 30).",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of runs for core callback simulation (default: 5).",
    )
    parser.add_argument(
        "--term",
        type=str,
        default=None,
        help="Optional specific glossary term to confirm (never printed to output).",
    )

    args = parser.parse_args()

    if args.profile:
        inspect_profile(args.profile, top_n=args.top)
        return 0

    if not args.project_path:
        parser.print_help()
        return 1

    if not args.project_path.exists():
        print(f"Error: Project path not found: {args.project_path}", file=sys.stderr)
        return 1

    sim = CoreCallbackBenchmark(
        live_project_path=args.project_path,
        runs=args.runs,
        target_term=args.term,
    )
    sim.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
