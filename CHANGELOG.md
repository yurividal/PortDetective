# Changelog

All notable changes to PortDetective will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] - 2026-01-12

### Added
- Copy button for each discovered neighbor row to quickly copy connection details to clipboard
  - Copies formatted text with Switch Name, Switch IP, Port, and Current VLAN
  - Small clipboard button (📋) appears in each row
  - Shows confirmation message in status bar when copied
- Smart interface filtering to hide virtual/tunnel adapters by default
  - Automatically hides loopback, VPN, tunnel, virtual machine, and other non-physical interfaces
  - Includes detection for Windows, Linux, and macOS virtual interfaces (utun, awdl, etc.)
  - Added "Show virtual/tunnel adapters" checkbox to display hidden interfaces when needed
  - Status bar shows count of hidden interfaces for better visibility

### Improved
- Interface list now shows only relevant physical network adapters by default
- Better user experience with cleaner interface selection
- Virtual interfaces are clearly labeled with "(Virtual)" tag when shown
- Cross-platform virtual interface detection for Windows, macOS, and Linux

## [1.1.0] - Previous Release

### Added
- Dual protocol support (CDP and LLDP)
- Protocol filtering modes (Auto, CDP Only, LLDP Only, Both)
- Multi-interface capture support
- Real-time neighbor discovery
- Export to TXT/CSV formats

### Features
- Cross-platform GUI (Windows, macOS, Linux)
- Detailed neighbor information display
- Protocol color coding (CDP in blue, LLDP in green)
