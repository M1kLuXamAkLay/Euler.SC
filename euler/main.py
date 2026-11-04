"""Application entry point.

The window is a WebView2 (or system WebKit) instance driven by pywebview, but
the Python-to-JavaScript channel is *not* pywebview's ``js_api``. That channel
introspects the object with ``dir()`` and produced either infinite recursion
into .NET members or an empty stub list, leaving a dead interface.

Instead the interface is served over a loopback-only HTTP server (see
``euler.transport``) and talks to the engine with plain ``fetch`` calls. This
works identically in a source checkout, in a frozen bundle and in a browser,
which also makes the UI testable without a window.
"""
from __future__ import annotations

import logging
import multiprocessing
import os
import sys
from pathlib import Path

import webview

from .bridge.api import Api
from .transport import Transport


def resource_root() -> Path:
    """Directory holding bundled resources."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def web_root() -> Path:
    """Directory with the frontend.

    Sources keep it in ``app/web``; the PyInstaller spec copies it to
    ``_MEIPASS/web``.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "web"
    return Path(__file__).resolve().parent.parent / "app" / "web"


def setup_logging() -> None:
    """Rotating log file under the application data directory."""
    from logging.handlers import RotatingFileHandler

    from .core.settings import data_dir

    log_dir = data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        root.addHandler(handler)


def configure_webview2() -> None:
    """Harden the WebView2 instance before the window is created."""
    if os.name != "nt":
        return
    try:
        import webview.platforms.edgechromium as edge

        debug = os.environ.get("EULER_DEBUG") == "1"
        edge.EdgeChrome._create_settings = lambda self: {
            "AreDefaultContextMenusEnabled": debug,
            "AreDevToolsEnabled": debug,
            "IsStatusBarEnabled": False,
            "AreBrowserAcceleratorKeysEnabled": debug,
            "IsZoomControlEnabled": True,
        }
    except (ImportError, AttributeError):
        logging.getLogger("euler").debug("WebView2 settings unavailable")


def main() -> int:
    """Serve the interface, open the window, run the event loop."""
    setup_logging()
    log = logging.getLogger("euler")

    index = web_root() / "index.html"
    if not index.exists():
        log.error("interface not found: %s", index)
        return 1

    api = Api()
    transport = Transport(api, web_root())
    base = transport.start()
    api.attach(transport)
    log.info("interface ready at %s", base)

    # Browser-only mode: useful for the automated UI tests and for debugging
    if os.environ.get("EULER_SERVE_ONLY") == "1":
        print(transport.url)
        try:
            threading_event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                api.shutdown()
            except Exception:                     # noqa: BLE001 - exit path
                log.exception("shutdown hook failed")
            transport.stop()
        return 0

    configure_webview2()

    window = webview.create_window(
        "Euler.SC",
        url=transport.url,
        js_api=None,                 # deliberately unused
        width=960,
        height=720,
        min_size=(960, 720),
        background_color="#8f4c56",
        text_select=True,
    )

    def on_closed() -> None:
        # Stop the service first: it holds the model in memory, and the window
        # is already gone so nothing else can do it.
        try:
            api.shutdown()
        except Exception:                         # noqa: BLE001 - exit path
            log.exception("shutdown hook failed")
        transport.stop()

    window.events.closed += on_closed

    try:
        webview.start(gui="edgechromium" if os.name == "nt" else None,
                      debug=os.environ.get("EULER_DEBUG") == "1")
    finally:
        try:
            api.shutdown()
        except Exception:                         # noqa: BLE001 - exit path
            log.exception("shutdown hook failed")
        transport.stop()
    return 0


def threading_event():
    """Block forever without importing threading at module level."""
    import threading

    return threading.Event()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
