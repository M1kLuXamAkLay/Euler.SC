"""
Bridge between JavaScript and Python.

Two channels are used:

* request/response - methods on :class:`Api`, exposed through pywebview ``js_api``;
* server push      - ``window.Euler.<event>(...)`` calls queued from worker threads.

Threading model
---------------
pywebview is not thread safe. Every call into the window goes through a single
queue drained by one dedicated thread, so worker threads never touch the UI.

Startup cost
------------
SymPy and NumPy take one to three seconds to import. Importing them at module
level meant the window stayed blank for that long. Imports are now deferred to
a background warm-up; the window opens immediately and the first user action
waits for the warm-up instead of the launch.
"""
from __future__ import annotations

import json
import queue
import threading
from pathlib import Path
import time
from typing import Any

_core: dict[str, Any] = {}
_warm_lock = threading.Lock()
_warm_done = threading.Event()


def _warmup() -> None:
    """Import heavy dependencies before the first request arrives."""
    try:
        from ..core import (
            analysis, calculus, exporter, format as fmt, grapher, hardware, llm,
            guard, intent, matrix, parser, reference, settings, solver, stepwise,
        )
        from ..core.parser import ExprError
        from ..core.registry import registry

        # Matrices saved in a previous session become available as A..H
        # immediately, so ``rank(F)`` works on the very first request.
        registry.load()

        with _warm_lock:
            _core.update({
                "solver": solver,
                "calculus": calculus,
                "analysis": analysis,
                "matrix": matrix,
                "registry": registry,
                "format": fmt,
                "parser": parser,
                "stepwise": stepwise,
                "exporter": exporter,
                "grapher": grapher,
                "hardware": hardware,
                "llm": llm,
                "settings": settings,
                "reference": reference,
                "guard": guard,
                "intent": intent,
                "ExprError": ExprError,
            })
    finally:
        _warm_done.set()


def _mod(name: str):
    """Return a warmed module, blocking until the warm-up finishes."""
    if not _warm_done.is_set():
        _warm_done.wait(timeout=30)
    with _warm_lock:
        return _core[name]


def _normalise(payload: dict) -> dict:
    """Guarantee ``result`` on every success payload.

    The solver layer returns ``{"ok": True, "text": ...}``; the interface reads
    ``res.result`` uniformly. Mapping once here keeps both sides simple and
    prevents silently empty output fields.
    """
    if not isinstance(payload, dict):
        return {"ok": False, "error": "ExprError.bad_response"}
    if payload.get("ok") and "result" not in payload:
        payload["result"] = payload.get("text", "") or payload.get("body", "")
    if not payload.get("ok") and "error" in payload:
        payload.setdefault("result", "")
    return payload


class Api:
    """Methods reachable from JavaScript as ``window.pywebview.api.<name>``."""

    # Methods callable from JavaScript. The HTTP transport refuses anything
    # outside this set, so a leaked URL token cannot reach arbitrary Python.
    _exported = frozenset({
        "ping", "ready", "solve", "solve_equation", "solve_system", "steps",
        "matrix_op", "matrix_list", "matrix_save", "matrix_delete", "matrix_get",
        "calculus", "analyze", "limit", "plot", "autoscale",
        "hardware", "model_catalogue", "cycle_form", "export_pdf", "export_latex",
        "settings_get", "settings_set",
        "ollama_status", "ollama_install", "ollama_start", "ollama_pull", "ollama_delete", "open_models_dir", "setup_all",
        "ai_ask", "ai_stop", "ai_reset", "ai_new_chat", "ai_drop_chat",
        "pick_image", "open_data_dir",
        "reference", "ollama_stop", "shutdown",
    })

    def __init__(self) -> None:
        self._transport = None
        self._stop = threading.Event()
        self._busy = threading.Event()
        # One history per conversation tab. The interface switches between
        # them, so a follow-up in tab B must not inherit the context of tab A.
        self._chats: dict[str, list[dict]] = {}
        self._active_chat = ""
        threading.Thread(target=_warmup, name="warmup", daemon=True).start()

    # ------------------------------------------------------- conversations
    def _chat_for(self, conversation: str) -> list[dict]:
        key = (conversation or "").strip() or "default"
        self._active_chat = key
        return self._chats.setdefault(key, [])

    def ai_new_chat(self, conversation: str) -> dict:
        """Start an empty history under ``conversation``."""
        key = (conversation or "").strip() or "default"
        self._chats[key] = []
        return {"ok": True, "conversation": key}

    def ai_drop_chat(self, conversation: str) -> dict:
        """Forget a conversation entirely."""
        key = (conversation or "").strip() or "default"
        self._chats.pop(key, None)
        return {"ok": True, "conversation": key}

    def attach(self, transport) -> None:
        """Wire the HTTP transport. Lifecycle only, never called from the page."""
        self._transport = transport

    attach._serializable = False

    def _emit(self, event: str, payload: dict) -> None:
        """Push a server-initiated event to the page over Server-Sent Events."""
        transport = self._transport
        if transport is not None:
            transport.emit(event, payload)

    def ping(self) -> dict:
        """Liveness probe. Called first by the interface."""
        return {"ok": True, "pong": True, "version": "2.2.0"}

    def ready(self) -> dict:
        """Reports whether heavy modules finished loading."""
        return {
            "ok": True,
            "warm": _warm_done.is_set(),
            "version": "2.2.0",
            "methods": sorted(_core.keys()),
        }

    # ------------------------------------------------------------- calculation
    def solve(self, expression: str, matrices: dict | None = None) -> dict:
        """
        Evaluate an expression, or solve it when a relation is present.

        Routing is automatic: input containing ``=``, ``<``, ``>``, ``<=`` or
        ``>=`` goes to the equation solver, everything else to evaluation.
        This keeps the calculator's single entry point useful for both cases.

        :param expression: user input in any supported notation
        :param matrices: optional map name -> grid, enabling ``A``..``H``
        """
        started = time.perf_counter()
        try:
            solver = _mod("solver")
            registry = _mod("registry")
            text = expression or ""

            # Saved matrices are visible to every expression, so rank(F) works
            # even when the caller passes nothing explicitly.
            if matrices is None:
                matrices = {name: registry.grid(name) for name in registry.names()} or None

            is_relation = any(op in text for op in ("=", "<", ">"))
            # A leading '=' or comparison inside a function call is not a relation
            if is_relation and not any(f in text for f in ("<=", ">=")):
                is_relation = "=" in text and not text.strip().startswith("=")

            result = (solver.solve_equation(text, matrices) if is_relation
                      else solver.evaluate(text, matrices))

            if result["ok"]:
                result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
            return _normalise(result)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "result": ""}

    def solve_equation(self, equation: str, matrices: dict | None = None) -> dict:
        try:
            return _normalise(_mod("solver").solve_equation(equation, matrices))
        except Exception as exc:
            return {"ok": False, "error": str(exc), "result": ""}

    def solve_system(self, equations: list[str]) -> dict:
        if not isinstance(equations, list) or len(equations) < 2:
            return {"ok": False, "error": "ExprError.need_two_equations", "result": ""}
        try:
            return _normalise(_mod("solver").solve_system([str(e) for e in equations[:8]]))
        except Exception as exc:
            return {"ok": False, "error": str(exc), "text": "", "latex": None}

    # ------------------------------------------------------------- matrices
    def matrix_op(self, operation: str, first, second=None, extra: str = "") -> dict:
        """
        Run a matrix operation on grids.

        Accepts grids (preferred) or legacy ``"1 2; 3 4"`` strings.
        """
        try:
            module = _mod("matrix")

            left = module.from_text(first) if isinstance(first, str) else module.to_matrix(first)
            right = None
            if second is not None:
                right = (module.from_text(second) if isinstance(second, str)
                         else module.to_matrix(second))

            if operation in ("det", "rank", "trace", "eigen", "eigenvec", "lu"):
                result = module.run(operation, module.to_grid(left))
            elif operation in ("inv", "transpose"):
                result = module.run(operation, module.to_grid(left))
            elif operation in ("multiply", "add", "subtract", "system"):
                if right is None:
                    return {"ok": False, "error": "ExprError.need_second_matrix"}
                result = module.run(operation, module.to_grid(left), module.to_grid(right))
            elif operation in ("scalar", "power"):
                result = module.run(operation, module.to_grid(left), None, extra)
            else:
                return {"ok": False, "error": f"ExprError.unknown_operation:{operation}"}

            return {"ok": True, **result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------- calculus
    def calculus(self, kind: str, expression: str, a: str = "",
                 b: str = "", direction: str = "both") -> dict:
        try:
            result = _mod("calculus").run(kind, expression, a, b, direction)
            return {"ok": True, **result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def analyze(self, expression: str, interval=None) -> dict:
        try:
            bounds = None
            if interval and len(interval) == 2:
                bounds = (float(interval[0]), float(interval[1]))
            report = _mod("analysis").full_report(expression, bounds)
            return {"ok": True, **report}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def limit(self, expression: str, point: str, direction: str = "both") -> dict:
        try:
            result = _mod("analysis").limit_at_point(expression, point, direction)
            return {"ok": True, **result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------- plotting
    def plot(self, equations: list[str], x_min: float, x_max: float,
             points: int = 1200) -> dict:
        try:
            data = _mod("grapher").sample(equations, x_min, x_max, points)
            return {"ok": True, **data}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def autoscale(self, equations: list[str], x_min: float, x_max: float) -> dict:
        try:
            return {"ok": True, **_mod("grapher").autoscale(equations, x_min, x_max)}
        except Exception:
            return {"ok": False, "y_min": -10.0, "y_max": 10.0}

    # ------------------------------------------------------------- named matrices
    def matrix_list(self) -> dict:
        """Saved matrices for the carousel."""
        try:
            registry = _mod("registry")
            from ..core.registry import LETTERS

            return {"ok": True, "items": registry.describe(), "letters": list(LETTERS)}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "items": []}

    def matrix_save(self, name: str, grid: list) -> dict:
        """Store a grid under a letter A..H. Every cell is validated first."""
        try:
            return {"ok": True, **_mod("registry").put(name, grid)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def matrix_delete(self, name: str) -> dict:
        try:
            return {"ok": _mod("registry").delete(name)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def matrix_get(self, name: str) -> dict:
        try:
            grid = _mod("registry").grid(name)
            if grid is None:
                return {"ok": False, "error": f"ExprError.matrix_missing:{name}"}
            return {"ok": True, "name": name.upper(), "grid": grid}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------- display forms
    def cycle_form(self, expression: str, current: str = "auto") -> dict:
        """Re-format an answer in the next available representation.

        The value is parsed again, then ``cycle`` moves to the following form:
        exact, decimal, scientific, mixed or radical. Recomputation keeps the
        result exact instead of re-parsing a rounded display string.
        """
        try:
            fmt = _mod("format")
            solver = _mod("solver")
            parser = _mod("parser")
            registry = _mod("registry")

            # Passing the raw grids (not SymPy objects) is what parse() expects
            grids = {name: registry.grid(name) for name in registry.names()} or None

            base = solver.evaluate(expression, matrices=grids)
            if not base.get("ok"):
                return base

            value = parser.parse(expression, matrices=grids)
            available = fmt.forms(value)
            if not available:
                return {"ok": True, "latex": base.get("latex"), "plain": base.get("text", ""),
                        "key": "exact", "forms": []}

            # ``current`` comes from the page. Falling back to the automatic key
            # restarted the cycle on every press, so ALT kept landing on the
            # same alternative instead of returning to the original form.
            start = current if current and current != "auto" else (
                base.get("form_key") or fmt.best(value)["key"])
            nxt = fmt.cycle(value, start)
            return {"ok": True, "latex": nxt["latex"], "plain": nxt["plain"],
                    "key": nxt["key"], "forms": available}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------- step-by-step
    def steps(self, expression: str, kind: str = "auto",
              extra: list[str] | None = None) -> dict:
        """Worked solution: numbered steps, each with plain text and LaTeX.

        ``extra`` carries the remaining equations when ``kind="system"``, so a
        two-equation system can be shown as Gaussian elimination rather than
        two unrelated answers.
        """
        try:
            return _mod("stepwise").steps(expression, kind or "auto", extra or [])
        except Exception as exc:
            return {"ok": False, "error": str(exc), "steps": []}

    # ------------------------------------------------------------- export files
    def _ask_save_path(self, default_name: str, file_types: tuple) -> str | None:
        """Native save dialog. Falls back to the documents folder when no GUI."""
        try:
            import tkinter
            from tkinter import filedialog

            root = tkinter.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.asksaveasfilename(
                initialfile=default_name, filetypes=list(file_types),
                defaultextension=Path(default_name).suffix)
            root.destroy()
            return path or None
        except Exception:                  # headless or tkinter missing
            from ..core.settings import data_dir

            fallback = data_dir() / "exports" / default_name
            fallback.parent.mkdir(parents=True, exist_ok=True)
            return str(fallback)

    def export_pdf(self, kind: str, payload: dict, filename: str = "") -> dict:
        """Render the current solution as a PDF the student can submit."""
        try:
            exporter = _mod("exporter")
            name = filename or f"{kind or 'solution'}.pdf"
            if not name.lower().endswith(".pdf"):
                name += ".pdf"

            target = self._ask_save_path(name, (("PDF", "*.pdf"),))
            if not target:
                return {"ok": False, "cancelled": True}

            data = exporter.to_pdf(payload if isinstance(payload, dict) else {})
            exporter.write(Path(target), data)
            return {"ok": True, "path": target, "bytes": len(data)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def export_latex(self, kind: str, payload: dict, filename: str = "") -> dict:
        """Write a compilable .tex document for the current solution."""
        try:
            exporter = _mod("exporter")
            name = filename or f"{kind or 'solution'}.tex"
            if not name.lower().endswith(".tex"):
                name += ".tex"

            target = self._ask_save_path(name, (("LaTeX", "*.tex"),))
            if not target:
                return {"ok": False, "cancelled": True}

            text = exporter.to_latex(payload if isinstance(payload, dict) else {})
            exporter.write(Path(target), text)
            return {"ok": True, "path": target, "bytes": len(text)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------- hardware and settings
    def hardware(self, force: bool = False) -> dict:
        """
        Machine profile. Cached in settings: re-probing on every launch is waste.
        ``force=True`` only behind the explicit "detect again" button.
        """
        try:
            settings = _mod("settings")
            if not force:
                cached = settings.load().get("hardware")
                if cached:
                    return {"ok": True, "cached": True, **cached}

            started = time.perf_counter()
            hardware = _mod("hardware")
            profile = hardware.recommend()
            profile["probe_ms"] = round((time.perf_counter() - started) * 1000)
            settings.save({"hardware": profile})
            return {"ok": True, "cached": False, **profile}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def shutdown(self) -> dict:
        """Release everything this session owns.

        Ollama keeps a model resident in RAM; leaving it running after the
        window closes makes the whole machine sluggish.
        """
        result: dict = {}
        try:
            llm = _mod("llm")
            result["ollama"] = llm.stop_server()
        except Exception as exc:                  # noqa: BLE001 - exit path
            result["ollama"] = {"stopped": False, "error": str(exc)}
        return {"ok": True, **result}

    def reference(self, query: str = "", area: str = "",
                  level: str = "") -> dict:
        """Theorem and formula reference, filtered by area, level and text."""
        try:
            module = _mod("reference")
            found = module.search(query, area, level)
            return {
                "ok": True,
                "entries": found,
                "areas": module.areas(),
                "total": len(module.ENTRIES),
                "shown": len(found),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "entries": []}

    def model_catalogue(self) -> dict:
        try:
            return {"ok": True, "models": _mod("hardware").catalogue()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def settings_get(self) -> dict:
        try:
            return {"ok": True, **_mod("settings").load()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def settings_set(self, patch: dict) -> dict:
        try:
            return _mod("settings").save(patch)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------- Ollama
    def ollama_stop(self) -> dict:
        """Stop the Ollama service if this session started it.

        Called from the window's close handler. Stopping only a server the app
        launched means a service the user was already running is left untouched.
        """
        try:
            llm = _mod("llm")
            result = llm.stop_server()
            return {"ok": True, **result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def ollama_delete(self, model: str) -> dict:
        """Remove a downloaded model and its disk footprint.

        Models run from a few hundred megabytes to several gigabytes; without
        this the only way to reclaim the space was a terminal.
        """
        if not model:
            return {"ok": False, "error": "ExprError.no_model"}
        try:
            llm = _mod("llm")
            result = llm.delete_model(model)
            if not result.get("ok"):
                return result

            # If the deleted model was the active one, fall back to whatever
            # remains installed so the assistant keeps working.
            settings = _mod("settings")
            config = settings.load()
            if config.get("model") == model:
                remaining = [m.name for m in llm.list_models()]
                settings.save({"model": remaining[0] if remaining else ""})
                result["fallback_model"] = remaining[0] if remaining else ""

            result["model"] = model
            return result
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def ollama_status(self) -> dict:
        try:
            return {"ok": True, **_mod("llm").status()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def ollama_install(self) -> dict:
        return self._background("ollama_install",
                                lambda llm: llm.install_windows(
                                    on_progress=lambda p: self._emit("onService", p)),
                                "onServiceDone")

    def ollama_start(self) -> dict:
        def task(llm):
            llm.start_server(on_progress=lambda p: self._emit("onService", p))
            return {"ok": True, "text": "ok"}
        return self._background("ollama_start", task, "onServiceDone")

    def ollama_pull(self, model: str) -> dict:
        if not model:
            return {"ok": False, "error": "ExprError.no_model"}

        def task(llm):
            llm.pull(model, on_progress=lambda p: self._emit("onPull", p),
                     should_stop=self._stop.is_set)
            return {"ok": True, "model": model}
        return self._background("ollama_pull", task, "onPullDone")

    def setup_all(self, model: str) -> dict:
        """Install service, start it and download the model in one action."""
        if not model:
            return {"ok": False, "error": "ExprError.no_model"}

        def task(llm):
            if not llm.is_installed():
                self._emit("onService", {"stage": "install", "text": "installing"})
                installed = llm.install_windows(
                    on_progress=lambda p: self._emit("onService", p))
                if not installed.get("ok"):
                    return {"ok": False, "text": installed.get("text")}

            llm.start_server(on_progress=lambda p: self._emit("onService", p))

            if not llm.has_model(model):
                self._emit("onService", {"stage": "model", "text": model})
                llm.pull(model, on_progress=lambda p: self._emit("onPull", p),
                         should_stop=self._stop.is_set)

            return {"ok": True, "text": model}
        return self._background("setup_all", task, "onSetupDone")

    def _background(self, name: str, task, done_event: str) -> dict:
        """Run ``task`` in a worker thread, reporting the outcome as an event."""
        if self._busy.is_set():
            return {"ok": False, "error": "ExprError.busy"}

        self._busy.set()
        self._stop.clear()

        def runner() -> None:
            try:
                result = task(_mod("llm"))
            except Exception as exc:
                result = {"ok": False, "text": str(exc), "error": str(exc)}
            finally:
                self._busy.clear()
            self._emit(done_event, result)

        threading.Thread(target=runner, name=name, daemon=True).start()
        return {"ok": True, "started": True}

    # ------------------------------------------------------------- AI chat
    def ai_ask(self, task: str, image_b64: str | None = None,
               model: str | None = None,
               conversation: str = "default") -> dict:
        """
        Ask the local model.

        The question is first matched against the theorem reference; the best
        entries are prepended to the system prompt as grounding. A small local
        model invents formulas when it has to recall them, and cannot be trusted
        with, say, the exact statement of Vieta's theorem — but it quotes a
        provided formula correctly. The matched entries are also sent to the
        interface, which shows them under the answer.

        History is per conversation, so tabs stay independent.
        """
        if self._busy.is_set():
            return {"ok": False, "error": "ExprError.busy"}
        if not task or not task.strip():
            return {"ok": False, "error": "ExprError.empty"}

        # Obvious harmful requests are declined here, before a small local
        # model is asked to refuse on its own. The check is narrow on purpose:
        # a maths question that mentions a sensitive word still goes through.
        guard = _mod("guard")
        refusal = guard.check(task)
        if refusal:
            # Self-harm is not a policy violation: it gets its own message,
            # with a suggestion to talk to someone, not a terse "I can't".
            self._emit("onAiDone", {
                "tokens": 0, "elapsed_s": 0, "tokens_per_s": 0,
                "stopped": False, "answer": refusal, "refused": True,
                "care": guard.is_care(refusal),
            })
            return {"ok": True, "refused": True}

        self._busy.set()
        self._stop.clear()
        chat = self._chat_for(conversation)

        def runner() -> None:
            started = time.perf_counter()
            tokens = 0
            chunks: list[str] = []
            try:
                settings = _mod("settings")
                llm = _mod("llm")
                config = settings.load()
                chosen = model or config.get("model") or "qwen2.5:7b"
                temperature = float(config.get("temperature", 0.3))

                if not llm.is_running() and not llm.start_server():
                    self._emit("onAiError", {"error": "ExprError.ollama_down"})
                    return
                if not llm.has_model(chosen):
                    self._emit("onAiError", {"error": "ExprError.model_missing",
                                             "needs_pull": chosen})
                    return

                language = config.get("language", "en")

                # Decide what is being asked, cheapest layer first:
                # lexical phrases (7 ms) -> model classifier (~2 s) -> ask back.
                # A wrong card teaches the reader to distrust the panel, so the
                # pipeline would rather ask than guess.
                reference = _mod("reference")
                resolver = _mod("intent")

                lexical = reference.rank(task, limit=4)
                decision = resolver.resolve(task, chosen, lexical)

                matched = decision["entries"]
                intent = decision["intent"]

                if intent == "clarify":
                    # No theory found and the model is not sure what is wanted.
                    # Ask the user to narrow it down instead of inventing an
                    # answer and a card to go with it. The question is dropped
                    # from history: a follow-up must not inherit a message the
                    # assistant declined to interpret.
                    chat.clear()
                    self._emit("onAiDone", {
                        "tokens": 0, "elapsed_s": 0, "tokens_per_s": 0,
                        "stopped": False, "answer": "ai.clarify",
                        "clarify": True,
                    })
                    return

                extra_system = ""
                if matched:
                    extra_system = (
                        "\n\nREFERENCE (authoritative; use these exact formulas "
                        "whenever they apply, do not restate them differently):\n"
                        + reference.as_prompt_context(matched)
                    )

                # The expected shape of the answer differs: a theorem needs a
                # statement and a use case, an exercise needs working.
                if intent == "theory":
                    extra_system += (
                        "\n\nINTENT: the user asks what this is, not for a "
                        "specific problem. Give: the statement, when it applies, "
                        "and one short worked example. Do not invent numbers the "
                        "user did not supply."
                    )

                message: dict = {"role": "user", "content": task.strip()}
                if image_b64:
                    if llm.supports_vision(chosen):
                        message["images"] = [image_b64]
                    else:
                        message["content"] += "\n\n[vision unsupported]"

                chat.append(message)
                self._emit("onAiStart", {
                    "model": chosen,
                    "conversation": conversation,
                    "intent": intent,
                    "source": decision["source"],
                    # The interface renders these as formula cards beside the answer
                    "theory": [
                        {"id": e["id"], "title": e["title"], "latex": e["latex"],
                         "example": e["example"], "area": e["area"],
                         "level": e["level"]}
                        for e in matched
                    ],
                })

                # A fresh guard, or the previous answer's last lines would
                # count towards this one's repeat window.
                llm.reset_loop_guard()

                # Masked per chunk: the user's own wording can come back in the
                # reply, and an obscenity inside a maths answer reads as a bug.
                # Masking here rather than at render time means the text stored
                # in history and copied out is already clean.
                for raw_piece in llm.chat_stream(chosen, chat, temperature,
                                                 should_stop=self._stop.is_set,
                                                 language=language,
                                                 extra_system=extra_system):
                    piece = guard.mask_profanity(raw_piece)
                    tokens += 1
                    chunks.append(piece)
                    self._emit("onToken", {"text": piece})
                    if tokens % 20 == 0:
                        elapsed = max(time.perf_counter() - started, 1e-6)
                        self._emit("onStats", {
                            "tokens": tokens,
                            "elapsed_s": round(elapsed, 1),
                            "tokens_per_s": round(tokens / elapsed, 1),
                        })

                # Mask the finished text as a whole. Masking each streamed
                # chunk misses a word split between two chunks ("ху" + "йня"),
                # so the stored and copied text is cleaned here as well.
                answer = guard.mask_profanity("".join(chunks))
                chat.append({"role": "assistant", "content": answer})

                elapsed = max(time.perf_counter() - started, 1e-6)
                self._emit("onAiDone", {
                    "tokens": tokens,
                    "elapsed_s": round(elapsed, 1),
                    "tokens_per_s": round(tokens / elapsed, 1),
                    "stopped": self._stop.is_set(),
                    "answer": answer,
                })
            except Exception as exc:
                text = str(exc)
                # A repetition guard is not a failure of the program: the
                # partial answer already streamed, so say what happened.
                if "ai_looping" in text:
                    self._emit("onAiDone", {
                        "tokens": len(chunks),
                        "elapsed_s": round(max(time.perf_counter() - started, 1e-6), 1),
                        "tokens_per_s": 0,
                        "stopped": True,
                        "answer": "".join(chunks),
                        "looping": True,
                    })
                    return
                self._emit("onAiError", {"error": text})
                if chat and chat[-1].get("role") == "user":
                    chat.pop()
            finally:
                self._busy.clear()

        threading.Thread(target=runner, name="ai", daemon=True).start()
        return {"ok": True}

    def ai_stop(self) -> dict:
        self._stop.set()
        return {"ok": True}

    def ai_reset(self, conversation: str = "default") -> dict:
        """Clear one conversation, leaving the others untouched."""
        self._chat_for(conversation).clear()
        return {"ok": True, "conversation": conversation}

    # ------------------------------------------------------------- files
    def pick_image(self) -> dict:
        """Open the OS file dialog for an image. Falls back to a hint."""
        try:
            import tkinter
            from tkinter import filedialog

            root = tkinter.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"),
                           ("All files", "*.*")])
            root.destroy()
            if not path:
                return {"ok": False, "cancelled": True}
            return {"ok": True, "path": path}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


    def open_models_dir(self) -> dict:
        """Open the folder where Ollama keeps downloaded models.

        Ollama honours ``OLLAMA_MODELS``; without it the default location is
        ``~/.ollama/models``. The folder is created if it does not exist yet, so
        the button works before the first download.
        """
        import os
        import sys
        from pathlib import Path

        try:
            override = os.environ.get("OLLAMA_MODELS", "").strip()
            if override:
                directory = Path(override).expanduser()
            else:
                directory = Path.home() / ".ollama" / "models"
            directory.mkdir(parents=True, exist_ok=True)

            if sys.platform == "win32":
                os.startfile(str(directory))         # noqa: S606
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", str(directory)])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(directory)])
            return {"ok": True, "path": str(directory)}
        except Exception as exc:                     # noqa: BLE001 - reported to UI
            return {"ok": False, "error": str(exc)}

    def open_data_dir(self) -> dict:
        import os

        try:
            directory = _mod("settings").data_dir()
            directory.mkdir(parents=True, exist_ok=True)
            if hasattr(os, "startfile"):
                os.startfile(str(directory))     # noqa: S606
            return {"ok": True, "path": str(directory)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


__all__ = ["Api"]
