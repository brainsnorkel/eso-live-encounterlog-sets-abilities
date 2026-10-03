; Inno Setup script for ESO Log Tail (GUI)
; Build: iscc /DAppVersion=x.y.z installer\esolog-gui.iss
; Expects the PyInstaller onedir output at dist\esolog-gui\

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "ESO Log Tail"
#define AppExe "esolog-gui.exe"
#define AppPublisher "brainsnorkel"
#define AppURL "https://github.com/brainsnorkel/eso-live-encounterlog-sets-abilities"

[Setup]
; Stable AppId GUID: never change, so newer versions upgrade in place
AppId={{7E2C4A9B-1D3F-4E8A-9C5B-6F0A2B8D4E71}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\ESO Log Tail
DefaultGroupName={#AppName}
; Per-user install: no administrator rights required
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=esolog-tail-windows-setup-{#AppVersion}
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\esolog-gui\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; The in-app "start when I sign in" toggle writes this value; remove it on
; uninstall so no stale autostart survives (never created at install time)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "ESO Log Tail"; Flags: uninsdeletevalue dontcreatekey

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

; Uninstall removes installed files and shortcuts only; the user's
; config.json (per-user config dir) and archived logs are left in place.
