# Build script for Windows executable
# Run this script from PowerShell as Administrator

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PortDetective - Windows Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Warning: Not running as Administrator. Some features may not work." -ForegroundColor Yellow
}

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Check for icon file
$iconPath = Join-Path $scriptDir "icon.png"
$icoPath = Join-Path $scriptDir "icon.ico"

if (Test-Path $iconPath) {
    Write-Host "`nIcon file found: $iconPath" -ForegroundColor Green
    
    # Convert PNG to ICO if needed (requires the icon file to already be .ico, or use a converter)
    # For now, we'll use the PNG and convert it using Python
    Write-Host "Converting icon to .ico format..." -ForegroundColor Yellow
    
    $convertScript = @"
from PIL import Image
import sys
try:
    img = Image.open('icon.png')
    # Create multiple sizes for better Windows icon support
    img.save('icon.ico', format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
    print('Icon converted successfully')
except Exception as e:
    print(f'Warning: Could not convert icon: {e}')
    sys.exit(1)
"@
    
    # Try to convert using PIL (will be installed with requirements)
    python -c $convertScript 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Note: Could not convert icon. Using default icon." -ForegroundColor Yellow
        $icoPath = $null
    }
}
else {
    Write-Host "No icon.png found. Using default icon." -ForegroundColor Yellow
    $icoPath = $null
}

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Host "`nCreating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "`nActivating virtual environment..." -ForegroundColor Yellow
& "$scriptDir\venv\Scripts\Activate.ps1"

# Install dependencies
Write-Host "`nInstalling dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt
pip install pyinstaller pillow

# Clean previous builds
Write-Host "`nCleaning previous builds..." -ForegroundColor Yellow
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "*.spec") { Remove-Item -Force "*.spec" }

# Build executable
Write-Host "`nBuilding executable..." -ForegroundColor Yellow

# Prepare icon argument
if ($icoPath -and (Test-Path $icoPath)) {
    $iconArg = "--icon `"$icoPath`""
}
else {
    $iconArg = ""
}

# Build command
$buildArgs = @(
    "--onefile",
    "--windowed",
    "--name", "PortDetective"
)

if ($icoPath -and (Test-Path $icoPath)) {
    $buildArgs += "--icon"
    $buildArgs += $icoPath
}

# Bundle icon.png for runtime window icon
if (Test-Path "icon.png") {
    $buildArgs += "--add-data"
    $buildArgs += "icon.png;."
}

$buildArgs += @(
    "--add-data", "README.md;.",
    "--hidden-import", "scapy.layers.l2",
    "--hidden-import", "scapy.contrib.cdp",
    "--hidden-import", "scapy.contrib.lldp",
    "--hidden-import", "PyQt6.QtCore",
    "--hidden-import", "PyQt6.QtWidgets",
    "--hidden-import", "PyQt6.QtGui",
    "--collect-all", "scapy",
    "main.py"
)

pyinstaller @buildArgs

# Check if build was successful
if (Test-Path "dist\PortDetective.exe") {
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "Executable build successful!" -ForegroundColor Green
    Write-Host "Executable: dist\PortDetective.exe" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    
    # Show file size
    $size = (Get-Item "dist\PortDetective.exe").Length / 1MB
    Write-Host "File size: $([math]::Round($size, 2)) MB" -ForegroundColor Cyan
}
else {
    Write-Host "`nBuild failed!" -ForegroundColor Red
    exit 1
}

# Build installer using Inno Setup
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Building Windows Installer..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Find Inno Setup compiler
$isccPaths = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 5\ISCC.exe"
)

$isccPath = $null
foreach ($path in $isccPaths) {
    if (Test-Path $path) {
        $isccPath = $path
        break
    }
}

if ($isccPath) {
    Write-Host "Found Inno Setup at: $isccPath" -ForegroundColor Green
    
    # Run Inno Setup compiler
    & $isccPath "installer.iss"
    
    if (Test-Path "dist\PortDetective-Setup.exe") {
        Write-Host "`n========================================" -ForegroundColor Green
        Write-Host "Installer build successful!" -ForegroundColor Green
        Write-Host "Installer: dist\PortDetective-Setup.exe" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        
        $installerSize = (Get-Item "dist\PortDetective-Setup.exe").Length / 1MB
        Write-Host "Installer size: $([math]::Round($installerSize, 2)) MB" -ForegroundColor Cyan
    }
    else {
        Write-Host "Installer build failed!" -ForegroundColor Red
    }
}
else {
    Write-Host "Inno Setup not found. Skipping installer creation." -ForegroundColor Yellow
    Write-Host "To create an installer, install Inno Setup from: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    Write-Host "The standalone executable is still available at: dist\PortDetective.exe" -ForegroundColor Yellow
}

Write-Host "`nNote: The application requires Npcap to be installed on the target system." -ForegroundColor Yellow
Write-Host "The installer will prompt users to download Npcap if not detected." -ForegroundColor Yellow
