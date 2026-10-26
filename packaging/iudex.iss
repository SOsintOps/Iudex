; Installer di Iudex per Windows (Inno Setup 6). Installazione per l'utente, senza diritti di
; amministratore; i dati restano in %APPDATA%\Iudex anche dopo la disinstallazione.
; Compilazione: ISCC /DVersione=0.7.0 /DSorgente=build\dist\Iudex packaging\iudex.iss

#ifndef Versione
  #define Versione "0.0.0"
#endif
#ifndef Sorgente
  #define Sorgente "..\build\dist\Iudex"
#endif

[Setup]
AppId={{6F2C1E0A-3B7D-4C55-9E1A-1D0B6A7C2F11}
AppName=Iudex
AppVersion={#Versione}
AppPublisher=SOsintOps
AppPublisherURL=https://github.com/SOsintOps/Iudex
DefaultDirName={localappdata}\Programs\Iudex
DefaultGroupName=Iudex
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=Iudex-{#Versione}-setup
OutputDir=..\build\installer
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\iudex\static\favicon.ico
UninstallDisplayIcon={app}\Iudex.exe
CloseApplications=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "italiano"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktop"; Description: "Icona sul desktop"; GroupDescription: "Collegamenti:"

[Files]
Source: "{#Sorgente}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Iudex"; Filename: "{app}\Iudex.exe"
Name: "{userdesktop}\Iudex"; Filename: "{app}\Iudex.exe"; Tasks: desktop

[Run]
Filename: "{app}\Iudex.exe"; Description: "Avvia Iudex"; Flags: nowait postinstall skipifsilent
