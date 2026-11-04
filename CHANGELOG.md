# Changelog

All notable changes to Σuler.SC. Versions follow `MAJOR.MINOR.PATCH`; the
project does not promise backwards compatibility for `settings.json` between
major versions.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

The project has two repositories. The first, [SmartCalculator], covers versions
1.0.0 through 1.3.0 and is kept for the record. From 2.0.0 onward the code
lives here, after a rewrite that replaced the Tkinter interface with a native
window and a WebView.

[SmartCalculator]: https://github.com/M1kLuXamAkLay/SmartCalculator

## [Unreleased]

Nothing yet.

---

## [5.0.3] — 2026-11-04

AI panel layout.

### Changed

- **The model name shows in the AI card header.** The chip beside "Решение с
  ИИ" used to read "—" until an answer had started, and then "Модель: …". It now
  shows the model name alone, set from the saved settings on startup and updated
  when the model changes, when an answer starts, and after a deletion falls back
  to another model. The full label is kept as a tooltip.
- **The input panel sits at the bottom of the card.** An empty status line
  reserved 16 px plus a gap beneath the buttons, which read as dead space. The
  status line is hidden while it is empty, so Photo, New dialog, Stop and Send
  sit at the bottom edge.

---

## [5.0.2] — 2026-11-04

Graph fixes from testing the small card and the fullscreen view.

### Fixed

- **Axis labels changed density while dragging on the small graph.** The
  x-axis label rule skipped any tick closer than 46 px to the previously
  labelled one, so which ticks were labelled depended on where they sat at that
  exact frame. The same axis read every 1 unit at one pixel position and every 2
  at the next, and the labelled set flickered as the mouse moved. The label
  multiple is now chosen once per redraw from the pixel width of one grid step,
  and labels are placed on whole multiples of it. The y-axis had the same rule
  (22 px) and gets the same fix. The label set is now a property of the zoom
  level, not of the drag.
- **Stray element beside the close button in the fullscreen header.** The
  function-title strip used `overflow-x: auto`, which draws a scrollbar whenever
  the typeset formula is wider than its box. It now uses hidden overflow with
  an ellipsis.

### Changed

- **Fullscreen graph uses the whole screen.** The dialog was 96×94 vh with a
  2 px rounded border; it is now 100×100 vh, borderless. The header and the
  control strip lost most of their padding, and the title dropped from 20 px to
  18 px to fit.

### Removed

- Two stale helpers from an intermediate attempt at the label fix. A
  hysteresis-based grid step was tried first; measurement showed the span does
  not change during a pan, so it was removed rather than kept as dead code.

---

## [5.0.1] — 2026-11-04

### Fixed

- **Deleting a model failed** with `ollama_delete() missing 1 required positional
  argument`. The bridge passes arguments by name, and the method was missing from
  the table that maps positional arguments to names, so the model never reached
  the engine.
- A service-status line showed the raw key `settings.running` instead of a
  translation. The engine's message keys are now translated on that path too.

### Changed

- **"Только сервис" renamed to "Скачать сервис".** The button installs the Ollama
  service only, not a model; the old label suggested it did something else.
- **New "Открыть папку моделей" button** next to "Открыть папку данных". It opens
  the folder Ollama stores models in: `OLLAMA_MODELS` if set, otherwise
  `~/.ollama/models`. The folder is created if missing, so it works before the
  first download.

---

## [5.0.0] — 2026-11-04

A rename, and one migration to go with it.

### Changed

- **Package `suler` → `euler`.** The product name keeps the sigma, Σuler.SC, but
  a Greek letter in an import path breaks on case-insensitive filesystems,
  cannot be typed easily, and ends up mangled in URLs. The import name is now
  plain ASCII. This is why the major version moved: anyone importing the old
  name gets an ImportError, and that is better than a silent half-rename.
- **Data directory `SulerSC` → `EulerSC`.** Moved automatically on first launch,
  once. Without it the rename would have quietly reset everyone's language,
  theme and saved matrices.
- **Executable `SulerSC.exe` → `EulerSC.exe`**, publisher `Euler Project`.

### Unchanged

- The interface wordmark stays **Σuler.SC**. That is the brand, and it renders
  fine where a filesystem path would not.
- `settings.json` keeps its format; the file moves, its contents do not change.

---

## [4.8.0] — 2026-11-04

Hardening pass after a real failure: the assistant answered a request for
instructions on killing someone.

### Added

- **Self-harm and violence rules in the guard.** The filter covered weapons,
  drugs and cyber-attacks but had no rule for violence against a person, so
  "как убить" reached the model untouched.
- **Supportive reply for self-harm.** Someone typing "не хочу жить" now gets a
  helpline message in their own language, not a flat refusal with a maths
  advertisement attached.
- **Profanity masking.** Obscenities in a reply are masked (`х***я`), not
  refused: the user came for mathematics. Masked twice — per streamed chunk for
  display, and over the finished text for history, because a word can be split
  between two chunks.
- **Explicit violence prohibition in the system prompt.** The previous wording
  ("help with real-world harm") was too abstract for a 0.5B model, which
  reformatted the request into "questions to consider" with methods inside.

### Fixed

- Idiom `убить время` ("to pass the time") is not a threat and passes through.
- Self-harm rules require the reflexive pronoun, so `как убить` is classified
  as violence rather than a cry for help.

### Metrics

`blocked 17/17`, `allowed 12/12`, `sweep 199 checks`.

---

## [4.7.0] — 2026-10-29

The reference learned to read descriptions, and to admit when it does not know.

### Added

- **`euler/core/intent.py`** — three-layer resolution of what the user wants:
  lexical phrases (7 ms) → model classifier (~2 s) → ask the user.
- **59 description phrases** in `reference.PHRASES`: "квадрат гипотенузы" →
  `pythagoras`, "вероятность ровно k успехов" → `bernoulli`. A description is
  as strong a signal as the theorem's name.
- **JSON-mode classifier.** The model chooses from a shortlist of 14 real ids
  and returns `{intent, theorem, confidence}`. Two safeguards make a 0.5B model
  usable: an id outside the shortlist is dropped, and confidence below 0.55
  turns a verdict into a question.
- **Clarification instead of guessing.** When nothing is certain the interface
  asks the user to rephrase and shows two examples of the shape that works.
- **Intent-specific answer structure.** A theorem gets statement → when it
  applies → example; an exercise gets given → solution → answer.
- **`llm.classify()`** — a separate non-streaming call in JSON mode. Kept apart
  from `chat_stream` so a classification failure can never break an answer.

### Fixed

- Shortlist ranked by raw hit count, so "квадрат" (three occurrences, half of
  algebra) buried "гипотенуз" (one occurrence, one theorem). Now weighted by
  inverse document frequency.

---

## [4.6.0] — 2026-10-24

### Added

- **`euler/core/guard.py`** — a local check for requests the assistant must
  decline: sexual content involving minors, weapons, explosives, drug
  synthesis, attacks on systems the user does not own. Runs before generation,
  so a small model is never asked to refuse on its own judgement.
- **Model deletion** in Settings, with confirmation and automatic fallback to a
  remaining model when the active one is removed.
- **`balanceMath()`** — unclosed delimiters are closed before rendering, so a
  formula streams as a formula instead of flashing as raw LaTeX.

### Fixed

- **Theory attached to any question.** "как дела" returned the one-sided limit
  theorem, because "дела" is a substring of "слева". Ranking now requires exact
  stems, has a score floor, and penalises low coverage.
- Off-topic messages produce no theory card at all.
- Four LaTeX delimiters recognised: `\[...\]`, `$$...$$`, `\(...\)`, `$...$`.
  Only `$` was handled, and the model prefers brackets.
- Scrollbar inside theory cards replaced by a frame that grows to fit.

---

## [4.5.0] — 2026-10-19

### Fixed

- Brand and logo were painted with `--accent-ink`, the colour of text *on* an
  accent fill, which is near-black in the dark theme. A separate `--brand-ink`
  keeps the wordmark visible.
- Dark palette restored to the saturated rose of earlier builds; the keys had
  been desaturated to grey-mauve.
- **Localisation lag.** Three keyboard buttons had no `data-i18n` attribute, and
  the hardware panel is rendered from data with no attribute to walk. Both
  update the moment the language changes now.
- **Graph.** `fitViewToSeries` ran on mouse release and silently undid the
  drag, which is why panning felt like fighting the plot. Removed; pan and zoom
  are pure drawing.
- Equal axis scaling forced the x-range to ±140 for `x³−3x`, collapsing the
  curve into a stripe. Reverted to per-axis fit.

---

## [4.4.0] — 2026-10-12

### Added

- Five analysis theorems lost in the 4.2 rewrite restored: Lagrange, Rolle,
  Cauchy, Fermat, Lipschitz. The reference is now 145 entries (94 school,
  51 university).

### Fixed

- **Fuzzy matching.** Levenshtein distance with radius 1–2 by word length, so
  `пифогор`, `логранжа` and `обьем` find their entries instead of returning
  nothing.
- **Infinite generation.** A small model could latch onto one line and stream
  it forever. Three defences: `num_predict: 900`, `repeat_penalty: 1.18`, and a
  repeat detector that cuts the answer after the third identical line and says
  why.
- Model output was not capped, so a loop ran for minutes.

---

## [4.3.0] — 2026-10-03

### Added

- Reference expanded to 140 entries across 10 areas: algebra, trigonometry,
  plane geometry, solid geometry, limits, derivatives, integrals, series,
  probability, complex numbers. 94 school, 46 university.
- Formula-shape recognition: a bare `x^2-5x+6=0` is recognised as a quadratic
  with no words to match.

---

## [4.2.0] — 2026-09-19

### Added

- **Conversation tabs** in the AI view, each with an independent history on the
  Python side and a close button. Closing the last tab creates a fresh one.
- The theorem reference is attached to the answer that used it, rendered from
  LaTeX under the response.
- 595 translations: 80 theorem titles plus interface strings.

### Removed

- The separate "Справочник" tab. A card index nobody browses is worse than
  theory placed where it is needed.

---

## [4.1.0] — 2026-08-28

### Added

- Ollama is stopped when the window closes — but only a server this app
  started. A service the user was already running is left alone.
- `Enter` sends in the AI box (`Shift+Enter` for a newline) and evaluates in
  both calculators.
- Installer rewritten: language page, licence page, components page, per-user
  install without UAC, and an uninstaller that stops processes *before*
  deleting files, removes app data, and offers to remove Ollama with its
  models.

### Fixed

- The dark theme ignored the calculator body and the language buttons, which
  kept fixed pastels.
- Matrix placeholder `rank(F)` removed; the field takes focus on tab switch.

---

## [4.0.0] — 2026-08-06

### Added

- **Theorem reference** — 60 entries with statement, worked example and
  keywords. Retrieval by relevance, injected into the model prompt as
  authoritative grounding: a small model quotes a supplied formula correctly
  and invents one badly.
- IDF-weighted ranking. Without it "теорема" outweighed "Пифагора" and a
  question about right triangles was answered with the law of sines.

---

## [3.9.0] — 2026-07-14

### Fixed

- Grid step came out at 0.2 on a 21-unit view, turning labels into a smear.
  Step is now derived from the wider span with a 1/2/5 sequence.
- Graph canvas fills its element exactly at any window size, with no
  letterboxing at high DPI.

---

## [3.0.0] — 2026-06-02

### Added

- Function analysis: domain, range, asymptotes, extrema, monotonicity.
- Export to PDF (with embedded Cyrillic-capable font) and to `.tex`.

---

## [2.2.0] — 2026-05-08

### Added

- Seven interface languages with a full translation table.
- Light, dark and auto themes.

---

## [2.0.0] — 2026-04-14

First release with a native window. A rewrite: the Tkinter interface, Matplotlib
canvas and `pix2text` OCR were dropped in favour of a native window around the
system WebView.

### Added

- SymPy-backed calculator with exact arithmetic and five output forms.
- Limits, derivatives, integrals, matrices by name (A–H), equation solving.
- Local AI assistant through Ollama.

### Removed

- Tkinter interface — replaced by pywebview.
- Matplotlib plotting — replaced by a canvas renderer with its own sampler.
- `pix2text` OCR and its PyTorch dependency, roughly 2 GB of wheels. Photographs
  of tasks are handled by a vision model through Ollama instead, which needs no
  separate stack.


---

## Version history at a glance

| Version | Date | Headline |
|---|---|---|
| 5.0.3 | 2026-11-04 | AI panel: model name in the header, input panel at the bottom |
| 5.0.2 | 2026-11-04 | Stable axis labels while dragging, fullscreen uses the whole screen |
| 5.0.1 | 2026-11-04 | Model deletion fixed, service button renamed, models folder button |
| 5.0.0 | 2026-11-04 | Rename: package `euler`, data directory migrated |
| 4.8.0 | 2026-11-04 | Violence and self-harm rules, profanity masking |
| 4.7.0 | 2026-10-29 | Description phrases, LLM classifier, clarify instead of guessing |
| 4.6.0 | 2026-10-24 | Request guard, model deletion, LaTeX streaming |
| 4.5.0 | 2026-10-19 | Brand colour, localisation lag, graph pan |
| 4.4.0 | 2026-10-12 | Fuzzy matching, loop detection, lost theorems |
| 4.3.0 | 2026-10-03 | Reference to 140 entries, formula-shape recognition |
| 4.2.0 | 2026-09-19 | Conversation tabs, theory under answers |
| 4.1.0 | 2026-08-28 | Ollama shutdown, installer rewrite, Enter key |
| 4.0.0 | 2026-08-06 | Theorem reference with retrieval |
| 3.9.0 | 2026-07-14 | Graph grid and canvas sizing |
| 3.0.0 | 2026-06-02 | Function analysis, PDF and TeX export |
| 2.2.0 | 2026-05-08 | Localisation and themes |
| 2.0.0 | 2026-04-14 | Rewrite: native window, WebView, no OCR stack |
| 1.3.0 | 2026-04-05 | Config file, automatic Ollama install · *legacy repo* |
| 1.2.3 | 2026-04-03 | Photograph input through Pix2Text · *legacy repo* |
| 1.2.1 | 2026-03-29 | Function analysis · *legacy repo* |
| 1.0.0 | 2026-03-09 | First calculator: expressions, equations, plots · *legacy repo* |

## Prehistory — SmartCalculator 1.0.0 … 1.3.0

Before the rewrite the project lived in
[M1kLuXamAkLay/SmartCalculator](https://github.com/M1kLuXamAkLay/SmartCalculator).
Sixteen commits between March and April 2026. Dates are commit dates, not
release dates: there were no tagged releases, only a `Setup/` folder holding the
installer script.

The stack at that time: **Tkinter** for the interface, **Matplotlib** for plots,
**SymPy 1.13** for algebra, **Pix2Text** (and through it, PyTorch) for
recognising formulas in photographs, **Ollama** for the assistant, on
**Python 3.12**. Configuration sat in a `config.txt` beside the executable:
model name, temperature, graph window, and two absolute paths the user had to
edit by hand — the source of most installation failures.

| Version | Date | What it was |
|---|---|---|
| 1.0.0 | 2026-03-09 | First working calculator: expressions, equations, systems of up to four, Matplotlib plots with zoom and pan |
| 1.2.0 | 2026-03-29 | Function analysis — derivative, integral, extrema, behaviour. Reverted the same day, then re-landed |
| 1.2.1 | 2026-03-29 | Re-landed 1.2.0 without the regression that forced the revert |
| 1.2.3 | 2026-04-03 | Photograph input through Pix2Text, routing simple tasks to SymPy and hard ones to the model |
| 1.3.0 | 2026-04-05 | Config file, model choice with a RAM estimate, automatic Ollama install and model pull on first launch |
| — | 2026-04-06 | Installer fix: the one that finally produced a working `Setup.exe` |

### A note on the record

This changelog was introduced at 4.0.0. Earlier work is reconstructed from the
build archives rather than written at the time, and intermediate builds —
2.1, 2.3, 3.1 through 3.8 — exist as installers with no separate entry here.
They are marked in the table above only where something notable shipped. The
archives themselves are the accurate record.

### Why it was rewritten

Three problems could not be fixed in place:

1. **Tkinter could not render the mathematics.** Results were plain text;
   fractions, integrals and matrices never looked like mathematics. LaTeX
   rendering was the reason the project existed.
2. **`pix2text` cost 2 GB and worked badly on photographs of handwriting.** A
   vision model behind Ollama does the same job with no extra dependency.
3. **The interface could not be tested.** A Tkinter widget tree needs a display
   and a live event loop. Serving the interface over loopback HTTP means every
   screen opens in a plain browser, which is why the release sweep exists today.

The rename from SmartCalculator to Σuler.SC and then to the package name
`euler` reflects the same thing: the application became one program with a
computational core, not a script with a window on top.

---

[Unreleased]: https://github.com/euler-project/euler/compare/v4.8.0...HEAD
[4.8.0]: https://github.com/euler-project/euler/compare/v4.7.0...v4.8.0
[4.7.0]: https://github.com/euler-project/euler/compare/v4.6.0...v4.7.0
[4.6.0]: https://github.com/euler-project/euler/compare/v4.5.0...v4.6.0
[4.5.0]: https://github.com/euler-project/euler/compare/v4.4.0...v4.5.0
[4.4.0]: https://github.com/euler-project/euler/compare/v4.3.0...v4.4.0
[4.3.0]: https://github.com/euler-project/euler/compare/v4.2.0...v4.3.0
[4.2.0]: https://github.com/euler-project/euler/compare/v4.1.0...v4.2.0
[4.1.0]: https://github.com/euler-project/euler/compare/v4.0.0...v4.1.0
[4.0.0]: https://github.com/euler-project/euler/compare/v3.9.0...v4.0.0
[3.9.0]: https://github.com/euler-project/euler/compare/v3.0.0...v3.9.0
[3.0.0]: https://github.com/euler-project/euler/compare/v2.2.0...v3.0.0
[2.2.0]: https://github.com/euler-project/euler/compare/v2.0.0...v2.2.0
[2.0.0]: https://github.com/euler-project/euler/releases/tag/v2.0.0
