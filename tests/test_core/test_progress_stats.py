"""Progress page: counting, daily history and streak, the room's board, the page itself."""
import json

import pytest
import requests

from core import progress_stats as ps
from core.collab.server import RoomServer


def _summary():
    data = [["Hello there", "{tag}", "Bye now"], ["Yes", "No"]]
    edited_file = [["Привіт тобі", "{tag}", "Bye now"], []]
    edited = {(1, 0): "Так"}
    return ps.summarize(data, edited_file, edited, {"0": "Intro", "1": "Menu"}, "TP")


class TestCounting:
    def test_rows_and_source_words_follow_the_editor_rule(self):
        summary = _summary()
        # "{tag}" needs no translation; "Bye now" equals its source: not done.
        assert (summary["rows_total"], summary["rows_done"]) == (4, 2)
        assert (summary["words_total"], summary["words_done"]) == (6, 3)
        assert summary["blocks"] == [{"name": "Intro", "total": 2, "done": 1, "words": 4},
                                     {"name": "Menu", "total": 2, "done": 1, "words": 2}]

    def test_history_keeps_one_entry_a_day_and_gives_streak_and_pace(self, tmp_path):
        summary = dict(_summary())
        for day, done in (("2026-10-01", 10), ("2026-10-02", 30), ("2026-10-03", 30), ("2026-10-04", 50),
                          ("2026-10-05", 80)):
            ps.record_day(tmp_path, {**summary, "rows_done": done, "words_done": done}, today=day)
        history = ps.record_day(tmp_path, {**summary, "rows_done": 90, "words_done": 90}, today="2026-10-05")
        assert history["2026-10-05"]["rows_done"] == 90                       # the latest of the day wins
        assert json.loads((tmp_path / ps.HISTORY_NAME).read_text(encoding="utf-8")) == history
        assert ps.daily_gains(history) == [("2026-10-01", 0), ("2026-10-02", 20), ("2026-10-03", 0),
                                           ("2026-10-04", 20), ("2026-10-05", 40)]
        assert ps.streak(history, today="2026-10-05") == 2
        assert ps.streak(history, today="2026-10-06") == 2                    # today not started yet: counts from yesterday
        assert ps.streak(history, today="2026-10-08") == 0
        assert ps.eta_days({"rows_total": 190, "rows_done": 90}, history) == 4  # 100 left at about 26.7 a day

    def test_the_board_sorts_by_words_and_shows_today(self):
        stats = {"Olena": {"2026-10-09": {"rows": 5, "words": 40, "edits": 7}, "2026-10-10": {"rows": 1, "words": 3, "edits": 1}},
                 "Taras": {"2026-10-10": {"rows": 9, "words": 60, "edits": 9}}}
        board = ps.leaderboard(stats, today="2026-10-10")
        assert [(r["name"], r["words"], r["today_words"]) for r in board] == [("Taras", 60, 60), ("Olena", 43, 3)]


class TestPage:
    def test_the_page_shows_numbers_board_badges_and_blocks(self):
        summary = {**_summary(), "rows_done": 120, "rows_total": 400}
        board = [{"name": "Taras <b>", "words": 60, "rows": 9, "edits": 9, "today_words": 60, "today_rows": 9, "days": 1},
                 {"name": "Olena", "words": 43, "rows": 6, "edits": 8, "today_words": 3, "today_rows": 1, "days": 2}]
        page = ps.render_html(summary, {"2026-10-09": {"rows_done": 100}, "2026-10-10": {"rows_done": 120}}, board, 30)
        assert "120 / 400" in page and "100 rows translated" in page and "🥇" in page
        assert "Taras &lt;b&gt;" in page and "Taras <b>" not in page            # names are escaped
        assert "Olena is 17 words behind Taras &lt;b&gt;." in page
        assert "http-equiv='refresh' content='30'" in page and "<polyline" in page
        assert page.index("Intro") > page.index("Blocks with the most left")


class TestRoom:
    @pytest.fixture
    def room(self, tmp_path):
        server = RoomServer("pw", "fp", port=0, host="127.0.0.1", journal=tmp_path / "room.json").start()
        yield server
        server.stop()

    def test_first_translations_count_words_polish_counts_edits_and_seeds_count_nothing(self, room):
        base = f"http://127.0.0.1:{room.port}"
        token = requests.post(base + "/join", json={"name": "Olena", "password": "pw", "fingerprint": "fp"}).json()["token"]
        headers = {"X-Room-Token": token}

        def edit(**fields):
            requests.post(base + "/edits", headers=headers, json={"edits": [fields]}).raise_for_status()

        edit(key="a", text="Привіт", base_rev=0, words=2)
        edit(key="a", text="Вітаю", base_rev=1, words=2)                  # polishing: an edit, not a new row
        edit(key="b", text="Так", base_rev=0, words=1, seed=True)          # shared at join: nobody's credit
        (day,) = room.room.stats["Olena"].values()
        assert day == {"rows": 1, "words": 2, "edits": 2}

        assert requests.post(base + "/summary", headers=headers, json={"rows_total": "x"}).status_code == 400
        requests.post(base + "/summary", headers=headers, json={**_summary(), "history": {}}).raise_for_status()
        page = requests.get(base + "/stats")
        assert page.headers["Content-Type"].startswith("text/html")
        assert "Olena" in page.text and "2 / 4" in page.text and "Привіт" not in page.text   # counts, never text

        room.stop()
        saved = json.loads(room.room.journal.read_text(encoding="utf-8"))
        assert saved["stats"]["Olena"] == room.room.stats["Olena"]
