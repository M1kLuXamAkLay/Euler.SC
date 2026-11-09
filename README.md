<div align="center">

![Σuler.SC](docs/headline.png)

# Σuler.SC

**A symbolic calculator with a local AI tutor. No account, no cloud, no telemetry.**

[![Version](https://img.shields.io/badge/version-5.2.3-c96b7a?style=flat-square)](CHANGELOG.md)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-8f4c56?style=flat-square)](#installation)
[![Python](https://img.shields.io/badge/python-3.10%2B-4b8bbe?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-6fc79a?style=flat-square)](LICENSE.txt)
[![Languages](https://img.shields.io/badge/languages-7-d98a97?style=flat-square)](#interface-languages)
[![Offline](https://img.shields.io/badge/network-loopback%20only-4a3438?style=flat-square)](#privacy)

[Features](#features) · [Installation](#installation) · [AI assistant](#the-ai-assistant) ·
[Building](#building-from-source) · [Changelog](CHANGELOG.md) · [Architecture](ARCHITECTURE.md)

</div>

---

## Why this exists

> **History.** This is the continuation of
> [SmartCalculator](https://github.com/M1kLuXamAkLay/SmartCalculator), which
> went from 1.0.0 to 1.3.0 before the rewrite. Every version since, and why each
> one exists, is in [CHANGELOG.md](CHANGELOG.md).

Most math apps either solve everything for you or nothing at all. This one is
built for the middle of a homework session: type an expression, get an exact
answer in the form a teacher expects, and when a theorem is the actual question
the assistant explains it instead of inventing numbers.

It runs entirely on your machine. The only network call is to a language model
running locally on `127.0.0.1`.

## Features

<table>
<tr>
<td width="50%" valign="top">

### 🧮 Calculator

- Exact arithmetic through SymPy — no floating-point drift
- Results pick the readable form automatically: `11/2` shows as `5½`,
  `sqrt(125)` as `5√5`, `0.000012345` as `1.2345×10⁻⁵`
- **ALT** cycles representations: exact, decimal, scientific, mixed, radical
- Named matrices `A`–`H` persist between sessions
- Three keyboard layouts (functions, analysis, equations)

</td>
<td width="50%" valign="top">

### 📈 Analysis

- Limits — two-sided and one-sided, with the working shown
- Derivatives up to order 10
- Indefinite and definite integrals
- Domain, range, asymptotes, extrema, monotonicity, inflection
- Live graph with pan and zoom, plus a fullscreen view
- Grid steps follow a 1/2/5 sequence at any zoom level
- **Annotate the graph by hand.** The fullscreen view is a drawing surface: pen,
  straight line, arrow, dashed line, rectangle, circle, text, and a point that
  labels itself with its own coordinates. The select tool frames any stroke with
  eight handles and a rotation knob, so a note can be moved, resized and turned
  into place after it is drawn. Strokes live in graph coordinates, not screen
  pixels — zoom in and the ink grows and stays on the curve it marks. The eraser
  rubs along the drag and cuts freehand ink where it passes, leaving the rest;
  `Ctrl+Z` undoes any edit, including an erase. Tools bind to the left or right
  mouse button independently, as in a paint program: left-click a tool for the
  left button, right-click for the right. Annotations are included in the
  exported PDF.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🤖 AI assistant

- Runs on [Ollama](https://ollama.com) — local, offline, no API key
- **145 theorems and formulas** as grounding, so formulas are quoted, not recalled
- Describes a theorem in your own words — even with typos — and it finds it
- Conversation tabs with independent histories
- Streaming answers, `Enter` to send

</td>
<td width="50%" valign="top">

### 🛡️ Safety and privacy

- Refuses requests for weapons, drugs, malware, violence, and child sexual content
- Self-harm gets a helpline message, not a lecture
- Masked profanity rather than refusals — you came here for mathematics
- Nothing leaves the machine: no accounts, no analytics, no remote calls

</td>
</tr>
</table>

## Installation

### Windows — installer

Download `EulerSC-Setup.exe` from [Releases](../../releases) and run it.

- Installs per-user into `%LOCALAPPDATA%\Programs\EulerSC`
- **Upgrading is the same download.** Run a newer `EulerSC-Setup.exe` over the
  installed copy: it reads the version already on the machine and shows you
  both numbers before touching a file. Settings, saved matrices and exports are
  kept — they live in `%APPDATA%\EulerSC`, not in the install directory.
  Running the same version repairs the program files; running an older one is
  refused unless you pass `/FORCE`
- **No administrator rights**, no UAC prompt
- Creates Desktop and Start Menu shortcuts
- Registers in *Apps & features* with a working uninstaller
- Uninstalling removes app data; Ollama and its models are offered separately,
  because re-downloading several gigabytes is a bad surprise

### From source — any platform

```bash
git clone https://github.com/M1kLuXamAkLay/Euler.SC.git
cd Euler.SC
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python run.py
```

Requirements: **Python 3.10+**. On Windows the interface uses WebView2, which
ships with Windows 11 and current Windows 10; the installer offers a download
link if it is missing.

## The AI assistant

Optional. The calculator works fully without it.

```mermaid
flowchart LR
    Q([Your question]) --> G{Guard}
    G -->|harmful| R[Refusal]
    G -->|fine| L[Lexical match<br/>~7 ms]
    L -->|found| A[Answer + theory card]
    L -->|miss| C[Model classifier<br/>~2 s]
    C -->|confident| A
    C -->|unsure| U[Ask to rephrase]
```

Three layers, cheapest first. The model is slow on small hardware, so it only
sees what keyword matching could not resolve.

**Grounding.** Before answering, the question is matched against 145 theorems.
The best entries go into the system prompt as authoritative text, and are
rendered as cards under the answer. A 0.5B model quotes a supplied formula
correctly and invents one badly — that is the whole reason for the reference.

**Models.** The assistant picks a model that fits your hardware on first launch.

| Model | Size | RAM needed | Notes |
|---|---:|:---:|---|
| `qwen2.5:0.5b` | 400 MB | 2 GB | Fastest, weakest reasoning |
| `qwen2.5:3b` | 2 GB | 6 GB | Good balance for a laptop |
| `qwen2.5:7b` | 4.7 GB | 12 GB | Best answers, needs a GPU or 16 GB |
| `llava:7b` | 4.7 GB | 12 GB | Photographs of tasks (vision) |

Models are downloaded from Ollama, not from this project. Settings has a
**Delete model** button, because otherwise reclaiming the disk space needs a
terminal.

## Building from source

<table>
<tr><th align="left">Command</th><th align="left">Produces</th><th align="left">Requires</th></tr>
<tr>
<td><code>build.bat</code></td>
<td>Installer, ~120 MB</td>
<td>Python 3.10+ on the target machine</td>
</tr>
<tr>
<td><code>build.bat bundled</code></td>
<td>Installer, ~160 MB</td>
<td>Nothing — ships a private Python runtime</td>
</tr>
<tr>
<td><code>./build/build.sh</code></td>
<td>Frozen directory</td>
<td>macOS / Linux; skips the Windows installer</td>
</tr>
</table>

Build machine needs Python 3.10+, `pip`, and [NSIS 3.x](https://nsis.sourceforge.io)
for the installer step. The script installs PyInstaller itself.

```bash
build.bat bundled          # Windows, self-contained installer
./build/build.sh           # macOS / Linux
```

## Tech stack

<div align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SymPy](https://img.shields.io/badge/SymPy-3B5526?style=for-the-badge&logo=sympy&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)

</div>

| Layer | Choice | Why |
|---|---|---|
| Algebra | [SymPy](https://www.sympy.org) | Exact results; no numeric drift in `11/2` |
| Numerics | [NumPy](https://numpy.org) | Plot sampling only |
| Window | [pywebview](https://pywebview.flowrl.com) | Native shell around the system WebView; no Electron |
| Formulas | [MathLive](https://mathlive.io) | Editable LaTeX in and out |
| Markdown | [marked](https://marked.js.org) | Small, fast, no framework |
| AI | [Ollama](https://ollama.com) | Local inference, one HTTP port, no keys |
| Fonts | DejaVu Sans | Cyrillic, Greek and CJK in exported PDFs |

No frontend framework. The interface is vanilla JavaScript over a loopback HTTP
server with a per-launch token — which also makes every screen testable in a
plain browser (see `HOW_TO_RUN.md`).

## Interface languages

English · Русский · 中文 · Español · Français · বাংলা · Português

The language chosen in the installer seeds the interface on first launch.
Theorem titles, error messages and the assistant's answers all follow it.

## Data and privacy

| Platform | Settings, logs, exports |
|---|---|
| Windows | `%APPDATA%\EulerSC\` |
| Linux | `~/.local/share/EulerSC/` |
| macOS | `~/Library/Application Support/EulerSC/` |

Contains `settings.json`, `logs/app.log` (rotating, 3 × 1 MB) and `exports/`.

**What leaves your machine:** nothing. The interface is served on `127.0.0.1`
with a token generated per launch. The assistant talks to a model on the same
loopback address. There is no analytics, no crash reporting, and no update
check.

## Testing

```bash
pytest tests/ -q            # 168 unit tests
python tests/sweep_full.py  # 199 end-to-end checks
```

The sweep covers parsing, solving, calculus, matrices, formatting, the theorem
reference, ranking quality, the request guard and intent classification. It
prints a single `199/199 passed` line, and is run before every release.

**Why 168 and not 170.** The runner reports a total of `170 passed`, while the
commands above say 168. The difference is `tests/test_doc_counts.py`, whose two
tests check the numbers in this documentation against the real suite. It counts
the suite with `--deselect tests/test_doc_counts.py`, so it cannot count itself:
170 collected minus those 2 equals the 168 quoted here. Both numbers are correct
and the check fails if either drifts.

## Project layout

```
euler/
  core/          mathematics, no UI and no network: parser, solver, analysis,
                 calculus, matrix, grapher, format, exporter, reference,
                 intent, guard, llm, download, hardware, settings, registry
  bridge/api     the only callable surface, allow-listed (see docs/API.md)
  transport.py   loopback HTTP, per-launch token, Host check
  main.py        window and lifecycle
app/web/         index.html, app.js, i18n.js, theme.css
build/           PyInstaller spec, NSIS installer, build scripts
docs/            API reference (generated), headline image
tests/           unit tests and the release sweep
tools/           generators: API reference and project tree
```

The full annotated tree is in [ARCHITECTURE.md](ARCHITECTURE.md#directory-structure).

## Contributing

Issues and pull requests are welcome. Before opening a PR:

1. `pytest tests/ -q` and `python tests/sweep_full.py` must pass.
2. A behaviour change needs a test in `tests/sweep_full.py`.
3. `CHANGELOG.md` gets an entry under `[Unreleased]`.

## License

MIT — see [LICENSE](LICENSE.txt). Bundled third-party components and their
licences are listed at the end of that file.

<div align="center">
<sub>Built for students who need to see the working, not just the answer.</sub>
</div>
