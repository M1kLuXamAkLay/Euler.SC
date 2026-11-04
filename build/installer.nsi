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
;   uninstall  uninstaller removes files, shortcuts, registry, app data and,
;              when the user agrees, Ollama together with its models
; ============================================================================

Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

!define APP_NAME      "Euler.SC"
!define APP_EXE       "EulerSC.exe"
!define APP_PUBLISHER "Euler Project"
!define APP_VERSION   "5.0.3"
!define APP_URL       "https://github.com/euler-project/euler"
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
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "$(LaunchApp)"
!define MUI_FINISHPAGE_SHOWREADME ""
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "Russian"
!insertmacro MUI_LANGUAGE "English"

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

; ---------------------------------------------------------------------------
; Remembering the chosen language so the uninstaller speaks it too
; ---------------------------------------------------------------------------

Function .onInit
  !insertmacro MUI_LANGDLL_DISPLAY
FunctionEnd

; ---------------------------------------------------------------------------
Section "$(SecAppName)" SecApp
  SectionIn RO
  SetShellVarContext current
  SetOutPath "$INSTDIR"

  ; The PyInstaller directory bundle: executable, _internal tree and web assets
  File /r "..\dist\EulerSC\*.*"

  ; Seed the interface language from the installer choice: the app reads this
  ; key on first launch and skips its own language question.
  ${If} $LANGUAGE == ${LANG_RUSSIAN}
    WriteRegStr HKCU "Software\EulerSC" "Language" "ru"
  ${Else}
    WriteRegStr HKCU "Software\EulerSC" "Language" "en"
  ${EndIf}

  WriteRegStr HKCU "Software\EulerSC" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\EulerSC" "Version" "${APP_VERSION}"

  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegStr   HKCU "${REG_UNINST}" "DisplayName"     "${APP_NAME}"
  WriteRegStr   HKCU "${REG_UNINST}" "DisplayVersion"  "${APP_VERSION}"
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
LangString AskRemoveOllama ${LANG_RUSSIAN} "Удалить также Ollama и все скачанные модели?$\r$\n$\r$\nМодели занимают несколько гигабайт; при повторной установке их придётся скачать заново.$\r$\n$\r$\nНажмите «Нет», чтобы сохранить Ollama для других программ."
LangString AskRemoveOllama ${LANG_ENGLISH} "Also remove Ollama and every downloaded model?$\r$\n$\r$\nThe models take several gigabytes and would have to be downloaded again.$\r$\n$\r$\nChoose No to keep Ollama for other programs."
