; -------------------------------
; mark2mind Windows Installer
; -------------------------------

[Setup]
AppId={{A5D7C9B2-6B54-4D3F-9D65-6E0D7B1C3E21}}
AppName=mark2mind
AppVersion=0.1.0                                
AppPublisher=Ahmed Elagami
DefaultDirName={userappdata}\mark2mind
DefaultGroupName=mark2mind
DisableDirPage=no
DisableProgramGroupPage=yes
OutputBaseFilename=mark2mind-setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
; Per-user by default
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Let Inno broadcast env var changes automatically
ChangesEnvironment=yes
UninstallDisplayIcon={app}\mark2mind.exe
MinVersion=8.0.0


[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; << EDIT THIS >> point Source to your built PyInstaller exe
Source: "dist\mark2mind.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\mark2mind"; Filename: "{app}\mark2mind.exe"
Name: "{userdesktop}\mark2mind"; Filename: "{app}\mark2mind.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Registry]
; Store DEEPSEEK_API_KEY under current user; removed on uninstall
; Only write it if user provided a non-empty value
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "DEEPSEEK_API_KEY"; \
  ValueData: "{code:GetApiKey}"; Flags: uninsdeletevalue; Check: HasApiKey

; PATH is modified from [Code]

[Run]
; Optionally open a README or run a quick smoke test after install
; Filename: "{cmd}"; Parameters: "/C ""{app}\mark2mind.exe --help & pause"""; Flags: nowait postinstall skipifsilent unchecked

[Code]
// ---- Helpers & Wizard page ----

var
  ApiPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  { Create a page to collect DEEPSEEK_API_KEY }
  ApiPage := CreateInputQueryPage(wpSelectTasks,
    'DeepSeek API Key',
    'Enter your DEEPSEEK_API_KEY',
    'Paste your DeepSeek API key. You can change it later in "Environment Variables".');
  ApiPage.Add('DEEPSEEK_API_KEY:', False);
end;

function GetApiKey(Param: string): string;
begin
  Result := Trim(ApiPage.Values[0]);
end;

function HasApiKey: Boolean;
begin
  Result := GetApiKey('') <> '';
end;

// ---- PATH manipulation (per-user HKCU\Environment\Path) ----

// Some Inno versions may not expose PosEx; include a safe helper.
function PosEx(const SubStr, S: string; Offset: Integer): Integer;
var
  T: string;
  P: Integer;
begin
  if Offset <= 1 then
  begin
    Result := Pos(SubStr, S);
    Exit;
  end;
  if Offset > Length(S) then
  begin
    Result := 0;
    Exit;
  end;
  T := Copy(S, Offset, MaxInt);
  P := Pos(SubStr, T);
  if P = 0 then Result := 0 else Result := P + Offset - 1;
end;

function CurrentUserPath(): string;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', Result) then
    Result := '';
end;

procedure WriteUserPath(const Value: string);
begin
  { Prefer expand string; fall back to plain string if not supported }
  if not RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Value) then
    RegWriteStringValue(HKCU, 'Environment', 'Path', Value);
end;

function PathContains(AppDir: string): Boolean;
var
  P: string;
begin
  P := ';' + CurrentUserPath() + ';';
  Result := Pos(';' + AppDir + ';', P) > 0;
end;

procedure AddToPath(AppDir: string);
var
  P: string;
begin
  P := CurrentUserPath();
  if P = '' then
    P := AppDir
  else if not PathContains(AppDir) then
    P := P + ';' + AppDir
  else
    Exit; { already present }
  WriteUserPath(P);
end;

procedure RemoveFromPath(AppDir: string);
var
  P, NewP, Part: string;
  I, StartPos: Integer;
begin
  P := CurrentUserPath();
  if P = '' then Exit;

  NewP := '';
  StartPos := 1;
  I := Pos(';', P);
  while I > 0 do
  begin
    Part := Copy(P, StartPos, I - StartPos);
    if (CompareText(Trim(Part), Trim(AppDir)) <> 0) and (Trim(Part) <> '') then
    begin
      if NewP <> '' then NewP := NewP + ';';
      NewP := NewP + Part;
    end;
    StartPos := I + 1;
    I := PosEx(';', P, StartPos);
  end;

  { add the last segment after the final semicolon }
  Part := Copy(P, StartPos, Length(P) - StartPos + 1);
  if (CompareText(Trim(Part), Trim(AppDir)) <> 0) and (Trim(Part) <> '') then
  begin
    if NewP <> '' then NewP := NewP + ';';
    NewP := NewP + Part;
  end;

  WriteUserPath(NewP);
end;

// ---- Install / Uninstall hooks ----

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    { Add install dir to PATH (per-user) }
    AddToPath(ExpandConstant('{app}'));
    { No manual broadcast needed; ChangesEnvironment=yes takes care of it }
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    { Remove install dir from PATH on uninstall }
    RemoveFromPath(ExpandConstant('{app}'));
    { No manual broadcast needed }
  end;
end;
