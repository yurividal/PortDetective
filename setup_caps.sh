#!/bin/bash
# PortDetective - Linux Capability Setup
#
# Grants cap_net_raw and cap_net_admin to the Python interpreter so that
# PortDetective can capture packets without running as root.
#
# Run this once after installing Python dependencies:
#   sudo bash setup_caps.sh
#
# To undo:
#   sudo setcap -r $(readlink -f $(which python3))

set -e

PYTHON_BIN="$(readlink -f "$(which python3)")"

echo "========================================"
echo " PortDetective - Capability Setup"
echo "========================================"
echo ""
echo "Python binary: $PYTHON_BIN"
echo ""
echo "This will grant cap_net_raw and cap_net_admin to:"
echo "  $PYTHON_BIN"
echo ""
echo "These capabilities allow Python to open raw packet sockets,"
echo "which is required for CDP/LLDP capture. They do NOT grant"
echo "full root access."
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run with sudo."
    echo "  sudo bash setup_caps.sh"
    exit 1
fi

# Check setcap is available
if ! command -v setcap &> /dev/null; then
    echo "Error: setcap not found. Install it with:"
    echo "  sudo apt install libcap2-bin"
    exit 1
fi

setcap cap_net_raw,cap_net_admin=eip "$PYTHON_BIN"

echo "Done! Capabilities set on $PYTHON_BIN"
echo ""
echo "You can now run PortDetective without sudo:"
echo "  python3 main.py"
echo ""
echo "To remove the capabilities later:"
echo "  sudo setcap -r $PYTHON_BIN"
