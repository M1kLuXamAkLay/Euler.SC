; ============================================================================
; Euler.SC installer
;
;   makensis /DBUNDLED installer.nsi    ships a private Python runtime
;   makensis installer.nsi              uses the system Python
;
; A per-user install into %LOCALAPPDATA%: no elevation, no UAC prompt, and the
; uninstall entry appears in "Apps & features" for the current user.
;
; Lifecycle
;   install    language page -> components -> files -> shortcuts -> registry
;   upgrade    the same script, run over an existing installation: the version
;              recorded by the previous run is read back and compared, and the
;              user is told what is about to happen before anything is touched
;   uninstall  uninstaller removes files, shortcuts, registry, app data and,
;              when the user agrees, Ollama together with its models
;
; Upgrade behaviour
;   newer build over an older one        upgrade, settings and matrices kept
;   same version over the same version   repair (rewrites the files)
;   older build over a newer one         refused, with the two versions shown
;   /FORCE                               downgrades anyway, for a rollback
;
; Settings, saved matrices and exports live in %APPDATA%\EulerSC and are never
; part of the install directory, so an upgrade does not touch them. The
; uninstaller removes them only when it runs, which an upgrade never does.
; ============================================================================

Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

; The version is NOT written here. build/sync_version.py derives it from
; euler/__init__.py and writes build/version.nsh, so the package, the Windows
; resource and this script can never disagree about what is being installed.
!include "version.nsh"

!define APP_NAME      "Euler.SC"
!define APP_EXE       "EulerSC.exe"
!define APP_PUBLISHER "Euler Project"
!define APP_URL       "https://github.com/euler-project/euler"
!define REG_APP       "Software\EulerSC"
!define REG_UNINST    "Software\Microsoft\Windows\CurrentVersion\Uninstall\EulerSC"
!define WEBVIEW2_GUID "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
!define OLLAMA_GUID   "{44E83376-CE68-45EB-8FC1-393500EB9D12}"

Name "${APP_NAME}"
OutFile "..\dist\EulerSC-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\EulerSC"
InstallDirRegKey HKCU "Software\EulerSC" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show
ShowUninstDetails show

!define MUI_ABORTWARNING
!define MUI_ICON "..\assets\icon.ico"
!define MUI_UNICON "..\assets\icon.ico"

; ---------------------------------------------------------------------------
; Language selection is the first page, as in any mainstream installer. The
; chosen language also seeds the app's own interface language on first launch.
; ---------------------------------------------------------------------------
!define MUI_LANGDLL_ALWAYSSHOW
!define MUI_LANGDLL_REGISTRY_ROOT "HKCU"
!define MUI_LANGDLL_REGISTRY_KEY "Software\EulerSC"
!define MUI_LANGDLL_REGISTRY_VALUENAME "InstallerLanguage"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\LICENSE.txt"
!insertmacro MUI_PAGE_COMPONENTS

; An upgrade goes back where it came from; the page would only invite the user
; to break the shortcuts and registry entries that already point at that path.
!define MUI_PAGE_CUSTOMFUNCTION_PRE SkipDirectoryOnUpgrade
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "$(LaunchApp)"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "Russian"
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "Spanish"
!insertmacro MUI_LANGUAGE "French"
!insertmacro MUI_LANGUAGE "PortugueseBR"

; Language strings used by the installer's own pages
LangString LaunchApp     ${LANG_RUSSIAN} "Запустить ${APP_NAME}"
LangString LaunchApp     ${LANG_ENGLISH} "Launch ${APP_NAME}"
LangString SecAppName    ${LANG_RUSSIAN} "Приложение (обязательно)"
LangString SecAppName    ${LANG_ENGLISH} "Application (required)"
LangString SecAppDesc    ${LANG_RUSSIAN} "Ядро, интерфейс и справочник."
LangString SecAppDesc    ${LANG_ENGLISH} "Engine, interface and reference."
LangString SecShortName  ${LANG_RUSSIAN} "Ярлыки"
LangString SecShortName  ${LANG_ENGLISH} "Shortcuts"
LangString SecShortDesc  ${LANG_RUSSIAN} "Ярлык на рабочем столе и в меню «Пуск»."
LangString SecShortDesc  ${LANG_ENGLISH} "Desktop and Start Menu shortcuts."
LangString SecAsseName   ${LANG_RUSSIAN} "Связывать файлы .tex"
LangString SecAsseName   ${LANG_ENGLISH} "Associate .tex files"
LangString SecAsseDesc   ${LANG_RUSSIAN} "Открывать .tex в приложении по двойному щелчку."
LangString SecAsseDesc   ${LANG_ENGLISH} "Open .tex files with the application."

; ---- additional installer languages ---------------------------------------
LangString LaunchApp     ${LANG_SIMPCHINESE} "启动 ${APP_NAME}"
LangString LaunchApp     ${LANG_SPANISH}     "Iniciar ${APP_NAME}"
LangString LaunchApp     ${LANG_FRENCH}      "Lancer ${APP_NAME}"
LangString LaunchApp     ${LANG_PORTUGUESEBR} "Iniciar ${APP_NAME}"
LangString SecAppName    ${LANG_SIMPCHINESE} "应用程序（必需）"
LangString SecAppName    ${LANG_SPANISH}     "Aplicación (obligatoria)"
LangString SecAppName    ${LANG_FRENCH}      "Application (obligatoire)"
LangString SecAppName    ${LANG_PORTUGUESEBR} "Aplicativo (obrigatório)"
LangString SecAppDesc    ${LANG_SIMPCHINESE} "核心、界面和参考手册。"
LangString SecAppDesc    ${LANG_SPANISH}     "Motor, interfaz y referencia."
LangString SecAppDesc    ${LANG_FRENCH}      "Moteur, interface et référence."
LangString SecAppDesc    ${LANG_PORTUGUESEBR} "Núcleo, interface e referência."
LangString SecShortName  ${LANG_SIMPCHINESE} "快捷方式"
LangString SecShortName  ${LANG_SPANISH}     "Accesos directos"
LangString SecShortName  ${LANG_FRENCH}      "Raccourcis"
LangString SecShortName  ${LANG_PORTUGUESEBR} "Atalhos"
LangString SecShortDesc  ${LANG_SIMPCHINESE} "桌面和“开始”菜单快捷方式。"
LangString SecShortDesc  ${LANG_SPANISH}     "Accesos directos en el escritorio y en el menú Inicio."
LangString SecShortDesc  ${LANG_FRENCH}      "Raccourcis sur le bureau et dans le menu Démarrer."
LangString SecShortDesc  ${LANG_PORTUGUESEBR} "Atalhos na área de trabalho e no menu Iniciar."
LangString SecAsseName   ${LANG_SIMPCHINESE} "关联 .tex 文件"
LangString SecAsseName   ${LANG_SPANISH}     "Asociar archivos .tex"
LangString SecAsseName   ${LANG_FRENCH}      "Associer les fichiers .tex"
LangString SecAsseName   ${LANG_PORTUGUESEBR} "Associar arquivos .tex"
LangString SecAsseDesc   ${LANG_SIMPCHINESE} "双击时用本应用打开 .tex 文件。"
LangString SecAsseDesc   ${LANG_SPANISH}     "Abrir archivos .tex con la aplicación al hacer doble clic."
LangString SecAsseDesc   ${LANG_FRENCH}      "Ouvrir les fichiers .tex avec l'application par double-clic."
LangString SecAsseDesc   ${LANG_PORTUGUESEBR} "Abrir arquivos .tex com o aplicativo ao clicar duas vezes."

; ---------------------------------------------------------------------------
; Version handling
;
; NSIS has no version type, so a dotted string is compared part by part. The
; numbers the build ships with come from version.nsh as separate definitions,
; which removes the parsing step for our own side and the classic bug where
; "5.10" sorts below "5.9".
;
; The installed side is read from the registry as one string and split here.
; Every part is coerced to a number with IntOp, so a hand-edited or truncated
; value ("5.2", "5.2.beta", "") becomes 0 instead of aborting the install.
; ---------------------------------------------------------------------------

; ParseVersion: $R0 = "5.2.1"  ->  $R1 = 5, $R2 = 2, $R3 = 1
Function ParseVersion
  StrCpy $R4 ""      ; digits of the current part
  StrCpy $R5 0       ; which part we are in
  StrCpy $R6 0       ; character index
  StrCpy $R1 0
  StrCpy $R2 0
  StrCpy $R3 0

  ${Do}
    StrCpy $R7 $R0 1 $R6
    ${If} $R7 == ""
      ; End of string: flush the part in hand.
      ${If} $R5 == 0
        StrCpy $R1 $R4
      ${ElseIf} $R5 == 1
        StrCpy $R2 $R4
      ${ElseIf} $R5 == 2
        StrCpy $R3 $R4
      ${EndIf}
      ${ExitDo}
    ${EndIf}

    ${If} $R7 == "."
      ${If} $R5 == 0
        StrCpy $R1 $R4
      ${ElseIf} $R5 == 1
        StrCpy $R2 $R4
      ${ElseIf} $R5 == 2
        StrCpy $R3 $R4
      ${EndIf}
      StrCpy $R4 ""
      IntOp $R5 $R5 + 1
      ${If} $R5 > 2
        ${ExitDo}
      ${EndIf}
    ${Else}
      StrCpy $R4 "$R4$R7"
    ${EndIf}

    IntOp $R6 $R6 + 1
  ${Loop}

  ; Non-numeric junk becomes 0 rather than a failed install.
  IntOp $R1 $R1 + 0
  IntOp $R2 $R2 + 0
  IntOp $R3 $R3 + 0
FunctionEnd

; CompareInstalled: $R1/$R2/$R3 installed vs. the build's own numbers.
;   $0 = 1  installed is newer (a downgrade)
;   $0 = 0  same version      (a repair)
;   $0 = -1 installed is older (an upgrade)
Function CompareInstalled
  StrCpy $0 -1
  ${If} $R1 > ${APP_VERSION_MAJOR}
    StrCpy $0 1
    Return
  ${EndIf}
  ${If} $R1 < ${APP_VERSION_MAJOR}
    Return
  ${EndIf}

  ${If} $R2 > ${APP_VERSION_MINOR}
    StrCpy $0 1
    Return
  ${EndIf}
  ${If} $R2 < ${APP_VERSION_MINOR}
    Return
  ${EndIf}

  ${If} $R3 > ${APP_VERSION_PATCH}
    StrCpy $0 1
  ${ElseIf} $R3 == ${APP_VERSION_PATCH}
    StrCpy $0 0
  ${EndIf}
FunctionEnd

; ---------------------------------------------------------------------------
; Upgrade detection, before any page is shown
;
; Everything is decided here so the pages can adapt: the directory page is
; skipped for an existing installation, and the first dialog names both
; versions before a single file is touched.
; ---------------------------------------------------------------------------

Var InstalledVersion      ; "" when nothing is installed
Var InstallDirFound       ; where the previous run put it
Var UpgradeState          ; "new" | "upgrade" | "repair" | "downgrade"

Function .onInit
  StrCpy $InstalledVersion ""
  StrCpy $InstallDirFound ""
  StrCpy $UpgradeState "new"

  ; 1. The version recorded by the previous run. Older builds of this installer
  ;    wrote only DisplayVersion, so that is the fallback rather than a second
  ;    source of truth.
  ClearErrors
  ReadRegStr $0 HKCU "${REG_APP}" "Version"
  ${If} $0 == ""
    ReadRegStr $0 HKCU "${REG_UNINST}" "DisplayVersion"
  ${EndIf}
  StrCpy $InstalledVersion $0

  ; 2. Where it is: the recorded directory, or the default when that default
  ;    actually holds our executable.
  ClearErrors
  ReadRegStr $0 HKCU "${REG_APP}" "InstallDir"
  ${If} $0 != ""
    StrCpy $InstallDirFound $0
  ${ElseIf} ${FileExists} "$LOCALAPPDATA\Programs\EulerSC\${APP_EXE}"
    StrCpy $InstallDirFound "$LOCALAPPDATA\Programs\EulerSC"
  ${EndIf}

  ; 3. A registry entry whose files are gone is the debris of a failed uninstall.
  ;    Treating it as an installation would make the first real install look
  ;    like an upgrade and inherit a broken directory.
  ${If} $InstallDirFound != ""
    ${IfNot} ${FileExists} "$InstallDirFound\${APP_EXE}"
      StrCpy $InstallDirFound ""
      StrCpy $InstalledVersion ""
    ${EndIf}
  ${EndIf}

  ; 4. Classify.
  ${If} $InstalledVersion != ""
    StrCpy $R0 $InstalledVersion
    Call ParseVersion
    Call CompareInstalled
    ${If} $0 == 1
      StrCpy $UpgradeState "downgrade"
    ${ElseIf} $0 == 0
      StrCpy $UpgradeState "repair"
    ${Else}
      StrCpy $UpgradeState "upgrade"
    ${EndIf}
  ${EndIf}

  ; 5. A downgrade is refused unless asked for explicitly. Rolling back after a
  ;    bad release is legitimate, so /FORCE exists and says nothing extra.
  ${If} $UpgradeState == "downgrade"
    ${GetParameters} $R8
    ClearErrors
    ${GetOptions} $R8 "/FORCE" $R9
    ${If} ${Errors}
      MessageBox MB_ICONSTOP|MB_OK \
        "$(MsgDowngradeBlocked)$\r$\n$\r$\n$(MsgInstalledIs)$InstalledVersion$\r$\n$(MsgThisIs)${APP_VERSION}"
      Abort
    ${EndIf}
  ${EndIf}

  ; 6. An upgrade keeps its location: shortcuts, the uninstall entry and the
  ;    .tex association all point at it, so moving it would orphan them.
  ${If} $InstallDirFound != ""
    StrCpy $INSTDIR $InstallDirFound
  ${EndIf}

  ; 7. Say what is about to happen, with both numbers.
  ${If} $UpgradeState == "upgrade"
    MessageBox MB_OK|MB_ICONINFORMATION \
      "$(MsgWillUpgrade)$\r$\n$\r$\n$(MsgFromVersion)$InstalledVersion$\r$\n$(MsgToVersion)${APP_VERSION}$\r$\n$\r$\n$(MsgSettingsKept)"
  ${ElseIf} $UpgradeState == "repair"
    MessageBox MB_OK|MB_ICONINFORMATION \
      "$(MsgSameVersion)$\r$\n$\r$\n$(MsgRepair)"
  ${EndIf}

  !insertmacro MUI_LANGDLL_DISPLAY
FunctionEnd

; The directory page is skipped for an existing installation (see the
; MUI_PAGE_CUSTOMFUNCTION_PRE above the page list).
Function SkipDirectoryOnUpgrade
  ${If} $UpgradeState != "new"
    Abort
  ${EndIf}
FunctionEnd

; ---------------------------------------------------------------------------
Section "$(SecAppName)" SecApp
  SectionIn RO
  SetShellVarContext current
  SetOutPath "$INSTDIR"

  ; An upgrade overwrites the program, never the data.
  ;
  ; %APPDATA%\EulerSC (settings, saved matrices, exports) is outside $INSTDIR,
  ; so it is untouched here by construction. What must be handled is the
  ; program itself: a running copy holds EulerSC.exe open, and Windows refuses
  ; to replace a locked file. Asking the user to close the window and retrying
  ; is friendlier than a failed install with a sharing-violation message.
  ${If} $UpgradeState != "new"
    DetailPrint "$(MsgClosingOld)"
    nsExec::Exec 'taskkill /IM "${APP_EXE}" /F /T'
    Sleep 400

    ; A stale file from the previous version can survive if it was renamed by an
    ; update; removing the tree first means an upgrade never leaves two copies
    ; of a module that no longer exists in the new package.
    RMDir /r "$INSTDIR\_internal"
    RMDir /r "$INSTDIR\web"
    RMDir /r "$INSTDIR\app"
    RMDir /r "$INSTDIR\euler"
    Delete "$INSTDIR\${APP_EXE}"
  ${EndIf}

  ; The PyInstaller directory bundle: executable, _internal tree and web assets
  File /r "..\dist\EulerSC\*.*"

  ; Seed the interface language from the installer choice: the app reads this
  ; key on first launch and skips its own language question.
  ${Switch} $LANGUAGE
    ${Case} ${LANG_RUSSIAN}
      StrCpy $R0 "ru"
      ${Break}
    ${Case} ${LANG_SIMPCHINESE}
      StrCpy $R0 "zh"
      ${Break}
    ${Case} ${LANG_SPANISH}
      StrCpy $R0 "es"
      ${Break}
    ${Case} ${LANG_FRENCH}
      StrCpy $R0 "fr"
      ${Break}
    ${Case} ${LANG_PORTUGUESEBR}
      StrCpy $R0 "pt"
      ${Break}
    ${Default}
      StrCpy $R0 "en"
  ${EndSwitch}
  WriteRegStr HKCU "Software\EulerSC" "Language" $R0

  WriteRegStr HKCU "${REG_APP}" "InstallDir" "$INSTDIR"
  ; The three keys the next run reads to decide upgrade / repair / downgrade.
  ; Written last, after the files are in place: a version recorded for a failed
  ; copy would make the next run believe an installation exists.
  WriteRegStr HKCU "${REG_APP}" "Version" "${APP_VERSION}"
  WriteRegDWORD HKCU "${REG_APP}" "VersionMajor" ${APP_VERSION_MAJOR}
  WriteRegDWORD HKCU "${REG_APP}" "VersionMinor" ${APP_VERSION_MINOR}
  WriteRegDWORD HKCU "${REG_APP}" "VersionPatch" ${APP_VERSION_PATCH}
  ; Support asks "when did you install it"; the file timestamps are wiped by a
  ; repair, so the date is recorded here. NSIS has no date variable, hence the
  ; one shell call.
  nsExec::ExecToStack 'cmd /c echo %DATE% %TIME%'
  Pop $1          ; exit code
  Pop $2          ; text, e.g. "08.11.2026 22:14:03,12"
  ${If} $1 == 0
    WriteRegStr HKCU "${REG_APP}" "InstalledOn" "$2"
  ${EndIf}
  ${If} $InstalledVersion != ""
    ; Keep the version this installation replaced, so a downgrade or a support
    ; question has an answer without guessing.
    WriteRegStr HKCU "${REG_APP}" "PreviousVersion" "$InstalledVersion"
  ${EndIf}

  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegStr   HKCU "${REG_UNINST}" "DisplayName"     "${APP_NAME}"
  WriteRegStr   HKCU "${REG_UNINST}" "DisplayVersion"  "${APP_VERSION}"
  WriteRegDWORD HKCU "${REG_UNINST}" "VersionMajor"    ${APP_VERSION_MAJOR}
  WriteRegDWORD HKCU "${REG_UNINST}" "VersionMinor"    ${APP_VERSION_MINOR}
  WriteRegStr   HKCU "${REG_UNINST}" "Publisher"       "${APP_PUBLISHER}"
  WriteRegStr   HKCU "${REG_UNINST}" "URLInfoAbout"    "${APP_URL}"
  WriteRegStr   HKCU "${REG_UNINST}" "DisplayIcon"     "$INSTDIR\${APP_EXE}"
  WriteRegStr   HKCU "${REG_UNINST}" "InstallLocation" "$INSTDIR"
  WriteRegStr   HKCU "${REG_UNINST}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr   HKCU "${REG_UNINST}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKCU "${REG_UNINST}" "NoModify" 1
  WriteRegDWORD HKCU "${REG_UNINST}" "NoRepair" 1
  WriteRegDWORD HKCU "${REG_UNINST}" "EstimatedSize" $0
SectionEnd

; ---------------------------------------------------------------------------
Section "$(SecShortName)" SecShortcuts
  SetShellVarContext current

  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
SectionEnd

; ---------------------------------------------------------------------------
Section /o "$(SecAsseName)" SecAssoc
  WriteRegStr HKCU "Software\Classes\.tex" "" "EulerSC.tex"
  WriteRegStr HKCU "Software\Classes\EulerSC.tex" "" "TeX document"
  WriteRegStr HKCU "Software\Classes\EulerSC.tex\DefaultIcon" "" "$INSTDIR\${APP_EXE},0"
  WriteRegStr HKCU "Software\Classes\EulerSC.tex\shell\open\command" "" '"$INSTDIR\${APP_EXE}" "%1"'
SectionEnd

; ---------------------------------------------------------------------------
; Runtime check: WebView2 is required, and older Windows 10 images lack it.
; The Ollama service is optional; the app offers to install it on first run.
; ---------------------------------------------------------------------------
Section "-Runtime" SecRuntime
!ifdef BUNDLED
  DetailPrint "Checking the WebView2 runtime"
  ClearErrors
  ReadRegStr $0 HKLM "SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\${WEBVIEW2_GUID}" "pv"
  ${If} ${Errors}
    ReadRegStr $0 HKLM "SOFTWARE\Microsoft\EdgeUpdate\Clients\${WEBVIEW2_GUID}" "pv"
  ${EndIf}
  ${If} ${Errors}
    MessageBox MB_YESNO|MB_ICONQUESTION \
      "WebView2 runtime is not installed. It is required by the interface.$\r$\n$\r$\nOpen the download page now?" \
      IDNO +2
    ExecShell "open" "https://developer.microsoft.com/microsoft-edge/webview2/"
  ${EndIf}
!else
  DetailPrint "Checking for Python"
  nsExec::ExecToStack 'cmd /c python --version'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_ICONSTOP \
      "Python 3.10 or newer was not found.$\r$\n$\r$\nInstall it from python.org and run this installer again, or use the bundled build."
    Abort
  ${EndIf}
!endif
SectionEnd

; ---------------------------------------------------------------------------
; Descriptions shown next to the components
; ---------------------------------------------------------------------------
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecApp}       "$(SecAppDesc)"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecShortcuts} "$(SecShortDesc)"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecAssoc}     "$(SecAsseDesc)"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ===========================================================================
; UNINSTALL
;
; Order matters: stop the processes first, or a running Ollama keeps its files
; locked and the models survive the "delete everything" answer.
; ===========================================================================
Function un.onInit
  !insertmacro MUI_UNGETLANGUAGE
FunctionEnd

Section "Uninstall"
  SetShellVarContext current

  DetailPrint "Stopping running processes"
  ; The app itself, if it is still open
  nsExec::Exec 'taskkill /IM "${APP_EXE}" /F /T'
  ; Ollama: the server and the tray helper, so no file stays locked
  nsExec::Exec 'taskkill /IM "ollama.exe" /F /T'
  nsExec::Exec 'taskkill /IM "ollama app.exe" /F /T'
  Sleep 800

  ; ---------------------------------------------------------------- shortcuts
  Delete "$DESKTOP\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk"
  RMDir  "$SMPROGRAMS\${APP_NAME}"

  ; ------------------------------------------------------------------- files
  RMDir /r "$INSTDIR\app"
  RMDir /r "$INSTDIR\_internal"
  RMDir /r "$INSTDIR\euler"
  RMDir /r "$INSTDIR\python"
  RMDir /r "$INSTDIR\assets"
  RMDir /r "$INSTDIR\web"
  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\requirements.txt"
  Delete "$INSTDIR\LICENSE.txt"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"

  ; file associations, if they were created
  DeleteRegKey HKCU "Software\Classes\EulerSC.tex"
  DeleteRegValue HKCU "Software\Classes\.tex" ""

  DeleteRegKey HKCU "${REG_UNINST}"
  DeleteRegKey HKCU "Software\EulerSC"

  ; --------------------------------------------------------------- app data
  ; Settings, saved matrices, logs and exported PDFs.
  DetailPrint "Removing application data"
  RMDir /r "$APPDATA\EulerSC"
  RMDir /r "$LOCALAPPDATA\EulerSC"

  ; ------------------------------------------------------------------ Ollama
  ; Two questions, because the answers differ: the models are gigabytes and
  ; re-downloading them is expensive, while the service itself is small.
  ReadRegStr $0 HKCU "Software\EulerSC" "UserChoseOllama"
  ${If} $0 != "keep"
    MessageBox MB_YESNO|MB_ICONQUESTION \
      "$(AskRemoveOllama)" IDNO skip_ollama

    DetailPrint "Removing Ollama and its models"
    ; The per-user models live here; the service lives in LOCALAPPDATA
    RMDir /r "$PROFILE\.ollama"
    RMDir /r "$LOCALAPPDATA\Programs\Ollama"
    RMDir /r "$LOCALAPPDATA\Ollama"

    ; The machine-wide installer, when present
    ReadRegStr $1 HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Ollama" "UninstallString"
    ${If} $1 != ""
      ExecWait '$1 /S'
    ${EndIf}
    DeleteRegKey HKCU "Software\Ollama"
    skip_ollama:
  ${EndIf}
SectionEnd

; ---------------------------------------------------------------------------
; Upgrade strings. Every page that can appear during an upgrade is translated:
; an English-only dialog in a Russian or Chinese interface reads as a failure.
; ---------------------------------------------------------------------------
LangString MsgWillUpgrade      ${LANG_RUSSIAN} "Версия ${APP_NAME} будет обновлена."
LangString MsgWillUpgrade      ${LANG_ENGLISH} "${APP_NAME} will be updated."
LangString MsgWillUpgrade      ${LANG_SIMPCHINESE} "将更新 ${APP_NAME}。"
LangString MsgWillUpgrade      ${LANG_SPANISH} "Se actualizará ${APP_NAME}."
LangString MsgWillUpgrade      ${LANG_FRENCH} "${APP_NAME} va être mis à jour."
LangString MsgWillUpgrade      ${LANG_PORTUGUESEBR} "${APP_NAME} será atualizado."

LangString MsgFromVersion      ${LANG_RUSSIAN} "Установлена версия: "
LangString MsgFromVersion      ${LANG_ENGLISH} "Installed version: "
LangString MsgFromVersion      ${LANG_SIMPCHINESE} "已安装版本："
LangString MsgFromVersion      ${LANG_SPANISH} "Versión instalada: "
LangString MsgFromVersion      ${LANG_FRENCH} "Version installée : "
LangString MsgFromVersion      ${LANG_PORTUGUESEBR} "Versão instalada: "

LangString MsgToVersion        ${LANG_RUSSIAN} "Будет установлена: "
LangString MsgToVersion        ${LANG_ENGLISH} "Will be installed: "
LangString MsgToVersion        ${LANG_SIMPCHINESE} "将安装："
LangString MsgToVersion        ${LANG_SPANISH} "Se instalará: "
LangString MsgToVersion        ${LANG_FRENCH} "Sera installée : "
LangString MsgToVersion        ${LANG_PORTUGUESEBR} "Será instalada: "

LangString MsgSettingsKept     ${LANG_RUSSIAN} "Настройки, сохранённые матрицы и история сохранятся."
LangString MsgSettingsKept     ${LANG_ENGLISH} "Settings, saved matrices and history are kept."
LangString MsgSettingsKept     ${LANG_SIMPCHINESE} "设置、已保存的矩阵和将保留。"
LangString MsgSettingsKept     ${LANG_SPANISH} "Se conservan los ajustes, las matrices guardadas y el historial."
LangString MsgSettingsKept     ${LANG_FRENCH} "Les réglages, les matrices enregistrées et l'historique sont conservés."
LangString MsgSettingsKept     ${LANG_PORTUGUESEBR} "Configurações, matrizes salvas e histórico são mantidos."

LangString MsgSameVersion      ${LANG_RUSSIAN} "${APP_NAME} ${APP_VERSION} уже установлена."
LangString MsgSameVersion      ${LANG_ENGLISH} "${APP_NAME} ${APP_VERSION} is already installed."
LangString MsgSameVersion      ${LANG_SIMPCHINESE} "已安装 ${APP_NAME} ${APP_VERSION}。"
LangString MsgSameVersion      ${LANG_SPANISH} "${APP_NAME} ${APP_VERSION} ya está instalado."
LangString MsgSameVersion      ${LANG_FRENCH} "${APP_NAME} ${APP_VERSION} est déjà installé."
LangString MsgSameVersion      ${LANG_PORTUGUESEBR} "${APP_NAME} ${APP_VERSION} já está instalado."

LangString MsgRepair           ${LANG_RUSSIAN} "Файлы программы будут записаны заново. Данные не затрагиваются."
LangString MsgRepair           ${LANG_ENGLISH} "The program files will be written again. Your data is not affected."
LangString MsgRepair           ${LANG_SIMPCHINESE} "将重新写入程序文件。您的数据不受影响。"
LangString MsgRepair           ${LANG_SPANISH} "Se volverán a escribir los archivos del programa. Sus datos no se modifican."
LangString MsgRepair           ${LANG_FRENCH} "Les fichiers du programme seront réécrits. Vos données ne sont pas touchées."
LangString MsgRepair           ${LANG_PORTUGUESEBR} "Os arquivos do programa serão gravados novamente. Seus dados não são afetados."

LangString MsgDowngradeBlocked ${LANG_RUSSIAN} "Установлена более новая версия. Понижение версии заблокировано; для отката запустите установщик с параметром /FORCE."
LangString MsgDowngradeBlocked ${LANG_ENGLISH} "A newer version is already installed. Downgrading is blocked; run the installer with /FORCE to roll back."
LangString MsgDowngradeBlocked ${LANG_SIMPCHINESE} "已安装较新的版本。禁止降级；如需回退，请使用 /FORCE 参数运行安装程序。"
LangString MsgDowngradeBlocked ${LANG_SPANISH} "Ya hay una versión más reciente. La degradación está bloqueada; use /FORCE para volver atrás."
LangString MsgDowngradeBlocked ${LANG_FRENCH} "Une version plus récente est installée. Le retour en arrière est bloqué ; utilisez /FORCE pour l'autoriser."
LangString MsgDowngradeBlocked ${LANG_PORTUGUESEBR} "Já existe uma versão mais recente. O downgrade está bloqueado; use /FORCE para reverter."

LangString MsgInstalledIs      ${LANG_RUSSIAN} "Установлено: "
LangString MsgInstalledIs      ${LANG_ENGLISH} "Installed: "
LangString MsgInstalledIs      ${LANG_SIMPCHINESE} "已安装："
LangString MsgInstalledIs      ${LANG_SPANISH} "Instalado: "
LangString MsgInstalledIs      ${LANG_FRENCH} "Installé : "
LangString MsgInstalledIs      ${LANG_PORTUGUESEBR} "Instalado: "

LangString MsgThisIs           ${LANG_RUSSIAN} "В этом установщике: "
LangString MsgThisIs           ${LANG_ENGLISH} "This installer contains: "
LangString MsgThisIs           ${LANG_SIMPCHINESE} "此安装程序包含："
LangString MsgThisIs           ${LANG_SPANISH} "Este instalador contiene: "
LangString MsgThisIs           ${LANG_FRENCH} "Cet installateur contient : "
LangString MsgThisIs           ${LANG_PORTUGUESEBR} "Este instalador contém: "

LangString MsgClosingOld       ${LANG_RUSSIAN} "Закрывается запущенная копия..."
LangString MsgClosingOld       ${LANG_ENGLISH} "Closing the running copy..."
LangString MsgClosingOld       ${LANG_SIMPCHINESE} "正在关闭正在运行的副本..."
LangString MsgClosingOld       ${LANG_SPANISH} "Cerrando la copia en ejecución..."
LangString MsgClosingOld       ${LANG_FRENCH} "Fermeture de la copie en cours d'exécution..."
LangString MsgClosingOld       ${LANG_PORTUGUESEBR} "Fechando a cópia em execução..."

; ---------------------------------------------------------------------------
LangString AskRemoveOllama ${LANG_RUSSIAN} "Удалить также Ollama и все скачанные модели?$\r$\n$\r$\nМодели занимают несколько гигабайт; при повторной установке их придётся скачать заново.$\r$\n$\r$\nНажмите «Нет», чтобы сохранить Ollama для других программ."
LangString AskRemoveOllama ${LANG_ENGLISH} "Also remove Ollama and every downloaded model?$\r$\n$\r$\nThe models take several gigabytes and would have to be downloaded again.$\r$\n$\r$\nChoose No to keep Ollama for other programs."
LangString AskRemoveOllama ${LANG_SIMPCHINESE} "同时删除 Ollama 及所有已下载的模型？$\r$\n$\r$\n模型体积达数 GB，需要重新下载。$\r$\n$\r$\n选择“否”以保留 Ollama 供其他程序使用。"
LangString AskRemoveOllama ${LANG_SPANISH} "¿Eliminar también Ollama y todos los modelos descargados?$\r$\n$\r$\nLos modelos ocupan varios GB y habría que descargarlos de nuevo.$\r$\n$\r$\nElija No para conservar Ollama para otros programas."
LangString AskRemoveOllama ${LANG_FRENCH} "Supprimer aussi Ollama et tous les modèles téléchargés ?$\r$\n$\r$\nLes modèles occupent plusieurs Go et devraient être téléchargés à nouveau.$\r$\n$\r$\nChoisissez Non pour conserver Ollama pour d'autres programmes."
LangString AskRemoveOllama ${LANG_PORTUGUESEBR} "Remover também o Ollama e todos os modelos baixados?$\r$\n$\r$\nOs modelos ocupam vários GB e teriam de ser baixados novamente.$\r$\n$\r$\nEscolha Não para manter o Ollama para outros programas."
