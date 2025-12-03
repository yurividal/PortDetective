#!/bin/bash
# Build script for macOS application (.app bundle and .dmg)
# Run this script on a macOS system

set -e

echo "========================================"
echo "PortDetective - macOS Build Script"
echo "========================================"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if running on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "Error: This script must be run on macOS"
    exit 1
fi

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    echo "Install with: brew install python3"
    exit 1
fi

# Check for icon file and convert if needed
ICON_PATH=""
if [ -f "icon.png" ]; then
    echo ""
    echo "Icon file found: icon.png"
    
    # Convert PNG to ICNS format for macOS
    echo "Converting icon to .icns format..."
    
    # Create iconset directory
    mkdir -p icon.iconset
    
    # Use sips to resize and create iconset
    sips -z 16 16     icon.png --out icon.iconset/icon_16x16.png 2>/dev/null || true
    sips -z 32 32     icon.png --out icon.iconset/icon_16x16@2x.png 2>/dev/null || true
    sips -z 32 32     icon.png --out icon.iconset/icon_32x32.png 2>/dev/null || true
    sips -z 64 64     icon.png --out icon.iconset/icon_32x32@2x.png 2>/dev/null || true
    sips -z 128 128   icon.png --out icon.iconset/icon_128x128.png 2>/dev/null || true
    sips -z 256 256   icon.png --out icon.iconset/icon_128x128@2x.png 2>/dev/null || true
    sips -z 256 256   icon.png --out icon.iconset/icon_256x256.png 2>/dev/null || true
    sips -z 512 512   icon.png --out icon.iconset/icon_256x256@2x.png 2>/dev/null || true
    sips -z 512 512   icon.png --out icon.iconset/icon_512x512.png 2>/dev/null || true
    sips -z 1024 1024 icon.png --out icon.iconset/icon_512x512@2x.png 2>/dev/null || true
    
    # Convert iconset to icns
    iconutil -c icns icon.iconset -o icon.icns 2>/dev/null || true
    
    if [ -f "icon.icns" ]; then
        ICON_PATH="icon.icns"
        echo "Icon converted successfully"
    else
        echo "Warning: Could not convert icon. Using default."
    fi
    
    # Clean up iconset
    rm -rf icon.iconset
else
    echo "No icon.png found. Using default icon."
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# Clean previous builds
echo ""
echo "Cleaning previous builds..."
rm -rf dist build *.spec

# Build application
echo ""
echo "Building application..."

# Prepare icon argument
ICON_ARG=""
if [ -n "$ICON_PATH" ] && [ -f "$ICON_PATH" ]; then
    ICON_ARG="--icon $ICON_PATH"
fi

pyinstaller --onefile \
    --windowed \
    --name "PortDetective" \
    --osx-bundle-identifier "com.portdetective.app" \
    $ICON_ARG \
    --add-data "README.md:." \
    --hidden-import "scapy.layers.l2" \
    --hidden-import "scapy.contrib.cdp" \
    --hidden-import "scapy.contrib.lldp" \
    --hidden-import "PyQt6.QtCore" \
    --hidden-import "PyQt6.QtWidgets" \
    --hidden-import "PyQt6.QtGui" \
    --collect-all "scapy" \
    main.py

# Check if .app was created
if [ -d "dist/PortDetective.app" ]; then
    echo ""
    echo "Application bundle created successfully!"
    
    # Create DMG
    echo ""
    echo "Creating DMG installer..."
    
    # Create a temporary directory for DMG contents
    DMG_DIR="dist/dmg_contents"
    mkdir -p "$DMG_DIR"
    
    # Copy app to DMG directory
    cp -R "dist/PortDetective.app" "$DMG_DIR/"
    
    # Create a symbolic link to Applications folder
    ln -s /Applications "$DMG_DIR/Applications"
    
    # Create DMG
    DMG_NAME="PortDetective-macOS.dmg"
    rm -f "dist/$DMG_NAME"
    
    # Add background image if icon exists
    if [ -n "$ICON_PATH" ] && [ -f "$ICON_PATH" ]; then
        hdiutil create -volname "PortDetective" \
            -srcfolder "$DMG_DIR" \
            -ov -format UDZO \
            "dist/$DMG_NAME"
    else
        hdiutil create -volname "PortDetective" \
            -srcfolder "$DMG_DIR" \
            -ov -format UDZO \
            "dist/$DMG_NAME"
    fi
    
    # Clean up
    rm -rf "$DMG_DIR"
    
    if [ -f "dist/$DMG_NAME" ]; then
        echo ""
        echo "========================================"
        echo "Build successful!"
        echo "Application: dist/PortDetective.app"
        echo "DMG Installer: dist/$DMG_NAME"
        echo "========================================"
        
        # Show file sizes
        echo ""
        APP_SIZE=$(du -sh "dist/PortDetective.app" | cut -f1)
        DMG_SIZE=$(du -sh "dist/$DMG_NAME" | cut -f1)
        echo "App size: $APP_SIZE"
        echo "DMG size: $DMG_SIZE"
    fi
elif [ -f "dist/PortDetective" ]; then
    echo ""
    echo "========================================"
    echo "Build successful (command-line executable)!"
    echo "Executable: dist/PortDetective"
    echo "========================================"
else
    echo ""
    echo "Build failed!"
    exit 1
fi

# Clean up icon files
rm -f icon.icns

echo ""
echo "Note: The application requires root privileges for packet capture."
echo "Run with: sudo /path/to/PortDetective.app/Contents/MacOS/PortDetective"
echo "Or right-click the app and select 'Open' to grant permissions."
