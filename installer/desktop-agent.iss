#ifndef AppVersion
  #error AppVersion must be provided by the release script
#endif
#ifndef SourceDir
  #error SourceDir must be provided by the release script
#endif
#ifndef OutputDir
  #error OutputDir must be provided by the release script
#endif
#ifndef InstallerDir
  #error InstallerDir must be provided by the release script
#endif

#define AppName "Desktop Agent"
#define AppExeName "DesktopAgent.exe"

[Setup]
AppId={{8C4D0DA9-5345-446A-B4C1-ADCA71EB4DA6}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Desktop Agent Contributors
DefaultDirName={localappdata}\Programs\Desktop Agent
DefaultGroupName=Desktop Agent
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UsedUserAreasWarning=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
SourceDir={#SourceDir}
OutputDir={#OutputDir}
OutputBaseFilename=DesktopAgent-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UsePreviousTasks=no
Uninstallable=yes
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExeName}
SetupLogging=yes

[Languages]
Name: "chinesesimplified"; MessagesFile: "{#InstallerDir}\languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式："

[Files]
Source: "*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Desktop Agent"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Desktop Agent"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[CustomMessages]
chinesesimplified.LaunchApp=启动 Desktop Agent
english.LaunchApp=Launch Desktop Agent

[Code]
var
  LaunchCheckBox: TNewCheckBox;

procedure InitializeWizard;
begin
  LaunchCheckBox := TNewCheckBox.Create(WizardForm.FinishedPage);
  LaunchCheckBox.Parent := WizardForm.FinishedPage;
  LaunchCheckBox.Left := WizardForm.RunList.Left;
  LaunchCheckBox.Top := WizardForm.RunList.Top;
  LaunchCheckBox.Width := WizardForm.RunList.Width;
  LaunchCheckBox.Height := ScaleY(20);
  LaunchCheckBox.Caption := CustomMessage('LaunchApp');
  LaunchCheckBox.Checked := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  if (CurPageID = wpFinished) and LaunchCheckBox.Checked then
    Exec(ExpandConstant('{app}\{#AppExeName}'), '', '', SW_SHOWNORMAL,
      ewNoWait, ResultCode);
end;
