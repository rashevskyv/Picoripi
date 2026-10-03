"""Shared helpers for the WP2/WP4 review-queue tests.

Two harnesses:

* ``Workbench`` -- a real MainWindow with a plain_text project on disk, its AI provider pointed at
  ``FakeAIServer`` (stdlib, 127.0.0.1). For the end-to-end checks: retry, prompt editor, fixed strings,
  restore, run memory, duplicate folding, resume.
* ``fixture_composer`` -- the real ``AIPromptComposer`` over an explicit fake window. The same function runs
  under the pre-audit code (``tests/fixtures/review_queue/wp2_4/make_golden.py``), so the request the
  baseline composed and the request the current code composes come from one input.

Only names that exist in both code bases are imported here, and only inside functions.
"""
from __future__ import annotations

import http.server
import json
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional


# ====================================================================== fake AI server

def completion(text: str) -> dict:
    """An OpenAI chat-completions reply carrying ``text``."""
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


def batch_payload(body: dict) -> Optional[dict]:
    """The JSON payload of a block-translation request, or None for another kind of request."""
    messages = body.get("messages") or []
    user = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
    _, sep, data = user.partition("JSON DATA TO PROCESS:")
    if not sep:
        return None
    start = data.index("{")
    payload, _ = json.JSONDecoder().raw_decode(data[start:])
    return payload


def system_of(body: dict) -> str:
    return next((m.get("content", "") for m in body.get("messages") or [] if m.get("role") == "system"), "")


def user_of(body: dict) -> str:
    return next((m.get("content", "") for m in body.get("messages") or [] if m.get("role") == "user"), "")


def ua(text: str) -> str:
    """The fake model's translation: every line prefixed, the line structure kept."""
    return "\n".join(("UA " + line) if line.strip() else line for line in text.split("\n"))


class FakeAIServer:
    """An OpenAI-compatible (and Ollama / native Gemini shaped) chat server on 127.0.0.1, port 0.

    ``requests`` keeps ``(path, parsed body)`` of every POST. ``script`` is a list of callables tried
    first, one per request (``body -> reply text`` or None to fall through); after it runs out the default
    reply translates every string with ``ua()``.
    """

    def __init__(self):
        self.requests: List[tuple] = []
        self.script: List[Callable] = []
        self.translate = ua
        self.lock = threading.Lock()
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                body = json.loads(raw or b"{}")
                with server.lock:
                    server.requests.append((self.path, body))
                    step = server.script.pop(0) if server.script else None
                text = step(body) if step else None
                if text is None:
                    text = server.default_reply(body)
                if "/api/chat" in self.path:  # Ollama: newline-delimited JSON
                    data = (json.dumps({"message": {"content": text}, "done": True}) + "\n").encode("utf-8")
                elif ":generateContent" in self.path:  # native Gemini
                    data = json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}}]}).encode("utf-8")
                else:
                    data = json.dumps(completion(text)).encode("utf-8")
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    pass

            def do_GET(self):
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def default_reply(self, body: dict) -> str:
        if "contents" in body:  # native Gemini
            body = {"messages": [{"role": "user", "content": body["contents"][0]["parts"][0]["text"]}]}
        payload = batch_payload(body)
        if payload is not None:
            items = payload["strings_to_translate"]
            return json.dumps({"translated_strings": [
                {"id": item["id"], "translation": self.translate(item["text"])} for item in items
            ]}, ensure_ascii=False)
        user = user_of(body)
        source = user.rsplit("Input text (Original source):\n\n", 1)[-1]
        return json.dumps({"translation": self.translate(source)}, ensure_ascii=False)

    def bodies(self) -> List[dict]:
        with self.lock:
            return [body for _, body in self.requests]

    def batch_payloads(self) -> List[dict]:
        return [p for p in (batch_payload(b) for b in self.bodies()) if p is not None]


# ====================================================================== real window

class TestRules:
    """Plugin hooks a game plugin may implement, mixed into the plain_text rules of the open project.

    Every hook reads a dict keyed by ``(block, string)`` so a test states what the "plugin knows".
    """

    speakers: Dict = {}
    addressees: Dict = {}
    flow_groups: Dict = {}
    contexts: Dict = {}
    lines_per_window: Dict = {}

    def get_speaker_for_string(self, block_idx, string_idx):
        return self.speakers.get((block_idx, string_idx))

    def is_placeholder_speaker(self, name):
        return False

    def get_string_layout(self, block_idx, string_idx):
        lines = self.lines_per_window.get((block_idx, string_idx))
        return {"lines_per_page": lines} if lines else {}

    def get_addressee_for_string(self, block_idx, string_idx, speaker=None):
        return self.addressees.get((block_idx, string_idx), "")

    def get_ai_flow_group_for_string(self, block_idx, string_idx):
        return self.flow_groups.get((block_idx, string_idx))

    def get_translation_context_for_string(self, block_idx, string_idx):
        return dict(self.contexts.get((block_idx, string_idx), {}))


def install_rules(mw, **hooks) -> object:
    """Give the open project's plain_text rules the hooks of ``TestRules`` with the given data."""
    base = type(mw.current_game_rules)
    cls = type("RQRules", (TestRules, base), {k: dict(v) for k, v in hooks.items()})
    mw.current_game_rules.__class__ = cls
    return mw.current_game_rules


def make_project(root: Path, blocks: Dict[str, List[str]], glossary: Optional[List[dict]] = None) -> Path:
    """A plain_text project: one source .txt per block (one string per line, ``\\n`` inside a string)."""
    from core.project_manager import ProjectManager

    source, translation = root / "source", root / "translation"
    source.mkdir(parents=True, exist_ok=True)
    translation.mkdir(parents=True, exist_ok=True)
    for name, lines in blocks.items():
        text = "\n".join(line.replace("\n", "\\n") for line in lines) + "\n"
        (source / f"{name}.txt").write_text(text, encoding="utf-8")
        (translation / f"{name}.txt").write_text(text, encoding="utf-8")
    manager = ProjectManager()
    assert manager.create_new_project(
        project_dir=root / "project", name="RQ", plugin_name="plain_text",
        source_path=str(source), translation_path=str(translation), is_directory_mode=True,
    )
    # A MemPalace database of its own (empty): without one the client searches the working directory and
    # its neighbours, and the repository keeps the owner's database there.
    from core.mempalace_client import MemePalaceClient

    MemePalaceClient(project_dir=str(root / "project"))
    if glossary is not None:
        (root / "project" / "glossary.json").write_text(json.dumps(glossary, ensure_ascii=False), encoding="utf-8")
    return root / "project" / "project.uiproj"


def open_window(qtbot, monkeypatch, project_file: Path, server: FakeAIServer, *, profile: str = "openai",
                workers: int = 1, **config):
    """A real MainWindow with ``project_file`` open and its AI provider pointed at ``server``."""
    import handlers.project_action.lifecycle_mixin as lifecycle
    from core.translation.script_speaker_finder import ScriptSpeakerFinder
    from main import MainWindow

    # The script lookup searches the working directory and a fixed path on the owner's disk for a game
    # script; what it finds there must not decide a test's speakers.
    monkeypatch.setattr(ScriptSpeakerFinder, "find_script_path", lambda self: None)
    mw = MainWindow()
    mw.is_testing = True
    qtbot.addWidget(mw, before_close_func=settle)
    monkeypatch.setattr(lifecycle.QFileDialog, "getOpenFileName",
                        staticmethod(lambda *a, **k: (str(project_file), "")))
    mw.project_action_handler.open_project_action()
    qtbot.waitUntil(lambda: len(mw.data_store.data) > 0 and not mw.is_loading_data, timeout=15000)
    configure_provider(mw, server, profile=profile, workers=workers, **config)
    mw.prompt_editor_enabled = False
    mw.log_ai_traffic = True
    return mw


def settle(mw) -> None:
    """Stop the preview pre-caching before the window is destroyed.

    Its time slices are re-armed with a static ``QTimer.singleShot`` that outlives the window; one still
    queued when the window goes raises "wrapped C/C++ object of type QTimer has been deleted"
    (ui/updaters/preview_cache.py). Cancel it and let the queued slice run while the window is alive.
    """
    from PyQt6.QtCore import QCoreApplication

    mw.ui_updater.preview_updater.cancel_idle_caching()
    for _ in range(3):
        QCoreApplication.processEvents()


def configure_provider(mw, server: FakeAIServer, *, provider: str = "openai", profile: str = "openai",
                       workers: int = 1, **config) -> None:
    from core.translation.config import build_default_translation_config

    cfg = build_default_translation_config()
    cfg["provider"] = provider
    cfg["workers"] = workers
    cfg["providers"]["openai"].update({"endpoint": server.url, "model": "fake", "profile": profile})
    cfg["providers"]["ollama_chat"].update({"base_url": server.url.rsplit("/v1", 1)[0], "model": "fake"})
    cfg["providers"]["gemini"].update({
        # A base URL that names the Google host takes the native path; the host is still the fake.
        "base_url": server.url.rsplit("/v1", 1)[0] + "/generativelanguage.googleapis.com/v1beta/models",
        "model": "fake", "api_key": "k",
    })
    cfg.update(config)
    mw.translation_config = cfg


def wait_idle(qtbot, mw, timeout: int = 15000) -> None:
    """Until the AI run, and any retry it scheduled, is over."""
    lifecycle = mw.translation_handler.ai_lifecycle_manager
    qtbot.waitUntil(
        lambda: not mw.translation_handler.is_ai_running and lifecycle._retry_context is None
        and not lifecycle._is_waiting_retry_delay,
        timeout=timeout,
    )


def row(mw, block: int, string: int) -> str:
    return mw.data_processor.get_current_string_text(block, string)[0]


class ModalAnswerer:
    """Answers the modal dialogs a run opens, from inside their own event loop (a polling timer).

    ``answer(widget) -> bool`` returns True once it has handled ``widget``.
    """

    def __init__(self, answer: Callable):
        from PyQt6.QtCore import QTimer

        self.answer = answer
        self.seen: List[object] = []
        self.timer = QTimer()
        self.timer.setInterval(20)
        self.timer.timeout.connect(self._poll)
        self.timer.start()

    def _poll(self):
        from PyQt6.QtWidgets import QApplication

        widget = QApplication.activeModalWidget()
        if widget is not None and widget not in self.seen and self.answer(widget):
            self.seen.append(widget)

    def stop(self):
        self.timer.stop()


# ====================================================================== composer over a fake window

# The fixed input both code bases compose from. Block 0 is a dialogue scene; block 1 has its own lines.
FIXTURE_BLOCKS = [
    [
        "Hello, Link!",                                   # 0  Midna -> Link, glossary Link
        "Welcome to Ordon Village.\nStay a while.",       # 1  two lines, glossary Ordon Village
        "Yes",                                            # 2  short
        "Did you see the [C1]Master Sword[/C1]?",         # 3  tag alias legend, glossary Master Sword
        "{0} rupees, please.",                            # 4  anchored tag
        "Line one\n\nLine three\n",                       # 5  blank line, trailing newline
        "A very long line that goes on and on to exceed the width of the dialog window easily",  # 6 own width
        "Page one\nPage one b\nPage two\nPage two b",     # 7  two windows of two lines
        "Thank you, Rusl.",                               # 8  Colin -> Rusl
        "Go to Faron Woods now.",                         # 9  role instruction
        "Ilia is waiting at the spring.",                 # 10
        "Goodbye.",                                       # 11
        "Hylia watches over Hyrule.",                     # 12 second chunk: glossary Hylia, Hyrule
        "Epona is fast.",                                 # 13
    ],
    ["Talo and Malo play.", "Uli smiles."],
]

FIXTURE_GLOSSARY = [
    {"original": "Link", "translation": "Лінк", "notes": "Hero; male; addressed informally"},
    {"original": "Midna", "translation": "Мідна", "notes": "Twili; female; sharp"},
    {"original": "Ordon Village", "translation": "Село Ордон", "notes": "Place"},
    {"original": "Master Sword", "translation": "Меч Майстра", "notes": "Item"},
    {"original": "Rusl", "translation": "Русл", "notes": "Male; formal"},
    {"original": "Colin", "translation": "Колін", "notes": "Boy"},
    {"original": "Faron Woods", "translation": "Ліс Фарон", "notes": "Place"},
    {"original": "Ilia", "translation": "Ілія", "notes": "Female"},
    {"original": "Hylia", "translation": "Гайлія", "notes": "Goddess"},
    {"original": "Hyrule", "translation": "Гайрул", "notes": "Kingdom"},
    {"original": "Epona", "translation": "Епона", "notes": "Horse; female"},
    {"original": "Talo", "translation": "Тало", "notes": "Boy"},
    {"original": "Malo", "translation": "Мало", "notes": "Boy"},
    {"original": "Uli", "translation": "Улі", "notes": "Female"},
]

FIXTURE_SPEAKERS = {(0, 0): "Midna", (0, 1): "Midna", (0, 3): "Link", (0, 8): "Colin", (0, 9): "Rusl"}
FIXTURE_ADDRESSEES = {(0, 0): "Link", (0, 8): "Rusl"}
FIXTURE_CONTEXTS = {
    (0, 9): {"window_type": "dialogue", "content_role": "order",
             "role_instruction": "Keep orders short and in the imperative."},
}
FIXTURE_LINES_PER_WINDOW = 2
FIXTURE_TAGS = {"[C1]": "[Color:Red]", "[/C1]": "[/Color]"}
FIXTURE_REFERENCES = {
    "German": {(0, 1): "Willkommen im Dorf Ordon.\nBleib eine Weile.", (0, 9): "Geh jetzt in den Wald von Phirone."},
    "French": {(0, 1): "Bienvenue au village d'Ordon.\nReste un peu.", (0, 9): "Va dans la forêt de Firone."},
}
FIXTURE_SYSTEM_PROMPT = (
    "You are a professional game translator into {target_lang}. Keep tags. "
    "Transcribe proper names carefully."
)


class FakeStoryClient:
    """What MemPalace knows about block 0: one event with Midna, Link and Colin, their profiles."""

    class _Event:
        document_id = 1
        participants = ("Midna", "Link", "Colin")
        event_title = "Twilight at the spring"
        summary = "Midna talks Link into entering the twilight."
        location = "Ordon Spring"
        interactions = ("Midna -> Link: urges him on",)
        previous_event = "Goats herded"
        next_event = "Into the twilight"

    class _Profile:
        def __init__(self, name, role, address, style):
            self.speaker_name = name
            self.role = role
            self.address_and_grammar = address
            self.speech_style = style
            self.personality = f"{name} personality: " + "proud " * 50
            self.vocabulary = f"{name} vocabulary"
            self.relationships = f"{name} relationships"
            self.translation_advice = f"{name} advice"
            self.evidence_notes = f"{name} evidence"

    PROFILES = {
        "Midna": _Profile("Midna", "Twili princess in exile", "Female; uses ти with Link", "Mocking, short"),
        "Link": _Profile("Link", "Silent hero from Ordon", "Male; addressed with ти by friends", "Silent"),
        "Colin": _Profile("Colin", "Rusl's son", "Male child; uses ви with adults " + "word " * 60, "Shy"),
    }

    def get_story_event_for_game_string(self, block, string):
        return self._Event() if str(block) == "0" else None

    def get_story_string_contexts(self, block, string):
        return []

    def get_story_speakers_for_game_string(self, block, string):
        speaker = FIXTURE_SPEAKERS.get((int(block), string))
        return [speaker] if speaker in self.PROFILES else []

    def get_character_profiles_for_game_string(self, block, string):
        return []

    def get_character_profile(self, name, document_id=None):
        return self.PROFILES.get(name)

    def get_relations(self, wing):
        return [{"source": "Midna", "relation": "ally_of", "target": "Link", "valid_from": ""}]

    def get_cached_context(self, bmg_id, text):
        return None

    def get_room_visual_context(self, wing, room):
        return ""


class _Block:
    def __init__(self):
        self.metadata: dict = {}
        self.name = "Block"


class _Project:
    def __init__(self, count):
        self.blocks = [_Block() for _ in range(count)]
        self.metadata: dict = {}


class _ProjectManager:
    def __init__(self, count, project_dir):
        self.project = _Project(count)
        self.project_dir = project_dir


class FakeDataProcessor:
    def __init__(self, mw):
        self.mw = mw

    def get_current_string_text(self, block, string):
        edited = self.mw.edited_data.get((block, string))
        if edited is not None:
            return edited, True
        return self.mw.data[block][string], False


class FakeWindow:
    """Everything the prompt composer reads from the main window, and nothing else."""

    def __init__(self, project_dir: str, rules_factory):
        self.data = [list(b) for b in FIXTURE_BLOCKS]
        self.edited_data = {(0, 10): "Ілія чекає біля джерела."}
        self.data_store = self
        self.block_names = {"0": "Spring", "1": "Village"}
        self.block_to_project_file_map = {0: 0, 1: 1}
        self.project_manager = _ProjectManager(len(self.data), project_dir)
        self.target_language = "Ukrainian"
        self.translation_config = {}
        self.default_tag_mappings = dict(FIXTURE_TAGS)
        self.string_metadata = {(0, 6): {"width": 400}}
        self.line_width_warning_threshold_pixels = 208
        self.game_dialog_max_width_pixels = 230
        self.lines_per_page = FIXTURE_LINES_PER_WINDOW
        self.reference_languages_data = {k: dict(v) for k, v in FIXTURE_REFERENCES.items()}
        self.reference_data = {}
        self.saved_translations_manager = None
        self.current_game_rules = rules_factory(self)
        self.active_game_rules = self.current_game_rules
        self.active_game_plugin = "plain_text"
        self.json_path = None
        self.project_file = None
        self.speaker_aliases = {}
        self.translation_handler = None


def _rules_factory(mw):
    from plugins.plain_text.rules import GameRules

    class Rules(GameRules):
        def get_display_name(self):
            return "Review Fixture Game"

        def get_speaker_for_string(self, block_idx, string_idx):
            return FIXTURE_SPEAKERS.get((block_idx, string_idx))

        def is_placeholder_speaker(self, name):
            return False

        def get_string_layout(self, block_idx, string_idx):
            # Item 13 sits in a taller window than the rest.
            return {"lines_per_page": 4} if (block_idx, string_idx) == (0, 13) else {}

        def get_addressee_for_string(self, block_idx, string_idx, speaker=None):
            return FIXTURE_ADDRESSEES.get((block_idx, string_idx), "")

        def get_translation_context_for_string(self, block_idx, string_idx):
            return dict(FIXTURE_CONTEXTS.get((block_idx, string_idx), {}))

        def get_ai_flow_context_for_string(self, block_idx, string_idx):
            return "after: Hello, Link!" if (block_idx, string_idx) == (0, 1) else ""

        def get_ai_flow_overview(self, block_idx, indices):
            return "Conversation 1: 0 -> 1 -> 2" if block_idx == 0 and 0 in indices else ""

    return Rules(mw)


class _MainHandler:
    def __init__(self, mw, glossary):
        self.mw = mw
        self.data_processor = FakeDataProcessor(mw)
        self.ui_updater = None
        self._glossary_manager = glossary
        mw.data_processor = self.data_processor


def fixture_composer(project_dir: str, story: bool = True):
    """``(composer, window)``: the real AIPromptComposer over the fixed fixture."""
    from core.glossary_manager import GlossaryManager
    from handlers.translation.ai_prompt_composer import AIPromptComposer

    glossary = GlossaryManager()
    glossary.load_from_text(plugin_name="plain_text", glossary_path=None,
                            raw_text=json.dumps(FIXTURE_GLOSSARY, ensure_ascii=False))
    mw = FakeWindow(project_dir, _rules_factory)
    handler = _MainHandler(mw, glossary)
    composer = AIPromptComposer(handler)
    client = FakeStoryClient() if story else None
    composer.story_context.get_mempalace_client = lambda: client
    composer.story_context.get_wing_name = lambda: "Fixture"
    # No marked-up script, and no legacy free-text story lookup (it searches the disk for a script).
    composer._find_speaker_in_script = lambda *a, **k: None
    composer.script_speaker_finder.find_speaker_in_script = lambda *a, **k: None
    composer._fetch_story_context = lambda *a, **k: None
    return composer, mw


def fixture_items(block: int = 0) -> List[dict]:
    return [{"id": i, "text": t} for i, t in enumerate(FIXTURE_BLOCKS[block])]


def compose_fixture_requests(project_dir: str) -> dict:
    """The requests both code bases compose from the fixture: a batch chunk, a single string, a variation."""
    composer, _ = fixture_composer(project_dir)
    items = fixture_items()
    batch_system, batch_user, _ = composer.compose_batch_request(
        FIXTURE_SYSTEM_PROMPT, items[:12], items, block_idx=0, mode_description="block 1",
    )
    single_system, single_user = composer.compose_messages(
        FIXTURE_SYSTEM_PROMPT, FIXTURE_BLOCKS[0][1], block_idx=0, string_idx=1, expected_lines=2,
        mode_description="translation",
    )
    variation_system, variation_user = composer.compose_messages(
        FIXTURE_SYSTEM_PROMPT, FIXTURE_BLOCKS[0][1], block_idx=0, string_idx=1, expected_lines=2,
        mode_description="translation variations", request_type="variation_list",
        current_translation="Ласкаво просимо.\nЗалишайся.",
    )
    selection_system, selection_user = composer.compose_messages(
        FIXTURE_SYSTEM_PROMPT, FIXTURE_BLOCKS[0][1], block_idx=0, string_idx=1, expected_lines=1,
        mode_description="translation variations", request_type="variation_list",
        current_translation="Ласкаво просимо.\nЗалишайся.", selected_text="Stay a while.",
    )
    notes_system, notes_user = composer.compose_messages(
        FIXTURE_SYSTEM_PROMPT, "Midna", block_idx=None, string_idx=None, expected_lines=1,
        mode_description="glossary notes", request_type="glossary_notes_variation",
        current_translation="Twili; female; sharp",
    )
    return {
        "batch": {"system": batch_system, "user": batch_user},
        "single": {"system": single_system, "user": single_user},
        "variation": {"system": variation_system, "user": variation_user},
        "variation_selection": {"system": selection_system, "user": selection_user},
        "glossary_notes": {"system": notes_system, "user": notes_user},
    }
