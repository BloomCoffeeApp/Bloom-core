; Inno Setup script — compiled by build/build.ps1, which passes the brand values from
; brand.json (name, exe, publisher, version) as /D defines.
;
; Per-user install (no UAC prompt): the app goes to %LOCALAPPDATA%\Programs\<AppName>, so the
; in-app updater can run a newer installer silently without admin rights:
;   Bloom-Setup-x.y.z.exe /SILENT /SUPPRESSMSGBOXES /NORESTART /UPDATE=1
; /UPDATE=1 reopens the app when the install finishes. CloseApplications closes a running copy.
;
; User data (database, backups, license) lives in %APPDATA%\<dataDirName> and is NEVER touched
; by the installer or the uninstaller.
;
; No firewall rule: a per-user installer can't add one. When LAN mode starts listening, Windows
; shows its own "allow access" prompt (the LAN help in the app explains it).

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
  #define AppVersion "0.0.0"
#endif
#ifndef AppMutexName
  ; launcher.py: f"{appId}-app-running"
  #define AppMutexName "bloom-cafe-app-running"
#endif
#ifndef SourceDir
  #define SourceDir "output\" + AppExeName
#endif

[Setup]
AppId={{6F2B8C1E-4C7A-4E59-9C3B-B100A1CAFE01}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
VersionInfoVersion={#AppVersion}
AppPublisher={#AppPublisher}
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
UsePreviousAppDir=yes
OutputDir=output\installer
OutputBaseFilename={#AppExeName}-Setup-{#AppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExeName}.exe
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[InstallDelete]
; An update replaces the whole program folder content (never the user data in %APPDATA%).
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}.exe"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}.exe"; Description: "Abrir {#AppName}"; Flags: nowait postinstall skipifsilent; Check: not IsUpdate
; Silent in-app update: reopen the app once the new version is in place.
Filename: "{app}\{#AppExeName}.exe"; Flags: nowait; Check: IsUpdate

[Code]
function IsUpdate(): Boolean;
begin
  Result := ExpandConstant('{param:UPDATE|0}') = '1';
end;

{ In-app update: the app launches us and then closes itself. Wait (up to 60 s) until it's gone
  before replacing its files: without admin rights the Restart Manager can't always close it. }
function InitializeSetup(): Boolean;
var
  Tries: Integer;
begin
  Result := True;
  if IsUpdate() then
  begin
    Tries := 0;
    while CheckForMutexes('{#AppMutexName}') and (Tries < 120) do
    begin
      Sleep(500);
      Tries := Tries + 1;
    end;
    Log(Format('Update mode: waited %d ms for the app to close', [Tries * 500]));
  end;
end;
