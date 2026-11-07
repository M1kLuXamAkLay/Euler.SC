"""Tests for euler.core.download against a local HTTP server.

The server can drop the connection mid-body, honour HTTP Range requests and
serve a corrupted payload, so resume, checksum and cancel paths are exercised
without the network.
"""
import hashlib
import http.server
import os
import sys
import threading
import unittest
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from euler.core import download as dl  # noqa: E402

PAYLOAD = os.urandom(600 * 1024)
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


class State:
    drop_after = None      # bytes to send before the connection is cut (once)
    corrupt = False        # serve wrong bytes of the right length
    range_ok = True        # honour Range requests
    hits = 0


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence test output
        pass

    def do_GET(self):
        State.hits += 1
        body = PAYLOAD
        if State.corrupt:
            body = bytes(b ^ 0xFF for b in PAYLOAD)
        start = 0
        rng = self.headers.get("Range")
        if rng and State.range_ok and rng.startswith("bytes="):
            start = int(rng[6:].split("-")[0])
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(body)-1}/{len(body)}")
        else:
            self.send_response(200)
        chunk = body[start:]
        self.send_header("Content-Length", str(len(chunk)))
        self.end_headers()
        cut = State.drop_after
        State.drop_after = None
        if cut is not None:
            self.wfile.write(chunk[:cut])
            self.wfile.flush()
            self.connection.shutdown(2)  # abrupt close, client sees short body
            return
        self.wfile.write(chunk)


class DownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/f.bin"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        State.drop_after = None
        State.corrupt = False
        State.range_ok = True
        State.hits = 0
        self.tmp = Path(tempfile.mkdtemp())
        self.target = self.tmp / "file.bin"

    def test_plain_download_is_verified(self):
        dl.fetch(self.url, self.target, sha256=DIGEST, size=len(PAYLOAD), retries=1, timeout=5)
        self.assertEqual(self.target.read_bytes(), PAYLOAD)
        self.assertFalse(dl.partial_path(self.target).exists())

    def test_interrupted_download_resumes_with_range(self):
        State.drop_after = 100 * 1024
        dl.fetch(self.url, self.target, sha256=DIGEST, size=len(PAYLOAD), retries=3, timeout=5)
        self.assertEqual(self.target.read_bytes(), PAYLOAD)
        self.assertGreaterEqual(State.hits, 2)

    def test_server_without_range_restarts_cleanly(self):
        State.drop_after = 100 * 1024
        State.range_ok = False
        dl.fetch(self.url, self.target, sha256=DIGEST, size=len(PAYLOAD), retries=3, timeout=5)
        self.assertEqual(self.target.read_bytes(), PAYLOAD)

    def test_checksum_mismatch_removes_partial(self):
        State.corrupt = True
        with self.assertRaises(dl.DownloadError) as ctx:
            dl.fetch(self.url, self.target, sha256=DIGEST, size=len(PAYLOAD), retries=1, timeout=5)
        self.assertEqual(str(ctx.exception), "ExprError.checksum_mismatch")
        self.assertFalse(self.target.exists())
        self.assertFalse(dl.partial_path(self.target).exists())

    def test_cancel_before_start(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(dl.DownloadCancelled):
            dl.fetch(self.url, self.target, cancel=cancel, retries=1, timeout=5)
        self.assertEqual(State.hits, 0)

    def test_cancel_keeps_partial_for_resume_not_final_name(self):
        State.drop_after = 50 * 1024
        cancel = threading.Event()
        # Cancel as soon as the first progress callback fires.
        with self.assertRaises(dl.DownloadCancelled):
            dl.fetch(self.url, self.target, sha256=DIGEST, size=len(PAYLOAD),
                     cancel=cancel, retries=0, timeout=5,
                     on_progress=lambda done, total: cancel.set())
        self.assertFalse(self.target.exists())

    def test_retries_exhausted_raises_download_error(self):
        with self.assertRaises(dl.DownloadError):
            dl.fetch("http://127.0.0.1:1/none", self.target, retries=0, timeout=1)


if __name__ == "__main__":
    unittest.main()
