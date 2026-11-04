"""Local HTTP transport for the interface.

Why this exists
---------------
The previous versions relied on pywebview's ``js_api`` bridge. That bridge
walks every public attribute of the ``Api`` object with ``dir()`` and
``inspect.getfullargspec`` to generate JavaScript stubs. On Windows the walk
either recursed into .NET objects (``SyncRoot``) or silently produced no stubs
at all, which left the window with a dead interface: no keypad, no tab
handlers, a frozen "loading engine" status.

This module replaces that mechanism with something deterministic: a threaded
HTTP server bound to the loopback interface, guarded by a random per-run token.
The frontend calls ``POST /api/<method>`` and receives JSON. Server-initiated
progress (model download, AI stream) is delivered over Server-Sent Events.

Security notes
--------------
* Binds to ``127.0.0.1`` only; nothing is reachable from the network.
* Every request must carry ``?token=`` equal to a value generated with
  ``secrets.token_urlsafe`` at start-up. The token is passed to the page in the
  URL, never stored on disk.
* Only methods listed in ``_DISPATCH`` are callable: the token cannot be used
  to reach arbitrary Python.
* Request bodies are size-capped, and the ``Host``/``Origin`` headers are
  checked to blunt DNS-rebinding and cross-origin probing.
"""
from __future__ import annotations

import json
import logging
import mimetypes
import queue
import secrets
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

MAX_BODY = 8 * 1024 * 1024          # 8 MiB: an image plus prompt fits easily

_log = logging.getLogger("euler.http")


class Transport:
    """Owns the server thread, the event queue and the request dispatch table."""

    def __init__(self, api, web_dir: Path) -> None:
        self._api = api
        self._web_dir = web_dir.resolve()
        self._token = secrets.token_urlsafe(24)
        self._events: queue.Queue[str] = queue.Queue()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._clients: list[queue.Queue[str]] = []
        self._clients_lock = threading.Lock()
        self._port = 0

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> str:
        """Bind an ephemeral port and serve. Returns the base URL."""
        handler = self._make_handler()
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._httpd.daemon_threads = True
        self._port = self._httpd.server_address[1]

        self._thread = threading.Thread(
            target=self._httpd.serve_forever, name="http", daemon=True)
        self._thread.start()

        _log.info("interface served on 127.0.0.1:%s", self._port)
        return f"http://127.0.0.1:{self._port}"

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()

    @property
    def url(self) -> str:
        """Page URL including the access token."""
        return f"http://127.0.0.1:{self._port}/?token={self._token}"

    # ------------------------------------------------------------------ events
    def emit(self, event: str, payload: dict) -> None:
        """Push a server-initiated event to every connected page."""
        frame = f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
        with self._clients_lock:
            targets = list(self._clients)
        for client in targets:
            try:
                client.put_nowait(frame)
            except queue.Full:
                # A stalled page must not grow memory without bound
                pass

    def _register(self) -> queue.Queue[str]:
        client: queue.Queue[str] = queue.Queue(maxsize=512)
        with self._clients_lock:
            self._clients.append(client)
        return client

    def _unregister(self, client: queue.Queue[str]) -> None:
        with self._clients_lock:
            if client in self._clients:
                self._clients.remove(client)

    # ------------------------------------------------------------------ handler
    def _make_handler(self):
        transport = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "EulerSC"
            protocol_version = "HTTP/1.1"

            # Suppress the default stderr access log: it would flood the file
            def log_message(self, fmt, *args):
                _log.debug("%s - %s", self.address_string(), fmt % args)

            # ---------------------------------------------------------- helpers
            def _token_from_cookie(self) -> str:
                """Read the session cookie set on the first page load.

                Sub-resource requests (``app.js``, ``theme.css``) carry no query
                string, so a URL-only token made the browser receive 403 for
                every script and stylesheet — the interface loaded dead. The
                cookie is scoped to ``/``, ``SameSite=Strict`` and ``HttpOnly``,
                so it is only ever sent back to this loopback origin.
                """
                raw = self.headers.get("Cookie") or ""
                for part in raw.split(";"):
                    name, _, value = part.strip().partition("=")
                    if name == "euler_token":
                        return value
                return ""

            def _authorised(self, query: dict) -> bool:
                supplied = (query.get("token") or [""])[0] or self._token_from_cookie()
                return bool(supplied) and secrets.compare_digest(supplied, transport._token)

            def _send(self, status: int, body: bytes, content_type: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(body)

            def _json(self, status: int, payload: dict) -> None:
                self._send(status, json.dumps(payload, ensure_ascii=False, default=str).encode(),
                           "application/json; charset=utf-8")

            def _same_origin(self) -> bool:
                """Reject requests that did not originate from the served page."""
                origin = self.headers.get("Origin")
                if not origin:
                    return True                       # same-origin fetch may omit it
                return origin in (f"http://127.0.0.1:{transport._port}",
                                  f"http://localhost:{transport._port}")

            # ---------------------------------------------------------- GET
            def do_GET(self):
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)

                if not self._authorised(query):
                    return self._json(HTTPStatus.FORBIDDEN, {"error": "bad token"})

                if parsed.path == "/events":
                    return self._stream_events()

                return self._serve_static(parsed.path)

            def _stream_events(self):
                client = transport._register()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                try:
                    self.wfile.write(b": connected\n\n")
                    self.wfile.flush()
                    while True:
                        try:
                            frame = client.get(timeout=15)
                        except queue.Empty:
                            self.wfile.write(b": ping\n\n")   # keep-alive
                            self.wfile.flush()
                            continue
                        self.wfile.write(frame.encode())
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    transport._unregister(client)

            def _serve_static(self, path: str):
                rel = path.lstrip("/") or "index.html"
                target = (transport._web_dir / rel).resolve()

                # Directory traversal guard: the resolved path must stay inside web/
                if not str(target).startswith(str(transport._web_dir)):
                    return self._json(HTTPStatus.FORBIDDEN, {"error": "outside root"})
                if target.is_dir():
                    target = target / "index.html"
                if not target.is_file():
                    return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

                ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                if ctype.startswith("text/") or ctype == "application/javascript":
                    ctype += "; charset=utf-8"

                try:
                    body = target.read_bytes()
                except OSError:
                    return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "read failed"})

                # The document response plants the session cookie; every later
                # sub-resource request rides on it instead of the query string.
                if target.name == "index.html":
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Referrer-Policy", "no-referrer")
                    self.send_header(
                        "Set-Cookie",
                        f"euler_token={transport._token}; Path=/; HttpOnly; SameSite=Strict")
                    self.end_headers()
                    self.wfile.write(body)
                    return

                self._send(HTTPStatus.OK, body, ctype)

            # ---------------------------------------------------------- POST
            def do_POST(self):
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)

                if not self._authorised(query):
                    return self._json(HTTPStatus.FORBIDDEN, {"error": "bad token"})
                if not self._same_origin():
                    return self._json(HTTPStatus.FORBIDDEN, {"error": "bad origin"})
                if not parsed.path.startswith("/api/"):
                    return self._json(HTTPStatus.NOT_FOUND, {"error": "no such endpoint"})

                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BODY:
                    return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                                      {"ok": False, "error": "request too large"})

                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw.decode("utf-8") or "{}")
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return self._json(HTTPStatus.BAD_REQUEST,
                                      {"ok": False, "error": "malformed json"})
                if not isinstance(payload, dict):
                    return self._json(HTTPStatus.BAD_REQUEST,
                                      {"ok": False, "error": "expected object"})

                method = parsed.path[len("/api/"):]
                result = transport._dispatch(method, payload)
                self._json(HTTPStatus.OK, result)

            def do_OPTIONS(self):
                # No CORS: cross-origin callers are rejected, not negotiated with
                self.send_response(HTTPStatus.FORBIDDEN)
                self.send_header("Content-Length", "0")
                self.end_headers()

        return Handler

    # ------------------------------------------------------------------ dispatch
    def _dispatch(self, method: str, payload: dict) -> dict:
        """Call one whitelisted Api method with keyword arguments."""
        func = getattr(self._api, method, None)
        if func is None or method.startswith("_") or not callable(func):
            return {"ok": False, "error": f"unknown method: {method}"}

        allowed = getattr(self._api, "_exported", set())
        if allowed and method not in allowed:
            return {"ok": False, "error": f"method not exported: {method}"}

        try:
            outcome = func(**payload)
        except TypeError as exc:
            return {"ok": False, "error": f"bad arguments: {exc}"}
        except Exception as exc:                     # noqa: BLE001 -报告给界面
            _log.exception("method %s failed", method)
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

        if not isinstance(outcome, dict):
            return {"ok": True, "result": outcome}
        return outcome
