#!/usr/bin/env bash
# ============================================================================
#  Build EulerSC on Linux or macOS.
#
#  The NSIS installer is Windows-only; on other platforms this script produces
#  the frozen application directory and skips the installer step.
#
#    ./build/build.sh          build dist/EulerSC/
#    ./build/build.sh --clean  also remove previous build artefacts first
# ============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ "${1:-}" == "--clean" ]]; then
    echo "==> Removing previous artefacts"
    rm -rf build/EulerSC build/*.spec.bak dist
fi

echo "==> Installing build dependencies"
python3 -m pip install --upgrade pip >/dev/null
python3 -m pip install -r requirements.txt pyinstaller

echo "==> Syncing the version stamp"
# One source of truth: euler/__init__.py -> build/version.nsh, version_info.txt
python3 build/sync_version.py

echo "==> Freezing the application"
pyinstaller build/euler.spec --noconfirm --clean

if [[ ! -d dist/EulerSC ]]; then
    echo "ERROR: dist/EulerSC was not produced" >&2
    exit 1
fi

echo "==> Verifying the bundle"
if [[ -f dist/EulerSC/EulerSC ]]; then
    echo "    launcher: dist/EulerSC/EulerSC"
elif [[ -f dist/EulerSC/EulerSC.exe ]]; then
    echo "    launcher: dist/EulerSC/EulerSC.exe"
else
    echo "ERROR: no launcher in dist/EulerSC" >&2
    exit 1
fi

# The interface must be inside the bundle, otherwise the window opens blank
if [[ ! -f dist/EulerSC/_internal/web/index.html ]] && \
   [[ ! -f dist/EulerSC/web/index.html ]]; then
    echo "ERROR: web assets were not bundled" >&2
    exit 1
fi

if command -v makensis >/dev/null 2>&1 && [[ "$(uname -s)" == "MINGW"* ]]; then
    echo "==> Building the installer"
    makensis build/installer.nsi
else
    echo "==> Skipping the installer (NSIS is Windows-only)"
fi

echo
echo "Build complete."
echo "  Application: dist/EulerSC/"
