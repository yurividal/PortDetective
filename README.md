# PortDetective

A cross-platform application for listening to **Cisco Discovery Protocol (CDP)** and **Link Layer Discovery Protocol (LLDP)** packets on your network interfaces.

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-green)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- 🖥️ **Cross-platform GUI** - Works on Windows, macOS, and Linux
- 🔌 **Multi-interface support** - Listen on multiple network interfaces simultaneously
- 🌐 **Dual protocol support** - Captures both CDP (Cisco) and LLDP (industry standard) packets
- 📊 **Real-time discovery** - See neighbors as they're discovered
- 📋 **Detailed information** - View complete neighbor details including:
  - Device ID and Platform/System Description
  - IP and Management Addresses
  - Port information and local port speed
  - Capabilities (Router, Switch, etc.)
  - Software Version
  - Native VLAN and Voice VLAN
  - VTP Domain and Duplex settings
- 🎨 **Protocol color coding** - CDP neighbors shown in blue, LLDP in green
- 💾 **Export capabilities** - Export results to TXT or CSV format

## Supported Protocols

### CDP (Cisco Discovery Protocol)
- Proprietary Cisco protocol
- Operates on Layer 2
- Sends advertisements every 60 seconds by default
- Destination MAC: `01:00:0c:cc:cc:cc`

### LLDP (Link Layer Discovery Protocol)
- IEEE 802.1AB standard
- Vendor-neutral alternative to CDP
- Works with all major switch vendors
- Destination MAC: `01:80:c2:00:00:0e`

## Requirements

### Running from Source
- Python 3.8 or higher
- Administrator/root privileges (required for packet capture)

### Running Compiled Executables
- **No Python required** - the executables are self-contained
- Administrator/root privileges (required for packet capture)

### Packet Capture Library (Required on all systems)
The application uses system-level packet capture drivers that cannot be bundled:
- **Windows**: [Npcap](https://npcap.com/) (install with WinPcap API-compatible mode)
- **Linux**: libpcap (`sudo apt install libpcap0.8`) - automatically installed with .deb package
- **macOS**: libpcap (pre-installed, no action needed)

## Installation

1. **Clone or download this repository**

2. **Create a virtual environment (recommended)**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/macOS
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Npcap (Windows only)**
   - Download from https://npcap.com/
   - During installation, check "Install Npcap in WinPcap API-compatible Mode"

## Usage

### Windows
```powershell
# Run as Administrator (required for packet capture)
python main.py
```
Or right-click on `main.py` and select "Run as Administrator"

### Linux/macOS
```bash
# Run with sudo (required for packet capture)
sudo python main.py
```

## How It Works

1. **Select Interfaces**: Choose one or more network interfaces from the list
2. **Start Capture**: Click "Start Capture" to begin listening for CDP and LLDP packets
3. **View Neighbors**: Neighbors will appear in the table as they're discovered
   - Blue rows indicate CDP neighbors (Cisco devices)
   - Green rows indicate LLDP neighbors (any vendor)
4. **View Details**: Click on a neighbor to see detailed information
5. **Export**: Export your results to TXT or CSV format

## Protocol Information

### CDP (Cisco Discovery Protocol)
Cisco Discovery Protocol is a proprietary Layer 2 protocol developed by Cisco. It's used to share information about directly connected Cisco equipment. CDP packets are sent every 60 seconds by default.

### LLDP (Link Layer Discovery Protocol)
LLDP is an IEEE standard (802.1AB) that provides similar functionality to CDP but is vendor-neutral. Most enterprise switches from HP, Juniper, Dell, Arista, and others support LLDP.

### Information Shared via Discovery Protocols
- Device hostname/System name
- IP addresses and management addresses
- Port identifier
- Platform/model/System description
- Capabilities (router, switch, bridge, etc.)
- Software version
- Native VLAN and Voice VLAN
- VTP management domain (CDP only)
- Duplex settings

## Troubleshooting

### "Permission denied" or no packets captured
- Ensure you're running with Administrator/root privileges
- On Windows, verify Npcap is installed correctly

### "No interfaces found"
- Check that your network adapters are enabled
- On Windows, ensure Npcap is installed with WinPcap compatibility mode

### No CDP/LLDP packets received
- Verify you're connected to a network with managed switches
- CDP must be enabled on the connected Cisco device
- LLDP must be enabled on non-Cisco managed switches
- Some switches may not forward discovery packets to end hosts
- Wait up to 60 seconds for CDP or 30 seconds for LLDP advertisements

## Project Structure

```
cdp_info/
├── main.py                    # Application entry point
├── discovery_listener_gui.py  # PyQt6 GUI implementation (CDP + LLDP)
├── discovery_capture.py       # Combined packet capture handling
├── cdp_parser.py              # CDP packet parsing
├── lldp_parser.py             # LLDP packet parsing
├── neighbor.py                # Unified neighbor data structure
├── nic_detector.py            # Network interface detection
├── requirements.txt           # Python dependencies
├── build_windows.ps1          # Windows build script
├── build_mac.sh               # macOS build script
├── build_linux.sh             # Linux build script
├── build_all.py               # Cross-platform build script
└── README.md                  # This file
```

## Building Executables

### Windows
```powershell
.\build_windows.ps1
# Output: dist\PortDetective.exe
```

### macOS
```bash
chmod +x build_mac.sh
./build_mac.sh
# Output: dist/PortDetective.app and dist/PortDetective-macOS.dmg
```

### Linux
```bash
chmod +x build_linux.sh
./build_linux.sh
# Output: dist/portdetective and dist/portdetective_1.0.0.deb
```

### Cross-platform (Python)
```bash
python build_all.py
# Automatically detects OS and builds appropriate package
```

## License

This project is provided as-is for educational and network administration purposes.

## Acknowledgments

- [Scapy](https://scapy.net/) - Packet manipulation library
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI framework
- [psutil](https://github.com/giampaolo/psutil) - System utilities
