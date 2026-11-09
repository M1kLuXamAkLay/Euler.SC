# Security Policy

## Supported versions

Only the latest release line receives security fixes.

| Version | Supported |
|---|---|
| 5.1.x | yes |
| < 5.0 | no |

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.

Report privately through GitHub: the repository's **Security** tab, then
**Report a vulnerability** (private vulnerability reporting). Include:

- the version (`euler/__init__.py`, or the installer's Apps & features entry);
- the platform and Python version;
- a minimal input or request that reproduces the problem;
- what you expected and what happened.

## What to expect

| Step | Target |
|---|---|
| Acknowledgement | within 3 working days |
| Assessment and severity | within 7 working days |
| Fix for a high-severity issue | next patch release, normally within 30 days |
| Public disclosure | after a fix is released, coordinated with the reporter |

## Scope

In scope: the Python engine (`euler/`), the loopback transport, the interface
(`app/web/`), the installer and build scripts.

Out of scope: vulnerabilities in Ollama or in the models it runs, in pywebview,
WebView2 or the operating system. Report those upstream; tell us if our use of
them makes the problem worse.

## Design notes that matter for a report

- The interface is served on `127.0.0.1` only, with a per-launch token and a
  `Host` check against DNS rebinding. A request with a foreign `Host` or a
  missing token is refused.
- Only the methods in `Api._exported` can be called from the page.
- Mathematical input is checked against a token allowlist before it reaches
  SymPy; `sympify` is not used.
- Model output is sanitised before it is inserted into the page.
- No telemetry, accounts or update checks: the app makes no outbound network
  calls except the explicit model and Ollama downloads.

Known open issue: evaluation has no time limit, so a pathological expression
such as `9**9**9` can keep one worker busy. This is a denial-of-service of the
local user's own session, tracked in `ARCHITECTURE.md` (Known Limitations 4).
