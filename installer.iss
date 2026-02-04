; Inno Setup Script para Utilitários PC
; Requer Inno Setup 6+: https://jrsoftware.org/isinfo.php

#define MyAppName "Utilitários PC"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Projeto Utilitarios"
#define MyAppURL "https://github.com/seu-usuario/utilitarios-pc"
#define MyAppExeName "UtilitariosPC.exe"
#define MyAppDataFolder ".utilitarios"
#define MyAppMutex "UtilitariosPCAppMutex"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={commonpf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=UtilitariosPC_Setup_{#MyAppVersion}
SetupIconFile=app\icone.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

; AppMutex - Detecta se o app está rodando
AppMutex={#MyAppMutex}

; Fechar aplicativo automaticamente
CloseApplications=force
CloseApplicationsFilter=*.exe
RestartApplications=yes

VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Suite de utilitários para Windows
VersionInfoCopyright=Copyright (C) 2026
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupentry"; Description: "Iniciar automaticamente com o Windows"; GroupDescription: "Opções adicionais:"; Flags: unchecked

[Files]
; Executável principal
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; VC++ Redistributable (necessário para Python/Nuitka)
Source: "dist\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "UtilitariosPC"; ValueData: """{app}\{#MyAppExeName}"" --minimized"; Flags: uninsdeletevalue; Tasks: startupentry

[Run]
; Instalar VC++ Redistributable silenciosamente (só se necessário)
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Instalando Microsoft Visual C++ Runtime (necessário para o aplicativo)..."; Flags: waituntilterminated skipifdoesntexist; Check: NeedToInstallVCRedist
; Iniciar o aplicativo
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  RemoveUserData: Boolean;
  VCRedistPage: TOutputMsgWizardPage;

function GetUserDataPath: String;
begin
  Result := ExpandConstant('{%USERPROFILE}') + '\{#MyAppDataFolder}';
end;

// Verifica se o VC++ Runtime já está instalado
function VCRuntimeInstalled: Boolean;
var
  RegValue: String;
begin
  Result := False;
  // Verificar se o VC++ 2015-2022 x64 está instalado
  if RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Version', RegValue) then
    Result := True
  else if RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Version', RegValue) then
    Result := True;
end;

// Usado pela seção [Run] para decidir se instala o VC++ Redist
function NeedToInstallVCRedist: Boolean;
begin
  Result := not VCRuntimeInstalled;
end;

// Adiciona página informativa sobre VC++ Redistributable
procedure InitializeWizard;
begin
  if not VCRuntimeInstalled then
  begin
    VCRedistPage := CreateOutputMsgPage(wpWelcome,
      'Componente Adicional Necessário',
      'Microsoft Visual C++ Runtime será instalado',
      'O {#MyAppName} requer o Microsoft Visual C++ 2015-2022 Redistributable (x64) ' +
      'para funcionar corretamente.' + #13#10 + #13#10 +
      'Este componente NÃO foi detectado no seu sistema e será instalado automaticamente ' +
      'durante a instalação do aplicativo.' + #13#10 + #13#10 +
      'O Visual C++ Runtime é um componente oficial da Microsoft, seguro e necessário ' +
      'para executar aplicativos desenvolvidos em C/C++ e Python.' + #13#10 + #13#10 +
      'Clique em Avançar para continuar.');
  end;
end;

// Chamado no início da desinstalação
function InitializeUninstall(): Boolean;
var
  DataPath: String;
  Msg: String;
  MsgResult: Integer;
begin
  Result := True;
  RemoveUserData := False;
  
  DataPath := GetUserDataPath();
  
  if DirExists(DataPath) then
  begin
    Msg := 'Deseja remover também os dados do usuário?' + #13#10 + #13#10 +
           'Isso inclui:' + #13#10 +
           '  • Histórico de organizações (undo)' + #13#10 +
           '  • Configurações do monitoramento' + #13#10 +
           '  • Histórico da área de transferência' + #13#10 + #13#10 +
           'Localização: ' + DataPath + #13#10 + #13#10 +
           'Sim = remover tudo' + #13#10 +
           'Não = manter dados' + #13#10 +
           'Cancelar = abortar desinstalação';
    
    MsgResult := MsgBox(Msg, mbConfirmation, MB_YESNOCANCEL);
    
    if MsgResult = IDCANCEL then
      Result := False
    else if MsgResult = IDYES then
      RemoveUserData := True;
  end;
end;

// Chamado após a desinstalação
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserDataPath: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'UtilitariosPC');
    RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\Projeto Utilitarios');
    
    if RemoveUserData then
    begin
      UserDataPath := GetUserDataPath();
      if DirExists(UserDataPath) then
        DelTree(UserDataPath, True, True, True);
    end;
  end;
end;
