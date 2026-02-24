#!/usr/bin/env python3
"""
PortDetective - Network Discovery Protocol Listener
A cross-platform application for listening to CDP and LLDP discovery protocol packets.

Usage:
    python main.py

Requirements:
    - Python 3.8+
    - PyQt6
    - Scapy
    - psutil
    - Npcap (Windows) or libpcap (Linux/Mac)
    - On Linux: run 'sudo bash setup_caps.sh' once to enable capture without root
"""

import sys
import os


def check_dependencies():
    """Check if all required dependencies are installed."""
    missing = []

    try:
        import PyQt6
    except ImportError:
        missing.append("PyQt6")

    try:
        import scapy
    except ImportError:
        missing.append("scapy")

    try:
        import psutil
    except ImportError:
        missing.append("psutil")

    if missing:
        print("Missing required packages:")
        for pkg in missing:
            print(f"  - {pkg}")
        print("\nInstall them with:")
        print(f"  pip install {' '.join(missing)}")
        return False

    return True


def check_npcap_windows():
    """Check if Npcap is installed on Windows. Returns True if installed or not on Windows."""
    if sys.platform != "win32":
        return True

    # Check for Npcap DLL in common locations
    npcap_paths = [
        os.path.join(
            os.environ.get("SystemRoot", "C:\\Windows"),
            "System32",
            "Npcap",
            "wpcap.dll",
        ),
        os.path.join(
            os.environ.get("SystemRoot", "C:\\Windows"), "System32", "wpcap.dll"
        ),
    ]

    for path in npcap_paths:
        if os.path.exists(path):
            return True

    # Also check if scapy can find any interfaces (indicates working pcap)
    try:
        from scapy.arch.windows import get_windows_if_list

        interfaces = get_windows_if_list()
        if interfaces:
            return True
    except:
        pass

    return False


def show_npcap_error():
    """Show a GUI error message about missing Npcap."""
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from PyQt6.QtCore import Qt

        app = QApplication(sys.argv)

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Npcap Required")
        msg.setText("Npcap is not installed!")
        msg.setInformativeText(
            "This application requires Npcap for packet capture.\n\n"
            "Please install Npcap from:\n"
            "https://npcap.com/\n\n"
            "During installation, make sure to check:\n"
            "☑ Install Npcap in WinPcap API-compatible Mode"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setDefaultButton(QMessageBox.StandardButton.Ok)

        # Add a button to open the download page
        open_button = msg.addButton(
            "Open Download Page", QMessageBox.ButtonRole.ActionRole
        )

        msg.exec()

        if msg.clickedButton() == open_button:
            import webbrowser

            webbrowser.open("https://npcap.com/")

        return False
    except Exception as e:
        # Fallback to console message if GUI fails
        print("=" * 60)
        print("ERROR: Npcap is not installed!")
        print("")
        print("This application requires Npcap for packet capture.")
        print("Please download and install Npcap from: https://npcap.com/")
        print("")
        print("During installation, make sure to check:")
        print("  [x] Install Npcap in WinPcap API-compatible Mode")
        print("=" * 60)
        return False


def check_libpcap_unix():
    """Check if libpcap is available on Unix systems. Returns True if available or on Windows."""
    if sys.platform == "win32":
        return True

    try:
        # Try to import scapy and check if it can access interfaces
        from scapy.all import get_if_list

        interfaces = get_if_list()
        return len(interfaces) > 0
    except Exception:
        return False


def show_libpcap_error():
    """Show a GUI error message about missing libpcap."""
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox

        app = QApplication(sys.argv)

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("libpcap Required")
        msg.setText("libpcap is not installed!")

        if sys.platform == "darwin":
            info_text = (
                "This application requires libpcap for packet capture.\n\n"
                "libpcap should be pre-installed on macOS.\n"
                "If you see this error, try reinstalling Xcode command line tools:\n\n"
                "xcode-select --install"
            )
        else:
            info_text = (
                "This application requires libpcap for packet capture.\n\n"
                "Install it using your package manager:\n\n"
                "Debian/Ubuntu:\n"
                "  sudo apt install libpcap0.8\n\n"
                "Fedora/RHEL:\n"
                "  sudo dnf install libpcap\n\n"
                "Arch Linux:\n"
                "  sudo pacman -S libpcap"
            )

        msg.setInformativeText(info_text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

        return False
    except Exception:
        # Fallback to console message
        print("=" * 60)
        print("ERROR: libpcap is not installed!")
        print("")
        if sys.platform == "darwin":
            print("libpcap should be pre-installed on macOS.")
            print("Try: xcode-select --install")
        else:
            print("Install with: sudo apt install libpcap0.8")
        print("=" * 60)
        return False


def check_privileges():
    """Check if running with appropriate privileges (Windows only)."""
    if sys.platform != "win32":
        return True  # Linux/Mac: handled via setcap on the binary
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


def main():
    """Main entry point for the Discovery Listener application."""
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Check for packet capture library
    if sys.platform == "win32":
        if not check_npcap_windows():
            show_npcap_error()
            sys.exit(1)
    else:
        if not check_libpcap_unix():
            show_libpcap_error()
            sys.exit(1)

    # Windows: warn if not running as administrator
    if sys.platform == "win32" and not check_privileges():
        print("=" * 60)
        print("WARNING: Not running as Administrator!")
        print("Packet capture may not work without elevated privileges.")
        print("Right-click the application and choose 'Run as Administrator'.")
        print("=" * 60)
        print("")

    # Import and run the GUI
    from discovery_listener_gui import main as gui_main

    gui_main()


if __name__ == "__main__":
    main()
