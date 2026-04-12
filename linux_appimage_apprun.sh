#!/bin/bash

set -e

APP_NAME="PortDetective"
APPDIR="${APPDIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
APP_PATH="$APPDIR/usr/bin/portdetective-bin"
RELAUNCH_TARGET="$APP_PATH"

if [ ! -x "$APP_PATH" ]; then
    echo "Error: bundled executable not found at $APP_PATH"
    exit 1
fi

if [ -n "$APPIMAGE" ] && [ -x "$APPIMAGE" ]; then
    RELAUNCH_TARGET="$(readlink -f "$APPIMAGE")"
fi

if [ "$EUID" -eq 0 ]; then
    exec "$APP_PATH" "$@"
fi

if command -v pkexec &> /dev/null; then
    exec pkexec /usr/bin/env \
        DISPLAY="$DISPLAY" \
        XAUTHORITY="$XAUTHORITY" \
        PORTDETECTIVE_ELEVATED=1 \
        "$RELAUNCH_TARGET" "$@"
fi

if command -v gksudo &> /dev/null; then
    exec gksudo -- "$RELAUNCH_TARGET" "$@"
fi

if command -v gksu &> /dev/null; then
    exec gksu -- "$RELAUNCH_TARGET" "$@"
fi

if command -v kdesudo &> /dev/null; then
    exec kdesudo -- "$RELAUNCH_TARGET" "$@"
fi

if command -v zenity &> /dev/null; then
    PASSWORD=$(zenity --password --title="$APP_NAME requires administrator privileges")
    if [ $? -eq 0 ]; then
        echo "$PASSWORD" | sudo -S "$RELAUNCH_TARGET" "$@"
        exit $?
    fi

    zenity --error --text="$APP_NAME requires administrator privileges to capture network packets."
    exit 1
fi

echo ""
echo "=============================================="
echo " $APP_NAME requires administrator privileges"
echo " to capture network packets."
echo "=============================================="
echo ""
exec sudo "$RELAUNCH_TARGET" "$@"