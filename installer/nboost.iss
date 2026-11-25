; Nboost - Inno Setup 6/7 installer script
; Build the exe FIRST (pyinstaller nboost.spec), then compile this with
; Inno Setup Compiler (ISCC.exe) - see BUILD.md for the exact commands.
;
; Output: installer/Output/NboostSetup.exe

#define MyAppName "Nboost"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "NengzXGODZ"
#define MyAppURL "https://github.com/NengzXGODZ"
#define MyAppExeName "Nboost.exe"

[Setup]
AppId={{B4C1E8F2-6A3D-4E9B-9F10-2D7A5C3E8A91}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=Output
OutputBaseFilename=NboostSetup
SetupIconFile=..\nboost\resources\nboost.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Nboost needs admin for Event Logs / Windows Update cache / RAM standby purge
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; Built by PyInstaller into ..\dist\Nboost.exe - adjust the path if you build
; elsewhere. onefile build = just the exe; onedir build = the whole folder.
Source: "..\dist\Nboost.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
