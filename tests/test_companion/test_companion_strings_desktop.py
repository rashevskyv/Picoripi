"""Translation rows on the desktop: sorting phone edits, the snapshot, and the sync flow through the data processor."""
import pytest

from core.companion_strings import RowsSnapshot, sort_phone_edits


def _snapshot(pc_texts, edited=None):
    data = [["Hello", "Bye", "Yes"]]
    return RowsSnapshot(data, [list(pc_texts)], dict(edited or {}), ["a.bmg::::"], {"0": "a.bmg"})


def _pulled(string, phone, base, key=None):
    return {"key": key or f"a.bmg::::{string}", "block": 0, "string": string, "original": "", "translation": phone,
            "base": base}


def test_sorting_takes_clean_edits_and_flags_both_sided_changes():
    snap = _snapshot(["Hello", "Бувай", "Так"], edited={(0, 2): "Еге"})
    out = sort_phone_edits([
        _pulled(0, "Привіт", "Hello"),       # PC still at base: take
        _pulled(1, "Бувай", "Bye"),          # PC already has the phone text
        _pulled(2, "Атож", "Так"),           # PC changed it (unsaved edit) too: conflict
        _pulled(1, "x", "y", key="other::::1"),   # another project's text
        {"key": "broken"},
    ], snap)
    assert out.take == [(0, 0, "Привіт")]
    assert [(c.key, c.pc, c.phone) for c in out.conflicts] == [("a.bmg::::2", "Еге", "Атож")]
    assert out.resolved == {"a.bmg::::0": "Привіт", "a.bmg::::1": "Бувай"}
    assert out.unknown == 2


def test_the_snapshot_reads_texts_like_the_data_processor():
    snap = RowsSnapshot([["A", "B", "C"]], [["a", None]], {(0, 0): "edited"}, ["f::k::"], {})
    assert [r["translation"] for r in snap.rows()] == ["edited", "B", "C"]
    assert snap.rows()[2]["key"] == "f::k::2"
    assert snap.current(0, 9) is None and snap.current(3, 0) is None


class _Store:
    def __init__(self):
        self.data = [["Hello", "Bye", "Yes"]]
        self.edited_file_data = [["Hello", "Бувай", "Так"]]
        self.edited_data = {(0, 2): "Еге"}
        self.block_names = {"0": "a.bmg"}
        self.physical_block_idx = 0


class _Processor:
    def __init__(self, store):
        self.store, self.calls = store, []

    def update_edited_data(self, block, string, text, action_type="TEXT_EDIT", skip_ui_refresh=False):
        self.calls.append((block, string, text, action_type))
        self.store.edited_data[(block, string)] = text


class _Window:
    def __init__(self):
        self.data_store = _Store()
        self.data_processor = _Processor(self.data_store)
        self.saved_translations_manager = type("M", (), {"block_key_prefixes": lambda self, n: ["a.bmg::::"] * n})()
        self.refreshed = []
        self.ui_updater = type("U", (), {
            "update_block_item_text_with_problem_count": lambda u, b: self.refreshed.append(b),
            "update_text_views": lambda u: self.refreshed.append("views")})()


@pytest.mark.parametrize("choose_phone", [True, False])
def test_the_desktop_flow_applies_through_the_data_processor_and_resolves_conflicts(monkeypatch, choose_phone):
    from components.companion import strings_sync

    mw = _Window()
    pushed, shown = {}, []
    monkeypatch.setattr(strings_sync, "run_companion_call",
                        lambda parent, call, on_result, label=None: on_result(call(lambda: False)))
    monkeypatch.setattr(strings_sync, "pull_phone_edits", lambda client, project, cancelled: (True, "", [
        _pulled(0, "Привіт", "Hello"), _pulled(2, "Атож", "Так")]))

    def push(client, project, snapshot, resolved, cancelled):
        pushed.update(rows=snapshot.rows(), resolved=dict(resolved))
        return True, "", 0
    monkeypatch.setattr(strings_sync, "push_rows", push)

    class Dialog:
        def __init__(self, conflicts, parent):
            self.conflicts = conflicts

        def exec(self):
            return strings_sync.QDialog.DialogCode.Accepted

        def phone_keys(self):
            return {c.key for c in self.conflicts} if choose_phone else set()
    monkeypatch.setattr(strings_sync, "StringConflictDialog", Dialog)
    monkeypatch.setattr(strings_sync.QMessageBox, "information", lambda *a: shown.append(a[2]))

    strings_sync._on_pulled(mw, object(), "TP", (True, "", strings_sync.pull_phone_edits(None, "TP", None)[2]))

    expected = [(0, 0, "Привіт", "COMPANION_REMOTE")] + ([(0, 2, "Атож", "COMPANION_REMOTE")] if choose_phone else [])
    assert mw.data_processor.calls == expected
    assert mw.refreshed == [0, "views"]
    assert pushed["resolved"] == {"a.bmg::::0": "Привіт", "a.bmg::::2": "Атож"}
    assert [r["translation"] for r in pushed["rows"]] == ["Привіт", "Бувай", "Атож" if choose_phone else "Еге"]
    assert "Phone edits taken into the project: " + str(len(expected)) in shown[0]


def test_cancelling_the_conflict_window_takes_and_sends_nothing(monkeypatch):
    from components.companion import strings_sync

    mw = _Window()
    calls = []
    monkeypatch.setattr(strings_sync, "run_companion_call", lambda *a, **k: calls.append(a))

    class Dialog:
        def __init__(self, conflicts, parent):
            pass

        def exec(self):
            return strings_sync.QDialog.DialogCode.Rejected
    monkeypatch.setattr(strings_sync, "StringConflictDialog", Dialog)

    strings_sync._on_pulled(mw, object(), "TP", (True, "", [_pulled(0, "Привіт", "Hello"), _pulled(2, "Атож", "Так")]))
    assert mw.data_processor.calls == [] and calls == []
