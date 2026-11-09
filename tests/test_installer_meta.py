"""The installer and the application must agree about the version.

These checks exist because they once did not. ``version_info.txt`` still said
``5,1,0,0`` while the package said ``5.2.1``, and the NSIS script carried a
third, hand-typed copy. An upgrade check built on a stale number either refuses
a legitimate upgrade or offers one that installs the same build again.

Nothing here runs NSIS: these are textual invariants, cheap enough to run in the
normal test pass. ``build.sh`` also has an optional compile step for machines
that do have makensis.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "euler" / "__init__.py"
NSI = ROOT / "build" / "installer.nsi"
NSH = ROOT / "build" / "version.nsh"
VERSION_INFO = ROOT / "build" / "version_info.txt"
SYNC = ROOT / "build" / "sync_version.py"


def _package_version() -> str:
    text = INIT.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "euler/__init__.py must declare __version__"
    return match.group(1)


def test_version_nsh_matches_the_package():
    """build/version.nsh is generated; if it is stale, a build would ship it."""
    assert NSH.exists(), "build/version.nsh is missing; run build/sync_version.py"
    text = NSH.read_text(encoding="utf-8")
    declared = re.search(r'!define APP_VERSION\s+"([^"]+)"', text)
    assert declared, "version.nsh must define APP_VERSION"
    assert declared.group(1) == _package_version()


def test_version_nsh_has_numeric_parts():
    """The comparison uses numbers, not strings: 5.10 must sort above 5.9."""
    text = NSH.read_text(encoding="utf-8")
    version = _package_version()
    major, minor, patch = (int(part) for part in version.split(".")[:3])
    for name, value in (("MAJOR", major), ("MINOR", minor), ("PATCH", patch)):
        found = re.search(rf"!define APP_VERSION_{name}\s+(\d+)", text)
        assert found and int(found.group(1)) == value, f"APP_VERSION_{name} is stale"


def test_version_info_matches_the_package():
    """The Windows resource is what Explorer and Apps & features display."""
    text = VERSION_INFO.read_text(encoding="utf-8")
    version = _package_version()
    major, minor, patch = version.split(".")[:3]
    assert f"filevers=({major}, {minor}, {patch}, 0)" in text
    assert f"prodvers=({major}, {minor}, {patch}, 0)" in text
    assert f"StringStruct('FileVersion', '{version}.0')" in text
    assert f"StringStruct('ProductVersion', '{version}.0')" in text


def test_installer_does_not_hardcode_the_version():
    """A literal version in the .nsi is the drift this suite prevents."""
    text = NSI.read_text(encoding="utf-8")
    assert '!include "version.nsh"' in text
    # No `APP_VERSION "x.y.z"` definition may remain in the script itself.
    assert not re.search(r'!define\s+APP_VERSION\s+"\d+\.\d+', text)


def test_installer_reads_previous_version_and_compares():
    """An upgrade needs the installed version and a three-way comparison."""
    text = NSI.read_text(encoding="utf-8")
    assert 'ReadRegStr $0 HKCU "${REG_APP}" "Version"' in text
    assert "Function ParseVersion" in text
    assert "Function CompareInstalled" in text
    # The states the interface distinguishes.
    for state in ("upgrade", "repair", "downgrade"):
        assert f'StrCpy $UpgradeState "{state}"' in text


def test_installer_refuses_downgrade_unless_forced():
    text = NSI.read_text(encoding="utf-8")
    assert "/FORCE" in text
    # The refusal must come before any file is written.
    abort = text.index("MsgDowngradeBlocked")
    first_write = text.index('File /r "..\\dist\\EulerSC\\*.*"')
    assert abort < first_write


def test_installer_keeps_user_data_outside_the_install_directory():
    """Settings live in %APPDATA%, not in $INSTDIR, so an upgrade cannot lose them.

    Checked by looking for the COMMANDS that would delete them, not for the word
    "APPDATA": the explanatory comment inside the upgrade block mentions the
    path, and a substring search would flag its own documentation.
    """
    text = NSI.read_text(encoding="utf-8")
    assert "$APPDATA\\EulerSC" in text            # only the uninstaller removes it

    upgrade_block = text[text.index('${If} $UpgradeState != "new"'):text.index('File /r')]
    for command in ("RMDir", "DeleteRegKey"):
        for line in upgrade_block.splitlines():
            code = line.split(";")[0]                 # ignore trailing comments
            if command in code:
                assert "APPDATA" not in code, f"upgrade must not remove app data: {line}"
                assert "REG_APP" not in code, f"upgrade must not remove settings: {line}"


def test_sync_script_exists_and_is_idempotent(tmp_path, monkeypatch):
    """Running it twice must produce the same files, so a build can call it always."""
    source = SYNC.read_text(encoding="utf-8")
    assert "_SEMVER" in source and "write_nsh" in source
    before = NSH.read_text(encoding="utf-8"), VERSION_INFO.read_text(encoding="utf-8")
    import subprocess
    import sys
    for _ in range(2):
        result = subprocess.run([sys.executable, str(SYNC)], cwd=ROOT,
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    after = NSH.read_text(encoding="utf-8"), VERSION_INFO.read_text(encoding="utf-8")
    assert before == after


def test_build_scripts_sync_before_packaging():
    """A build that forgets the step ships the previous version's number."""
    for name in ("build.bat", "build.sh"):
        text = (ROOT / "build" / name).read_text(encoding="utf-8")
        assert "sync_version" in text, f"{name} must call build/sync_version.py"

    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "sync_version.py" in workflow
