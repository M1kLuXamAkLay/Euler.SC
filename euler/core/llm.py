"""Local Ollama client: service installation, model download, streaming generation.

All traffic targets 127.0.0.1. The only outbound request is the Ollama
installer download, triggered by an explicit user action.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Iterator

HOST = "http://127.0.0.1:11434"
# Enough for a worked solution; far too little for a runaway loop.
MAX_ANSWER_TOKENS = 900
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Language of the answer follows the interface language, not the prompt text:
# a user with a French interface who pastes a Russian task still wants French.
_LANGUAGE_NAMES = {
    "ru": "Russian",
    "en": "English",
    "zh": "Chinese (Simplified)",
    "es": "Spanish",
    "fr": "French",
    "bn": "Bengali",
    "pt": "Portuguese",
}

_BASE_PROMPT = (
    "You are a mathematics tutor inside a calculator application. "
    "Give a finished solution, not a discussion.\n\n"
    "Structure for a mathematical task, exactly three parts:\n"
    "## Given — one or two lines restating the task as formulas.\n"
    "## Solution — numbered steps, each one line: the operation, then the result. "
    "No explanation of what a logarithm or a trig identity is; the reader is a student "
    "who needs the working, not a lecture.\n"
    "## Answer — the final value, boxed and nothing else.\n\n"
    "If the message is small talk or has nothing to do with mathematics, do not "
    "invent a mathematical structure. Answer briefly and naturally, in one or two "
    "sentences, and offer to help with a task.\n\n"
    "Two kinds of mathematical message exist. If the user asks WHAT something is, "
    "give the statement and when it applies, then one short example. If the user "
    "gives a specific exercise, work it out. Never mix the two: a theorem is not "
    "an exercise, and an exercise does not need a lecture.\n\n"
    "REFUSAL. Decline clearly and briefly, without lecturing, when the request asks "
    "for: violence against a person, self-harm, sexual content, anything involving "
    "minors in a sexual context, instructions for weapons, explosives, drugs or other "
    "illegal activity, malware or attacks on systems the user does not own. One "
    "sentence is enough — for example \"Извините, но я не могу ответить на этот "
    "вопрос.\" — then offer a mathematical alternative if one exists.\n\n"
    "Never produce content that could guide someone to harm a person, even in the "
    "form of 'questions to consider' or an outline. A request as short as 'как "
    "убить' is a request for instructions, not for a discussion. Never repeat the "
    "harmful request back, never list methods, and do not add a disclaimer paragraph. "
    "For a legitimate request, answer normally; a question that merely mentions a "
    "sensitive word is not grounds for refusal.\n\n"
    "Write every formula in LaTeX between $...$ (inline) or $$...$$ (display). "
    "Keep a solution under 250 words. No preamble, no summary at the end, "
    "no 'in conclusion', no remark that you are an AI."
)


def system_prompt(language: str | None = None) -> str:
    """Build the system prompt for a given interface language.

    The language rule is stated three times on purpose. Small local models slip
    into English as soon as the task itself is in English or looks like code,
    and a single instruction was not enough to hold them.
    """
    code = (language or "en").lower()[:2]
    name = _LANGUAGE_NAMES.get(code, "English")
    return (
        f"{_BASE_PROMPT}\n\n"
        f"LANGUAGE RULE (highest priority): write the entire answer in {name}. "
        f"Every heading, every list item, every explanation sentence and every "
        f"remark must be in {name}. Mathematical notation, formulas and variable "
        f"names stay as they are. If the task is written in another language, "
        f"still answer in {name}. Do not translate formulas. Do not add an "
        f"English summary."
    )


# Kept for callers that do not pass a language.
SYSTEM_PROMPT = system_prompt("en")


class OllamaError(RuntimeError):
    """Error carrying a message suitable for display."""


@dataclass
class ModelInfo:
    name: str
    size_gb: float


# ------------------------------------------------------------------ service
def _get(path: str, timeout: float = 4.0) -> dict:
    req = urllib.request.Request(f"{HOST}{path}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_running(timeout: float = 1.2) -> bool:
    try:
        _get("/api/version", timeout=timeout)
        return True
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return False


def is_installed() -> bool:
    return shutil.which("ollama") is not None


def start_server(wait_seconds: float = 25.0,
                 on_progress: Callable[[dict], None] | None = None) -> bool:
    """Start `ollama serve` and wait until it answers, reporting progress."""
    if is_running():
        return True
    if not is_installed():
        raise OllamaError("ExprError.ollama_missing")

    if on_progress:
        on_progress({"stage": "starting", "text": "settings.starting"})

    try:
        process = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
        # The app owns this server: it may stop it on exit.
        mark_started_by_app()
        globals()["SERVER_PID"] = process.pid
    except OSError as exc:
        raise OllamaError(f"ExprError.ollama_start_failed:{exc}") from None

    deadline = time.monotonic() + wait_seconds
    tick = 0
    while time.monotonic() < deadline:
        if is_running():
            if on_progress:
                on_progress({"stage": "ready", "text": "settings.running"})
            return True
        tick += 1
        if on_progress and tick % 4 == 0:
            waited = int(time.monotonic() - (deadline - wait_seconds))
            on_progress({"stage": "starting", "text": f"settings.waiting:{waited}"})
        time.sleep(0.5)

    raise OllamaError("ExprError.ollama_timeout")


def install_windows(on_progress: Callable[[dict], None] | None = None) -> dict:
    """
    Install Ollama on Windows via winget, falling back to the official installer.

    Returns a result dictionary instead of raising: the outcome is shown in the UI.
    """
    if is_installed():
        return {"ok": True, "already": True, "text": "settings.running"}

    winget = shutil.which("winget")
    if winget:
        if on_progress:
            on_progress({"stage": "install", "text": "settings.installing"})
        try:
            proc = subprocess.run(
                [winget, "install", "-e", "--id", "Ollama.Ollama",
                 "--accept-package-agreements", "--accept-source-agreements",
                 "--disable-interactivity"],
                capture_output=True, text=True, timeout=900,
                creationflags=CREATE_NO_WINDOW,
            )
            if proc.returncode == 0 and is_installed():
                return {"ok": True, "text": "settings.installed"}
        except (subprocess.SubprocessError, OSError) as exc:
            if on_progress:
                on_progress({"stage": "install", "text": f"ExprError.winget_failed:{exc}"})

    # Fallback: official installer. Downloaded and run directly rather than piped to the shell.
    if on_progress:
        on_progress({"stage": "download", "text": "settings.downloading"})
    try:
        url = "https://ollama.com/download/OllamaSetup.exe"
        target = os.path.join(os.environ.get("TEMP", "."), "OllamaSetup.exe")
        urllib.request.urlretrieve(url, target)

        if on_progress:
            on_progress({"stage": "install", "text": "settings.installing"})
        subprocess.run([target, "/SILENT", "/NORESTART"], timeout=1800,
                       creationflags=CREATE_NO_WINDOW)
        os.remove(target)

        # The installer edits PATH; the current process does not see that change.
        for candidate in (
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama"),
            r"C:\Program Files\Ollama",
        ):
            exe = os.path.join(candidate, "ollama.exe")
            if os.path.exists(exe):
                os.environ["PATH"] = candidate + os.pathsep + os.environ.get("PATH", "")
                return {"ok": True, "text": "settings.installed"}

        return {"ok": False, "text": "ExprError.ollama_not_found"}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "text": f"ExprError.install_failed:{exc}"}


# ------------------------------------------------------------------ models
def list_models() -> list[ModelInfo]:
    try:
        data = _get("/api/tags")
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return []
    result = []
    for item in data.get("models", []):
        name = item.get("name") or item.get("model") or ""
        size = item.get("size") or 0
        if name:
            result.append(ModelInfo(name=name, size_gb=round(size / 1024 ** 3, 2)))
    return result


def has_model(name: str) -> bool:
    """Exact tag comparison: substring matching selected qwen2.5:3b instead of 7b."""
    want = name if ":" in name else f"{name}:latest"
    return any(m.name in (name, want) for m in list_models())


def pull(name: str,
         on_progress: Callable[[dict], None] | None = None,
         should_stop: Callable[[], bool] | None = None) -> None:
    """Download a model, reporting progress in percent and gigabytes."""
    body = json.dumps({"model": name, "stream": True}).encode()
    req = urllib.request.Request(
        f"{HOST}/api/pull", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw in resp:
                if should_stop and should_stop():
                    return
                if not raw.strip():
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if event.get("error"):
                    raise OllamaError(f"Ollama: {event['error']}")
                if on_progress:
                    total = event.get("total") or 0
                    done = event.get("completed") or 0
                    on_progress({
                        "stage": event.get("status", "download"),
                        "percent": int(done * 100 / total) if total else 0,
                        "completed_gb": round(done / 1024 ** 3, 2),
                        "total_gb": round(total / 1024 ** 3, 2),
                    })
    except urllib.error.URLError as exc:
        raise OllamaError(f"ExprError.pull_failed:{exc.reason}") from None


def delete_model(name: str) -> dict:
    try:
        body = json.dumps({"model": name}).encode()
        req = urllib.request.Request(
            f"{HOST}/api/delete", data=body,
            headers={"Content-Type": "application/json"}, method="DELETE",
        )
        urllib.request.urlopen(req, timeout=30)
        return {"ok": True}
    except (urllib.error.URLError, OSError) as exc:
        return {"ok": False, "error": str(exc)}


# ------------------------------------------------------------------ generation
def classify(model: str, system: str, user: str,
             timeout: float = 45.0) -> dict | None:
    """One short, non-streaming completion in JSON mode, for classification.

    Returns the parsed object, or ``None`` when the model produced something
    unusable. Deliberately separate from ``chat_stream``: this call must be
    cheap, bounded and silent — it produces no user-visible text, and a failure
    here must never break the answer.

    ``num_predict`` is small because the expected reply is a single small
    object. A model that ignores the format and starts explaining will hit the
    cap and return nothing, which the caller treats as "not sure".
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "format": "json",            # Ollama constrains the reply to valid JSON
        "keep_alive": "30m",
        "options": {
            "temperature": 0.0,      # classification wants the likeliest label
            "num_ctx": 4096,
            "num_predict": 160,
        },
    }

    request = urllib.request.Request(
        f"{HOST}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
        return None

    content = (body.get("message") or {}).get("content", "")
    if not content:
        return None

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # A model may wrap JSON in prose or code fences; take the outermost object
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(content[start:end + 1])
        except json.JSONDecodeError:
            return None

    return parsed if isinstance(parsed, dict) else None


def chat_stream(model: str, messages: list[dict], temperature: float = 0.3,
                should_stop: Callable[[], bool] | None = None,
                language: str | None = None,
                extra_system: str = "") -> Iterator[str]:
    """
    Stream a chat completion.

    ``messages`` carries the full conversation so follow-up questions stay
    on topic. ``extra_system`` appends retrieved reference material to the
    system prompt: a small model reproduces a supplied formula far more
    reliably than it recalls one.
    """
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt(language) + (extra_system or "")}] + messages,
        "stream": True,
        "keep_alive": "30m",
        "options": {
            "temperature": temperature,
            "num_ctx": 4096,
            # A loop used to stream forever. This cap bounds it in time and
            # tokens; a normal answer needs a fraction of it.
            "num_predict": MAX_ANSWER_TOKENS,
            # Repeating a line is the usual failure; stop before it starts.
            "stop": ["\n\n\n", "```\n\n```"],
            # Slightly penalise repetition, which discourages the loop without
            # hurting normal prose.
            "repeat_penalty": 1.18,
            "repeat_last_n": 128,
        },
    }

    req = urllib.request.Request(
        f"{HOST}/api/chat", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            for raw in resp:
                if should_stop and should_stop():
                    return
                if not raw.strip():
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if event.get("error"):
                    raise OllamaError(f"Ollama: {event['error']}")
                piece = (event.get("message") or {}).get("content", "")
                if piece:
                    yield piece
                    # Abort a runaway repetition: the same line three times in a
                    # row means the model is stuck, not explaining.
                    if _looks_like_loop(piece):
                        raise OllamaError("ExprError.ai_looping")
                if event.get("done"):
                    return
    except urllib.error.URLError as exc:
        raise OllamaError(f"ExprError.connection_lost:{exc.reason}") from None


def supports_vision(model: str) -> bool:
    """Models that accept images. The list is deliberately narrow: others silently ignore them."""
    name = model.lower()
    return any(tag in name for tag in ("llava", "moondream", "qwen2-vl", "qwen2.5vl", "minicpm-v", "bakllava"))


def status() -> dict:
    installed = is_installed()
    running = is_running() if installed else False
    return {
        "installed": installed,
        "running": running,
        "models": [{"name": m.name, "size_gb": m.size_gb} for m in (list_models() if running else [])],
        "host": HOST,
    }

# ------------------------------------------------------------------ shutdown
# The app owns the server it starts. Leaving `ollama serve` behind means a
# background process that keeps a model in RAM after the window is closed, which
# on a 16 GB laptop is the difference between a usable machine and a slow one.
_STARTED_BY_US = False
SERVER_PID: int | None = None


def mark_started_by_app() -> None:
    """Record that this process launched the service, so it may stop it."""
    global _STARTED_BY_US
    _STARTED_BY_US = True


def started_by_app() -> bool:
    return _STARTED_BY_US


def _pids_on_port(port: int = 11434) -> list[int]:
    """Process ids listening on the Ollama port."""
    found: list[int] = []

    # Windows: netstat -ano prints the owning pid in the last column
    if os.name == "nt":
        try:
            output = subprocess.run(
                ["netstat", "-ano", "-p", "TCP"],
                capture_output=True, text=True, timeout=8,
                creationflags=CREATE_NO_WINDOW).stdout
            for line in output.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[3].upper() == "LISTENING":
                    if parts[1].endswith(f":{port}"):
                        try:
                            found.append(int(parts[4]))
                        except ValueError:
                            pass
        except (OSError, subprocess.SubprocessError):
            pass
        return found

    # POSIX: lsof is present on macOS, ss on Linux
    for command in (["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
                    ["ss", "-lptn", f"sport = :{port}"]):
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.SubprocessError):
            continue

        if command[0] == "lsof":
            for line in result.stdout.split():
                try:
                    found.append(int(line))
                except ValueError:
                    pass
        else:
            import re as _re
            for pid in _re.findall(r"pid=(\d+)", result.stdout):
                found.append(int(pid))
        if found:
            break
    return found


def stop_server(wait_seconds: float = 6.0) -> dict:
    """Stop the Ollama service this application started.

    Only called for a server the app launched: if Ollama was already running
    before the window opened, it belongs to the user and is left alone.

    Killing the process is what actually frees the memory. ``ollama stop`` only
    unloads the model from VRAM and leaves the server resident.
    """
    if not _STARTED_BY_US:
        return {"stopped": False, "reason": "not_started_by_app"}

    if not is_running(timeout=1.0):
        return {"stopped": True, "reason": "already_down"}

    # Ask politely first: this unloads the model and closes the socket cleanly
    try:
        subprocess.run(["ollama", "stop"], capture_output=True, timeout=10,
                       creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        pass

    time.sleep(0.4)

    if not is_running(timeout=1.0):
        return {"stopped": True, "reason": "graceful"}

    # It ignored the request: terminate the listening process
    killed = []
    for pid in _pids_on_port():
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                               capture_output=True, timeout=8,
                               creationflags=CREATE_NO_WINDOW)
            else:
                os.kill(pid, 15)      # SIGTERM
            killed.append(pid)
        except (OSError, subprocess.SubprocessError):
            continue

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if not is_running(timeout=0.6):
            return {"stopped": True, "reason": "killed", "pids": killed}
        time.sleep(0.3)

    # Still alive: SIGKILL as the last resort
    for pid in killed:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                               capture_output=True, timeout=8,
                               creationflags=CREATE_NO_WINDOW)
            else:
                os.kill(pid, 9)
        except (OSError, subprocess.SubprocessError):
            continue

    return {"stopped": not is_running(timeout=0.8), "reason": "hard_kill",
            "pids": killed}


# ------------------------------------------------------------ loop detection
class _LoopGuard:
    """Detects a model repeating itself.

    A small model grounded on a reference block can latch onto one sentence and
    emit it forever. Watching the last few non-empty lines catches that within
    a second or two instead of letting it fill the window.
    """

    def __init__(self, window: int = 3, min_length: int = 12) -> None:
        self.window = window
        self.min_length = min_length
        self._tail = ""
        self._recent: list[str] = []

    def feed(self, piece: str) -> bool:
        self._tail += piece
        # Only complete lines are compared: a partial line is not a repeat yet
        if "\n" not in self._tail:
            return False

        *lines, self._tail = self._tail.split("\n")
        for line in lines:
            text = line.strip()
            if len(text) < self.min_length:
                continue
            self._recent.append(text)
            if len(self._recent) < self.window:
                continue
            if len(set(self._recent[-self.window:])) == 1:
                return True
            # Keep the history short: only the last window matters
            if len(self._recent) > self.window * 4:
                self._recent = self._recent[-self.window * 2:]
        return False


_guard = _LoopGuard()


def _looks_like_loop(piece: str) -> bool:
    return _guard.feed(piece)


def reset_loop_guard() -> None:
    """Called before each answer so the previous one cannot poison the next."""
    _guard.__init__()

