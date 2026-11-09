# How to run Σuler.SC

## From source (development)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
python run.py
```

The window opens at 960x720, the smallest size the layout supports.

**No window, browser only** — useful for debugging the interface:

```bash
EULER_SERVE_ONLY=1 python run.py
# prints http://127.0.0.1:<port>/?token=...
```

Open that URL in a browser. Every feature works; only the native window is
missing. Press Ctrl+C to stop.

**Dev tools** — right-click and DevTools are disabled by default. Enable them:

```bash
EULER_DEBUG=1 python run.py
```

## From the installer (end users)

Run `EulerSC-Setup.exe`. It installs per-user into
`%LOCALAPPDATA%\Programs\EulerSC`, creates Desktop and Start Menu shortcuts,
and registers an uninstaller. No administrator rights are required.

### Upgrading

Run the installer of a newer release the same way you ran the first one; there
is no separate updater and nothing to uninstall first.

| What you run | What happens |
|---|---|
| newer build over an older one | upgrade — files replaced, your data untouched |
| the same build again | repair — the program files are rewritten |
| an older build over a newer one | refused, with both versions shown |
| any of the above with `/FORCE` | proceeds even when it would downgrade |

The installer records the version it installed in
`HKCU\Software\EulerSC\Version` (next to `InstallDir`), and reads it back on
the next run. That value, not the file dates and not a guess, decides what to
do. The version that an upgrade replaced is kept in `PreviousVersion`, which is
what you want on the phone with support.

Settings, saved matrices and exported files live in `%APPDATA%\EulerSC` and are
never part of the install directory, so an upgrade cannot overwrite them. Only
the uninstaller removes that folder.

If a copy of the application is running during the upgrade, the installer closes
it — Windows will not replace a locked executable, and failing with a sharing
violation is a worse answer than closing a window.

Two installer flavours:

| Build | Requires | Size |
|---|---|---|
| `build.bat` | Python 3.10+ on the target machine | ~120 MB |
| `build.bat bundled` | nothing | ~160 MB |

The bundled flavour ships a private Python 3.10 runtime inside the installer.

## Building the installer

```bash
build.bat              # system-Python flavour
build.bat bundled      # embedded Python runtime
```

Requirements on the build machine: Python 3.10+, NSIS 3.x, and `pip`.
The script installs PyInstaller itself, freezes the app, then calls `makensis`.

On Linux or macOS use `./build/build.sh`; it produces the frozen directory and
skips the Windows-only installer step.

## Where data lives

| Platform | Path |
|---|---|
| Windows | `%APPDATA%\EulerSC\` |
| Linux | `~/.local/share/EulerSC/` |
| macOS | `~/Library/Application Support/EulerSC/` |

Contents: `settings.json` (language, theme, saved matrices, window state) and
`logs/app.log` (rotating, 3 files x 1 MB). Exported PDFs and `.tex` files go to
`exports/` inside that folder unless you pick another location.

## Troubleshooting

**Blank window, no keypad.** The interface is served over loopback HTTP. If a
firewall blocks `127.0.0.1`, the page cannot load its scripts. Allow Python to
listen on localhost, or run with `EULER_SERVE_ONLY=1` and open the printed URL.

**"Bad token" errors.** Each launch generates a new token and passes it in the
URL and a cookie. Opening `index.html` directly from disk does not work by
design: start the app, do not open the file.

**AI tab does nothing.** It needs Ollama. Open Settings and press
"Install everything"; the engine downloads Ollama and the recommended model for
your hardware.

**Slow first launch.** SymPy is imported in a background thread. The status bar
shows elapsed seconds while warming up; the calculator becomes usable in about
a second.

## AI assistant behaviour

The assistant reads three layers before answering, cheapest first:

| Layer | Cost | What it does |
|---|---|---|
| Lexical | ~7 ms | Phrase and keyword match against 145 theorems |
| Classifier | ~2 s | Model picks from a shortlist of real ids |
| Fallback | — | Asks you to rephrase instead of guessing |

A refusal comes from `euler/core/guard.py` and happens before the model is
called, so it is instant and works even when Ollama is not running. Profanity in
an answer is masked (`х***я`), not refused.

**The classifier needs a model.** Without Ollama, lexical matching still works
and the calculator is unaffected; only free-form descriptions stop resolving.

## Testing

```bash
pytest tests/ -q             # 168 unit tests, about fifteen seconds
python tests/sweep_full.py   # 199 end-to-end checks
```

The sweep is the release gate. Run both before packaging.

The runner prints a total of `170 passed`; the 168 above is the same suite
without the two tests in `tests/test_doc_counts.py`, which check these numbers
and exclude themselves so they can be stable. See
[README](README.md#testing) for the full explanation.
