#!/bin/bash
# PortDetective Linux Launcher
# This script ensures the application runs with root privileges

APP_NAME="PortDetective"
APP_PATH="/usr/bin/portdetective-bin"

# Check if already running as root
if [ "$EUID" -eq 0 ]; then
    exec "$APP_PATH" "$@"
    exit 0
fi

# Try different methods to get root privileges with GUI prompt

# Method 1: pkexec (PolicyKit) - most common on modern distros
if command -v pkexec &> /dev/null; then
    pkexec "$APP_PATH" "$@"
    exit $?
fi

# Method 2: gksudo/gksu (older GNOME)
if command -v gksudo &> /dev/null; then
    gksudo "$APP_PATH" "$@"
    exit $?
fi

if command -v gksu &> /dev/null; then
    gksu "$APP_PATH" "$@"
    exit $?
fi

# Method 3: kdesudo (KDE)
if command -v kdesudo &> /dev/null; then
    kdesudo "$APP_PATH" "$@"
    exit $?
fi

# Method 4: zenity with sudo (fallback GUI)
if command -v zenity &> /dev/null; then
    PASSWORD=$(zenity --password --title="$APP_NAME requires administrator privileges")
    if [ $? -eq 0 ]; then
        echo "$PASSWORD" | sudo -S "$APP_PATH" "$@"
        exit $?
    else
        zenity --error --text="$APP_NAME requires administrator privileges to capture network packets."
        exit 1
    fi
fi

# Method 5: Terminal fallback
echo ""
echo "=============================================="
echo " $APP_NAME requires administrator privileges"
echo " to capture network packets."
echo "=============================================="
echo ""
sudo "$APP_PATH" "$@"
