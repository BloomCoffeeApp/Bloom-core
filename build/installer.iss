; Inno Setup script — compiled by build/build.ps1, which passes the brand values
; from brand.json as /D defines. The database lives in %APPDATA%\<dataDirName>
; and is NOT removed on uninstall.

#ifndef AppName
  #define AppName "Bloom"
#endif
#ifndef AppExeName
  #define AppExeName "Bloom"
#endif
#ifndef AppPublisher
  #define AppPublisher "Bloom contributors"
#endif
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6F2B8C1E-4C7A-4E59-9C3B-B100A1CAFE01}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppExeName}
DefaultGroupName={#AppName}
OutputDir=output\installer
OutputBaseFilename={#AppExeName}-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExeName}.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "output\{#AppExeName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}.exe"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent
