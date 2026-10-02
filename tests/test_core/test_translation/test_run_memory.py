"""One source, one translation per run: duplicate folding and the run memory (WP4 4.1)."""
import threading

from core.translation.run_memory import RunMemory, fold_duplicates, normalize_source


def _items(*texts):
    return [{"id": index, "text": text} for index, text in enumerate(texts)]


class TestNormalize:
    def test_tags_case_and_spacing_do_not_distinguish_sources(self):
        assert normalize_source("  Yes ,  [Color:Red]SIR[/Color] ") == normalize_source("yes , sir")

    def test_different_words_stay_different(self):
        assert normalize_source("Yes") != normalize_source("No")

    def test_nothing_is_nothing(self):
        assert normalize_source(None) == "" and normalize_source("[Wait:10]") == ""


class TestFolding:
    def test_five_identical_strings_send_one(self):
        kept, followers = fold_duplicates(_items("Yes", "Yes", "No", "Yes", "Yes", "Yes"))

        assert [item["id"] for item in kept] == [0, 2]
        assert followers == {0: [1, 3, 4, 5]}

    def test_only_exactly_equal_text_folds(self):
        """Tags, case and trailing spaces are part of the string: a different one gets its own request."""
        kept, followers = fold_duplicates(_items("Yes", "yes", "Yes ", "[Color:Red]Yes[/Color]"))

        assert len(kept) == 4 and followers == {}

    def test_the_same_text_under_different_conditions_does_not_fold(self):
        speakers = {0: "Ilia", 1: "Ilia", 2: "Rusl", 3: "Rusl"}

        kept, followers = fold_duplicates(_items(*["I'm ready"] * 4), lambda item: speakers[item["id"]])

        assert [item["id"] for item in kept] == [0, 2]         # one per speaker: her wording and his may differ
        assert followers == {0: [1], 2: [3]}

    def test_the_conditions_are_asked_only_for_texts_that_repeat(self):
        asked = []

        fold_duplicates(_items("Hello", "Bye", "Hello", "Once"), lambda item: asked.append(item["id"]))

        assert asked == [0, 2]

    def test_empty_strings_and_items_without_an_id_are_left_alone(self):
        items = [{"id": 0, "text": ""}, {"id": 1, "text": ""}, {"text": "A"}, {"text": "A"}, "A", "A"]

        kept, followers = fold_duplicates(items)

        assert kept == items and followers == {}

    def test_folding_twice_changes_nothing(self):
        """A resumed run folds an already folded list: the chunk plan must stay the same."""
        kept, _ = fold_duplicates(_items("Yes", "Yes", "No"))

        assert fold_duplicates(kept) == (kept, {})


class TestRunMemory:
    def test_a_source_that_differs_only_in_tags_or_case_finds_the_earlier_translation(self):
        memory = RunMemory()
        memory.remember("Thank you!", "Дякую!")

        assert memory.similar(["[Color:Red]thank you![/Color]"]) == [{"text": "Thank you!", "translation": "Дякую!"}]
        assert memory.similar(["Thanks"]) == []

    def test_empty_sources_and_empty_translations_are_not_remembered(self):
        memory = RunMemory()
        memory.remember("", "щось")
        memory.remember("[Wait:10]", "щось")
        memory.remember("Yes", "   ")

        assert len(memory) == 0

    def test_the_same_pair_is_stored_once_and_variants_are_kept(self):
        memory = RunMemory()
        for translation in ("Так", "Так", "Авжеж"):
            memory.remember("Yes", translation)

        assert [row["translation"] for row in memory.similar(["Yes"])] == ["Так", "Авжеж"]

    def test_a_request_gets_at_most_the_limit(self):
        memory = RunMemory()
        for index in range(30):
            memory.remember(f"Line {index}", f"Рядок {index}")

        assert len(memory.similar([f"Line {index}" for index in range(30)], limit=10)) == 10

    def test_clear_forgets(self):
        memory = RunMemory()
        memory.remember("Yes", "Так")
        memory.clear()

        assert memory.similar(["Yes"]) == []

    def test_writers_and_readers_on_different_threads(self):
        memory = RunMemory()

        def write(base):
            for index in range(200):
                memory.remember(f"Line {base}-{index}", f"Рядок {base}-{index}")

        writers = [threading.Thread(target=write, args=(base,)) for base in range(4)]
        for writer in writers:
            writer.start()
        for _ in range(200):
            memory.similar(["Line 0-0", "Line 3-199"])
        for writer in writers:
            writer.join()

        assert len(memory) == 800
