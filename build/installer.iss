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
; LAN mode (tablets, menu QR): let the app accept connections on private networks only.
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#AppName}"" dir=in action=allow program=""{app}\{#AppExeName}.exe"" enable=yes profile=private"; Flags: runhidden
Filename: "{app}\{#AppExeName}.exe"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#AppName}"" program=""{app}\{#AppExeName}.exe"""; Flags: runhidden; RunOnceId: "DelFirewallRule"
