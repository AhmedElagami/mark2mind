; -------------------------------
; mark2mind Windows Installer (Nuitka folder build)
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
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ChangesEnvironment=yes
UninstallDisplayIcon={app}\mark2mind.exe
MinVersion=8.0.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; *** Nuitka folder build output ***
; Copy the entire .dist folder created by: build\mark2mind.dist\
Source: "build\mark2mind.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\mark2mind"; Filename: "{app}\mark2mind.exe"
Name: "{userdesktop}\mark2mind"; Filename: "{app}\mark2mind.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Registry]
; Optional: store user-provided DEEPSEEK_API_KEY under HKCU and remove on uninstall
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "DEEPSEEK_API_KEY"; \
  ValueData: "{code:GetApiKey}"; Flags: uninsdeletevalue; Check: HasApiKey

[Run]
; Optional smoke test after install (unchecked by default)
; Filename: "{cmd}"; Parameters: "/C """"{app}\mark2mind.exe"" --help & pause"""; Flags: nowait postinstall skipifsilent unchecked

[Code]
// ---- Helpers & Wizard page ----
var
  ApiPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
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
function PosEx(const SubStr, S: string; Offset: Integer): Integer;
var
  T: string; P: Integer;
begin
  if Offset <= 1 then begin Result := Pos(SubStr, S); Exit; end;
  if Offset > Length(S) then begin Result := 0; Exit; end;
  T := Copy(S, Offset, MaxInt); P := Pos(SubStr, T);
  if P = 0 then Result := 0 else Result := P + Offset - 1;
end;

function CurrentUserPath(): string;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', Result) then Result := '';
end;

procedure WriteUserPath(const Value: string);
begin
  if not RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Value) then
    RegWriteStringValue(HKCU, 'Environment', 'Path', Value);
end;

function PathContains(AppDir: string): Boolean;
var P: string;
begin
  P := ';' + CurrentUserPath() + ';';
  Result := Pos(';' + AppDir + ';', P) > 0;
end;

procedure AddToPath(AppDir: string);
var P: string;
begin
  P := CurrentUserPath();
  if P = '' then P := AppDir
  else if not PathContains(AppDir) then P := P + ';' + AppDir
  else Exit;
  WriteUserPath(P);
end;

procedure RemoveFromPath(AppDir: string);
var P, NewP, Part: string; I, StartPos: Integer;
begin
  P := CurrentUserPath(); if P = '' then Exit;
  NewP := ''; StartPos := 1; I := Pos(';', P);
  while I > 0 do begin
    Part := Copy(P, StartPos, I - StartPos);
    if (CompareText(Trim(Part), Trim(AppDir)) <> 0) and (Trim(Part) <> '') then begin
      if NewP <> '' then NewP := NewP + ';';
      NewP := NewP + Part;
    end;
    StartPos := I + 1; I := PosEx(';', P, StartPos);
  end;
  Part := Copy(P, StartPos, Length(P) - StartPos + 1);
  if (CompareText(Trim(Part), Trim(AppDir)) <> 0) and (Trim(Part) <> '') then begin
    if NewP <> '' then NewP := NewP + ';';
    NewP := NewP + Part;
  end;
  WriteUserPath(NewP);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    AddToPath(ExpandConstant('{app}'));
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then begin
    RemoveFromPath(ExpandConstant('{app}'));
  end;
end;
