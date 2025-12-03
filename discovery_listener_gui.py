"""
PortDetective - Main GUI Application
Cross-platform GUI for listening to CDP and LLDP discovery protocol packets.
"""

import sys
import os
from datetime import datetime
from typing import Dict, Optional
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
    QTextEdit,
    QSplitter,
    QHeaderView,
    QMessageBox,
    QStatusBar,
    QCheckBox,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QTabWidget,
    QComboBox,
    QFrame,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QIcon, QAction, QPalette

from nic_detector import NICDetector, NetworkInterface
from neighbor import DiscoveryNeighbor
from discovery_capture import MultiInterfaceDiscoveryCapture


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller bundle."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)


def get_icon_path() -> Optional[str]:
    """Get the path to the application icon."""
    # Check various locations for the icon
    possible_paths = [
        get_resource_path("icon.png"),
        get_resource_path(os.path.join("assets", "icon.png")),
        os.path.join(os.path.dirname(__file__), "icon.png"),
        os.path.join(os.path.dirname(__file__), "assets", "icon.png"),
        "icon.png",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None


class NeighborSignals(QObject):
    """Signals for thread-safe GUI updates."""

    neighbor_discovered = pyqtSignal(object)
    capture_error = pyqtSignal(str)
    status_update = pyqtSignal(str)


class PortDetectiveWindow(QMainWindow):
    """Main application window for PortDetective."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PortDetective - CDP/LLDP Discovery")
        self.setMinimumSize(1100, 750)

        # Set application icon
        icon_path = get_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        # Initialize components
        self.nic_detector = NICDetector()
        self.interfaces: Dict[str, NetworkInterface] = {}
        self.capture: Optional[MultiInterfaceDiscoveryCapture] = None
        self.neighbors: Dict[str, DiscoveryNeighbor] = {}

        # Thread-safe signals
        self.signals = NeighborSignals()
        self.signals.neighbor_discovered.connect(self._on_neighbor_discovered_gui)
        self.signals.capture_error.connect(self._show_error)
        self.signals.status_update.connect(self._update_status)

        # Protocol mode setting: "auto", "cdp", "lldp", "both"
        self.protocol_mode = "auto"

        # Setup UI
        self._setup_ui()
        self._load_interfaces()

        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_capture_status)
        self.status_timer.start(1000)

    def _setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Top section - Interface selection and Settings
        top_layout = QHBoxLayout()
        self._setup_interface_section(top_layout)
        self._setup_settings_section(top_layout)
        main_layout.addLayout(top_layout)

        # Middle section - Splitter with neighbors table and details
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Neighbors table
        neighbors_group = QGroupBox("Discovered Neighbors")
        neighbors_layout = QVBoxLayout(neighbors_group)
        self._setup_neighbors_table(neighbors_layout)
        splitter.addWidget(neighbors_group)

        # Details section with tabs
        details_group = QGroupBox("Neighbor Details")
        details_layout = QVBoxLayout(details_group)
        self._setup_details_section(details_layout)
        splitter.addWidget(details_group)

        splitter.setSizes([400, 250])
        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(
            "Ready - Select interfaces and click Start to begin capturing CDP/LLDP packets"
        )

        # Menu bar
        self._setup_menu()

    def _setup_interface_section(self, parent_layout):
        """Setup the interface selection section."""
        interface_group = QGroupBox("Network Interfaces")
        interface_layout = QVBoxLayout(interface_group)

        info_label = QLabel(
            "Select one or more network interfaces to listen for discovery packets:"
        )
        info_label.setWordWrap(True)
        interface_layout.addWidget(info_label)

        h_layout = QHBoxLayout()

        # Interface list widget
        self.interface_list = QListWidget()
        self.interface_list.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        self.interface_list.setMinimumHeight(100)
        self.interface_list.setMaximumHeight(150)
        h_layout.addWidget(self.interface_list, stretch=3)

        # Control buttons
        btn_layout = QVBoxLayout()

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setToolTip("Refresh the list of network interfaces")
        self.refresh_btn.clicked.connect(self._load_interfaces)
        btn_layout.addWidget(self.refresh_btn)

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all_interfaces)
        btn_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self._deselect_all_interfaces)
        btn_layout.addWidget(self.deselect_all_btn)

        btn_layout.addStretch()

        h_layout.addLayout(btn_layout, stretch=1)
        interface_layout.addLayout(h_layout)

        parent_layout.addWidget(interface_group, stretch=2)

    def _setup_settings_section(self, parent_layout):
        """Setup the settings section."""
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout(settings_group)

        # Protocol mode
        protocol_label = QLabel("Protocol Mode:")
        protocol_label.setStyleSheet("font-weight: bold;")
        settings_layout.addWidget(protocol_label)

        self.protocol_combo = QComboBox()
        self.protocol_combo.addItem("Auto (CDP preferred)", "auto")
        self.protocol_combo.addItem("CDP Only", "cdp")
        self.protocol_combo.addItem("LLDP Only", "lldp")
        self.protocol_combo.addItem("Both (show all)", "both")
        self.protocol_combo.setToolTip(
            "Auto: Shows CDP if available, LLDP only if no CDP found\n"
            "CDP Only: Only capture CDP packets\n"
            "LLDP Only: Only capture LLDP packets\n"
            "Both: Show all discovered neighbors"
        )
        self.protocol_combo.currentIndexChanged.connect(self._on_protocol_mode_changed)
        settings_layout.addWidget(self.protocol_combo)

        # Mode explanation
        self.mode_explanation = QLabel()
        self.mode_explanation.setWordWrap(True)
        self.mode_explanation.setStyleSheet("color: #888; font-size: 11px;")
        self._update_mode_explanation()
        settings_layout.addWidget(self.mode_explanation)

        settings_layout.addStretch()

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        settings_layout.addWidget(separator)

        # Action buttons
        self.start_btn = QPushButton("▶ Start Capture")
        self.start_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;"
        )
        self.start_btn.clicked.connect(self._toggle_capture)
        settings_layout.addWidget(self.start_btn)

        self.clear_btn = QPushButton("🗑 Clear Results")
        self.clear_btn.clicked.connect(self._clear_results)
        settings_layout.addWidget(self.clear_btn)

        parent_layout.addWidget(settings_group, stretch=1)

    def _on_protocol_mode_changed(self):
        """Handle protocol mode change."""
        self.protocol_mode = self.protocol_combo.currentData()
        self._update_mode_explanation()
        # Refresh table display to apply filter
        self._refresh_neighbor_display()

    def _update_mode_explanation(self):
        """Update the mode explanation label."""
        mode = self.protocol_combo.currentData()
        explanations = {
            "auto": "Shows CDP neighbors. Only shows LLDP if no CDP is found for a device.",
            "cdp": "Only captures and displays Cisco CDP packets.",
            "lldp": "Only captures and displays IEEE LLDP packets.",
            "both": "Shows all discovered neighbors from both protocols.",
        }
        self.mode_explanation.setText(explanations.get(mode, ""))

    def _setup_neighbors_table(self, parent_layout):
        """Setup the neighbors table."""
        toolbar_layout = QHBoxLayout()

        self.neighbor_count_label = QLabel("Neighbors: 0 (CDP: 0, LLDP: 0)")
        self.neighbor_count_label.setStyleSheet("font-weight: bold;")
        toolbar_layout.addWidget(self.neighbor_count_label)

        toolbar_layout.addStretch()

        self.auto_scroll_cb = QCheckBox("Auto-scroll")
        self.auto_scroll_cb.setChecked(True)
        toolbar_layout.addWidget(self.auto_scroll_cb)

        parent_layout.addLayout(toolbar_layout)

        # Table with protocol column
        self.neighbors_table = QTableWidget()
        self.neighbors_table.setColumnCount(11)
        self.neighbors_table.setHorizontalHeaderLabels(
            [
                "Protocol",
                "Device ID",
                "IP Address",
                "Port",
                "Platform",
                "Capabilities",
                "VLAN",
                "Local Interface",
                "Local Speed",
                "Last Seen",
                "TTL",
            ]
        )

        self.neighbors_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.neighbors_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.neighbors_table.setAlternatingRowColors(True)
        self.neighbors_table.setSortingEnabled(True)

        header = self.neighbors_table.horizontalHeader()
        header.setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )  # Protocol
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Device ID
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(10, QHeaderView.ResizeMode.ResizeToContents)

        self.neighbors_table.itemSelectionChanged.connect(self._on_neighbor_selected)

        parent_layout.addWidget(self.neighbors_table)

    def _setup_details_section(self, parent_layout):
        """Setup the details section with tabs."""
        self.details_tabs = QTabWidget()

        # General info tab
        self.general_info = QTextEdit()
        self.general_info.setReadOnly(True)
        self.general_info.setFont(QFont("Consolas", 10))
        self.details_tabs.addTab(self.general_info, "General")

        # Software version tab
        self.version_info = QTextEdit()
        self.version_info.setReadOnly(True)
        self.version_info.setFont(QFont("Consolas", 10))
        self.details_tabs.addTab(self.version_info, "Software/Description")

        # Raw data tab
        self.raw_info = QTextEdit()
        self.raw_info.setReadOnly(True)
        self.raw_info.setFont(QFont("Consolas", 9))
        self.details_tabs.addTab(self.raw_info, "All Details")

        parent_layout.addWidget(self.details_tabs)

    def _setup_menu(self):
        """Setup the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        export_action = QAction("&Export Results...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._export_results)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _load_interfaces(self):
        """Load available network interfaces."""
        self.interface_list.clear()
        self.interfaces.clear()

        try:
            all_interfaces = self.nic_detector.get_all_interfaces()

            for iface in all_interfaces:
                status = "🟢" if iface.is_up else "🔴"
                loopback = " (Loopback)" if iface.is_loopback else ""
                ips = (
                    ", ".join(iface.ip_addresses[:2]) if iface.ip_addresses else "No IP"
                )
                speed = (
                    iface.get_speed_display()
                    if hasattr(iface, "get_speed_display")
                    else ""
                )

                display_text = f"{status} {iface.display_name}{loopback}\n    {ips} {f'[{speed}]' if speed else ''}"

                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, iface.name)

                if iface.is_loopback:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                    item.setForeground(QColor("#999"))

                self.interface_list.addItem(item)
                self.interfaces[iface.name] = iface

            self.status_bar.showMessage(
                f"Found {len(all_interfaces)} network interfaces"
            )

        except Exception as e:
            self._show_error(f"Error loading interfaces: {e}")

    def _select_all_interfaces(self):
        """Select all non-loopback interfaces."""
        for i in range(self.interface_list.count()):
            item = self.interface_list.item(i)
            if item.flags() & Qt.ItemFlag.ItemIsEnabled:
                item.setSelected(True)

    def _deselect_all_interfaces(self):
        """Deselect all interfaces."""
        self.interface_list.clearSelection()

    def _toggle_capture(self):
        """Start or stop packet capture."""
        if self.capture and self.capture.is_running():
            self._stop_capture()
        else:
            self._start_capture()

    def _start_capture(self):
        """Start capturing on selected interfaces."""
        selected_items = self.interface_list.selectedItems()

        if not selected_items:
            QMessageBox.warning(
                self,
                "No Interface Selected",
                "Please select at least one network interface to capture on.",
            )
            return

        selected_interfaces = [
            item.data(Qt.ItemDataRole.UserRole) for item in selected_items
        ]

        self.capture = MultiInterfaceDiscoveryCapture(self._on_neighbor_callback)

        for iface_name in selected_interfaces:
            self.capture.add_interface(iface_name)

        try:
            self.capture.start_all()

            self.start_btn.setText("⏹ Stop Capture")
            self.start_btn.setStyleSheet(
                "background-color: #f44336; color: white; font-weight: bold; padding: 10px;"
            )
            self.interface_list.setEnabled(False)
            self.refresh_btn.setEnabled(False)

            iface_names = ", ".join(selected_interfaces)
            self.status_bar.showMessage(f"Capturing CDP/LLDP packets on: {iface_names}")

        except Exception as e:
            self._show_error(f"Failed to start capture: {e}")

    def _stop_capture(self):
        """Stop packet capture."""
        if self.capture:
            self.capture.stop_all()
            self.capture = None

        self.start_btn.setText("▶ Start Capture")
        self.start_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;"
        )
        self.interface_list.setEnabled(True)
        self.refresh_btn.setEnabled(True)

        self.status_bar.showMessage("Capture stopped")

    def _on_neighbor_callback(self, neighbor: DiscoveryNeighbor):
        """Callback from capture thread."""
        self.signals.neighbor_discovered.emit(neighbor)

    def _on_neighbor_discovered_gui(self, neighbor: DiscoveryNeighbor):
        """Handle neighbor discovered (runs on GUI thread)."""
        key = f"{neighbor.protocol}:{neighbor.local_interface}:{neighbor.device_id}:{neighbor.port_id}"
        self.neighbors[key] = neighbor

        # Refresh the display with filtering
        self._refresh_neighbor_display()

        if self.auto_scroll_cb.isChecked():
            self.neighbors_table.scrollToBottom()

    def _should_display_neighbor(self, neighbor: DiscoveryNeighbor) -> bool:
        """Determine if a neighbor should be displayed based on protocol mode."""
        mode = self.protocol_mode

        if mode == "both":
            return True
        elif mode == "cdp":
            return neighbor.protocol == "CDP"
        elif mode == "lldp":
            return neighbor.protocol == "LLDP"
        elif mode == "auto":
            # In auto mode, show CDP. Only show LLDP if no CDP exists for this device/interface
            if neighbor.protocol == "CDP":
                return True
            else:
                # Check if there's a CDP neighbor for the same device on the same local interface
                for key, other in self.neighbors.items():
                    if (
                        other.protocol == "CDP"
                        and other.device_id == neighbor.device_id
                        and other.local_interface == neighbor.local_interface
                    ):
                        return False  # CDP exists, hide LLDP
                return True  # No CDP found, show LLDP

        return True

    def _refresh_neighbor_display(self):
        """Refresh the neighbor table based on current filter settings."""
        self.neighbors_table.setRowCount(0)

        # Filter and display neighbors
        displayed_neighbors = []
        for key, neighbor in self.neighbors.items():
            if self._should_display_neighbor(neighbor):
                displayed_neighbors.append((key, neighbor))

        for key, neighbor in displayed_neighbors:
            row = self.neighbors_table.rowCount()
            self.neighbors_table.insertRow(row)
            self._set_row_data(row, neighbor, key)

        # Update counts (show both total and filtered)
        total_cdp = sum(1 for n in self.neighbors.values() if n.protocol == "CDP")
        total_lldp = sum(1 for n in self.neighbors.values() if n.protocol == "LLDP")
        displayed_cdp = sum(1 for _, n in displayed_neighbors if n.protocol == "CDP")
        displayed_lldp = sum(1 for _, n in displayed_neighbors if n.protocol == "LLDP")

        if self.protocol_mode == "both":
            self.neighbor_count_label.setText(
                f"Neighbors: {len(displayed_neighbors)} (CDP: {displayed_cdp}, LLDP: {displayed_lldp})"
            )
        else:
            self.neighbor_count_label.setText(
                f"Showing: {len(displayed_neighbors)} (CDP: {displayed_cdp}, LLDP: {displayed_lldp}) | "
                f"Total captured: {len(self.neighbors)}"
            )

    def _set_row_data(self, row: int, neighbor: DiscoveryNeighbor, key: str):
        """Set data for a table row."""
        # Get IP address
        ip_display = neighbor.get_display_ip()

        # Get VLAN info
        vlan_display = str(neighbor.native_vlan) if neighbor.native_vlan else "N/A"
        if neighbor.voice_vlan:
            vlan_display += f" (Voice: {neighbor.voice_vlan})"

        items = [
            neighbor.protocol,
            neighbor.device_id,
            ip_display,
            neighbor.port_id,
            (
                neighbor.platform[:30] + "..."
                if len(neighbor.platform) > 30
                else neighbor.platform
            ),
            ", ".join(neighbor.capabilities[:3]) if neighbor.capabilities else "N/A",
            vlan_display,
            neighbor.local_interface,
            neighbor.local_port_speed if neighbor.local_port_speed else "N/A",
            neighbor.last_seen.strftime("%H:%M:%S"),
            f"{neighbor.ttl}s",
        ]

        # Determine if we're in dark mode by checking the palette
        app = QApplication.instance()
        is_dark_mode = app.palette().color(QPalette.ColorRole.Window).lightness() < 128

        for col, text in enumerate(items):
            item = QTableWidgetItem(str(text))
            if col == 0:
                item.setData(Qt.ItemDataRole.UserRole, key)

            # Color code by protocol - use colors that work in both light and dark mode
            if neighbor.protocol == "CDP":
                if is_dark_mode:
                    # Dark mode: use blue text
                    item.setForeground(QColor("#64B5F6"))  # Light blue text
                else:
                    # Light mode: use dark blue text on light blue background
                    item.setForeground(QColor("#1565C0"))  # Dark blue text
                    item.setBackground(QColor("#E3F2FD"))  # Light blue background
            else:  # LLDP
                if is_dark_mode:
                    # Dark mode: use green text
                    item.setForeground(QColor("#81C784"))  # Light green text
                else:
                    # Light mode: use dark green text on light green background
                    item.setForeground(QColor("#2E7D32"))  # Dark green text
                    item.setBackground(QColor("#E8F5E9"))  # Light green background

            self.neighbors_table.setItem(row, col, item)

    def _on_neighbor_selected(self):
        """Handle neighbor selection in table."""
        selected_rows = self.neighbors_table.selectedItems()
        if not selected_rows:
            self.general_info.clear()
            self.version_info.clear()
            self.raw_info.clear()
            return

        row = selected_rows[0].row()
        key_item = self.neighbors_table.item(row, 0)
        if not key_item:
            return

        key = key_item.data(Qt.ItemDataRole.UserRole)
        neighbor = self.neighbors.get(key)

        if not neighbor:
            return

        # Update general info
        all_ips = list(set(neighbor.ip_addresses + neighbor.mgmt_addresses))

        general_text = f"""Protocol: {neighbor.protocol}
Device ID: {neighbor.device_id}
Platform: {neighbor.platform}
Port ID: {neighbor.port_id}
{"Port Description: " + neighbor.port_description if neighbor.port_description else ""}

IP/Management Addresses: {', '.join(all_ips) if all_ips else 'N/A'}

Capabilities: {', '.join(neighbor.capabilities) if neighbor.capabilities else 'N/A'}
Native VLAN: {neighbor.native_vlan if neighbor.native_vlan else 'N/A'}"""

        if neighbor.protocol == "CDP":
            general_text += f"""
Voice VLAN: {neighbor.voice_vlan if neighbor.voice_vlan else 'N/A'}
Duplex: {neighbor.duplex if neighbor.duplex else 'N/A'}
VTP Domain: {neighbor.vtp_domain if neighbor.vtp_domain else 'N/A'}"""
        else:
            general_text += f"""
VLAN Name: {neighbor.vlan_name if neighbor.vlan_name else 'N/A'}"""

        general_text += f"""

Source MAC: {neighbor.source_mac}
Local Interface: {neighbor.local_interface}
Local Port Speed: {neighbor.local_port_speed if neighbor.local_port_speed else 'N/A'}
TTL: {neighbor.ttl} seconds
Last Seen: {neighbor.last_seen.strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.general_info.setPlainText(general_text)

        # Update version info
        self.version_info.setPlainText(
            neighbor.software_version if neighbor.software_version else "N/A"
        )

        # Update raw info (all details)
        raw_text = ""
        for k, value in neighbor.to_dict().items():
            raw_text += f"{k}: {value}\n"
        self.raw_info.setPlainText(raw_text)

    def _clear_results(self):
        """Clear all results."""
        self.neighbors.clear()
        self.neighbors_table.setRowCount(0)
        self.neighbor_count_label.setText("Neighbors: 0 (CDP: 0, LLDP: 0)")
        self.general_info.clear()
        self.version_info.clear()
        self.raw_info.clear()

        if self.capture:
            self.capture.clear_all_neighbors()

        self.status_bar.showMessage("Results cleared")

    def _update_capture_status(self):
        """Update capture status periodically."""
        if self.capture and self.capture.is_running():
            cdp_count = sum(1 for n in self.neighbors.values() if n.protocol == "CDP")
            lldp_count = sum(1 for n in self.neighbors.values() if n.protocol == "LLDP")
            self.status_bar.showMessage(
                f"Capturing... {len(self.neighbors)} neighbors (CDP: {cdp_count}, LLDP: {lldp_count})"
            )

    def _export_results(self):
        """Export results to file."""
        if not self.neighbors:
            QMessageBox.information(self, "No Data", "No neighbors to export.")
            return

        from PyQt6.QtWidgets import QFileDialog

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Results",
            "discovery_neighbors.txt",
            "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)",
        )

        if filename:
            try:
                with open(filename, "w") as f:
                    if filename.endswith(".csv"):
                        headers = [
                            "Protocol",
                            "Device ID",
                            "IP Addresses",
                            "Port ID",
                            "Platform",
                            "Capabilities",
                            "Native VLAN",
                            "Local Interface",
                            "Last Seen",
                        ]
                        f.write(",".join(headers) + "\n")

                        for neighbor in self.neighbors.values():
                            all_ips = list(
                                set(neighbor.ip_addresses + neighbor.mgmt_addresses)
                            )
                            row = [
                                neighbor.protocol,
                                neighbor.device_id,
                                "|".join(all_ips),
                                neighbor.port_id,
                                neighbor.platform,
                                "|".join(neighbor.capabilities),
                                (
                                    str(neighbor.native_vlan)
                                    if neighbor.native_vlan
                                    else ""
                                ),
                                neighbor.local_interface,
                                neighbor.last_seen.strftime("%Y-%m-%d %H:%M:%S"),
                            ]
                            f.write(",".join(f'"{v}"' for v in row) + "\n")
                    else:
                        f.write("Discovery Protocol Neighbors Report\n")
                        f.write("=" * 60 + "\n")
                        f.write(
                            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        )
                        f.write(f"Total Neighbors: {len(self.neighbors)}\n")
                        cdp_count = sum(
                            1 for n in self.neighbors.values() if n.protocol == "CDP"
                        )
                        lldp_count = sum(
                            1 for n in self.neighbors.values() if n.protocol == "LLDP"
                        )
                        f.write(f"CDP: {cdp_count}, LLDP: {lldp_count}\n")
                        f.write("=" * 60 + "\n\n")

                        for neighbor in self.neighbors.values():
                            f.write(f"[{neighbor.protocol}] {neighbor.device_id}\n")
                            for k, value in neighbor.to_dict().items():
                                f.write(f"  {k}: {value}\n")
                            f.write("\n")

                self.status_bar.showMessage(f"Results exported to {filename}")

            except Exception as e:
                self._show_error(f"Export failed: {e}")

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Discovery Listener",
            """<h2>CDP/LLDP Discovery Listener</h2>
            <p>Version 1.1</p>
            <p>A cross-platform application for listening to network discovery protocol packets.</p>
            <p><b>Supported Protocols:</b></p>
            <ul>
                <li>CDP (Cisco Discovery Protocol)</li>
                <li>LLDP (Link Layer Discovery Protocol)</li>
            </ul>
            <p><b>Features:</b></p>
            <ul>
                <li>Multi-interface capture support</li>
                <li>Real-time neighbor discovery</li>
                <li>Detailed neighbor information display</li>
                <li>Export capabilities</li>
            </ul>
            <p><b>Requirements:</b></p>
            <ul>
                <li>Administrator/root privileges for packet capture</li>
                <li>Npcap (Windows) or libpcap (Linux/Mac)</li>
            </ul>
            <p>Built with Python, PyQt6, and Scapy</p>
            """,
        )

    def _show_error(self, message: str):
        """Show error message."""
        QMessageBox.critical(self, "Error", message)

    def _update_status(self, message: str):
        """Update status bar message."""
        self.status_bar.showMessage(message)

    def closeEvent(self, event):
        """Handle window close event."""
        if self.capture and self.capture.is_running():
            self._stop_capture()
        event.accept()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Set application icon
    icon_path = get_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    window = PortDetectiveWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
