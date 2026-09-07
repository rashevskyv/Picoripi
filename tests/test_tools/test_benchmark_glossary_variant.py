"""
Tests for glossary variant cProfile probe, safety helpers, and benchmark tools.
"""

from __future__ import annotations

import cProfile
import json
import pickle
import re
from pathlib import Path

import pytest

from components.glossary.details_mixin import DetailsMixin
from tools.benchmark_glossary_variant import (
    CoreCallbackBenchmark,
    calculate_sha256,
    get_monitored_live_files,
    inspect_profile,
    main as benchmark_main,
    record_initial_hashes,
    verify_live_hashes,
)


class FakeEdit:
    def __init__(self) -> None:
        self.text_val = ""

    def setText(self, text: str) -> None:
        self.text_val = text


class FakeItem:
    def __init__(self, val: str) -> None:
        self._val = val

    def data(self, role: int) -> str:
        return self._val


class FakeHost(DetailsMixin):
    def __init__(self) -> None:
        self._translation_edit = FakeEdit()
        self._refresh_notes_called = False
        self._confirm_call_count = 0
        self._confirmed_advance = None
        self._raise_on_confirm = False

    def _refresh_rendered_notes(self) -> None:
        self._refresh_notes_called = True

    def _on_confirm_clicked(self, advance: bool = False) -> None:
        self._confirm_call_count += 1
        self._confirmed_advance = advance
        if self._raise_on_confirm:
            raise RuntimeError("Deliberate failure during confirmation")


@pytest.fixture
def mini_benchmark_project(tmp_path: Path) -> Path:
    """Create a minimal project fixture with a multi-variant glossary and session."""
    proj_dir = tmp_path / "MiniBenchProject"
    proj_dir.mkdir(parents=True, exist_ok=True)

    secret_term = "SecretTermAlpha"
    secret_trans_1 = "ТаємнийТермінОдин"
    secret_trans_2 = "ТаємнийТермінДва"
    secret_notes = "ДелікатніНотатки"

    # 1. project.uiproj
    proj_data = {
        "id": "mini-test-id",
        "name": "MiniBench",
        "plugin_name": "plain_text",
        "blocks": [
            {
                "id": "b1",
                "name": "block_0",
                "source_file": "src.txt",
                "translation_file": "dst.txt",
            }
        ],
    }
    (proj_dir / "project.uiproj").write_text(json.dumps(proj_data), encoding="utf-8")
    (proj_dir / "project_settings.json").write_text("{}", encoding="utf-8")

    # 2. glossary.json
    entries = [
        {
            "original": secret_term,
            "translation": secret_trans_1,
            "notes": secret_notes,
            "section": "General",
            "profiled": False,
            "status": "translated",
            "translation_variants": [
                {"translation": secret_trans_1, "model": "m1"},
                {"translation": secret_trans_2, "model": "m2"},
            ],
        }
    ]
    (proj_dir / "glossary.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")

    # 3. .picoripi_session
    session_snapshot = {
        "version": 1,
        "data": [
            [
                f"Hello {secret_term} world!",
                f"Another line with {secret_term}.",
            ]
        ],
        "edited_data": {},
        "block_names": {0: "block_0"},
    }
    with (proj_dir / ".picoripi_session").open("wb") as f:
        pickle.dump(session_snapshot, f)

    (proj_dir / ".picoripi_session.clean").write_text("dummy_clean_id", encoding="ascii")
    (proj_dir / ".picoripi_session.json").write_text(json.dumps(session_snapshot), encoding="utf-8")

    return proj_dir / "project.uiproj"


# ---------------------------------------------------------------------------
# 1. In-App Probe Unit Tests
# ---------------------------------------------------------------------------


def test_probe_disabled_by_default(monkeypatch, capsys):
    """When PICORIPI_PROFILE_GLOSSARY_VARIANT is unset, no profiling or stdout overhead occurs."""
    monkeypatch.delenv("PICORIPI_PROFILE_GLOSSARY_VARIANT", raising=False)

    host = FakeHost()
    item = FakeItem("NewVariantTranslation")

    host._apply_variant_item(item, advance=True)

    assert host._translation_edit.text_val == "NewVariantTranslation"
    assert host._refresh_notes_called is True
    assert host._confirm_call_count == 1
    assert host._confirmed_advance is True

    captured = capsys.readouterr()
    assert "GLOSSARY VARIANT WALL TIME:" not in captured.out
    assert "PROFILE:" not in captured.out


def test_probe_enabled_generates_prof_and_executes_once(monkeypatch, capsys):
    """When PICORIPI_PROFILE_GLOSSARY_VARIANT=1, dumps .prof, outputs timings and inspection command."""
    monkeypatch.setenv("PICORIPI_PROFILE_GLOSSARY_VARIANT", "1")

    host = FakeHost()
    secret_variant = "SecretVariantText12345"
    item = FakeItem(secret_variant)

    host._apply_variant_item(item, advance=True)

    assert host._translation_edit.text_val == secret_variant
    assert host._confirm_call_count == 1
    assert host._confirmed_advance is True

    captured = capsys.readouterr()
    out = captured.out

    assert "GLOSSARY VARIANT WALL TIME:" in out
    assert "PROFILE:" in out
    assert "benchmark_glossary_variant.py --profile" in out

    # Privacy guarantee: secret variant content must NOT appear in printed probe output
    assert secret_variant not in out

    # Verify generated prof file
    match = re.search(r"PROFILE:\s*(.+?\.prof)", out)
    assert match is not None
    prof_path = Path(match.group(1).strip())
    try:
        assert prof_path.exists()
        assert prof_path.stat().st_size > 0
    finally:
        if prof_path.exists():
            prof_path.unlink()


def test_probe_handles_exceptions_and_disables_profiler(monkeypatch, capsys):
    """Exceptions during confirm still disable the profiler and dump stats without leaking state."""
    monkeypatch.setenv("PICORIPI_PROFILE_GLOSSARY_VARIANT", "1")

    host = FakeHost()
    host._raise_on_confirm = True
    item = FakeItem("VariantFailing")

    with pytest.raises(RuntimeError, match="Deliberate failure during confirmation"):
        host._apply_variant_item(item, advance=False)

    captured = capsys.readouterr()
    out = captured.out
    assert "GLOSSARY VARIANT WALL TIME:" in out
    assert "PROFILE:" in out

    match = re.search(r"PROFILE:\s*(.+?\.prof)", out)
    assert match is not None
    prof_path = Path(match.group(1).strip())
    try:
        assert prof_path.exists()
    finally:
        if prof_path.exists():
            prof_path.unlink()


# ---------------------------------------------------------------------------
# 2. SHA-256 Safety and Profile Inspection Tests
# ---------------------------------------------------------------------------


def test_sha256_helpers(tmp_path: Path):
    """Test calculate_sha256 and verify_live_hashes behavior across lifecycle mutations."""
    file_a = tmp_path / "file_a.txt"
    file_a.write_text("initial content", encoding="utf-8")
    file_b = tmp_path / "file_b.txt"

    # Missing file returns None
    assert calculate_sha256(file_b) is None

    # Existing file returns 64-char hex
    hash_a = calculate_sha256(file_a)
    assert hash_a is not None and len(hash_a) == 64

    initial_hashes = record_initial_hashes([file_a, file_b])
    assert initial_hashes[file_a] == hash_a
    assert initial_hashes[file_b] is None

    # 1. Unchanged files verify successfully
    intact, mismatches = verify_live_hashes(initial_hashes)
    assert intact is True
    assert len(mismatches) == 0

    # 2. Modified file is detected
    file_a.write_text("modified content", encoding="utf-8")
    intact, mismatches = verify_live_hashes(initial_hashes)
    assert intact is False
    assert any("File modified:" in m for m in mismatches)

    # Revert file_a
    file_a.write_text("initial content", encoding="utf-8")

    # 3. Unexpectedly created file is detected
    file_b.write_text("created now", encoding="utf-8")
    intact, mismatches = verify_live_hashes(initial_hashes)
    assert intact is False
    assert any("File unexpectedly created:" in m for m in mismatches)

    # 4. Deleted file is detected
    file_b.unlink()
    file_a.unlink()
    intact, mismatches = verify_live_hashes(initial_hashes)
    assert intact is False
    assert any("File unexpectedly deleted:" in m for m in mismatches)


def test_inspect_profile(tmp_path: Path, capsys):
    """Test inspecting a cProfile dump via inspect_profile."""
    prof_path = tmp_path / "test_sample.prof"

    # Generate a small prof file
    profiler = cProfile.Profile()
    profiler.enable()
    _ = sum(x * x for x in range(1000))
    profiler.disable()
    profiler.dump_stats(str(prof_path))

    inspect_profile(prof_path, top_n=5)
    captured = capsys.readouterr()
    assert "CPROFILE INSPECTION" in captured.out
    assert "cumulative functions" in captured.out

    # Non-existent file reports error
    inspect_profile(tmp_path / "non_existent.prof", top_n=5)
    captured = capsys.readouterr()
    assert "Error: Profile file not found" in captured.err


def test_core_callback_benchmark_simulation_safety_and_privacy(
    mini_benchmark_project: Path, capsys
):
    """Test isolated core callback simulation on temporary copy with privacy guarantees."""
    proj_file = mini_benchmark_project
    proj_dir = proj_file.parent

    monitored = get_monitored_live_files(proj_file)
    hashes_before = record_initial_hashes(monitored)

    secret_term = "SecretTermAlpha"
    secret_trans_1 = "ТаємнийТермінОдин"
    secret_trans_2 = "ТаємнийТермінДва"
    secret_notes = "ДелікатніНотатки"

    sim = CoreCallbackBenchmark(
        live_project_path=proj_file,
        runs=3,
        target_term=None,
    )
    sim.run()

    captured = capsys.readouterr()
    out = captured.out

    # 1. Verification of live file safety
    intact, mismatches = verify_live_hashes(hashes_before)
    assert intact is True, f"Live files were modified: {mismatches}"
    assert "LIVE INPUT HASHES: UNCHANGED" in out

    # Live glossary file still has unconfirmed status and initial translation
    live_gloss_data = json.loads((proj_dir / "glossary.json").read_text(encoding="utf-8"))
    assert live_gloss_data[0]["status"] == "translated"
    assert live_gloss_data[0]["translation"] == secret_trans_1

    # 2. Output structure
    assert "CORE CALLBACK SIMULATION (Isolated Copy)" in out
    assert "Run #01:" in out
    assert "Run #02:" in out
    assert "Run #03:" in out
    assert "SUMMARY (seconds):" in out
    assert "update_entry / persist" in out
    assert "update_occurrences_for_entry" in out

    # 3. Privacy guarantee
    assert secret_term not in out
    assert secret_trans_1 not in out
    assert secret_trans_2 not in out
    assert secret_notes not in out


def test_benchmark_cli_profile_flag(tmp_path: Path, capsys, monkeypatch):
    """Test CLI invoking --profile."""
    prof_path = tmp_path / "cli_sample.prof"
    profiler = cProfile.Profile()
    profiler.enable()
    _ = [i for i in range(100)]
    profiler.disable()
    profiler.dump_stats(str(prof_path))

    monkeypatch.setattr("sys.argv", ["benchmark_glossary_variant.py", "--profile", str(prof_path)])
    code = benchmark_main()
    assert code == 0

    captured = capsys.readouterr()
    assert "CPROFILE INSPECTION" in captured.out
