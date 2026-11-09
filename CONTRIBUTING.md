# Contributing

## Before a pull request

```bash
pytest tests/ -q             # must be 168 passed
python tests/sweep_full.py   # must be 199/199 passed
node --check app/web/app.js
```

The suite prints `170 passed`; the comment above says 168 on purpose. Two of
those tests are in `tests/test_doc_counts.py`, which verifies these very numbers
and therefore excludes itself when counting (170 - 2 = 168). If you change the
suite size, update the documented number and let that test tell you whether you
missed a place.

Run the suite against the lowest supported interpreter too, if you have it:

```bash
python3.10 -m pytest tests/ -q
```

CI runs Python 3.10 and 3.12 on Linux, Windows and macOS. The 3.10 jobs are not
ceremonial: they are the only thing that catches syntax newer than the floor.
`tests/test_syntax_floor.py` replays that check locally by re-parsing every file
with `feature_version=(3, 10)`.

A behaviour change needs a test. Put it where it belongs:

- a module-level guarantee -> `tests/test_*.py`
- an end-to-end check through the public `Api` -> `tests/sweep_full.py`

The sweep is the release gate: it covers parsing, solving, calculus, matrices,
formatting, the theorem reference, ranking quality, the request guard and intent
classification. A change only a browser can see - layout, theme, the boot
sequence - gets a note in the pull request saying what was checked at 960x720
and 1276x900, because no assertion here can see a repaint.

Add an entry to `CHANGELOG.md` under `[Unreleased]`. Keep the style: say what
changed, then why it needed changing.

## Repository history

`build/euler/` (PyInstaller's work directory, ~3 MB of `.toc`, `.pyz` and
`xref` files) was committed by mistake and removed from the index in 5.2.0. It
is no longer tracked, but it is still present in every older commit, so a fresh
clone downloads it. The rewrite is a one-off operation, described in
[ARCHITECTURE.md](ARCHITECTURE.md#rewriting-history); nothing in the build
depends on it and it does not change any file in the working tree.

## Code style

- Python 3.10+, type hints on public functions, no `from x import *`.
- **No syntax newer than 3.10.** No `match`, no PEP 701 f-strings with a
  backslash inside the braces, no runtime `X | Y` annotation without
  `from __future__ import annotations`.
- Comments explain *why*, not *what*. If a line needs a comment to be
  understood, the line is usually the problem.
- **Comments, docstrings and identifiers are English.** The Cyrillic text in
  `i18n.js` is data, not a comment.
- **Tests must not depend on the platform.** No `signal.alarm` without a guard,
  no hard-coded path separators, no assumption that a filesystem is
  case-sensitive. `tests/_guard.py` exists for the first of these.
- Frontend is vanilla JavaScript — no build step, no framework. Keep it that
  way; the whole interface is testable in a plain browser because of it.
- Every user-visible string goes through `i18n.js` with all seven languages,
  not just Russian.

## Adding a refusal rule

`euler/core/guard.py`. Rules are deliberately narrow: match a clear intent, not a topic.
A legitimate chemistry or physics question must not be blocked. Add a case to the sweep 
for both the block and a nearby legitimate question that must pass.

## Reporting a security issue

Do not open a public issue. Write to the address in `LICENSE.txt`.
