; ThaiCustoms desktop shortcut installer (Windows).
; Installs a Start Menu + optional Desktop icon that opens the web app
; in the user's default browser. No admin rights required.
;
; Build (CI does this on windows-latest):
;   iscc /DAppVersion=1.0.0 installer.iss
; Output: dist\ThaiCustoms-Setup-<version>-win64.exe
;
; NOTE: the app URL is duplicated in desktop/macos/build-dmg.sh -
; update both files if the gateway URL ever changes.

#ifndef AppVersion
#define AppVersion "1.0.0"
#endif
#define AppURL "https://gateway-1008099094873.asia-southeast1.run.app"
#define AppNameThai "Boy Fans"

[Setup]
AppId={{8C4A2B1E-6F3D-4A9C-9E5B-2D7C1A0F4E63}
AppName={#AppNameThai}
AppVersion={#AppVersion}
AppPublisher=ThaiCustoms
DefaultDirName={localappdata}\ThaiCustoms
DefaultGroupName={#AppNameThai}
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=ThaiCustoms-Setup-{#AppVersion}-win64
Compression=lzma
SolidCompression=yes
SetupIconFile=..\assets\logo.ico
WizardStyle=modern
DisableProgramGroupPage=yes

[Tasks]
Name: desktopicon; Description: "Create desktop icon"; GroupDescription: "Additional icons:"; Flags: checkedonce

[Files]
Source: "..\assets\logo.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppNameThai}"; Filename: "{#AppURL}"; IconFilename: "{app}\logo.ico"
Name: "{autodesktop}\{#AppNameThai}"; Filename: "{#AppURL}"; IconFilename: "{app}\logo.ico"; Tasks: desktopicon

[Run]
Filename: "{#AppURL}"; Description: "Open {#AppNameThai} now"; Flags: postinstall shellexec skipifsilent
