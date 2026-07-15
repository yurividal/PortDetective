#!/bin/bash
# Build script for openSUSE-compatible releases (.rpm + AppImage)
# Run this script on openSUSE or any RPM-based Linux with rpmbuild installed.

set -euo pipefail

echo "========================================"
echo "PortDetective - openSUSE Build Script"
echo "========================================"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="portdetective"
APP_VERSION="${APP_VERSION_OVERRIDE:-$(python3 -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); from version import APP_VERSION; print(APP_VERSION)")}"
SUMMARY="CDP and LLDP discovery protocol monitor"
DESCRIPTION="A cross-platform GUI application for listening to CDP and LLDP discovery protocol packets"

get_rpm_arch() {
    case "$(uname -m)" in
        x86_64|amd64)
            echo "x86_64"
            ;;
        aarch64|arm64)
            echo "aarch64"
            ;;
        *)
            echo "$(uname -m)"
            ;;
    esac
}

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

    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$url" -o "$output_path"
        return 0
    fi

    if command -v wget >/dev/null 2>&1; then
        wget -qO "$output_path" "$url"
        return 0
    fi

    echo "Error: curl or wget is required to download AppImage tooling"
    return 1
}

create_icon_svg() {
    local output_file="$1"

    cat > "$output_file" << 'SVGEOF'
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
}

create_appimage() {
    local appimage_arch appimage_build_dir appdir appimagetool_dir appimagetool_path
    local appimagetool_url desktop_file output_file appimage_size

    echo ""
    echo "Creating AppImage package..."

    if ! appimage_arch="$(get_appimage_arch)"; then
        echo "Warning: unsupported AppImage architecture: $(uname -m)"
        echo "Skipping AppImage build"
        return 0
    fi

    appimage_build_dir=".appimage-build"
    appdir="$appimage_build_dir/PortDetective.AppDir"
    appimagetool_dir="$appimage_build_dir/tools"
    appimagetool_path="$appimagetool_dir/appimagetool-${appimage_arch}.AppImage"
    appimagetool_url="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${appimage_arch}.AppImage"
    desktop_file="$appdir/portdetective.desktop"
    output_file="dist/PortDetective-Linux-${APP_VERSION}-${appimage_arch}.AppImage"

    rm -rf "$appdir"
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

    if [ -n "${ICON_FILE}" ] && [ -f "${ICON_FILE}" ]; then
        cp "${ICON_FILE}" "$appdir/portdetective.png"
        cp "${ICON_FILE}" "$appdir/usr/share/icons/hicolor/256x256/apps/portdetective.png"
        ln -sf "portdetective.png" "$appdir/.DirIcon"
    else
        create_icon_svg "$appdir/usr/share/icons/hicolor/256x256/apps/portdetective.svg"
    fi

    rm -f "$output_file"
    ARCH="$appimage_arch" "$appimagetool_path" --appimage-extract-and-run "$appdir" "$output_file"

    if [ ! -f "$output_file" ]; then
        echo "Warning: AppImage build failed"
        return 0
    fi

    appimage_size=$(du -sh "$output_file" | cut -f1)
    echo "AppImage created: $output_file"
    echo "AppImage size: $appimage_size"
}

create_rpm() {
    local rpm_root rpm_sources rpm_specs rpm_srpms rpm_build rpm_rpms
    local stage_root src_root tarball spec_file rpm_arch output_rpm rpm_output

    echo ""
    echo "Creating RPM package..."

    rpm_arch="$(get_rpm_arch)"
    rpm_root=".rpmbuild"
    rpm_sources="$rpm_root/SOURCES"
    rpm_specs="$rpm_root/SPECS"
    rpm_srpms="$rpm_root/SRPMS"
    rpm_build="$rpm_root/BUILD"
    rpm_rpms="$rpm_root/RPMS"
    stage_root=".rpm-stage"
    src_root="$stage_root/${APP_NAME}-${APP_VERSION}"
    tarball="$rpm_sources/${APP_NAME}-${APP_VERSION}.tar.gz"
    spec_file="$rpm_specs/${APP_NAME}.spec"
    output_rpm="dist/PortDetective-openSUSE-${APP_VERSION}-${rpm_arch}.rpm"

    rm -rf "$rpm_root" "$stage_root"
    mkdir -p "$rpm_sources" "$rpm_specs" "$rpm_srpms" "$rpm_build" "$rpm_rpms"

    mkdir -p "$src_root/usr/bin"
    mkdir -p "$src_root/usr/share/applications"
    mkdir -p "$src_root/usr/share/doc/$APP_NAME"
    mkdir -p "$src_root/usr/share/icons/hicolor/256x256/apps"

    cp "dist/portdetective" "$src_root/usr/bin/portdetective"
    chmod 755 "$src_root/usr/bin/portdetective"

    cat > "$src_root/usr/share/applications/portdetective.desktop" << EOF
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

    cp README.md "$src_root/usr/share/doc/$APP_NAME/README.md"

    if [ -n "${ICON_FILE}" ] && [ -f "${ICON_FILE}" ]; then
        cp "${ICON_FILE}" "$src_root/usr/share/icons/hicolor/256x256/apps/portdetective.png"
    else
        create_icon_svg "$src_root/usr/share/icons/hicolor/256x256/apps/portdetective.svg"
    fi

    (
        cd "$stage_root"
        tar -czf "../$tarball" "${APP_NAME}-${APP_VERSION}"
    )

    cat > "$spec_file" << EOF
Name:           $APP_NAME
Version:        $APP_VERSION
Release:        1%{?dist}
Summary:        $SUMMARY
License:        MIT
URL:            https://github.com/yurividal/PortDetective
Source0:        %{name}-%{version}.tar.gz
BuildArch:      $rpm_arch
Requires:       libpcap
Requires:       polkit

%description
$DESCRIPTION

%prep
%autosetup

%build

%install
mkdir -p %{buildroot}
cp -a usr %{buildroot}/

%post
if command -v setcap >/dev/null 2>&1; then
    setcap cap_net_raw,cap_net_admin=eip /usr/bin/portdetective || true
fi

%files
%{_bindir}/portdetective
%{_datadir}/applications/portdetective.desktop
%doc %{_datadir}/doc/$APP_NAME/README.md
%{_datadir}/icons/hicolor/256x256/apps/portdetective.*

%changelog
* $(date '+%a %b %d %Y') PortDetective <portdetective@example.com> - $APP_VERSION-1
- Build openSUSE-compatible RPM release
EOF

    rpmbuild --define "_topdir $(pwd)/$rpm_root" -bb "$spec_file"

    rpm_output="$(find "$rpm_rpms" -type f -name "${APP_NAME}-${APP_VERSION}-1*.rpm" | head -n 1 || true)"
    if [ -z "$rpm_output" ]; then
        echo "Error: RPM build completed but no package was found"
        return 1
    fi

    mkdir -p dist
    cp "$rpm_output" "$output_rpm"
    echo "RPM package created: $output_rpm"
}

if [[ "$(uname)" != "Linux" ]]; then
    echo "Error: This script must be run on Linux"
    exit 1
fi

echo ""
echo "Checking required tools..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: Python 3 is required. Install with: sudo zypper install python3"
    exit 1
fi

if ! command -v rpmbuild >/dev/null 2>&1; then
    echo "Error: rpmbuild is required. Install with: sudo zypper install rpm-build"
    exit 1
fi

ICON_FILE=""
if [ -f "icon.png" ]; then
    echo "Icon file found: icon.png"
    ICON_FILE="icon.png"
else
    echo "No icon.png found. Will use generated SVG icon."
fi

if [ ! -d "venv" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo ""
echo "Activating virtual environment..."
source venv/bin/activate

echo ""
echo "Installing dependencies..."
if ! python -m pip --version >/dev/null 2>&1; then
    echo "Bootstrapping pip in the virtual environment..."
    python -m ensurepip --upgrade
fi

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo ""
echo "Cleaning previous builds..."
rm -rf dist build *.spec
rm -rf .appimage-build .rpmbuild .rpm-stage

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

if [ ! -f "dist/portdetective" ]; then
    echo "Error: PyInstaller build failed"
    exit 1
fi

create_rpm
create_appimage

echo ""
echo "========================================"
echo "Build successful!"
echo "Executable: dist/portdetective"

RPM_FILE="dist/PortDetective-openSUSE-${APP_VERSION}-$(get_rpm_arch).rpm"
if [ -f "$RPM_FILE" ]; then
    echo "RPM Package: $RPM_FILE"
fi

APPIMAGE_FILE="$(find dist -maxdepth 1 -type f -name "PortDetective-Linux-${APP_VERSION}-*.AppImage" | head -n 1 || true)"
if [ -n "$APPIMAGE_FILE" ] && [ -f "$APPIMAGE_FILE" ]; then
    echo "AppImage: $APPIMAGE_FILE"
fi

echo "========================================"
echo ""

EXE_SIZE="$(du -sh dist/portdetective | cut -f1)"
echo "Executable size: $EXE_SIZE"

if [ -f "$RPM_FILE" ]; then
    RPM_SIZE="$(du -sh "$RPM_FILE" | cut -f1)"
    echo "RPM size: $RPM_SIZE"
fi

if [ -n "$APPIMAGE_FILE" ] && [ -f "$APPIMAGE_FILE" ]; then
    APPIMAGE_SIZE="$(du -sh "$APPIMAGE_FILE" | cut -f1)"
    echo "AppImage size: $APPIMAGE_SIZE"
fi

echo ""
echo "To install on openSUSE:"
echo "  sudo zypper install --allow-unsigned-rpm $RPM_FILE"
echo ""
echo "If polkit/libpcap dependencies are missing, install:"
echo "  sudo zypper install libpcap1 polkit"
