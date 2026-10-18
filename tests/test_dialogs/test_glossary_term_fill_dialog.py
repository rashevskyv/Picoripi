"""The Fill Terms from the Glossary dialog (D45, item 1): the plan is shown, and Fill writes the untranslated lines."""
from types import SimpleNamespace

from core.data_state_processor import DataStateProcessor
from core.translation.series_memory import source_hash
from dialogs.glossary_term_fill_dialog import GlossaryTermFillDialog
from handlers import glossary_term_fill
from test_core.test_series_memory import window  # noqa: F401  (window fixture)


def test_the_dialog_lists_the_plan_and_fill_writes_the_untranslated_line(window, monkeypatch, qapp):  # noqa: F811
    window.data_processor = DataStateProcessor(window)
    window.saved_translations_manager.source_positions = {source_hash("Yes"): [(0, 3)]}
    series = SimpleNamespace(get_entries=lambda: [SimpleNamespace(original="Yes", translation="Так")])
    monkeypatch.setattr(glossary_term_fill, "series_managers_of", lambda mw: [series])

    dialog = GlossaryTermFillDialog(window)

    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 5).text() == "Will be filled"
    assert dialog.fill_btn.isEnabled()
    dialog._apply()
    assert window.data_processor.get_current_string_text(0, 3)[0] == "Так"
    assert dialog.table.item(0, 5).text() == "Filled"
    assert not dialog.fill_btn.isEnabled()
    dialog.close()
