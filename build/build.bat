@echo off
REM ==========================================================================
REM  Build EulerSC for Windows: executable, then installer.
REM
REM    build.bat              system-Python installer (requires Python 3.10+)
REM    build.bat bundled      installer with an embedded Python runtime
REM
REM  Requirements on the build machine:
REM    * Python 3.10 or newer on PATH
REM    * NSIS 3.x (makensis) on PATH, e.g. C:\Program Files (x86)\NSIS
REM ==========================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0\.."

set MODE=%1
if "%MODE%"=="" set MODE=system

echo.
echo === 1/3  Installing build dependencies ===
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :failed

echo.
echo === 2/3  Freezing the application ===
REM  --noconfirm replaces dist\EulerSC without prompting
pyinstaller build\euler.spec --noconfirm --clean
if errorlevel 1 goto :failed

if not exist "dist\EulerSC\EulerSC.exe" (
    echo ERROR: dist\EulerSC\EulerSC.exe was not produced.
    goto :failed
)

echo.
echo === 3/3  Building the installer ===
where makensis >nul 2>&1
if errorlevel 1 (
    echo WARNING: makensis was not found on PATH.
    echo          Install NSIS from https://nsis.sourceforge.io and run:
    echo              makensis build\installer.nsi
    echo.
    echo The frozen application is ready at dist\EulerSC\
    goto :done
)

if /i "%MODE%"=="bundled" (
    echo Mode: bundled ^(embedded Python runtime^)
    call :stage_python
    makensis /DBUNDLED build\installer.nsi
) else (
    echo Mode: system Python
    copy /y requirements.txt dist\EulerSC\requirements.txt >nul
    makensis build\installer.nsi
)
if errorlevel 1 goto :failed

:done
echo.
echo Build complete.
echo   Application : dist\EulerSC\EulerSC.exe
echo   Installer   : dist\EulerSC-Setup.exe
exit /b 0

:failed
echo.
echo BUILD FAILED. See the messages above.
exit /b 1

REM --------------------------------------------------------------------------
REM  Copies a portable Python into dist\EulerSC\python so the installer can
REM  ship a self-contained runtime. Uses the embeddable distribution, which
REM  needs pip bootstrapped manually.
REM --------------------------------------------------------------------------
:stage_python
if exist "dist\EulerSC\python\python.exe" (
    echo Embedded Python already staged, skipping download.
    exit /b 0
)
echo Downloading the embeddable Python 3.10 runtime...
set PYVER=3.10.11
set PYDIR=dist\EulerSC\python
mkdir "%PYDIR%" 2>nul
powershell -NoProfile -Command ^
  "$u='https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-embed-amd64.zip';" ^
  "Invoke-WebRequest -Uri $u -OutFile '%TEMP%\py-embed.zip' -UseBasicParsing"
if errorlevel 1 (
    echo WARNING: download failed, continuing without an embedded runtime.
    exit /b 0
)
powershell -NoProfile -Command ^
  "Expand-Archive -Path '%TEMP%\py-embed.zip' -DestinationPath '%PYDIR%' -Force"

REM  The embeddable build ignores site-packages until this file is edited:
REM  uncomment "import site" so pip-installed wheels are visible.
powershell -NoProfile -Command ^
  "(Get-Content '%PYDIR%\python310._pth') -replace '#import site','import site' | Set-Content '%PYDIR%\python310._pth'"

echo Installing packages into the embedded runtime...
"%PYDIR%\python.exe" -m ensurepip --upgrade
"%PYDIR%\python.exe" -m pip install --no-warn-script-location -r requirements.txt
copy /y requirements.txt dist\EulerSC\requirements.txt >nul
exit /b 0
