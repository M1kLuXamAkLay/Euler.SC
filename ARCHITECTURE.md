# Σuler.SC — Architecture Documentation

**Version:** 5.0.3  
**Last Updated:** 11.04.2026

## Overview

Σuler.SC is a symbolic calculator with AI-powered math assistance. The application runs locally on Windows/macOS/Linux, using Python for computation and a WebView-based UI for presentation.

## Technology Stack

### Backend (Python 3.10+)
- **SymPy** — symbolic computation engine (algebra, calculus, matrices)
- **pywebview** — native window with WebView2/WebKit bridge
- **Ollama** (optional) — local LLM inference for AI assistant
- **NumPy** — numerical operations and plotting

### Frontend (Web)
- **Vanilla JavaScript** — no frameworks, direct DOM manipulation
- **MathLive** — LaTeX equation editor
- **Marked** — Markdown rendering for AI responses
- **KaTeX** — formula rendering in AI chat

### Build & Distribution
- **PyInstaller** — standalone executable creation
- **NSIS** — Windows installer with dependency auto-setup

---

## Directory Structure

```
EulerSC/
├── run.py                  # Entry point: creates window, starts bridge
├── requirements.txt        # Python dependencies
├── euler/
│   ├── core/              # Computation engine (no UI dependencies)
│   │   ├── parser.py      # LaTeX → SymPy AST, security validation
│   │   ├── solver.py      # Equation solving, inequalities
│   │   ├── calculus.py    # Limits, derivatives, integrals
│   │   ├── analysis.py    # Function analysis (domain, extrema, asymptotes)
│   │   ├── matrix.py      # Matrix operations (det, inverse, eigenvalues)
│   │   ├── grapher.py     # Function plotting (data generation only)
│   │   ├── hardware.py    # CPU/RAM/VRAM detection for model recommendation
│   │   ├── llm.py         # Ollama integration (install, pull, inference)
│   │   └── settings.py    # Persistent storage (JSON file)
│   └── bridge/
│       └── api.py         # Python↔JS bridge, exposes methods to UI
├── app/
│   ├── main.py            # Window creation, native menu, lifecycle
│   └── web/
│       ├── index.html     # UI structure (7 tabs)
│       ├── app.js         # UI logic (1751 lines, no Cyrillic)
│       ├── i18n.js        # 7-language localization (ru/en/zh/es/fr/bn/pt)
│       ├── theme.css      # Casio fx-991ES PLUS inspired theme
│       ├── fonts/         # Handjet (pixel font), KaTeX fonts
│       └── vendor/        # MathLive, Marked, KaTeX (bundled)
├── assets/
│   └── icon.png           # Application icon
├── tests/
│   └── test_core.py       # 28 unit tests (pytest)
└── build/
    ├── euler.spec         # PyInstaller configuration
    └── installer.nsi      # NSIS installer script
```

---

## Core Architecture

### 1. Security Model

**Threat:** User input comes from UI (typed), OCR (scanned), and LLM (AI-generated) — all untrusted sources.

**Defense Layers:**

1. **Parser (`euler/core/parser.py`)**
   - Blocks dangerous Python calls: `__import__`, `eval`, `exec`, `compile`, `lambda`
   - Blocks attribute access: `().__class__`, `__builtins__`, `__globals__`
   - Regex validation before AST processing
   - Raises `ExprError` with translation key (not raw input)

2. **Preprocessing**
   - Replaces Unicode superscripts/subscripts: `x²` → `x^2`
   - Normalizes multiplication: `2x` → `2*x`, `3(x+1)` → `3*(x+1)`
   - Rejects expressions with forbidden patterns

3. **SymPy Sandboxing**
   - All computation happens in SymPy (safe by design)
   - No `eval()` or `exec()` anywhere in codebase
   - Timeout protection: operations limited to 10 seconds (not yet implemented)

### 2. Transport: why not `js_api`

pywebview's `js_api` mechanism walks the API object with `dir()` and
`inspect.getfullargspec` to generate JavaScript stubs. On Windows that walk:

* recursed into the WebView2 window object, whose .NET members (`.SyncRoot`)
  reference themselves — `maximum recursion depth exceeded`, frozen window;
* or completed but produced no usable stubs, leaving `window.pywebview.api`
  empty. The interface then showed a keypad-less window with inert tabs and a
  status line stuck on "loading engine".

The fix is not a patch on that walk: it is replacing the mechanism.

**Design.** `euler/transport.py` starts a `ThreadingHTTPServer` bound to
`127.0.0.1` on an ephemeral port. The page is loaded from it, not from disk.
JavaScript calls `POST /api/<method>` with a JSON body of keyword arguments and
receives JSON back. Server-initiated progress (model download, AI tokens)
arrives over Server-Sent Events at `GET /events`.

**Security.** Five layers guard the channel:

1. **Loopback only** — bound to `127.0.0.1`; nothing is reachable from a
   network.
2. **Per-launch token** — `secrets.token_urlsafe(24)`, passed in the page URL
   and planted as an `HttpOnly; SameSite=Strict` cookie so sub-resource requests
   (`app.js`, `theme.css`) authenticate without a query string. Without the
   token every request gets `403`.
3. **Method allowlist** — `Api._exported` names the callable methods; the
   dispatcher refuses anything else, so a leaked token cannot reach arbitrary
   Python.
4. **Path containment** — the resolved static path must stay inside `app/web`,
   blocking `../` traversal.
5. **Body cap and origin check** — requests above 8 MiB are rejected, and a
   present `Origin` header must match the server itself.

**Method surface.**

| Method | Parameters | Returns |
|--------|-----------|---------|
| `ready` | — | `{warm, version, methods}` |
| `solve` | `expression`, `matrices?` | `{ok, result, latex, form_key, forms}` |
| `solve_system` | `equations[]` | `{ok, result}` |
| `steps` | `expression`, `kind` | `{ok, title, steps[]}` |
| `calculus` | `kind`, `expression`, `a`, `b`, `direction` | `{ok, title, lines[]}` |
| `analyze` | `expression`, `interval?` | `{ok, function_latex, sections[]}` |
| `matrix_op` | `operation`, `first`, `second?`, `extra?` | `{ok, title, body, grid?}` |
| `matrix_save` / `matrix_get` / `matrix_delete` / `matrix_list` | name / grid | `{ok, ...}` |
| `cycle_form` | `expression` | `{ok, latex, key, forms[]}` |
| `plot` / `autoscale` | `equations[]`, `x_min`, `x_max`, `points` | `{ok, series[]}` |
| `export_pdf` / `export_latex` | `kind`, `payload`, `filename` | `{ok, path}` |
| `ai_ask` / `ai_stop` / `ai_reset` | `task`, `image_b64?`, `model?` | streams via SSE |
| `settings_get` / `settings_set` | `patch?` | `{ok, settings}` |
| `hardware`, `ollama_*`, `setup_all` | — | `{ok, ...}` |

**Positional arguments.** Call sites stay readable (`py('solve', '2+2')`)
because `app.js` keeps a `PARAMS` table mapping method name to parameter names
and converts positional arguments to the keyword object before sending.

### 3. Localization System

**File:** `app/web/i18n.js`

**Supported Languages:** Russian, English, Chinese, Spanish, French, Bengali, Portuguese (146 keys each, programmatically verified for completeness)

**Translation Flow:**

1. **Static HTML**: `data-i18n="key"` → `textContent`, `data-i18n-ph="key"` → `placeholder`
2. **Dynamic JS**: `t('key')` → translated string
3. **After Language Switch**: `I18n.apply()` updates HTML, `retranslateDynamic()` rebuilds keyboards/charts

**Storage:** Language preference saved to `settings.json`, restored on startup

### 4. Matrix Operations

**Input Format:** Grid of `<input>` cells (HTML) → 2D array of strings (JS) → SymPy `Matrix` (Python)

**Operations Returning Matrices:**
- Add `grid` field: `[[str]]` (2D array)
- UI fills grid back into cells via `writeMatrix()`
- User clicks "Result → A" to continue operation chain

**Example:**
```
User fills: A = [1,2; 3,4]
Click "Transpose" → Python returns grid=[['1','3'],['2','4']]
Click "Result → A" → UI writes grid into A cells
Click "Determinant" → det(transposed A) = -2
```

**Why Not `det(A)` Syntax?**  
Template grids are more intuitive for non-programmers. Function syntax would require:
- Variable manager UI (create/delete A/B/C/D)
- Expression parser for nested calls: `inv(A * B)`
- Error handling for undefined variables

Current grid approach: **zero cognitive overhead**, works like a paper worksheet.

### 5. Graph Rendering

**Two Modes:**

1. **Inline Canvas** (Analysis tab): Small, no labels, pan/zoom
2. **Fullscreen Overlay**: Large canvas with:
   - Axis labels (tick values on X/Y)
   - Function name in top-left
   - Controls: Reset view, Auto-fit Y, Close

**Discontinuity Handling:**  
Threshold: if `|y[i] - y[i-1]| > 0.6 * canvas.height`, start new segment (prevents `1/x` drawing line through asymptote)

**Auto-Scale Y:**  
Uses 2nd–98th percentiles of Y values → outliers (infinity at asymptotes) don't flatten the curve

### 6. Persistence

**File:** `~/.euler/settings.json` (Windows: `%APPDATA%\Euler\settings.json`)

**Saved State:**
- `language` — UI language code
- `unit` — DEG or RAD mode
- `model` — selected Ollama model
- `temperature` — LLM temperature (0.0–1.0)
- `onboarding_done` — first-run wizard completed
- `hardware` — cached CPU/RAM/VRAM detection (prevents repeated nvidia-smi calls)
- `last_calc_expr` — last calculator input (restored on startup)
- `last_analysis_fn` — last analyzed function
- `last_calculus_fn` — last calculus function
- `graph_view` — last pan/zoom state `{xMin, xMax, yMin, yMax}`

**Restoration:** Called in `loadSettings()` after bridge ready, before first render

---

## Build Process

### Development

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

### Testing

```bash
pytest tests -v
```

**Coverage:** 28 tests, focus on:
- Security (blocked expressions)
- Parser (LaTeX → SymPy)
- Solver (equations, systems, inequalities)
- Matrix operations (all operations)
- Calculus (limits, derivatives, integrals)

### Standalone Executable

```bash
pyinstaller build/euler.spec
```

**Output:** `dist/Euler.SC.exe` (Windows) or `dist/Euler.SC` (macOS/Linux)

**Hidden Imports:**
```python
hiddenimports=[
    'sympy',
    'numpy',
    'webview',
    'markupsafe',
    'jinja2',
]
```

**Data Files:**
```python
datas=[
    ('app/web', 'web'),  # HTML/CSS/JS
    ('assets', 'assets'),  # Icon
]
```

### Installer (Windows)

**Tool:** NSIS (Nullsoft Scriptable Install System)

**Script:** `build/installer.nsi`

**Features:**
- Installs to `C:\Program Files\Euler.SC`
- Creates Start Menu shortcut
- Adds uninstaller
- Optional: Auto-install Python dependencies (not yet implemented)

**Build:**
```bash
makensis build/installer.nsi
```

**Output:** `EulerSC-Setup.exe`

---

## Result formatting

`euler/core/format.py` answers one question: given a SymPy value, which
notation reads best?

| Value | Chosen | Alternatives |
|---|---|---|
| `6` | `6` | — |
| `11/2` | `5\frac{1}{2}` | `\frac{11}{2}`, `5.5` |
| `1/3` | `\frac{1}{3}` | `0.333…` (recurring: keep the fraction) |
| `0.25` | `0.25` | `\frac{1}{4}` |
| `\sqrt{125}` | `5\sqrt{5}` | `11.1803…` |
| `\pi` | `\pi` | `3.14159…` (never the default) |
| `1.2345e-5` | `1.2345 \times 10^{-5}` | `0.000012345` |

Rules: integers stay integers; terminating decimals read as decimals; recurring
ones stay exact fractions; radicals stay radicals; extreme magnitudes switch to
scientific. The ALT key cycles through every available form, and the value is
recomputed from the original expression each time, so precision is never lost to
round-tripping a display string.

## Step-by-step solutions

`euler/core/stepwise.py` uses two strategies:

1. **Rule based**, for the shapes a student meets: linear equations, quadratics
   (discriminant), term-by-term differentiation, standard integrals, limits with
   an indeterminacy and a series expansion. Steps are generated explicitly, so
   the output reads like a worked example.
2. **SymPy helpers** (`manualintegrate`, `dsolve` hints) when the rule table has
   no entry; their output is unpacked into numbered steps.

Each step is `{n, text, latex}`: the LaTeX is typeset in the interface, the text
is the short caption ("Compute the discriminant").

## Export

`euler/core/exporter.py` writes both formats without external binaries:

* `.tex` — a complete `\documentclass`…`\end{document}` file, compile with
  pdflatex or drop into Overleaf. Heading follows the interface language.
* `.pdf` — generated directly (page tree, Flate-compressed content stream,
  Helvetica core fonts). LaTeX is converted to readable plain text first:
  `\frac{a}{b}` → `(a)/(b)`, `\sqrt{x}` → `sqrt(x)`, Greek and operators
  transliterated. A brace-matching reader handles nesting, which a regular
  expression cannot.

## Performance Characteristics

| Operation | Typical Time | Bottleneck |
|-----------|--------------|------------|
| Simple equation | 10–30 ms | SymPy parsing |
| Matrix 8×8 determinant | 50–150 ms | SymPy factorization |
| Definite integral | 100–500 ms | SymPy `integrate()` |
| Function analysis | 200–800 ms | Multiple SymPy calls (limit, derivative, solve) |
| Plot 900 points | 50–200 ms | SymPy `lambdify()` + NumPy eval |
| AI response (7B model) | 5–20 s | Ollama inference (10–50 tok/s depending on hardware) |

**Caching:** None currently. Each operation recomputes from scratch. Future: LRU cache for repeated expressions.

---

## Security Considerations

### Input Validation

**Never trust:**
- User-typed expressions
- OCR output (scanned homework)
- LLM-generated code

**Always validate:**
1. Regex pre-filter (blocks Python keywords)
2. AST walk (rejects dangerous nodes)
3. SymPy parsing (safe by design)

### Sandboxing

- No `eval()` or `exec()` in codebase
- SymPy runs in same process (trusted library)
- Ollama runs as separate process (isolated)

### Data Privacy

- All computation happens locally
- No network requests except:
  - Ollama model download (explicit user action)
  - Optional: check for updates (not yet implemented)
- User data never leaves device

---

## Known Limitations

1. **No Multi-Variable Calculus**  
   Partial derivatives, multiple integrals not supported. Reason: UI complexity (3D plots, multiple input fields).

2. **No Equation Graphing in Implicit Form**  
   `x^2 + y^2 = 1` not supported. Workaround: solve for `y`, plot both branches.

3. ~~No step-by-step solutions~~ — implemented for linear/quadratic equations,
   derivatives, integrals and limits (`euler/core/stepwise.py`). Other shapes
   still return only the final answer.

4. **Timeout Not Implemented**  
   Pathological expressions (e.g., `integrate(exp(-x^2)*sin(1/x), x)`) can hang indefinitely. Planned: 10-second timeout with `signal.alarm()` (Unix) or `threading.Timer()` (cross-platform).

5. **Complex numbers in matrix output**  
   Eigenvalues with an imaginary part still print as `(2+3j)`; the formatter
   handles real values only.

6. **PDF uses core fonts only**  
   The generated PDF embeds Helvetica and therefore Latin-1. Cyrillic and CJK
   headings fall back to transliteration. Exporting LaTeX avoids the limit
   entirely, since pdflatex handles the full character set.

---

## Future Roadmap

### Planned Features

- [ ] **Step-by-step solver** (requires SymPy `manualintegrate` or custom engine)
- [ ] **3D plotting** (surface plots, parametric curves)
- [ ] **Dark mode** (auto-detect system preference)
- [ ] **Export to LaTeX/PDF** (homework submission format)
- [ ] **Mobile version** (React Native with Python backend via REST API)

### Performance Improvements

- [ ] Expression caching (LRU, 100 entries)
- [ ] Parallel evaluation (plot multiple functions concurrently)
- [ ] WASM port of SymPy core (eliminate Python startup time)

### Infrastructure

- [ ] CI/CD pipeline (GitHub Actions: test → build → release)
- [ ] Auto-update system (check GitHub releases, download installer)
- [ ] Crash reporting (optional, anonymous, user consent required)

---

## Contributing

**Code Style:**
- Python: PEP 8, type hints (`def solve(expr: str) -> dict`)
- JavaScript: Standard (2-space indent, no semicolons optional)
- Comments: English only (Cyrillic removed in v2.2)

**Testing:**
- All new features must have tests
- Target: 80% coverage (currently ~70%)

**Translation:**
- Add new languages via `i18n.js` (copy `ru` object, translate values)
- Verify completeness: `python scripts/check_i18n.py` (not yet implemented)

---

## License

MIT License. See `LICENSE` file for details.

---

## Support

**Issues:** GitHub Issues (not yet public)  
**Email:** support@euler.sc (placeholder)  
**Documentation:** This file + `HOW_TO_RUN.md`

## Understanding a question

Three layers, cheapest first. The order matters: the model is slow, so it only
sees what the cheap layers could not resolve.

```
1. reference.rank()          phrases + keywords + formula shape       ~7 ms
   confident hit  ──────────────────────────────────────────────►  answer

2. intent.classify()         model picks from a shortlist of real ids  ~2 s
   theory + valid id, confidence >= 0.55 ───────────────────────►  answer

3. neither                   ──────────────────────────────────►  ask the user
```

**Layer 1 — descriptions.** `reference.PHRASES` maps how people actually speak
to entry ids: "квадрат гипотенузы" → `pythagoras`, "вероятность ровно k
успехов" → `bernoulli`. This is not guessing; it is a recognised formulation.

**Layer 2 — the model.** `intent.py` sends a shortlist of plausible ids and
asks for one JSON object: `{"intent", "theorem", "confidence"}`. Ollama is put
in JSON mode, so the reply always parses. Two safeguards make a small model
usable here:

* `_coerce()` drops any id that is not in the shortlist. A 0.5B model invents
  plausible-looking ids; validation turns that from a bug into a miss.
* Below `MIN_CONFIDENCE` a "theory" verdict becomes a question. A wrong card
  teaches the reader to distrust the panel, so the pipeline asks instead.

Results are cached by normalised text, so the same wording costs one model call
in the session, not one per keystroke.

**Layer 3 — asking.** When nothing is certain the user gets "уточните,
пожалуйста" plus two examples of the shape that works. The question is dropped
from history: a follow-up must not inherit a message the assistant declined to
interpret.

### Why not always use the model

A classifier pass costs 1.5–3 s on a 0.5B model running on CPU. Running it
before every answer would make the calculator feel slow to solve `2+2`. The
lexical layer answers most questions in single-digit milliseconds; the model is
reserved for the phrasing nobody anticipated.
