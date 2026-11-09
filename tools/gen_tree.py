"""Print the project tree used in ARCHITECTURE.md, README.md and HOW_TO_RUN.md.

Each entry is annotated from ``ANNOTATIONS`` so the descriptions cannot drift
away from the files. A file that exists but has no annotation is reported and
the script exits non-zero, which keeps the tree honest when modules are added.

Run:  python tools/gen_tree.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ANNOTATIONS: dict[str, str] = {
    "run.py": "launcher; stable entry point for PyInstaller",
    "requirements.txt": "runtime dependencies (pinned minimums)",
    "pyproject.toml": "ruff configuration",
    ".pre-commit-config.yaml": "local checks before commit",
    "SECURITY.md": "vulnerability reporting policy",
    ".env.example": "environment variables the app reads",
    "euler/__init__.py": "package and __version__",
    "euler/main.py": "window creation, lifecycle, boot",
    "euler/transport.py": "loopback HTTP, token, Host check, boot document",
    "euler/bridge/api.py": "the only callable surface (_exported allowlist)",
    "euler/core/parser.py": "token allowlist, notation rewriting, parse_expr",
    "euler/core/solver.py": "evaluation, equations, systems",
    "euler/core/stepwise.py": "step-by-step explanations",
    "euler/core/analysis.py": "domain, range, zeros, asymptotes, extrema",
    "euler/core/calculus.py": "limits, derivatives, integrals",
    "euler/core/matrix.py": "matrix operations and display",
    "euler/core/registry.py": "named matrices A-H, persisted",
    "euler/core/grapher.py": "sampling with discontinuity splits",
    "euler/core/format.py": "result forms: exact, decimal, scientific, radical",
    "euler/core/exporter.py": "PDF and LaTeX export",
    "euler/core/pdf_font.py": "embedded TrueType for Unicode PDF text",
    "euler/core/reference.py": "theorem reference and ranking",
    "euler/core/intent.py": "lexical then model intent resolution",
    "euler/core/guard.py": "declines harmful requests, masks profanity",
    "euler/core/llm.py": "Ollama client: install, pull, streaming",
    "euler/core/download.py": "resumable, checksummed downloads",
    "euler/core/hardware.py": "RAM/VRAM probe and model catalogue",
    "euler/core/settings.py": "atomic settings.json, allowlisted keys",
    "app/web/index.html": "interface markup and boot attributes",
    "app/web/app.js": "interface logic, sanitiser, boot sequence, drawing",
    "app/web/drawgeom.js": "annotation geometry: transforms, hit tests",
    "tests/test_installer_meta.py": "installer and package agree on the version",
    "build/sync_version.py": "one source of truth for the version stamp",
    "build/version.nsh": "generated version defines for the installer",
    "tests/test_doc_counts.py": "documented counts match the code",
    "tests/test_v521.py": "regression cases from the 5.2.x reports",
    "app/web/i18n.js": "seven-language strings and engine messages",
    "app/web/theme.css": "styles, light and dark themes",
    "tests/test_core.py": "parser, solver, matrices, calculus",
    "tests/test_scenarios.py": "every tab through the public Api",
    "tests/test_export.py": "PDF and LaTeX output",
    "tests/test_settings.py": "atomic writes, unknown-key dropping",
    "tests/test_stepwise.py": "step generation per equation shape",
    "tests/test_download.py": "resumable download, checksum",
    "tests/test_llm_download.py": "Ollama client against a local fake",
    "tests/test_boot_and_ci.py": "boot document, engine gate, guard",
    "tests/test_p1_fixes.py": "angle functions and 0^0 caveat",
    "tests/test_api_doc.py": "docs/API.md matches the code",
    "tests/test_syntax_floor.py": "every file parses on Python 3.10",
    "tests/sweep_full.py": "release gate: 199 end-to-end checks",
    "tests/_guard.py": "per-check timeout, portable",
    "tools/gen_api_doc.py": "generates docs/API.md",
    "tools/gen_tree.py": "generates this tree",
    "docs/API.md": "generated method reference",
    "build/euler.spec": "PyInstaller configuration",
    "build/build.bat": "Windows build and installer",
    "build/build.sh": "macOS and Linux frozen build",
    "build/installer.nsi": "NSIS installer: install, upgrade, uninstall",
    "build/version_info.txt": "Windows file-version resource",
    ".github/workflows/test.yml": "CI: tests on 3.10 and 3.12, three OSes",
    ".github/workflows/release.yml": "CI: Windows installer on tag push",
    ".gitignore": "untracked: caches, build output, local data",
    "ARCHITECTURE.md": "design, security model, boot sequence, roadmap",
    "CHANGELOG.md": "release history (Keep a Changelog)",
    "CONTRIBUTING.md": "how to propose a change",
    "HOW_TO_RUN.md": "running from source, data locations, troubleshooting",
    "LICENSE.txt": "MIT licence and bundled-component notices",
    "README.md": "entry point: what it is, installation, features",
    "euler/bridge/__init__.py": "bridge package marker",
    "euler/core/__init__.py": "core package marker",
}

SKIP = {".git", "__pycache__", ".pytest_cache", "build/euler", "node_modules"}
SKIP_SUFFIXES = {".pyc", ".woff2", ".ttf", ".ico", ".png", ".pyz", ".pkg", ".zip"}


# Directories the fallback walk must skip. `git ls-files` applies .gitignore on
# its own; the walk has to be told, or it reports caches as undescribed files.
FALLBACK_IGNORE = {
    ".git", ".ruff_cache", ".pytest_cache", "__pycache__", "node_modules",
    ".mypy_cache", "build/euler", "dist", "docs/adr",
}


def _tracked() -> list[str]:
    """Files under version control; falls back to a filtered filesystem walk.

    The fallback used to return every file under the tree, so a local
    `.ruff_cache` or `dist/` appeared as an undescribed source file and the
    script refused to run. git itself can also refuse (a repository owned by
    another user, as in a container), which is exactly when the fallback runs.
    """
    import subprocess

    try:
        result = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                                text=True, check=True)
        files = [line for line in result.stdout.splitlines() if line]
        if files:
            return files
    except (OSError, subprocess.CalledProcessError):
        pass

    out = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        if any(rel == d or rel.startswith(d + "/") for d in FALLBACK_IGNORE):
            continue
        if "__pycache__" in rel or rel.endswith((".pyc", ".pyo")):
            continue
        out.append(rel)
    return out


def _keep(rel: str) -> bool:
    if any(rel == s or rel.startswith(s + "/") for s in SKIP):
        return False
    return Path(rel).suffix not in SKIP_SUFFIXES and not rel.startswith("app/web/vendor")


def missing_annotations() -> list[str]:
    """Tracked source files with no description. Reported, never silently skipped."""
    interesting = [p for p in _tracked() if _keep(p)]
    return sorted(p for p in interesting
                  if p not in ANNOTATIONS and not p.startswith("docs/adr/"))


def render() -> str:
    lines = ["Euler.SC/"]
    entries = sorted(p for p in _tracked() if _keep(p) and p in ANNOTATIONS)
    dirs_seen: set[str] = set()
    for path in entries:
        parts = path.split("/")
        for depth in range(1, len(parts)):
            folder = "/".join(parts[:depth])
            if folder not in dirs_seen:
                dirs_seen.add(folder)
                lines.append("  " * depth + f"{parts[depth - 1]}/")
        name = parts[-1]
        lines.append("  " * len(parts) + f"{name:<24} # {ANNOTATIONS[path]}")
    return "\n".join(lines)


def main() -> int:
    missing = missing_annotations()
    if missing:
        print("undescribed files (add to ANNOTATIONS):", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        return 1
    print(render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
