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
import re
import secrets
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

MAX_BODY = 8 * 1024 * 1024          # 8 MiB: an image plus prompt fits easily

_log = logging.getLogger("euler.http")

# Attributes the document needs *before* the first paint. The theme used to be
# applied by app.js after `settings_get` returned, so a user who pinned light
# saw the OS dark scheme for a second and then a repaint. Reading the stored
# choice here and writing it into <html> makes the first frame correct, and
# nothing flickers because nothing changes afterwards.
_BOOT_ATTRIBUTES = re.compile(rb"<html\b([^>]*)>", re.IGNORECASE)


def boot_document(document: bytes) -> bytes:
    """Write the stored theme and language into the <html> tag.

    Everything else in the tag is preserved, including ``data-booting``, which
    the interface removes once its keypad exists. When settings are unreadable
    the document is returned untouched: a corrupt configuration must never stop
    the interface from loading.
    """
    try:
        from .core.settings import load as load_settings

        stored = load_settings()
        theme = str(stored.get("theme") or "auto")
        language = str(stored.get("language") or "")
    except Exception:                            # noqa: BLE001 - never fatal
        _log.debug("boot preferences unavailable", exc_info=True)
        return document

    if theme not in ("light", "dark"):
        theme = "auto"

    def rewrite(match: "re.Match") -> bytes:
        attributes = match.group(1).decode("utf-8", "replace")
        if language:
            attributes = re.sub(r'\slang="[^"]*"', "", attributes)
            attributes += f' lang="{language}"'
        # Replace any hard-coded scheme with the stored one. "auto" means "no
        # attribute", which is what lets the CSS media query follow the OS.
        attributes = re.sub(r'\sdata-theme="[^"]*"', "", attributes)
        if theme != "auto":
            attributes += f' data-theme="{theme}"'
        return f"<html{attributes}>".encode("utf-8")

    replaced, count = _BOOT_ATTRIBUTES.subn(rewrite, document)
    return replaced if count else document


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

            def _host_allowed(self) -> bool:
                """Reject a request addressed to some other host name.

                This is the DNS-rebinding guard: a page on attacker.example can
                resolve its own name to 127.0.0.1, but the browser then sends
                ``Host: attacker.example``, which this refuses. Without it a
                token-less GET still needed the token, but the check costs
                nothing and makes the promise in the module docstring true.
                """
                host = (self.headers.get("Host") or "").strip().lower()
                if not host:
                    return True                       # HTTP/1.0 client, no rebinding risk
                port = transport._port
                return host in (f"127.0.0.1:{port}", f"localhost:{port}",
                                f"[::1]:{port}")

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

                if not self._host_allowed():
                    return self._json(HTTPStatus.FORBIDDEN, {"error": "bad host"})
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

                # Path containment. A plain str.startswith() check accepted a
                # sibling directory such as app/web_secret, because that string
                # also begins with app/web; is_relative_to() compares whole path
                # components.
                if not target.is_relative_to(transport._web_dir):
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

                # The document carries the stored theme and language from the
                # first byte, so it paints once, in the right scheme.
                if target.name == "index.html":
                    body = boot_document(body)

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

                if not self._host_allowed():
                    return self._json(HTTPStatus.FORBIDDEN, {"error": "bad host"})
                if not self._authorised(query):
                    return self._json(HTTPStatus.FORBIDDEN, {"error": "bad token"})
                if not self._same_origin():
                    return self._json(HTTPStatus.FORBIDDEN, {"error": "bad origin"})
                if not parsed.path.startswith("/api/"):
                    return self._json(HTTPStatus.NOT_FOUND, {"error": "no such endpoint"})

                # A malformed header must be a 400, not an unhandled ValueError
                # escaping the request thread and polluting the log.
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                except (TypeError, ValueError):
                    return self._json(HTTPStatus.BAD_REQUEST,
                                      {"ok": False, "error": "bad content-length"})
                if length < 0:
                    return self._json(HTTPStatus.BAD_REQUEST,
                                      {"ok": False, "error": "bad content-length"})
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
