; Project Chloe 2.0 - Official Inno Setup Windows Installer Script
; Produces a native, single-file Chloe_Setup_v2.0.exe with Desktop/Start Menu shortcuts and Uninstaller.

#define MyAppName "Project Chloe"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Abhishek"
#define MyAppURL "http://localhost:8000"
#define MyAppExeName "Chloe.exe"

[Setup]
AppId={{C8E9B1A2-4D3E-4B7C-9A1F-8E2D7C5B3A1E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE.txt
OutputDir=..\dist
OutputBaseFilename=Chloe_Setup_v2.0
SetupIconFile=..\backend\app\static\favicon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardSmallImageFile=..\backend\app\static\logo.png
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Launch Chloe silently on Windows startup"; GroupDescription: "System Integration:"; Flags: unchecked

[Files]
Source: "..\backend\*"; DestDir: "{app}\backend"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\run.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\run.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\run.bat"; IconFilename: "{app}\backend\app\static\favicon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\run.bat"; IconFilename: "{app}\backend\app\static\favicon.ico"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\run.bat"; IconFilename: "{app}\backend\app\static\favicon.ico"; Tasks: startupicon

[Run]
Filename: "{app}\run.bat"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
