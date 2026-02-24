; PortDetective Inno Setup Script
; This script creates a Windows installer with:
; - Npcap dependency detection and installation prompt
; - Installation to Program Files
; - Optional Start Menu and Desktop shortcuts

#define MyAppName "PortDetective"
#define MyAppVersion "1.6.0"
#define MyAppPublisher "PortDetective"
#define MyAppURL "https://github.com/yurividal/PortDetective"
#define MyAppExeName "PortDetective.exe"

[Setup]
; Application info
AppId={{B8F3D2E1-4A5C-6D7E-8F9A-0B1C2D3E4F5A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Allow user to disable Start Menu folder
AllowNoIcons=yes
; License and info files (optional)
; LicenseFile=LICENSE.txt
InfoBeforeFile=README.md
; Output settings
OutputDir=dist
OutputBaseFilename=PortDetective-Setup
SetupIconFile=icon.ico
; Compression
Compression=lzma2
SolidCompression=yes
; Modern installer look
WizardStyle=modern
; Require admin (needed for Program Files and Npcap)
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
; Uninstaller
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenuicon"; Description: "Create a Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; Main application folder (onedir build for fast startup)
Source: "dist\PortDetective\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Icon file for shortcuts
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion
; README
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu shortcut (if selected)
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startmenuicon
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"; Tasks: startmenuicon
; Desktop shortcut (if selected)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Option to run the app after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent runascurrentuser

[Code]
// Check if Npcap is installed by looking for the DLL
function IsNpcapInstalled: Boolean;
begin
  Result := FileExists(ExpandConstant('{sys}\Npcap\wpcap.dll')) or 
            FileExists(ExpandConstant('{sys}\wpcap.dll'));
end;

// Check if WinPcap is installed (legacy)
function IsWinPcapInstalled: Boolean;
begin
  Result := FileExists(ExpandConstant('{sys}\wpcap.dll')) and 
            FileExists(ExpandConstant('{sys}\Packet.dll'));
end;

// Called during initialization
function InitializeSetup(): Boolean;
var
  NpcapResult: Integer;
begin
  Result := True;
  
  // Check for Npcap/WinPcap
  if not IsNpcapInstalled() and not IsWinPcapInstalled() then
  begin
    NpcapResult := MsgBox(
      'PortDetective requires Npcap to capture network packets.' + #13#10 + #13#10 +
      'Npcap is not currently installed on your system.' + #13#10 + #13#10 +
      'Would you like to download Npcap now?' + #13#10 + #13#10 +
      '(Click Yes to open the Npcap download page, No to continue anyway, or Cancel to abort installation)',
      mbConfirmation, MB_YESNOCANCEL);
    
    case NpcapResult of
      IDYES:
        begin
          // Open Npcap download page
          ShellExec('open', 'https://npcap.com/#download', '', '', SW_SHOWNORMAL, ewNoWait, NpcapResult);
          MsgBox(
            'Please download and install Npcap from the website that just opened.' + #13#10 + #13#10 +
            'IMPORTANT: During Npcap installation, make sure to check:' + #13#10 +
            '  "Install Npcap in WinPcap API-compatible Mode"' + #13#10 + #13#10 +
            'After installing Npcap, run this installer again or launch PortDetective from the installation folder.',
            mbInformation, MB_OK);
          Result := False; // Abort installation to let user install Npcap first
        end;
      IDNO:
        begin
          // Continue anyway, but warn the user
          MsgBox(
            'Installation will continue, but PortDetective will not work until Npcap is installed.' + #13#10 + #13#10 +
            'You can download Npcap later from: https://npcap.com/',
            mbInformation, MB_OK);
          Result := True;
        end;
      IDCANCEL:
        begin
          Result := False; // Abort installation
        end;
    end;
  end;
end;

// Show a reminder at the end if Npcap is still not installed
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not IsNpcapInstalled() and not IsWinPcapInstalled() then
    begin
      MsgBox(
        'Reminder: Npcap is required for PortDetective to capture network packets.' + #13#10 + #13#10 +
        'Please install Npcap from https://npcap.com/ before running PortDetective.',
        mbInformation, MB_OK);
    end;
  end;
end;
