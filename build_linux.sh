#!/bin/bash
# Build script for Linux (.deb package)
# Run this script on a Debian/Ubuntu-based system

set -e

echo "========================================"
echo "PortDetective - Linux Build Script"
echo "========================================"

# Get script directory first (needed for version lookup)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
APP_NAME="portdetective"
APP_VERSION="${APP_VERSION_OVERRIDE:-$(python3 -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); from version import APP_VERSION; print(APP_VERSION)")}"
MAINTAINER="PortDetective <portdetective@example.com>"
DESCRIPTION="A cross-platform GUI application for listening to CDP and LLDP discovery protocol packets"

get_appimage_arch() {
    case "$(uname -m)" in
        x86_64|amd64)
            echo "x86_64"
            ;;
        aarch64|arm64)
            echo "aarch64"
            ;;
        *)
            return 1
            ;;
    esac
}

download_file() {
    local url="$1"
    local output_path="$2"

    if command -v curl &> /dev/null; then
        curl -fsSL "$url" -o "$output_path"
        return 0
    fi

    if command -v wget &> /dev/null; then
        wget -qO "$output_path" "$url"
        return 0
    fi

    echo "Error: curl or wget is required to download AppImage tooling"
    return 1
}

create_appimage() {
    local appimage_arch appimage_build_dir appdir appimagetool_dir appimagetool_path
    local appimagetool_url desktop_file output_file appimage_size

    echo ""
    echo "Creating AppImage package..."

    if ! appimage_arch="$(get_appimage_arch)"; then
        echo "Error: unsupported AppImage architecture: $(uname -m)"
        return 1
    fi

    appimage_build_dir=".appimage-build"
    appdir="$appimage_build_dir/PortDetective.AppDir"
    appimagetool_dir="$appimage_build_dir/tools"
    appimagetool_path="$appimagetool_dir/appimagetool-${appimage_arch}.AppImage"
    appimagetool_url="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${appimage_arch}.AppImage"
    desktop_file="$appdir/portdetective.desktop"
    output_file="dist/PortDetective-Linux-${APP_VERSION}-${appimage_arch}.AppImage"

    mkdir -p "$appdir/usr/bin"
    mkdir -p "$appdir/usr/share/applications"
    mkdir -p "$appdir/usr/share/doc/$APP_NAME"
    mkdir -p "$appdir/usr/share/icons/hicolor/256x256/apps"
    mkdir -p "$appimagetool_dir"

    if [ ! -f "$appimagetool_path" ]; then
        echo "Downloading appimagetool..."
        download_file "$appimagetool_url" "$appimagetool_path"
        chmod 755 "$appimagetool_path"
    fi

    rm -rf "$appdir"
    mkdir -p "$appdir/usr/bin"
    mkdir -p "$appdir/usr/share/applications"
    mkdir -p "$appdir/usr/share/doc/$APP_NAME"
    mkdir -p "$appdir/usr/share/icons/hicolor/256x256/apps"

    cp "dist/portdetective" "$appdir/usr/bin/portdetective-bin"
    chmod 755 "$appdir/usr/bin/portdetective-bin"
    cp "linux_appimage_apprun.sh" "$appdir/AppRun"
    chmod 755 "$appdir/AppRun"
    cp README.md "$appdir/usr/share/doc/$APP_NAME/"

    cat > "$desktop_file" << EOF
[Desktop Entry]
Name=PortDetective
Comment=CDP and LLDP Discovery Protocol Monitor
Exec=AppRun
Icon=portdetective
Terminal=false
Type=Application
Categories=Network;Monitor;System;
Keywords=CDP;LLDP;Cisco;network;discovery;neighbor;protocol;
StartupWMClass=portdetective
X-AppImage-Version=$APP_VERSION
EOF
    cp "$desktop_file" "$appdir/usr/share/applications/portdetective.desktop"

    if [ -n "$ICON_FILE" ] && [ -f "$ICON_FILE" ]; then
        cp "$ICON_FILE" "$appdir/portdetective.png"
        cp "$ICON_FILE" "$appdir/usr/share/icons/hicolor/256x256/apps/portdetective.png"
        ln -sf "portdetective.png" "$appdir/.DirIcon"
    fi

    rm -f "$output_file"
    ARCH="$appimage_arch" "$appimagetool_path" --appimage-extract-and-run "$appdir" "$output_file"

    if [ ! -f "$output_file" ]; then
        echo "Error: AppImage build failed"
        return 1
    fi

    appimage_size=$(du -sh "$output_file" | cut -f1)
    echo "AppImage created: $output_file"
    echo "AppImage size: $appimage_size"
}

# Check if running on Linux
if [[ "$(uname)" != "Linux" ]]; then
    echo "Error: This script must be run on Linux"
    exit 1
fi

# Check for required tools
echo ""
echo "Checking required tools..."

if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required. Install with: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

if ! command -v dpkg-deb &> /dev/null; then
    echo "Error: dpkg-deb is required. Install with: sudo apt install dpkg"
    exit 1
fi

# Check for icon file
ICON_FILE=""
if [ -f "icon.png" ]; then
    echo "Icon file found: icon.png"
    ICON_FILE="icon.png"
else
    echo "No icon.png found. Will create default icon."
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
if ! python -m pip --version &> /dev/null; then
    echo "Bootstrapping pip in the virtual environment..."
    python -m ensurepip --upgrade
fi

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

# Clean previous builds
echo ""
echo "Cleaning previous builds..."
rm -rf dist build *.spec
rm -rf "${APP_NAME}_${APP_VERSION}"
rm -rf .appimage-build

# Build executable with PyInstaller
echo ""
echo "Building executable..."
pyinstaller --onefile \
    --name "portdetective" \
    --add-data "README.md:." \
    --hidden-import "scapy.layers.l2" \
    --hidden-import "scapy.contrib.cdp" \
    --hidden-import "scapy.contrib.lldp" \
    --hidden-import "PyQt6.QtCore" \
    --hidden-import "PyQt6.QtWidgets" \
    --hidden-import "PyQt6.QtGui" \
    --exclude-module "scapy.modules.krack" \
    --collect-all "scapy" \
    main.py

# Check if executable was created
if [ ! -f "dist/portdetective" ]; then
    echo "Error: PyInstaller build failed!"
    exit 1
fi

echo ""
echo "Creating .deb package structure..."

# Create directory structure for .deb
DEB_DIR="${APP_NAME}_${APP_VERSION}"
mkdir -p "$DEB_DIR/DEBIAN"
mkdir -p "$DEB_DIR/usr/bin"
mkdir -p "$DEB_DIR/usr/share/applications"
mkdir -p "$DEB_DIR/usr/share/doc/$APP_NAME"
mkdir -p "$DEB_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$DEB_DIR/usr/share/icons/hicolor/128x128/apps"
mkdir -p "$DEB_DIR/usr/share/icons/hicolor/64x64/apps"
mkdir -p "$DEB_DIR/usr/share/icons/hicolor/48x48/apps"
mkdir -p "$DEB_DIR/usr/share/pixmaps"

# Copy executable
cp "dist/portdetective" "$DEB_DIR/usr/bin/"
chmod 755 "$DEB_DIR/usr/bin/portdetective"

# Copy icon if exists, otherwise create placeholder
if [ -n "$ICON_FILE" ] && [ -f "$ICON_FILE" ]; then
    echo "Installing icon..."
    cp "$ICON_FILE" "$DEB_DIR/usr/share/icons/hicolor/256x256/apps/portdetective.png"
    cp "$ICON_FILE" "$DEB_DIR/usr/share/pixmaps/portdetective.png"
    
    # Try to create resized versions if imagemagick is available
    if command -v convert &> /dev/null; then
        convert "$ICON_FILE" -resize 128x128 "$DEB_DIR/usr/share/icons/hicolor/128x128/apps/portdetective.png" 2>/dev/null || true
        convert "$ICON_FILE" -resize 64x64 "$DEB_DIR/usr/share/icons/hicolor/64x64/apps/portdetective.png" 2>/dev/null || true
        convert "$ICON_FILE" -resize 48x48 "$DEB_DIR/usr/share/icons/hicolor/48x48/apps/portdetective.png" 2>/dev/null || true
    fi
else
    # Create a simple SVG icon as fallback
    cat > "$DEB_DIR/usr/share/icons/hicolor/256x256/apps/portdetective.svg" << 'SVGEOF'
<?xml version="1.0" encoding="UTF-8"?>
<svg width="256" height="256" viewBox="0 0 256 256" xmlns="http://www.w3.org/2000/svg">
  <rect width="256" height="256" rx="32" fill="#1a5fb4"/>
  <text x="128" y="100" font-family="sans-serif" font-size="48" font-weight="bold" 
        text-anchor="middle" fill="white">CDP</text>
  <text x="128" y="150" font-family="sans-serif" font-size="48" font-weight="bold" 
        text-anchor="middle" fill="#4CAF50">LLDP</text>
  <circle cx="64" cy="210" r="16" fill="#4CAF50"/>
  <circle cx="128" cy="210" r="16" fill="#4CAF50"/>
  <circle cx="192" cy="210" r="16" fill="#4CAF50"/>
  <line x1="64" y1="210" x2="128" y2="210" stroke="white" stroke-width="3"/>
  <line x1="128" y1="210" x2="192" y2="210" stroke="white" stroke-width="3"/>
</svg>
SVGEOF
fi

# Create control file
cat > "$DEB_DIR/DEBIAN/control" << EOF
Package: $APP_NAME
Version: $APP_VERSION
Section: net
Priority: optional
Architecture: amd64
Depends: libpcap0.8, pkexec | polkitd | policykit-1 | policykit | polkit
Maintainer: $MAINTAINER
Description: $DESCRIPTION
 PortDetective is a GUI application that captures and displays
 CDP (Cisco Discovery Protocol) and LLDP (Link Layer Discovery Protocol)
 packets from network interfaces. Features include multi-interface support,
 real-time discovery, and detailed neighbor information display.
EOF

# Create postinst script (runs after installation)
cat > "$DEB_DIR/DEBIAN/postinst" << 'EOF'
#!/bin/bash
set -e

# Set capabilities to allow packet capture without root
if command -v setcap &> /dev/null; then
    setcap cap_net_raw,cap_net_admin=eip /usr/bin/portdetective || true
fi

echo ""
echo "PortDetective installed successfully!"
echo ""
echo "You can run it from the application menu or with: portdetective"
echo ""
echo "Note: If this is a source install, run once to enable capture without root:"
echo "  sudo bash /usr/share/portdetective/setup_caps.sh"
echo ""

exit 0
EOF
chmod 755 "$DEB_DIR/DEBIAN/postinst"

# Create .desktop file for application menu
cat > "$DEB_DIR/usr/share/applications/portdetective.desktop" << EOF
[Desktop Entry]
Name=PortDetective
Comment=CDP and LLDP Discovery Protocol Monitor
Exec=portdetective
Icon=portdetective
Terminal=false
Type=Application
Categories=Network;Monitor;System;
Keywords=CDP;LLDP;Cisco;network;discovery;neighbor;protocol;
StartupWMClass=portdetective
EOF

# Create a simple icon (placeholder - you can replace with a real icon)
# This creates a simple SVG icon
cat > "$DEB_DIR/usr/share/icons/hicolor/256x256/apps/portdetective.svg" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<svg width="256" height="256" viewBox="0 0 256 256" xmlns="http://www.w3.org/2000/svg">
  <rect width="256" height="256" rx="32" fill="#1a5fb4"/>
  <text x="128" y="100" font-family="sans-serif" font-size="48" font-weight="bold" 
        text-anchor="middle" fill="white">CDP</text>
  <text x="128" y="150" font-family="sans-serif" font-size="48" font-weight="bold" 
        text-anchor="middle" fill="#4CAF50">LLDP</text>
  <circle cx="64" cy="210" r="16" fill="#4CAF50"/>
  <circle cx="128" cy="210" r="16" fill="#4CAF50"/>
  <circle cx="192" cy="210" r="16" fill="#4CAF50"/>
  <line x1="64" y1="210" x2="128" y2="210" stroke="white" stroke-width="3"/>
  <line x1="128" y1="210" x2="192" y2="210" stroke="white" stroke-width="3"/>
</svg>
EOF

# Copy documentation
cp README.md "$DEB_DIR/usr/share/doc/$APP_NAME/"

# Create copyright file
cat > "$DEB_DIR/usr/share/doc/$APP_NAME/copyright" << EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: portdetective
Source: https://github.com/yurividal/PortDetective

Files: *
Copyright: $(date +%Y) PortDetective Authors
License: MIT
 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:
 .
 The above copyright notice and this permission notice shall be included in all
 copies or substantial portions of the Software.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 SOFTWARE.
EOF

# Build .deb package
echo ""
echo "Building .deb package..."
dpkg-deb --build "$DEB_DIR"

# Move .deb to dist folder
mv "${DEB_DIR}.deb" "dist/"

# Build AppImage package
create_appimage

# Clean up
rm -rf "$DEB_DIR"

# Check if packages were created
DEB_FILE="dist/${APP_NAME}_${APP_VERSION}.deb"
APPIMAGE_FILE=$(find dist -maxdepth 1 -type f -name "PortDetective-Linux-${APP_VERSION}-*.AppImage" | head -n 1)
if [ -f "$DEB_FILE" ] && [ -n "$APPIMAGE_FILE" ] && [ -f "$APPIMAGE_FILE" ]; then
    echo ""
    echo "========================================"
    echo "Build successful!"
    echo "Executable: dist/portdetective"
    echo "DEB Package: $DEB_FILE"
    echo "AppImage: $APPIMAGE_FILE"
    echo "========================================"
    
    # Show file sizes
    echo ""
    EXE_SIZE=$(du -sh "dist/portdetective" | cut -f1)
    DEB_SIZE=$(du -sh "$DEB_FILE" | cut -f1)
    APPIMAGE_SIZE=$(du -sh "$APPIMAGE_FILE" | cut -f1)
    echo "Executable size: $EXE_SIZE"
    echo "DEB size: $DEB_SIZE"
    echo "AppImage size: $APPIMAGE_SIZE"
    
    echo ""
    echo "To install the .deb package:"
    echo "  sudo dpkg -i $DEB_FILE"
    echo ""
    echo "To install dependencies if needed:"
    echo "  sudo apt-get install -f"
    echo ""
    echo "To run the AppImage:"
    echo "  chmod +x $APPIMAGE_FILE"
    echo "  ./$APPIMAGE_FILE"
else
    echo ""
    echo "Build failed!"
    exit 1
fi
