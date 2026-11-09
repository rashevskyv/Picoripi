"""Image AI: send a texture to an image model with a prompt and get the edited image back, at the texture's size.

Settings live in ``image_ai`` (Settings > Image AI). Two providers:

* ``openai``: the images API. The key is the AI Translation OpenAI key or an environment variable (never
  stored in ``image_ai``). Image models answer on a few fixed canvases, so the texture is scaled onto the canvas whose shape is
  closest ("fit": scaled up and padded with transparency, the same box is cut out of the answer) or stretched
  over it ("stretch"); the answer is scaled back to the texture's size.
* ``command``: a local CLI agent (Codex, Claude Code, Gemini CLI, Hermes or any other command). The command runs
  in a temporary folder with the task on its standard input; ``{input}``, ``{output}`` and ``{prompt_file}`` in
  it are replaced by the texture PNG, the PNG the agent must write and the task file.

Blocking code only -- call it off the UI thread.
"""
from __future__ import annotations

import base64
import io
import math
import os
import shlex
import shutil
import subprocess
import tempfile
import time
from typing import Callable, Dict, Optional, Tuple

import requests
from PIL import Image

DEFAULT_PROMPT = ("Translate all text in this image into Ukrainian. Keep the style, font look, size, position, "
                  "colours and transparency of the original; change nothing else.")
DEFAULTS = {
    "provider": "openai",
    "model": "gpt-image-1.5",
    "use_translation_api_key": True,
    "api_key_env": "OPENAI_API_KEY",
    "endpoint": "",
    "prompt": DEFAULT_PROMPT,
    "size_rule": "fit",
    "timeout": 180,
    "command": "",
}
# Local CLI agents: the task arrives on standard input (Hermes reads the task file).
AGENT_PRESETS = {
    "codex": 'codex exec --full-auto --skip-git-repo-check -i "{input}" -',
    "claude": 'claude -p --permission-mode acceptEdits --allowedTools "Read,Write,Bash"',
    "gemini": "gemini --yolo",
    "hermes": 'hermes chat --query-file "{prompt_file}" --image "{input}" --oneshot --yolo -Q',
}
AGENT_TASK = ("{prompt}\n\nThe image to edit is {input} ({width}x{height} pixels). Write the edited image as a PNG "
              "of the same size to {output}. Do not ask questions; the task is done when {output} exists.")
SIZE_RULES = ("fit", "stretch")
CANVASES = ((1024, 1024), (1536, 1024), (1024, 1536))
Box = Tuple[int, int, int, int]


class ImageAIError(Exception):
    """The request could not be made or the answer holds no image."""


def settings(saved: Optional[Dict]) -> Dict:
    return {**DEFAULTS, **(saved if isinstance(saved, dict) else {})}


def api_key(config: Dict, translation_config: Optional[Dict]) -> str:
    """The key for ``config``: the AI Translation OpenAI key (its value or its variable) or ``api_key_env``."""
    if config.get("use_translation_api_key"):
        providers = (translation_config or {}).get("providers", {}) if isinstance(translation_config, dict) else {}
        openai = providers.get("openai", {}) or {}
        key = openai.get("api_key") or os.getenv(str(openai.get("api_key_env") or ""), "")
        if key:
            return key
    return os.getenv(str(config.get("api_key_env") or ""), "")


def canvas_for(size: Tuple[int, int]) -> Tuple[int, int]:
    """The canvas whose shape is closest to ``size``."""
    ratio = math.log(size[0] / size[1])
    return min(CANVASES, key=lambda canvas: abs(math.log(canvas[0] / canvas[1]) - ratio))


def to_canvas(image: Image.Image, rule: str) -> Tuple[Image.Image, Box]:
    """``(image on its canvas, box of the texture on it)``."""
    canvas = canvas_for(image.size)
    if rule == "stretch":
        return image.convert("RGBA").resize(canvas, Image.Resampling.LANCZOS), (0, 0, *canvas)
    scale = min(canvas[0] / image.width, canvas[1] / image.height)
    width, height = max(1, round(image.width * scale)), max(1, round(image.height * scale))
    left, top = (canvas[0] - width) // 2, (canvas[1] - height) // 2
    sheet = Image.new("RGBA", canvas, (0, 0, 0, 0))
    sheet.paste(image.convert("RGBA").resize((width, height), Image.Resampling.LANCZOS), (left, top))
    return sheet, (left, top, left + width, top + height)


def from_canvas(answer: Image.Image, canvas: Tuple[int, int], box: Box, size: Tuple[int, int]) -> Image.Image:
    """Cut the texture's box out of the answer (scaled to the canvas first) and scale it to ``size``."""
    answer = answer.convert("RGBA")
    if answer.size != canvas:
        answer = answer.resize(canvas, Image.Resampling.LANCZOS)
    return answer.crop(box).resize(size, Image.Resampling.LANCZOS)


def missing(config: Dict, key: str) -> str:
    """What ``config`` lacks to send a request ("" when nothing): no key, no command, a command not installed."""
    provider = config.get("provider")
    if provider == "openai" and not key:
        return "No OpenAI API key."
    if provider == "command":
        command = str(config.get("command") or "").strip()
        if not command:
            return "No agent command."
        program = shlex.split(command, posix=False)[0].strip('"')
        if not shutil.which(program):
            return f"{program} is not installed or not on PATH."
    return ""


def _edit_openai(config: Dict, key: str, png: bytes, prompt: str, canvas: Tuple[int, int],
                 cancelled: Callable[[], bool] = lambda: False) -> bytes:
    """OpenAI ``/images/edits``: the PNG of the edited image."""
    if not key:
        raise ImageAIError("No OpenAI API key: set the AI Translation key or the environment variable "
                           f"{config.get('api_key_env') or 'OPENAI_API_KEY'}.")
    base = (config.get("endpoint") or "https://api.openai.com/v1").rstrip("/")
    model = config.get("model") or DEFAULTS["model"]
    data = {"model": model, "prompt": prompt, "size": f"{canvas[0]}x{canvas[1]}", "n": "1"}
    if model.startswith("gpt-image-1"):  # gpt-image-2 has no transparent background
        data.update(background="transparent", output_format="png", input_fidelity="high")
    reply = requests.post(f"{base}/images/edits", headers={"Authorization": f"Bearer {key}"}, data=data,
                          files={"image": ("texture.png", png, "image/png")},
                          timeout=float(config.get("timeout") or DEFAULTS["timeout"]))
    if not reply.ok:
        raise ImageAIError(f"HTTP {reply.status_code}: {reply.text[:500]}")
    try:
        return base64.b64decode(reply.json()["data"][0]["b64_json"])
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ImageAIError(f"The answer holds no image: {exc}") from exc


def _stop(process: subprocess.Popen) -> None:
    if os.name == "nt":   # the shell's children too
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True, check=False)
    else:
        process.kill()
    process.wait()


def _edit_command(config: Dict, key: str, png: bytes, prompt: str, canvas: Tuple[int, int],
                  cancelled: Callable[[], bool] = lambda: False) -> bytes:
    """A local CLI agent: the PNG it wrote to ``{output}`` (empty when cancelled)."""
    command = str(config.get("command") or "").strip()
    if not command:
        raise ImageAIError("No agent command.")
    timeout = float(config.get("timeout") or DEFAULTS["timeout"])
    with tempfile.TemporaryDirectory(prefix="picoripi_image_ai_") as folder:
        paths = {name: os.path.join(folder, file) for name, file in
                 (("input", "texture.png"), ("output", "answer.png"), ("prompt_file", "task.txt"))}
        with open(paths["input"], "wb") as stream:
            stream.write(png)
        with open(paths["prompt_file"], "w", encoding="utf-8") as stream:
            stream.write(AGENT_TASK.format(prompt=prompt, input=paths["input"], output=paths["output"],
                                           width=canvas[0], height=canvas[1]))
        for name, path in paths.items():
            command = command.replace("{" + name + "}", path)
        log_path = os.path.join(folder, "agent.log")
        with open(log_path, "wb") as log, open(paths["prompt_file"], "rb") as task:
            process = subprocess.Popen(command, shell=True, cwd=folder, stdin=task, stdout=log,
                                       stderr=subprocess.STDOUT)
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if cancelled():
                    _stop(process)
                    return b""
                if time.monotonic() > deadline:
                    _stop(process)
                    raise ImageAIError(f"The agent did not finish in {timeout:g} s.")
                time.sleep(0.3)
        if not os.path.isfile(paths["output"]):
            with open(log_path, "rb") as stream:
                tail = stream.read()[-800:].decode("utf-8", "replace").strip()
            raise ImageAIError(f"The agent wrote no image (exit code {process.returncode}). {tail}")
        with open(paths["output"], "rb") as stream:
            return stream.read()


# provider id -> fn(config, key, png, prompt, canvas, cancelled) -> PNG bytes; add Gemini and others here.
PROVIDERS: Dict[str, Callable[..., bytes]] = {"openai": _edit_openai, "command": _edit_command}


def edit(image: Image.Image, prompt: str, config: Dict, key: str,
         cancelled: Callable[[], bool] = lambda: False) -> Optional[Image.Image]:
    """The edited ``image`` at its own size, or ``None`` when cancelled."""
    send = PROVIDERS.get(config.get("provider") or "")
    if send is None:
        raise ImageAIError(f"Unknown image AI provider: {config.get('provider')}")
    if config.get("provider") == "command":   # an agent edits the texture itself, at its own size
        sheet, box = image.convert("RGBA"), (0, 0, *image.size)
    else:
        sheet, box = to_canvas(image, config.get("size_rule") or "fit")
    buffer = io.BytesIO()
    sheet.save(buffer, "PNG")
    if cancelled():
        return None
    answer = send(config, key, buffer.getvalue(), prompt, sheet.size, cancelled)
    if cancelled() or not answer:
        return None
    with Image.open(io.BytesIO(answer)) as result:
        return from_canvas(result, sheet.size, box, image.size)
