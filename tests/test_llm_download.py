import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from euler.core import download as dl
from euler.core import llm


class _OllamaHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    state: dict = {}

    def log_message(self, *args):
        pass

    def do_POST(self):
        st = self.state
        st["pulls"] += 1
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        events = [{"status": "pulling", "total": 1000, "completed": n} for n in range(0, 1001, 250)]
        events.append({"status": "success"})
        if st["drop_first"] and st["pulls"] == 1:
            self._chunk(json.dumps(events[0]).encode() + b"\n")
            self.close_connection = True
            return
        for event in events:
            self._chunk(json.dumps(event).encode() + b"\n")
            time.sleep(st["delay"])
        self.wfile.write(b"0\r\n\r\n")

    def _chunk(self, data: bytes) -> None:
        self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
        self.wfile.flush()


@pytest.fixture
def ollama(monkeypatch):
    _OllamaHandler.state = {"pulls": 0, "drop_first": False, "delay": 0.0}
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _OllamaHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setattr(llm, "HOST", f"http://127.0.0.1:{httpd.server_address[1]}")
    llm.begin_job()
    yield _OllamaHandler.state
    httpd.shutdown()
    httpd.server_close()


def test_pull_retries_after_dropped_stream(ollama):
    ollama["drop_first"] = True
    seen = []
    llm.pull("qwen", on_progress=lambda p: seen.append(p["percent"]))
    assert ollama["pulls"] == 2
    assert seen[-1] == 100


def test_pull_cancel_stops_stream(ollama):
    ollama["delay"] = 0.05

    def cancel_after_first(progress):
        llm.cancel_job()

    with pytest.raises(dl.DownloadCancelled):
        llm.pull("qwen", on_progress=cancel_after_first)
    assert ollama["pulls"] == 1
    llm.begin_job()


def test_abort_all_kills_running_installer_and_returns_quickly():
    result: dict = {}

    def run():
        try:
            llm._run_tracked([sys.executable, "-c", "import time; time.sleep(60)"], timeout=120)
        except dl.DownloadCancelled as exc:
            result["cancelled"] = str(exc)

    llm.begin_job()
    worker = threading.Thread(target=run)
    worker.start()
    time.sleep(0.5)
    started = time.monotonic()
    llm.abort_all()
    worker.join(timeout=10)
    assert not worker.is_alive()
    assert time.monotonic() - started < 5
    assert result == {"cancelled": "ExprError.cancelled"}
    assert not llm._children
    llm.begin_job()


def test_installer_asset_requires_published_checksum(monkeypatch):
    release = {"assets": [{"name": "OllamaSetup.exe", "size": 10,
                           "browser_download_url": "https://example.test/a.exe"}]}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(release).encode()

    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda *a, **k: _Resp())
    with pytest.raises(llm.OllamaError, match="no_checksum"):
        llm._installer_asset()
