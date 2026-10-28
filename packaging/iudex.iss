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

[Code]
// Cartella dei PDF scelta qui e scritta in %APPDATA%\Iudex\installazione.ini ([pdf] cartella):
// Iudex la legge al primo avvio; poi si cambia dalla scheda Impostazioni.
var
  PaginaPdf: TInputDirWizardPage;

function FileInstallazione: String;
begin
  Result := ExpandConstant('{userappdata}\Iudex\installazione.ini');
end;

function WebView2Presente: Boolean;
var
  Versione: String;
begin
  // Il runtime WebView2 Evergreen si registra con questo id (documentazione Microsoft).
  Result :=
    (RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Versione) and (Versione <> '') and (Versione <> '0.0.0.0')) or
    (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Versione) and (Versione <> '') and (Versione <> '0.0.0.0'));
end;

function InitializeSetup: Boolean;
begin
  Result := True;
  if not WebView2Presente then
    MsgBox('La finestra di Iudex usa Microsoft Edge WebView2, che su questo computer non risulta installato (su Windows 11 c''è già).' + #13#10 + #13#10 +
      'Installalo da https://developer.microsoft.com/microsoft-edge/webview2/ (Evergreen Bootstrapper) prima di avviare Iudex.',
      mbInformation, MB_OK);
end;

procedure InitializeWizard;
var
  Attuale: String;
begin
  PaginaPdf := CreateInputDirPage(wpSelectDir, 'Cartella dei PDF',
    'Dove vuoi conservare i PDF delle sentenze?',
    'Iudex salva qui il PDF di ogni sentenza che apri, la prima volta, e poi lo riapre da qui senza chiederlo di nuovo alla Corte. Puoi cambiarla in seguito dalla scheda Impostazioni.',
    False, '');
  PaginaPdf.Add('');
  Attuale := GetIniString('pdf', 'cartella', '', FileInstallazione);
  if Attuale = '' then
    Attuale := ExpandConstant('{userappdata}\Iudex\pdf');
  PaginaPdf.Values[0] := Attuale;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Righe: TArrayOfString;
begin
  if CurStep = ssPostInstall then
  begin
    ForceDirectories(ExpandConstant('{userappdata}\Iudex'));
    ForceDirectories(PaginaPdf.Values[0]);
    SetArrayLength(Righe, 3);
    Righe[0] := '; Scritto dall''installer di Iudex: cartella dei PDF scelta all''installazione.';
    Righe[1] := '[pdf]';
    Righe[2] := 'cartella = ' + PaginaPdf.Values[0];
    SaveStringsToUTF8File(FileInstallazione, Righe, False);
  end;
end;
