[Setup]
AppName=Trilan NVR Backup Agent
AppVersion=1.0
DefaultDirName={pf}\Trilan NVR Backup Agent
DefaultGroupName=Trilan NVR
OutputBaseFilename=TrilanAgentSetup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
OutputDir=dist

[Files]
Source: "dist\TrilanAgentService.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\TrilanAgentTray.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Trilan Agent Tray"; Filename: "{app}\TrilanAgentTray.exe"
Name: "{commonstartup}\Trilan Agent Tray"; Filename: "{app}\TrilanAgentTray.exe"

[Run]
Filename: "{app}\TrilanAgentService.exe"; Parameters: "install"; Flags: runhidden
Filename: "{app}\TrilanAgentService.exe"; Parameters: "start"; Flags: runhidden
Filename: "{app}\TrilanAgentTray.exe"; Flags: nowait postinstall; Description: "Iniciar o Trilan Agent Tray agora"

[UninstallRun]
Filename: "{app}\TrilanAgentService.exe"; Parameters: "stop"; Flags: runhidden
Filename: "{app}\TrilanAgentService.exe"; Parameters: "remove"; Flags: runhidden
Filename: "taskkill"; Parameters: "/f /im TrilanAgentTray.exe"; Flags: runhidden

[Code]
var
  ConfigPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  ConfigPage := CreateInputQueryPage(wpSelectDir,
    'Configuração do Agente Trilan',
    'Insira os dados de conexão com o servidor na nuvem.',
    'Esses dados serão salvos no arquivo agent.conf.');

  ConfigPage.Add('URL do Servidor:', False);
  ConfigPage.Add('Client ID:', False);
  ConfigPage.Add('API Key:', False);
  
  // Sugestões de placeholders
  ConfigPage.Values[0] := 'http://192.168.75.112:7001';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  if CurPageID = ConfigPage.ID then
  begin
    if Trim(ConfigPage.Values[0]) = '' then
    begin
      MsgBox('Por favor, informe a URL do Servidor.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if Trim(ConfigPage.Values[1]) = '' then
    begin
      MsgBox('Por favor, informe o Client ID do cliente.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigFile: String;
  ConfigContent: TArrayOfString;
begin
  if CurStep = ssInstall then
  begin
    ConfigFile := ExpandConstant('{app}\agent.conf');
    SetArrayLength(ConfigContent, 7);
    ConfigContent[0] := '[server]';
    ConfigContent[1] := 'url = ' + Trim(ConfigPage.Values[0]);
    ConfigContent[2] := '';
    ConfigContent[3] := '[auth]';
    ConfigContent[4] := 'client_id = ' + Trim(ConfigPage.Values[1]);
    ConfigContent[5] := 'api_key = ' + Trim(ConfigPage.Values[2]);
    ConfigContent[6] := '';
    SaveStringsToFile(ConfigFile, ConfigContent, False);
  end;
end;
