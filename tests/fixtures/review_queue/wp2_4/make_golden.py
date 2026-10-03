"""Golden output of the pre-audit code for the WP2/WP4 review-queue tests.

Run it against the baseline worktree (commit 691699c0) from Git Bash:

    cd /d/git/dev/Picoripi-baseline && PYTHONPATH=. QT_QPA_PLATFORM=offscreen \
        ../Picoripi/venv/Scripts/python.exe ../Picoripi/tests/fixtures/review_queue/wp2_4/make_golden.py < /dev/null

It writes, next to this file:

* ``requests.json`` -- the batch-chunk, single-string and variation requests the baseline composed from the
  fixture in ``tests/test_review/_rq_wp2_4_helpers.py`` (``compose_fixture_requests``).
* ``resume.json`` -- a block translation as the baseline ran it: the chunks its worker cut, and the
  ``translation_progress`` project metadata it saved after the first chunk came back.

Pass ``--print`` to print the requests instead (run it in the current worktree to compare by eye).
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "test_review"))

# Settings and logs of this run go to a temporary directory, never to ~/.picoripi or the worktree.
_TMP = Path(tempfile.mkdtemp(prefix="rq_wp2_4_"))
import utils.constants as constants  # noqa: E402
import utils.logging_utils as logging_utils  # noqa: E402

constants.SETTINGS_DIR = _TMP / "settings"
constants.SETTINGS_FILE_PATH = str(_TMP / "settings" / "settings.json")
logging_utils.default_log_file_path = logging_utils.log_file_path = str(_TMP / "app_debug.txt")

from PyQt6.QtWidgets import QApplication  # noqa: E402

import _rq_wp2_4_helpers as helpers  # noqa: E402

# The block the resume test translates: 30 strings, repeated ones among them.
RESUME_BLOCK = [
    "Yes" if i % 5 == 0 else ("No" if i % 7 == 0 else f"Line number {i}.") for i in range(30)
]


class _Provider:
    def translate(self, messages, session=None, settings_override=None):
        from core.translation.providers import ProviderResponse

        items = json.loads(messages[-1]["content"])
        return ProviderResponse(text=json.dumps(
            {"translated_strings": [{"id": item["id"], "translation": "UA " + item["text"]} for item in items]}
        ))


class _Composer:
    """Hands the chunk's items to the provider as they are; only the chunk cut is of interest."""

    mw = None

    def _get_mempalace_client(self):
        return None

    def _get_wing_name(self):
        return "Fixture"

    def _get_block_label(self, block_idx):
        return "Resume"

    def compose_batch_request(self, system_prompt, source_items, all_source_items, **kwargs):
        return "system", json.dumps(source_items), {}


def baseline_resume() -> dict:
    from handlers.translation.ai_worker import AIWorker
    from handlers.translation.progress_manager import TranslationProgressManager

    items = [{"id": i, "text": t} for i, t in enumerate(RESUME_BLOCK)]
    task = {
        'type': 'translate_block_chunked', 'source_items': items, 'block_idx': 0, 'attempt': 1,
        'temp_id_map': {i: (0, i) for i in range(len(items))}, 'mode_description': 'block 1',
        'composer_args': {'system_prompt': 's'}, 'workers': 1, 'chunks_to_skip': set(),
    }
    worker = AIWorker(_Provider(), _Composer(), task)
    done = []
    worker.chunk_translated.connect(lambda index, text, ctx: done.append(index))
    worker.run()
    chunks = [[item["id"] for item in chunk] for chunk in task['calculated_chunks']]

    # The progress entry as the baseline's initiate_batch_translation created it, after chunk 0 came back.
    class _Handler:
        translation_progress = {0: {
            'completed_chunks': {0}, 'total_chunks': len(chunks), 'source_items': items,
            'temp_id_map': task['temp_id_map'],
        }}

    class _Block:
        metadata = {}

    class _Window:
        block_to_project_file_map = {0: 0}

        class project_manager:  # noqa: N801 -- stands in for the attribute
            class project:  # noqa: N801
                blocks = [_Block()]

            @staticmethod
            def save():
                return True

    handler = _Handler()
    handler.mw = _Window()
    handler.data_processor = handler.ui_updater = None
    TranslationProgressManager(handler).save_progress_to_metadata(0)
    return {
        "block": RESUME_BLOCK,
        "chunks": chunks,
        "chunks_sent": done,
        "progress_metadata": json.loads(json.dumps(_Block.metadata['translation_progress'])),
    }


def main() -> None:
    QApplication.instance() or QApplication([])
    requests = helpers.compose_fixture_requests(str(_TMP / "project"))
    if "--print" in sys.argv:
        for kind, parts in requests.items():
            for part, text in parts.items():
                print(f"===== {kind} {part}\n{text}\n")
        return
    (HERE / "requests.json").write_text(json.dumps(requests, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "resume.json").write_text(json.dumps(baseline_resume(), ensure_ascii=False, indent=1) + "\n",
                                      encoding="utf-8")
    print("written to", HERE)


if __name__ == "__main__":
    main()
