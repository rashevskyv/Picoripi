"""Optional subprocess bridge to the Python 3.11 CUDA candidate retriever."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile


def retrieve_gpu_candidates(dialogues, messages, *, top_k: int = 16) -> tuple[dict, dict]:
    project_root = Path(__file__).resolve().parents[2]
    python = project_root / ".venv-gpu" / "Scripts" / "python.exe"
    helper = project_root / "tools" / "mempalace_gpu_candidates.py"
    if not python.is_file():
        raise RuntimeError("The optional MemPalace GPU environment is not installed.")
    payload = {
        "dialogues": [
            {"node_id": dialogue.node_id, "text": dialogue.text}
            for dialogue in dialogues
        ],
        "messages": [
            {"message_id": message.message_id, "text": message.text}
            for message in messages
        ],
    }
    with tempfile.TemporaryDirectory(prefix="mempalace-gpu-") as directory:
        input_path = Path(directory) / "input.json"
        output_path = Path(directory) / "output.json"
        input_path.write_text(json.dumps(payload), encoding="utf-8")
        completed = subprocess.run(
            [
                str(python),
                str(helper),
                "--input", str(input_path),
                "--output", str(output_path),
                "--top-k", str(top_k),
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        if completed.returncode != 0 or not output_path.is_file():
            detail = (completed.stderr or completed.stdout or "unknown error").strip()
            raise RuntimeError(f"CUDA candidate retrieval failed: {detail[-1000:]}")
        report = json.loads(output_path.read_text(encoding="utf-8"))
    candidates = {
        int(node_id): [(int(index), float(score)) for index, score in values]
        for node_id, values in report.pop("candidates").items()
    }
    return candidates, report
