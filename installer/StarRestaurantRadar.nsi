Unicode true
RequestExecutionLevel user

!include "MUI2.nsh"
!include "FileFunc.nsh"
!insertmacro GetParameters
!insertmacro GetOptions

!define APP_ID "StarRestaurantRadar"
!define APP_EXE "StarRestaurantRadar.exe"
!define APP_DISPLAY_NAME "스타 레스토랑 레이더"
!define APP_PRODUCT_NAME "Star Restaurant Radar"
!define APP_VERSION "1.0.0"
!define APP_PUBLISHER "YumStoneSteak"
!define APP_REPO_URL "https://github.com/YumStoneSteak/Star-Restaurant-Radar"
!define BUILD_DIR "..\dist\StarRestaurantRadar"

Name "${APP_DISPLAY_NAME}"
OutFile "..\dist\Star-Restaurant-Radar-Setup-v${APP_VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\${APP_PRODUCT_NAME}"
InstallDirRegKey HKCU "Software\${APP_ID}" "InstallDir"

!define MUI_ABORTWARNING
!define MUI_ICON "..\assets\app_icon.ico"
!define MUI_UNICON "..\assets\app_icon.ico"

!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Korean"
!insertmacro MUI_LANGUAGE "English"

Var LaunchAfterInstall

Function .onInit
  StrCpy $LaunchAfterInstall "0"
  ${GetParameters} $R0
  ${GetOptions} $R0 "/LAUNCH=" $R1
  IfErrors done
  StrCpy $LaunchAfterInstall $R1
done:
FunctionEnd

Section "Install"
  SetShellVarContext current
  SetOutPath "$INSTDIR"

  ExecWait 'taskkill /IM "${APP_EXE}" /F'
  ExecWait 'taskkill /IM "ByeolsikdangNotifier.exe" /F'
  ExecWait 'schtasks /Delete /F /TN "ByeolsikdangNotifier"'

  Delete "$INSTDIR\${APP_EXE}"
  RMDir /r "$INSTDIR\_internal"
  RMDir /r "$INSTDIR\assets"

  File /r "${BUILD_DIR}\*.*"

  CreateDirectory "$SMPROGRAMS\${APP_PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${APP_PRODUCT_NAME}\${APP_DISPLAY_NAME}.lnk" "$INSTDIR\${APP_EXE}"

  WriteRegStr HKCU "Software\${APP_ID}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "DisplayName" "${APP_DISPLAY_NAME}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "URLInfoAbout" "${APP_REPO_URL}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "DisplayIcon" "$INSTDIR\${APP_EXE}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}" "NoRepair" 1
  WriteUninstaller "$INSTDIR\uninstall.exe"

  StrCmp $LaunchAfterInstall "1" 0 done
  Exec '"$INSTDIR\${APP_EXE}" --minimized'
done:
SectionEnd

Section "Uninstall"
  SetShellVarContext current

  ExecWait 'taskkill /IM "${APP_EXE}" /F'
  Delete "$SMPROGRAMS\${APP_PRODUCT_NAME}\${APP_DISPLAY_NAME}.lnk"
  RMDir "$SMPROGRAMS\${APP_PRODUCT_NAME}"

  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\uninstall.exe"
  RMDir /r "$INSTDIR\_internal"
  RMDir /r "$INSTDIR\assets"

  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}"
  DeleteRegKey HKCU "Software\${APP_ID}"

  RMDir "$INSTDIR"
SectionEnd
