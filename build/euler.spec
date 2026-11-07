# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build definition for Σuler.SC.

Produces a single directory (``dist/EulerSC/``) rather than a one-file bundle:
the application starts in under a second from a directory, while a one-file
bundle unpacks ~120 MB of SymPy to a temporary folder on every launch.

Build:
    pyinstaller build/euler.spec --noconfirm

The NSIS script in ``build/installer.nsi`` packages the resulting directory.
"""
import sys
from pathlib import Path

# The spec is executed by PyInstaller with build/ as the working directory
ROOT = Path(SPECPATH).resolve().parent

block_cipher = None

ICON = ROOT / "assets" / "icon.ico"
VERSION_RESOURCE = ROOT / "build" / "version_info.txt"

# Everything the application reads at run time. Missing entries here are the
# single most common cause of a frozen build that starts but shows no UI.
datas = [
    (str(ROOT / "app" / "web"), "web"),
    (str(ROOT / "assets"), "assets"),
]

# Imported dynamically through ``importlib`` or by SymPy itself, so static
# analysis cannot see them.
hiddenimports = [
    "sympy",
    "sympy.parsing.sympy_parser",
    "sympy.integrals.manualintegrate",
    "sympy.polys",
    "sympy.solvers",
    "sympy.simplify",
    "sympy.functions",
    "sympy.matrices",
    "sympy.plotting",
    "numpy",
    "webview",
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    "clr",                       # pythonnet, required by the Windows backend
    "euler",
    "euler.core",
    "euler.bridge",
    "euler.transport",
]

# Modules that PyInstaller pulls in but the app never uses. Excluding them
# removes roughly 40 MB from the bundle.
excludes = [
    "tkinter",
    "PyQt5", "PyQt6", "PySide2", "PySide6",
    "IPython", "jupyter", "notebook",
    "pytest", "setuptools", "pip",
    "PIL",
]

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EulerSC",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # UPX corrupts pythonnet assemblies
    console=False,             # no console window for the user
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.exists() else None,
    version=str(VERSION_RESOURCE) if VERSION_RESOURCE.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="EulerSC",
)
