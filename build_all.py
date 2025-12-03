#!/usr/bin/env python3
"""
Cross-platform build script for PortDetective.
This script can be run on any platform to build for that platform.
"""

import os
import sys
import subprocess
import shutil
import platform


APP_NAME = "PortDetective"
APP_VERSION = "1.0.0"


def get_platform():
    """Get the current platform."""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "mac"
    elif system == "linux":
        return "linux"
    else:
        return "unknown"


def run_command(cmd, shell=False):
    """Run a command and print output."""
    print(f"Running: {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
    result = subprocess.run(cmd, shell=shell, capture_output=False)
    return result.returncode == 0


def check_dependencies():
    """Check and install required dependencies."""
    print("\nChecking dependencies...")

    # Install/upgrade pip
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

    # Install requirements
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    # Install PyInstaller and Pillow (for icon conversion)
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller", "pillow"])

    return True


def prepare_icon():
    """Prepare icon file for the current platform."""
    icon_png = "icon.png"

    if not os.path.exists(icon_png):
        print("No icon.png found, using default icon.")
        return None

    print(f"Icon file found: {icon_png}")
    current_platform = get_platform()

    if current_platform == "windows":
        # Convert PNG to ICO for Windows
        try:
            from PIL import Image

            ico_path = "icon.ico"
            img = Image.open(icon_png)
            img.save(
                ico_path,
                format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
            )
            print(f"Converted to: {ico_path}")
            return ico_path
        except Exception as e:
            print(f"Warning: Could not convert icon to ICO: {e}")
            return None

    elif current_platform == "mac":
        # Convert PNG to ICNS for macOS
        try:
            iconset_dir = "icon.iconset"
            os.makedirs(iconset_dir, exist_ok=True)

            from PIL import Image

            img = Image.open(icon_png)

            sizes = [
                (16, "icon_16x16.png"),
                (32, "icon_16x16@2x.png"),
                (32, "icon_32x32.png"),
                (64, "icon_32x32@2x.png"),
                (128, "icon_128x128.png"),
                (256, "icon_128x128@2x.png"),
                (256, "icon_256x256.png"),
                (512, "icon_256x256@2x.png"),
                (512, "icon_512x512.png"),
                (1024, "icon_512x512@2x.png"),
            ]

            for size, name in sizes:
                resized = img.resize((size, size), Image.Resampling.LANCZOS)
                resized.save(os.path.join(iconset_dir, name))

            # Convert iconset to icns
            icns_path = "icon.icns"
            subprocess.run(["iconutil", "-c", "icns", iconset_dir, "-o", icns_path])

            # Cleanup
            shutil.rmtree(iconset_dir)

            if os.path.exists(icns_path):
                print(f"Converted to: {icns_path}")
                return icns_path
        except Exception as e:
            print(f"Warning: Could not convert icon to ICNS: {e}")
            return None

    elif current_platform == "linux":
        # Just return the PNG path for Linux
        return icon_png

    return None


def clean_build():
    """Clean previous build artifacts."""
    print("\nCleaning previous builds...")

    dirs_to_remove = ["dist", "build", "__pycache__"]
    files_to_remove = []

    for d in dirs_to_remove:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"  Removed {d}/")

    for f in os.listdir("."):
        if f.endswith(".spec"):
            os.remove(f)
            print(f"  Removed {f}")


def build_windows(icon_path=None):
    """Build Windows executable."""
    print("\n" + "=" * 50)
    print("Building for Windows...")
    print("=" * 50)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        APP_NAME,
    ]

    if icon_path and os.path.exists(icon_path):
        cmd.extend(["--icon", icon_path])
        # Also bundle the PNG for runtime window icon
        cmd.extend(["--add-data", "icon.png;."])

    cmd.extend(
        [
            "--add-data",
            "README.md;.",
            "--hidden-import",
            "scapy.layers.l2",
            "--hidden-import",
            "scapy.contrib.cdp",
            "--hidden-import",
            "scapy.contrib.lldp",
            "--hidden-import",
            "PyQt6.QtCore",
            "--hidden-import",
            "PyQt6.QtWidgets",
            "--hidden-import",
            "PyQt6.QtGui",
            "--collect-all",
            "scapy",
            "main.py",
        ]
    )

    if run_command(cmd):
        exe_path = os.path.join("dist", f"{APP_NAME}.exe")
        if os.path.exists(exe_path):
            size = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"\n✓ Build successful!")
            print(f"  Output: {exe_path}")
            print(f"  Size: {size:.2f} MB")
            return True

    print("\n✗ Build failed!")
    return False


def build_mac(icon_path=None):
    """Build macOS application."""
    print("\n" + "=" * 50)
    print("Building for macOS...")
    print("=" * 50)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        APP_NAME,
        "--osx-bundle-identifier",
        "com.discoverylistener.app",
    ]

    if icon_path and os.path.exists(icon_path):
        cmd.extend(["--icon", icon_path])
        # Also bundle the PNG for runtime window icon
        if os.path.exists("icon.png"):
            cmd.extend(["--add-data", "icon.png:."])

    cmd.extend(
        [
            "--add-data",
            "README.md:.",
            "--hidden-import",
            "scapy.layers.l2",
            "--hidden-import",
            "scapy.contrib.cdp",
            "--hidden-import",
            "scapy.contrib.lldp",
            "--hidden-import",
            "PyQt6.QtCore",
            "--hidden-import",
            "PyQt6.QtWidgets",
            "--hidden-import",
            "PyQt6.QtGui",
            "--collect-all",
            "scapy",
            "main.py",
        ]
    )

    if run_command(cmd):
        app_path = os.path.join("dist", f"{APP_NAME}.app")
        exe_path = os.path.join("dist", APP_NAME)

        if os.path.exists(app_path):
            print(f"\n✓ Build successful!")
            print(f"  Output: {app_path}")

            # Try to create DMG
            print("\nCreating DMG...")
            create_dmg()
            return True
        elif os.path.exists(exe_path):
            print(f"\n✓ Build successful (command-line executable)!")
            print(f"  Output: {exe_path}")
            return True

    print("\n✗ Build failed!")
    return False


def create_dmg():
    """Create a DMG file for macOS."""
    try:
        dmg_dir = os.path.join("dist", "dmg_contents")
        os.makedirs(dmg_dir, exist_ok=True)

        app_src = os.path.join("dist", f"{APP_NAME}.app")
        if os.path.exists(app_src):
            shutil.copytree(app_src, os.path.join(dmg_dir, f"{APP_NAME}.app"))
            os.symlink("/Applications", os.path.join(dmg_dir, "Applications"))

            dmg_name = f"{APP_NAME}-macOS.dmg"
            dmg_path = os.path.join("dist", dmg_name)

            subprocess.run(
                [
                    "hdiutil",
                    "create",
                    "-volname",
                    "Discovery Listener",
                    "-srcfolder",
                    dmg_dir,
                    "-ov",
                    "-format",
                    "UDZO",
                    dmg_path,
                ]
            )

            shutil.rmtree(dmg_dir)

            if os.path.exists(dmg_path):
                size = os.path.getsize(dmg_path) / (1024 * 1024)
                print(f"  DMG created: {dmg_path}")
                print(f"  DMG size: {size:.2f} MB")
    except Exception as e:
        print(f"  Warning: Could not create DMG: {e}")


def build_linux(icon_path=None):
    """Build Linux executable."""
    print("\n" + "=" * 50)
    print("Building for Linux...")
    print("=" * 50)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "portdetective",
    ]

    # Bundle the PNG icon for runtime window icon
    if os.path.exists("icon.png"):
        cmd.extend(["--add-data", "icon.png:."])

    cmd.extend(
        [
            "--add-data",
            "README.md:.",
            "--hidden-import",
            "scapy.layers.l2",
            "--hidden-import",
            "scapy.contrib.cdp",
            "--hidden-import",
            "scapy.contrib.lldp",
            "--hidden-import",
            "PyQt6.QtCore",
            "--hidden-import",
            "PyQt6.QtWidgets",
            "--hidden-import",
            "PyQt6.QtGui",
            "--collect-all",
            "scapy",
            "main.py",
        ]
    )

    if run_command(cmd):
        exe_path = os.path.join("dist", "portdetective")
        if os.path.exists(exe_path):
            size = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"\n✓ Build successful!")
            print(f"  Output: {exe_path}")
            print(f"  Size: {size:.2f} MB")

            # Try to create .deb
            print("\nCreating .deb package...")
            create_deb(icon_path)
            return True

    print("\n✗ Build failed!")
    return False


def create_deb(icon_path=None):
    """Create a .deb package for Debian/Ubuntu."""
    try:
        deb_dir = f"portdetective_{APP_VERSION}"

        # Create directory structure
        os.makedirs(f"{deb_dir}/DEBIAN", exist_ok=True)
        os.makedirs(f"{deb_dir}/usr/bin", exist_ok=True)
        os.makedirs(f"{deb_dir}/usr/share/applications", exist_ok=True)
        os.makedirs(f"{deb_dir}/usr/share/doc/portdetective", exist_ok=True)
        os.makedirs(f"{deb_dir}/usr/share/icons/hicolor/256x256/apps", exist_ok=True)
        os.makedirs(f"{deb_dir}/usr/share/pixmaps", exist_ok=True)

        # Copy executable
        shutil.copy("dist/portdetective", f"{deb_dir}/usr/bin/")
        os.chmod(f"{deb_dir}/usr/bin/portdetective", 0o755)

        # Copy icon if available
        if icon_path and os.path.exists(icon_path):
            shutil.copy(
                icon_path,
                f"{deb_dir}/usr/share/icons/hicolor/256x256/apps/portdetective.png",
            )
            shutil.copy(icon_path, f"{deb_dir}/usr/share/pixmaps/portdetective.png")

        # Create control file
        with open(f"{deb_dir}/DEBIAN/control", "w") as f:
            f.write(
                f"""Package: portdetective
Version: {APP_VERSION}
Section: net
Priority: optional
Architecture: amd64
Depends: libpcap0.8
Maintainer: PortDetective <portdetective@example.com>
Description: CDP and LLDP Discovery Protocol Monitor
 A GUI application for capturing and displaying CDP and LLDP packets.
"""
            )

        # Create .desktop file
        with open(f"{deb_dir}/usr/share/applications/portdetective.desktop", "w") as f:
            f.write(
                """[Desktop Entry]
Name=PortDetective
Comment=CDP and LLDP Discovery Protocol Monitor
Exec=portdetective
Icon=portdetective
Terminal=false
Type=Application
Categories=Network;Monitor;
Keywords=CDP;LLDP;Cisco;Network;Discovery;
"""
            )

        # Copy README
        shutil.copy("README.md", f"{deb_dir}/usr/share/doc/portdetective/")

        # Build .deb
        subprocess.run(["dpkg-deb", "--build", deb_dir])

        # Move to dist
        deb_file = f"{deb_dir}.deb"
        if os.path.exists(deb_file):
            shutil.move(deb_file, "dist/")
            shutil.rmtree(deb_dir)

            deb_path = f"dist/{deb_file}"
            size = os.path.getsize(deb_path) / (1024 * 1024)
            print(f"  DEB created: {deb_path}")
            print(f"  DEB size: {size:.2f} MB")

    except Exception as e:
        print(f"  Warning: Could not create .deb: {e}")
        if os.path.exists(f"portdetective_{APP_VERSION}"):
            shutil.rmtree(f"portdetective_{APP_VERSION}")


def cleanup_icons():
    """Clean up temporary icon files."""
    for f in ["icon.ico", "icon.icns"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except:
                pass


def main():
    """Main build function."""
    print("=" * 50)
    print(f"PortDetective Build Script v{APP_VERSION}")
    print("=" * 50)

    current_platform = get_platform()
    print(f"\nDetected platform: {current_platform}")

    if current_platform == "unknown":
        print("Error: Unknown platform!")
        sys.exit(1)

    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"Working directory: {script_dir}")

    # Check dependencies
    check_dependencies()

    # Prepare icon
    icon_path = prepare_icon()

    # Clean previous builds
    clean_build()

    # Build for current platform
    success = False
    if current_platform == "windows":
        success = build_windows(icon_path)
    elif current_platform == "mac":
        success = build_mac(icon_path)
    elif current_platform == "linux":
        success = build_linux(icon_path)

    # Clean up temporary icon files
    cleanup_icons()

    # Summary
    print("\n" + "=" * 50)
    if success:
        print("BUILD COMPLETE")
        print("=" * 50)
        print(f"\nOutput files are in the 'dist' directory.")

        if current_platform == "windows":
            print("\nNote: Npcap must be installed on target systems.")
            print("Download from: https://npcap.com/")
        elif current_platform == "mac":
            print("\nNote: Run with sudo for packet capture permissions.")
        elif current_platform == "linux":
            print("\nTo install .deb: sudo dpkg -i dist/portdetective_*.deb")
    else:
        print("BUILD FAILED")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    main()
