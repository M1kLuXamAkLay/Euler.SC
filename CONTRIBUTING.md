# Contributing

## Before a pull request

```bash
pytest tests/ -q             # must be 40 passed
python tests/sweep_full.py   # must be 199/199 passed
node --check app/web/app.js
```

A behaviour change needs a test in `tests/sweep_full.py`. That file is the
release gate: it covers parsing, solving, calculus, matrices, formatting, the
theorem reference, ranking quality, the request guard and intent classification.

Add an entry to `CHANGELOG.md` under `[Unreleased]`. Keep the style: say what
changed, then why it needed changing.

## Code style

- Python 3.10+, type hints on public functions, no `from x import *`.
- Comments explain *why*, not *what*. If a line needs a comment to be
  understood, the line is usually the problem.
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
