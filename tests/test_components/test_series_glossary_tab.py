"""The linked series glossary as a tab of the Glossary window, copy/promote, and in AI prompts."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt

from components.glossary_dialog import GlossaryDialog
from components.glossary.widgets import _CONFLICT_BRUSH
from core.glossary.series import link_series
from core.glossary_manager import GlossaryManager
from core.project_models import Project
from handlers.translation.ai_prompt_composer import AIPromptComposer
from handlers.translation.glossary_handler import GlossaryHandler


class _ProjectManager:
    def __init__(self, project):
        self.project = project
        self.saved = 0

    def save(self):
        self.saved += 1
        return True


def _write(path: Path, rows) -> Path:
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return path


def _handler(tmp_path, series_rows, project_rows):
    project = Project(name="TP")
    series_path = _write(tmp_path / "zelda.json", series_rows)
    link_series(project, series_path)
    mw = SimpleNamespace(
        project_manager=_ProjectManager(project),
        data_store=SimpleNamespace(data=[["Talk to Beedle"]]),
        statusBar=None,
    )
    main_handler = SimpleNamespace(mw=mw, data_processor=None, ui_updater=None, _cached_glossary="")
    handler = GlossaryHandler(main_handler)
    glossary_path = _write(tmp_path / "glossary.json", project_rows)
    handler.glossary_manager.load_from_text(
        plugin_name=None, glossary_path=glossary_path, raw_text=glossary_path.read_text(encoding="utf-8")
    )
    handler._update_glossary_highlighting = lambda: None
    handler.dialog = GlossaryDialog(
        parent=None,
        entries=handler.glossary_manager.get_entries(),
        occurrence_map={},
        jump_callback=lambda occ: None,
        transfer_callback=handler._promote_to_series,
        transfer_label="Promote",
        series_menu_callback=handler._show_series_glossary_menu,
    )
    return handler, series_path, glossary_path


def _terms(page: GlossaryDialog):
    table = page._active_table()
    return [table.item(row, 0).text() for row in range(table.rowCount())]


def test_linked_series_glossary_appears_as_a_tab_with_its_terms_and_conflicts(qtbot, tmp_path):
    handler, _, _ = _handler(
        tmp_path,
        series_rows=[
            {"original": "Beedle", "translation": "Бідл", "notes": "merchant"},
            {"original": "Cucco", "translation": "Кокко", "notes": ""},
        ],
        project_rows=[{"original": "Cucco", "translation": "Кукко", "notes": ""}],
    )
    qtbot.addWidget(handler.dialog)

    handler._attach_series_page()

    tabs = handler.dialog._series_tabs
    assert tabs is not None and tabs.count() == 2
    assert tabs.tabText(1) == "Series: zelda"
    page = handler.series_page
    assert tabs.widget(1) is page
    assert _terms(page) == ["Beedle", "Cucco"]
    assert handler.dialog._transfer_button.isVisibleTo(handler.dialog)

    # The conflicting term is marked in both tabs, each naming the other translation.
    cucco_row = _terms(page).index("Cucco")
    series_item = page._active_table().item(cucco_row, 0)
    assert series_item.background() == _CONFLICT_BRUSH
    assert "Кукко" in series_item.toolTip()
    project_item = handler.dialog._active_table().item(0, 0)
    assert project_item.background() == _CONFLICT_BRUSH
    assert "Кокко" in project_item.toolTip()

    # Search works inside the series tab on its own.
    page._apply_filter("merchant")
    assert _terms(page) == ["Beedle"]


def test_copy_series_terms_into_project_and_promote_project_terms(qtbot, tmp_path):
    handler, series_path, glossary_path = _handler(
        tmp_path,
        series_rows=[{"original": "Beedle", "translation": "Бідл", "notes": "merchant"}],
        project_rows=[{"original": "Midna", "translation": "Мідна", "notes": "imp"}],
    )
    qtbot.addWidget(handler.dialog)
    handler._attach_series_page()
    page = handler.series_page

    page._active_table().selectRow(0)
    qtbot.mouseClick(page._transfer_button, Qt.MouseButton.LeftButton)
    assert handler.glossary_manager.get_entry("Beedle").translation == "Бідл"
    assert "Бідл" in glossary_path.read_text(encoding="utf-8")
    assert "Beedle" in _terms(handler.dialog)

    midna = handler.glossary_manager.get_entry("Midna")
    handler._promote_to_series([midna])
    assert handler.series_glossary_manager.get_entry("Midna").translation == "Мідна"
    assert "Мідна" in series_path.read_text(encoding="utf-8")
    assert "Midna" in _terms(page)


def test_unlinking_removes_the_tab_and_saves_the_project(qtbot, tmp_path):
    handler, _, _ = _handler(
        tmp_path, series_rows=[{"original": "Beedle", "translation": "Бідл", "notes": ""}], project_rows=[]
    )
    qtbot.addWidget(handler.dialog)
    handler._attach_series_page()

    handler.set_series_link(None)

    assert handler.series_page is None
    assert handler.dialog._series_tabs.count() == 1
    assert handler.mw.project_manager.saved == 1
    assert handler.series_glossary_manager.get_entries() == []


def test_prompts_put_series_rows_after_the_project_glossary_and_only_for_missing_terms(tmp_path):
    project = GlossaryManager()
    project.load_from_text(plugin_name=None, glossary_path=None, raw_text=json.dumps(
        [{"original": "Link", "translation": "Лінк", "notes": ""}]
    ))
    series = GlossaryManager()
    series.load_from_text(plugin_name=None, glossary_path=None, raw_text=json.dumps([
        {"original": "Link", "translation": "ЛІНК-СЕРІЯ", "notes": ""},
        {"original": "Beedle", "translation": "Бідл", "notes": ""},
    ], ensure_ascii=False))
    mw = MagicMock()
    mw.data_store = mw
    mw.data_store.data = [["Link meets Beedle"]]
    composer = AIPromptComposer(SimpleNamespace(
        mw=mw, data_processor=None, ui_updater=None, _glossary_manager=project, _series_glossary_manager=series
    ))
    composer._get_mempalace_client = MagicMock(return_value=None)
    composer._find_speaker_in_script = MagicMock(return_value=None)
    composer._fetch_story_context = MagicMock(return_value=None)
    composer._get_structured_story_context = MagicMock(return_value={})

    _, single_user = composer.compose_messages(
        "Translate into {target_lang}.", "Link meets Beedle", block_idx=0, string_idx=0,
        expected_lines=1, mode_description="translation",
    )
    _, batch_user, _ = composer.compose_batch_request(
        "Translate into {target_lang}.", [{"id": 0, "text": "Link meets Beedle"}],
        [{"id": 0, "text": "Link meets Beedle"}], block_idx=0, mode_description="translation",
    )

    for user in (single_user, batch_user):
        assert "| Link | Лінк |" in user
        assert "ЛІНК-СЕРІЯ" not in user
        assert "| Beedle | Бідл |" in user
    assert single_user.index("GLOSSARY (use with absolute priority)") < single_user.index("SERIES GLOSSARY (lower priority")
    assert '"series_glossary": "Lower priority than the project glossary' in batch_user
