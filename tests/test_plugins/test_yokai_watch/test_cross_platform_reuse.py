"""Two-project cross-platform translation reuse between Yo-kai Watch (3DS) and Yo-kai Watch (Switch).

Verifies the full end-to-end workflow:
1. Two temporary Yo-kai projects registered with a shared series glossary and registry.
2. Accepted 3DS translations are loaded through the real registry and memory loading path into Switch series candidates.
3. Unverified Switch layout (ywnx) flags candidate as unverified (safe=False) preventing silent auto-application.
4. Explicitly confirmed series candidates apply to the destination project without provider AI calls.
5. Batch duplicate folding groups identical contexts; permitted Switch followers receive translations via production code.
6. Safety barriers (speaker mismatch, tag corruption, line count overflow) remain strictly blocking.
7. Local conflicting translations in Switch survive batch application and persistence/reload.
8. Series glossary integration uses the standard series interface without a competing store.
"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.data_state_processor import DataStateProcessor
from core.glossary.series import METADATA_KEY, linked_series_paths, series_chain
from core.saved_translations_manager import SavedTranslationsManager
from core.translation.layout_contract import text_fits_place
from core.translation.series_memory import (
    MEMORY_NAME,
    index_neutral_rows,
    index_source_positions,
    load_series_memory,
    register_project,
    registry_path,
    source_hash,
)
from dialogs.series_sentence_dialog import SeriesSentenceDialog
from handlers.translation.batch_translator import AIBatchTranslator
from handlers.translation_handler import TranslationHandler
from plugins.common.tag_logic import TAG_STATUS_OK, compare_tags
from plugins.testing import load_rules


SENTENCE_WHISPER = "I am Whisper, your Yo-kai butler!"
TRANSLATION_3DS = "Я Віспер, твій дворецький-йокай!"
SENTENCE_REPEATED = "Take care of yourself today!"


def _setup_yokai_project(tmp_path: Path, game: str = "ywnx", shared_glossary: Path = None):
    """Constructs a real Yo-kai Watch project window with DataStateProcessor and SavedTranslationsManager."""
    rules = load_rules("yokai_watch")
    rules._game = lambda root=None: game

    project_name = "Yo-kai Watch (3DS)" if game == "yw1" else "Yo-kai Watch (Switch)"
    meta = {}
    if shared_glossary:
        meta[METADATA_KEY] = [str(shared_glossary)]

    blocks = [
        SimpleNamespace(
            name="ev001_01_m_en.cfg.bin",
            source_file="data/txt/ev/en/ev001_01_m_en.cfg.bin",
            internal_key="",
            metadata={},
            id="b0",
        )
    ]
    proj = SimpleNamespace(name=project_name, metadata=meta, blocks=blocks, virtual_folders=[])
    pm = SimpleNamespace(project=proj, project_dir=str(tmp_path))

    data = [
        [SENTENCE_WHISPER, SENTENCE_WHISPER, SENTENCE_REPEATED, SENTENCE_REPEATED],
    ]

    mw = SimpleNamespace()
    mw.current_game_rules = rules
    rules.mw = mw   # as the app wires them: the fit check reads the window's width maps
    mw.project_manager = pm
    mw.block_to_project_file_map = {0: 0}
    mw.translation_config = {
        "series_reuse_sentences": True,
        "series_sentence_words": 2,
        "series_safe_ticked": False,
        "fold_duplicates": True,
    }
    mw.line_width_warning_threshold_pixels = 300
    mw.game_dialog_max_width_pixels = 320
    mw.width_tolerance_percent = 5
    mw.typeset_enabled = False
    mw.data_store = SimpleNamespace(
        data=data,
        edited_data={},
        edited_file_data=[],
        unsaved_changes=False,
        unsaved_block_indices=set(),
        block_names={"0": "ev001_01_m_en.cfg.bin"},
        physical_block_idx=0,
        current_block_idx=0,
        current_string_idx=0,
        json_path=str(tmp_path / "project.json"),
        get_session_snapshot=lambda: {},
    )
    mw.string_metadata = {}
    mw.default_font_file = "ft_nrm.json"
    # A letter is about 9 pixels in the 3DS font and about 24 in the Switch font (layout.json is measured with each).
    mw.font_map = {"a": {"width": 8 if game == "yw1" else 24}}
    mw.all_font_maps = {"ft_nrm.json": mw.font_map}
    mw.all_bfn_fonts = {}
    mw.ui_updater = MagicMock()
    mw.undo_manager = MagicMock()
    sb = MagicMock()
    sb.return_value = sb
    mw.statusBar = sb
    mw.text_operation_handler = MagicMock()

    dp = DataStateProcessor(mw)
    mw.data_processor = dp

    saved_mgr = SavedTranslationsManager(mw)
    saved_mgr.source_positions = index_source_positions(data)
    mw.saved_translations_manager = saved_mgr

    with patch("handlers.translation.facade.handler.TranslationUIHandler"), \
         patch("PyQt6.QtCore.QTimer.singleShot"):
        handler = TranslationHandler(mw, dp, mw.ui_updater)
    handler.ui_handler = MagicMock()
    mw.translation_handler = handler

    # Set up row resolution on rules
    def mock_row(block_idx, string_idx):
        param = 2  # dialogue
        row_mock = SimpleNamespace(kind="TEXT_INFO", param=param, text_id=f"txt_{string_idx}", number=string_idx, text="")
        return ("data/txt/ev/en/ev001_01_m_en.cfg.bin", row_mock, None)

    rules._row = mock_row
    # Speaker logic: row 2 has Jibanyan, other rows have Whisper
    rules.get_speaker_for_string = lambda b, s: "Jibanyan" if s == 2 else "Whisper"

    return mw, rules, handler


def test_two_project_registration_and_candidate_loading(tmp_path):
    """Two temporary Yo-kai projects share a series glossary; 3DS saves a translation, Switch loads it via registry."""
    shared_glossary = tmp_path / "shared" / "_glossary" / "glossary.json"
    shared_glossary.parent.mkdir(parents=True)
    shared_glossary.write_text("[]", encoding="utf-8")

    # 1. Project 1: Yo-kai Watch 3DS
    p1_dir = tmp_path / "yw_3ds"
    p1_dir.mkdir()
    mw_3ds, _, _ = _setup_yokai_project(p1_dir, game="yw1", shared_glossary=shared_glossary)

    # Save translation in 3DS project memory
    mw_3ds.saved_translations_manager.save_translation(0, 0, TRANSLATION_3DS)
    chain_1 = series_chain(mw_3ds.project_manager.project, p1_dir)
    register_project(chain_1, "Yo-kai Watch (3DS)", p1_dir / MEMORY_NAME)

    # Verify registry was created beside the shared glossary
    assert registry_path(shared_glossary).is_file()

    # 2. Project 2: Yo-kai Watch Switch (ywnx)
    p2_dir = tmp_path / "yw_switch"
    p2_dir.mkdir()
    mw_switch, _, _ = _setup_yokai_project(p2_dir, game="ywnx", shared_glossary=shared_glossary)

    chain_2 = series_chain(mw_switch.project_manager.project, p2_dir)
    register_project(chain_2, "Yo-kai Watch (Switch)", p2_dir / MEMORY_NAME)

    # Load series memory through the real registry path
    loaded_memory = load_series_memory(chain_2, p2_dir / MEMORY_NAME)
    assert source_hash(SENTENCE_WHISPER) in loaded_memory

    mw_switch.saved_translations_manager.series_memory = loaded_memory
    mw_switch.saved_translations_manager.series_neutral = index_neutral_rows(loaded_memory)
    mw_switch.saved_translations_manager.configure_series_reuse(enabled=True, min_words=2, safe_ticked=False)

    # Check Switch candidates
    own_rows, series = mw_switch.saved_translations_manager.acceptable_rows(0, 0, SENTENCE_WHISPER)
    assert own_rows == []
    assert len(series) >= 1

    candidate = next((c for c in series if c["speaker_en"] == "Whisper"), None)
    assert candidate is not None
    assert candidate["translation"] == TRANSLATION_3DS
    assert candidate["project"] == "Yo-kai Watch (3DS)"
    assert candidate["applicable"] is True

    # The Switch message window is measured (layout.json "ywnx"): the 3DS sentence fits it, so it is safe
    assert candidate["safe"] is True, candidate["reason"]
    assert candidate["reason"] == ""


def test_explicit_confirmed_candidate_applies_without_ai_provider(tmp_path):
    """When the user explicitly confirms an unverified-layout candidate, it applies without requesting AI."""
    shared_glossary = tmp_path / "shared" / "_glossary" / "glossary.json"
    shared_glossary.parent.mkdir(parents=True)
    shared_glossary.write_text("[]", encoding="utf-8")

    # Setup 3DS and save
    p1_dir = tmp_path / "yw_3ds"
    p1_dir.mkdir()
    mw_3ds, _, _ = _setup_yokai_project(p1_dir, game="yw1", shared_glossary=shared_glossary)
    mw_3ds.saved_translations_manager.save_translation(0, 0, TRANSLATION_3DS)
    register_project(series_chain(mw_3ds.project_manager.project, p1_dir), "Yo-kai Watch (3DS)", p1_dir / MEMORY_NAME)

    # Setup Switch
    p2_dir = tmp_path / "yw_switch"
    p2_dir.mkdir()
    mw_switch, _, handler_switch = _setup_yokai_project(p2_dir, game="ywnx", shared_glossary=shared_glossary)
    chain_2 = series_chain(mw_switch.project_manager.project, p2_dir)
    register_project(chain_2, "Yo-kai Watch (Switch)", p2_dir / MEMORY_NAME)

    loaded_memory = load_series_memory(chain_2, p2_dir / MEMORY_NAME)
    mw_switch.saved_translations_manager.series_memory = loaded_memory
    mw_switch.saved_translations_manager.series_neutral = index_neutral_rows(loaded_memory)
    mw_switch.saved_translations_manager.configure_series_reuse(enabled=True, min_words=2, safe_ticked=False)

    # Count AI provider requests
    ai_requests = []
    handler_switch._run_ai_task = lambda provider, context: ai_requests.append(context)

    # Explicit user confirmation in SeriesSentenceDialog
    with patch.object(SeriesSentenceDialog, "exec", return_value=1), \
         patch.object(SeriesSentenceDialog, "accepted_rows", return_value=[(0, 0, TRANSLATION_3DS, SENTENCE_WHISPER)]):
        remaining, _ = handler_switch.batch_translator.filter_already_saved_translations(
            [{"id": 0, "text": SENTENCE_WHISPER}],
            {0: (0, 0)},
        )

    # Candidate was applied to destination project data with zero AI requests
    assert remaining == []
    assert len(ai_requests) == 0
    applied_text, _ = mw_switch.data_processor.get_current_string_text(0, 0)
    assert applied_text == TRANSLATION_3DS


def test_batch_duplicate_folding_and_follower_application_on_switch(tmp_path):
    """Duplicate folding groups identical strings; production handle_chunk_translated applies to followers."""
    p_dir = tmp_path / "yw_switch"
    p_dir.mkdir()
    mw, rules, handler = _setup_yokai_project(p_dir, game="ywnx")

    # Row 1 and Row 2 have the same text:
    # Row 1 (index 1) speaker: Whisper -> leader
    # Row 2 (index 2) speaker: Jibanyan -> different speaker, kept separate
    # Add a Row 3 (index 3) speaker: Whisper -> follower of Row 1
    mw.data_store.data[0].append(SENTENCE_REPEATED)
    rules.get_speaker_for_string = lambda b, s: "Jibanyan" if s == 2 else "Whisper"

    items = [
        {"id": 1, "text": SENTENCE_REPEATED},
        {"id": 2, "text": SENTENCE_REPEATED},
        {"id": 3, "text": SENTENCE_REPEATED},
    ]
    temp_id_map = {1: (0, 1), 2: (0, 2), 3: (0, 3)}

    context = {
        "type": "translate_block_chunked",
        "source_items": list(items),
        "temp_id_map": temp_id_map,
        "block_idx": 0,
        "mode_description": "Translate",
    }

    # 1. Run production duplicate folding
    handler.batch_translator._fold_duplicate_sources(context)

    # Items 1 and 2 kept; item 3 folded into followers of item 1
    kept = context["source_items"]
    assert len(kept) == 2
    assert kept[0]["id"] == 1
    assert kept[1]["id"] == 2
    assert context["duplicate_followers"] == {1: [3]}

    # 2. Production batch completion through handle_chunk_translated
    # AI responds only for leaders (items 1 and 2)
    leader_whisper = "Бережіть себе сьогодні (Whisper)!"
    leader_jibanyan = "Бережіть себе сьогодні (Jibanyan)!"
    chunk_text = json.dumps({
        "translated_strings": [
            {"id": 1, "translation": leader_whisper},
            {"id": 2, "translation": leader_jibanyan},
        ]
    })

    # Call production batch application path directly (no test-copied loop)
    handler.batch_translator.handle_chunk_translated(0, chunk_text, context)

    # 3. Assert observable state
    t1, _ = mw.data_processor.get_current_string_text(0, 1)
    t2, _ = mw.data_processor.get_current_string_text(0, 2)
    t3, _ = mw.data_processor.get_current_string_text(0, 3)

    assert t1 == leader_whisper
    assert t2 == leader_jibanyan  # Different speaker remained separate
    assert t3 == leader_whisper   # Follower automatically received leader translation via production code


def test_safety_barriers_speaker_tags_and_lines_remain_blocking(tmp_path):
    """Actual tag corruption, line overflows, or speaker mismatches remain strictly blocked in series and batch application."""
    p_dir = tmp_path / "yw_3ds"
    p_dir.mkdir()
    mw, rules, handler = _setup_yokai_project(p_dir, game="yw1")
    mgr = mw.saved_translations_manager
    mgr.series_reuse_enabled = True
    mgr.series_min_words = 2

    # 1. Speaker mismatch: candidate Whisper, target row Jibanyan
    mgr.series_memory = {
        source_hash(SENTENCE_WHISPER): [{
            "source": SENTENCE_WHISPER,
            "translation": TRANSLATION_3DS,
            "project": "Yo-kai Watch (3DS)",
            "speaker_en": "Whisper",
            "addressee": "",
        }]
    }
    # Row 2 in our setup is Jibanyan
    _, series = mgr.acceptable_rows(0, 2, SENTENCE_WHISPER)
    assert len(series) == 1
    assert series[0]["safe"] is False
    assert "differ" in series[0]["reason"].lower() or "відрізняються" in series[0]["reason"].lower()

    # 2. Tag corruption: translation missing in-game tags
    tagged_source = "Hello, my {CR}friend{/C}!"
    bad_tag_trans = "Привіт, мій друже!"  # missing {CR} and {/C}
    mgr.series_memory[source_hash(tagged_source)] = [{
        "source": tagged_source,
        "translation": bad_tag_trans,
        "project": "Yo-kai Watch (3DS)",
        "speaker_en": "Whisper",
        "addressee": "",
    }]
    _, series_tag = mgr.acceptable_rows(0, 0, tagged_source)
    assert len(series_tag) == 1
    assert series_tag[0]["safe"] is False
    assert "tags" in series_tag[0]["reason"].lower() or "тег" in series_tag[0]["reason"].lower()
    # compare_tags and _series_row_passes_checks strictly block tag violations
    assert compare_tags(bad_tag_trans, tagged_source)[0] != TAG_STATUS_OK
    assert not AIBatchTranslator._series_row_passes_checks(mw, tagged_source, bad_tag_trans, 0, 0)

    # 3. Line overflow: translation exceeds lines per window
    three_line_trans = "Line one\nLine two\nLine three"
    assert "LINES" in rules.get_text_fit_problems_for_string(0, 0, three_line_trans)
    assert not text_fits_place(mw, SENTENCE_WHISPER, three_line_trans, 0, 0)

    # 4. In batch application, a follower with real line overflow is refused by production code
    context = {
        "type": "translate_block_chunked",
        "block_idx": 0,
        "source_items": [{"id": 1, "text": SENTENCE_REPEATED}],
        "temp_id_map": {1: (0, 1), 2: (0, 2)},
        "duplicate_followers": {1: [2]},
    }
    chunk_text = json.dumps({
        "translated_strings": [
            {"id": 1, "translation": three_line_trans},
        ]
    })
    handler.batch_translator.handle_chunk_translated(0, chunk_text, context)
    f2_text, _ = mw.data_processor.get_current_string_text(0, 2)
    assert f2_text != three_line_trans  # Follower was NOT applied due to line overflow!

    # 5. On the Switch a 3DS text is measured with the Switch font: a line wider than the Switch window is refused
    p_sw = p_dir / "sw"
    p_sw.mkdir()
    mw_switch, rules_sw, _ = _setup_yokai_project(p_sw, game="ywnx")
    mgr_sw = mw_switch.saved_translations_manager
    wide = "Я Віспер, твій вірний дворецький-йокай, і я з тобою!"      # 52 letters x 24 px > 923 px
    mgr_sw.series_memory = {source_hash(SENTENCE_WHISPER): [dict(mgr.series_memory[source_hash(SENTENCE_WHISPER)][0],
                                                                 translation=wide)]}
    mgr_sw.configure_series_reuse(enabled=True, min_words=2, safe_ticked=False)
    _, sw_series = mgr_sw.acceptable_rows(0, 0, SENTENCE_WHISPER)
    assert "WIDTH" in rules_sw.get_text_fit_problems_for_string(0, 0, wide)
    assert sw_series[0]["safe"] is False and sw_series[0]["applicable"] is True, sw_series
    assert not AIBatchTranslator._series_row_passes_checks(mw_switch, SENTENCE_WHISPER, wide, 0, 0)

    # 6. A kind of text with nothing measured still never becomes a silent safe approval
    rules_sw._row = lambda b, s: ("data/res/text/unmeasured_text_ja.cfg.bin",
                                  SimpleNamespace(kind="TEXT_INFO", param=2, text=""), None)
    assert rules_sw.get_text_fit_problems_for_string(0, 0, TRANSLATION_3DS) == ["UNVERIFIED_LAYOUT"]
    mgr_sw.series_memory = mgr.series_memory
    _, unmeasured = mgr_sw.acceptable_rows(0, 0, SENTENCE_WHISPER)
    assert unmeasured[0]["safe"] is False
    assert "unverified" in unmeasured[0]["reason"].lower() or "не перевірена" in unmeasured[0]["reason"].lower()


def test_local_conflicting_translations_are_preserved(tmp_path):
    """A row that already has a local translation retains it during batch application and persistence/reload."""
    p_dir = tmp_path / "yw_switch"
    p_dir.mkdir()
    mw, _, handler = _setup_yokai_project(p_dir, game="ywnx")
    mgr = mw.saved_translations_manager

    local_text = "Індивідуальний локальний переклад"
    # Pre-translate Row 0 locally
    mw.data_processor.update_edited_data(0, 0, local_text, action_type="TRANSLATE")
    mgr.save_translation(0, 0, local_text)

    # Verify initial local translation is in data store
    assert mw.data_processor.is_string_translated(0, 0)
    t0_before, _ = mw.data_processor.get_current_string_text(0, 0)
    assert t0_before == local_text

    # Series memory has a conflicting candidate from 3DS
    mgr.series_memory = {
        source_hash(SENTENCE_WHISPER): [{
            "source": SENTENCE_WHISPER,
            "translation": TRANSLATION_3DS,
            "project": "Yo-kai Watch (3DS)",
            "speaker_en": "Whisper",
            "addressee": "",
        }]
    }

    # 1. Series acceptable_rows prefers local translation over series memory
    own_rows, _ = mgr.acceptable_rows(0, 0, SENTENCE_WHISPER)
    assert len(own_rows) == 1
    assert own_rows[0]["translation"] == local_text

    # 2. Batch application workflow with a conflicting incoming chunk:
    context = {
        "type": "translate_block_chunked",
        "block_idx": 0,
        "source_items": [{"id": 0, "text": SENTENCE_WHISPER}],
        "temp_id_map": {0: (0, 0)},
    }
    chunk_text = json.dumps({
        "translated_strings": [
            {"id": 0, "translation": "Конфліктний AI переклад"},
        ]
    })
    # Run through production batch application
    handler.batch_translator.handle_chunk_translated(0, chunk_text, context)

    # Production code checks is_string_translated and protects local translation from overwrite
    t0_after, _ = mw.data_processor.get_current_string_text(0, 0)
    assert t0_after == local_text

    # 3. Persistence / reload check
    reloaded_mgr = SavedTranslationsManager(mw)
    reloaded_mgr.source_positions = index_source_positions(mw.data_store.data)
    reloaded_mgr.context_for = handler.prompt_composer.saved_context
    reloaded_all = reloaded_mgr.load_all_saved_translations()
    key = reloaded_mgr._get_string_unique_key(0, 0)
    assert reloaded_all.get(key) == local_text
    reloaded_own, _ = reloaded_mgr.acceptable_rows(0, 0, SENTENCE_WHISPER)
    assert len(reloaded_own) == 1
    assert reloaded_own[0]["translation"] == local_text


def test_shared_glossary_uses_standard_series_interface():
    """Verify that series glossary lookup uses the standard core.glossary.series interface."""
    project = SimpleNamespace(metadata={METADATA_KEY: ["shared/series_glossary.json"]})
    paths = linked_series_paths(project)
    assert len(paths) == 1
    assert paths[0] == Path("shared/series_glossary.json")
