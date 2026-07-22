"""The editor and the Story Timeline must resolve the speaker identically."""
from core.speaker_resolution import resolve_speaker_for_string


class _Block:
    def __init__(self, name="zel_00", assignments=None):
        self.name = name
        self.metadata = {"character_assignments": assignments or {}}


class _Project:
    def __init__(self, blocks):
        self.blocks = blocks


class _PM:
    def __init__(self, project):
        self.project = project


class _Client:
    def __init__(self, speaker=None):
        self._speaker = speaker

    def get_cached_context(self, bmg_id, _default=None):
        return {"speaker": self._speaker} if self._speaker else None


class _Composer:
    """Records the text it was asked to match, so we can assert it got the original."""

    def __init__(self, client=None, speaker="TALO", line="2099"):
        self._client = client
        self._speaker = speaker
        self._line = line
        self.seen_text = None

    def _get_mempalace_client(self):
        return self._client

    def _find_speaker_in_script(self, b, s, text):
        self.seen_text = text
        return (self._speaker, self._line)


class _DS:
    def __init__(self, original="Wait..."):
        self.data = [[original]]
        self.block_names = {}


class _MW:
    def __init__(self, assignments=None, client=None):
        self.data_store = _DS()
        self.project_manager = _PM(_Project([_Block(assignments=assignments)]))
        self.block_to_project_file_map = {}
        self.translation_handler = None


def test_assignment_wins():
    mw = _MW(assignments={"0": "MAYOR"})
    res = resolve_speaker_for_string(mw, 0, 0, composer=_Composer(_Client("FROM_DB")))
    assert res.name == "MAYOR"
    assert res.source == "assignment"


def test_mempalace_beats_script():
    mw = _MW()
    res = resolve_speaker_for_string(mw, 0, 0, composer=_Composer(_Client("FROM_DB")))
    assert res.name == "FROM_DB"
    assert res.source == "mempalace"


def test_script_is_last_resort_and_gets_original_text():
    mw = _MW()
    composer = _Composer(_Client(None))
    res = resolve_speaker_for_string(mw, 0, 0, composer=composer)
    assert res.name == "TALO"
    assert res.source == "script"
    assert res.script_line == 2099
    # regression: the script is in the source language, so the ORIGINAL text must
    # be matched against it — never the edited/translated text.
    assert composer.seen_text == "Wait..."


def test_unknown_speaker_is_none():
    mw = _MW()
    res = resolve_speaker_for_string(mw, 0, 0, composer=_Composer(_Client(None), speaker="NONE"))
    assert res.name is None
    assert not res


def test_invalid_indices_short_circuit():
    mw = _MW()
    assert resolve_speaker_for_string(mw, -1, 0, composer=_Composer()).name is None
    assert resolve_speaker_for_string(mw, -2, 0, composer=_Composer()).name is None
