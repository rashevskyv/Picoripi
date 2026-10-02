import pytest

from core.translation.chunk_result import verify_chunk_ids

CHUNK = [{"id": 40, "text": "a"}, {"id": 41, "text": "b"}, {"id": 42, "text": "c"}]


@pytest.mark.parametrize("ids", [
    [40, 41, 42],          # echoed
    ["40", "41", "42"],    # echoed as strings
    [None, None, None],    # not echoed at all
    [0, 1, 2],             # the model's own numbering
    [1, 2, 3],
])
def test_accepts_replies_that_can_only_mean_position(ids):
    verify_chunk_ids([{"id": i, "translation": "x"} for i in ids], CHUNK)


@pytest.mark.parametrize("ids", [
    [42, 41, 40],   # reordered
    [40, 42, 41],
    [40, 41, 99],   # another string
    [40, 41],       # one missing
])
def test_rejects_replies_that_would_land_in_the_wrong_rows(ids):
    with pytest.raises(ValueError):
        verify_chunk_ids([{"id": i, "translation": "x"} for i in ids], CHUNK)
