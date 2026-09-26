#define AppVersion "1.0.0"
#define AppName "JARVIS Local"
#define AppExeName "JARVIS.exe"

[Setup]
AppId={{5B99A146-88CA-4F50-90A6-7564E1C43F3D}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=KamekFPS
DefaultDirName={localappdata}\Programs\JARVIS Local
DefaultGroupName=JARVIS Local
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
OutputDir=dist
OutputBaseFilename=JARVIS-Local-Setup
UninstallDisplayIcon={app}\{#AppExeName}
LicenseFile=LICENSE
InfoBeforeFile=TERMS_OF_USE.md
WizardStyle=modern
Compression=lzma2
SolidCompression=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "dist\JARVIS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\JARVIS Local"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\JARVIS Local"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch JARVIS Local"; Flags: postinstall nowait skipifsilent
