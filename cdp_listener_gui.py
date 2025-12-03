"""
CDP Listener - Main GUI Application
Cross-platform GUI for listening to CDP (Cisco Discovery Protocol) packets.
"""

import sys
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
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
    QTextEdit,
    QSplitter,
    QHeaderView,
    QMessageBox,
    QStatusBar,
    QCheckBox,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QTabWidget,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QIcon, QAction

from nic_detector import NICDetector, NetworkInterface
from cdp_parser import CDPNeighbor
from cdp_capture import CDPCapture, MultiInterfaceCapture


class NeighborSignals(QObject):
    """Signals for thread-safe GUI updates."""

    neighbor_discovered = pyqtSignal(object)
    capture_error = pyqtSignal(str)
    status_update = pyqtSignal(str)


class CDPListenerWindow(QMainWindow):
    """Main application window for CDP Listener."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CDP Listener - Cisco Discovery Protocol Monitor")
        self.setMinimumSize(1000, 700)

        # Initialize components
        self.nic_detector = NICDetector()
        self.interfaces: Dict[str, NetworkInterface] = {}
        self.capture: Optional[MultiInterfaceCapture] = None
        self.neighbors: Dict[str, CDPNeighbor] = {}

        # Thread-safe signals
        self.signals = NeighborSignals()
        self.signals.neighbor_discovered.connect(self._on_neighbor_discovered_gui)
        self.signals.capture_error.connect(self._show_error)
        self.signals.status_update.connect(self._update_status)

        # Setup UI
        self._setup_ui()
        self._load_interfaces()

        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_capture_status)
        self.status_timer.start(1000)  # Update every second

    def _setup_ui(self):
        """Setup the user interface."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Top section - Interface selection
        self._setup_interface_section(main_layout)

        # Middle section - Splitter with neighbors table and details
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Neighbors table
        neighbors_group = QGroupBox("Discovered CDP Neighbors")
        neighbors_layout = QVBoxLayout(neighbors_group)
        self._setup_neighbors_table(neighbors_layout)
        splitter.addWidget(neighbors_group)

        # Details section with tabs
        details_group = QGroupBox("Neighbor Details")
        details_layout = QVBoxLayout(details_group)
        self._setup_details_section(details_layout)
        splitter.addWidget(details_group)

        # Set splitter sizes
        splitter.setSizes([400, 250])
        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(
            "Ready - Select interfaces and click Start to begin capturing"
        )

        # Menu bar
        self._setup_menu()

    def _setup_interface_section(self, parent_layout):
        """Setup the interface selection section."""
        interface_group = QGroupBox("Network Interfaces")
        interface_layout = QVBoxLayout(interface_group)

        # Info label
        info_label = QLabel(
            "Select one or more network interfaces to listen for CDP packets:"
        )
        info_label.setStyleSheet("color: #666;")
        interface_layout.addWidget(info_label)

        # Interface list and controls
        h_layout = QHBoxLayout()

        # Interface list widget (allows multiple selection)
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

        self.start_btn = QPushButton("▶ Start Capture")
        self.start_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;"
        )
        self.start_btn.clicked.connect(self._toggle_capture)
        btn_layout.addWidget(self.start_btn)

        self.clear_btn = QPushButton("🗑 Clear Results")
        self.clear_btn.clicked.connect(self._clear_results)
        btn_layout.addWidget(self.clear_btn)

        h_layout.addLayout(btn_layout, stretch=1)
        interface_layout.addLayout(h_layout)

        parent_layout.addWidget(interface_group)

    def _setup_neighbors_table(self, parent_layout):
        """Setup the neighbors table."""
        # Toolbar
        toolbar_layout = QHBoxLayout()

        self.neighbor_count_label = QLabel("Neighbors: 0")
        self.neighbor_count_label.setStyleSheet("font-weight: bold;")
        toolbar_layout.addWidget(self.neighbor_count_label)

        toolbar_layout.addStretch()

        self.auto_scroll_cb = QCheckBox("Auto-scroll")
        self.auto_scroll_cb.setChecked(True)
        toolbar_layout.addWidget(self.auto_scroll_cb)

        parent_layout.addLayout(toolbar_layout)

        # Table
        self.neighbors_table = QTableWidget()
        self.neighbors_table.setColumnCount(10)
        self.neighbors_table.setHorizontalHeaderLabels(
            [
                "Device ID",
                "IP Address",
                "Port",
                "Platform",
                "Capabilities",
                "Native VLAN",
                "Voice VLAN",
                "Local Interface",
                "Local Speed",
                "Last Seen",
            ]
        )

        # Table settings
        self.neighbors_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.neighbors_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.neighbors_table.setAlternatingRowColors(True)
        self.neighbors_table.setSortingEnabled(True)

        # Column widths
        header = self.neighbors_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Device ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)

        # Selection changed
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
        self.details_tabs.addTab(self.version_info, "Software Version")

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
                # Create list item
                status = "🟢" if iface.is_up else "🔴"
                loopback = " (Loopback)" if iface.is_loopback else ""
                ips = (
                    ", ".join(iface.ip_addresses[:2]) if iface.ip_addresses else "No IP"
                )

                display_text = f"{status} {iface.display_name}{loopback}\n    {ips}"

                item = QListWidgetItem(display_text)
                item.setData(Qt.ItemDataRole.UserRole, iface.name)

                # Disable loopback interfaces (can't capture CDP on them)
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

        # Get selected interface names
        selected_interfaces = [
            item.data(Qt.ItemDataRole.UserRole) for item in selected_items
        ]

        # Create capture instance
        self.capture = MultiInterfaceCapture(self._on_neighbor_callback)

        for iface_name in selected_interfaces:
            self.capture.add_interface(iface_name)

        try:
            self.capture.start_all()

            # Update UI
            self.start_btn.setText("⏹ Stop Capture")
            self.start_btn.setStyleSheet(
                "background-color: #f44336; color: white; font-weight: bold; padding: 10px;"
            )
            self.interface_list.setEnabled(False)
            self.refresh_btn.setEnabled(False)

            iface_names = ", ".join(selected_interfaces)
            self.status_bar.showMessage(f"Capturing CDP packets on: {iface_names}")

        except Exception as e:
            self._show_error(f"Failed to start capture: {e}")

    def _stop_capture(self):
        """Stop packet capture."""
        if self.capture:
            self.capture.stop_all()
            self.capture = None

        # Update UI
        self.start_btn.setText("▶ Start Capture")
        self.start_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;"
        )
        self.interface_list.setEnabled(True)
        self.refresh_btn.setEnabled(True)

        self.status_bar.showMessage("Capture stopped")

    def _on_neighbor_callback(self, neighbor: CDPNeighbor):
        """Callback from capture thread - emit signal for thread-safe GUI update."""
        self.signals.neighbor_discovered.emit(neighbor)

    def _on_neighbor_discovered_gui(self, neighbor: CDPNeighbor):
        """Handle neighbor discovered (runs on GUI thread)."""
        key = f"{neighbor.local_interface}:{neighbor.device_id}:{neighbor.port_id}"
        is_new = key not in self.neighbors
        self.neighbors[key] = neighbor

        if is_new:
            self._add_neighbor_row(neighbor, key)
        else:
            self._update_neighbor_row(neighbor, key)

        self.neighbor_count_label.setText(f"Neighbors: {len(self.neighbors)}")

        if self.auto_scroll_cb.isChecked():
            self.neighbors_table.scrollToBottom()

    def _add_neighbor_row(self, neighbor: CDPNeighbor, key: str):
        """Add a new row to the neighbors table."""
        row = self.neighbors_table.rowCount()
        self.neighbors_table.insertRow(row)

        self._set_row_data(row, neighbor, key)

    def _update_neighbor_row(self, neighbor: CDPNeighbor, key: str):
        """Update an existing row in the neighbors table."""
        # Find the row with this key
        for row in range(self.neighbors_table.rowCount()):
            item = self.neighbors_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == key:
                self._set_row_data(row, neighbor, key)
                break

    def _set_row_data(self, row: int, neighbor: CDPNeighbor, key: str):
        """Set data for a table row."""
        items = [
            neighbor.device_id,
            ", ".join(neighbor.ip_addresses) if neighbor.ip_addresses else "N/A",
            neighbor.port_id,
            neighbor.platform,
            ", ".join(neighbor.capabilities) if neighbor.capabilities else "N/A",
            str(neighbor.native_vlan) if neighbor.native_vlan else "N/A",
            str(neighbor.voice_vlan) if neighbor.voice_vlan else "N/A",
            neighbor.local_interface,
            neighbor.local_port_speed if neighbor.local_port_speed else "N/A",
            neighbor.last_seen.strftime("%H:%M:%S"),
        ]

        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            if col == 0:
                item.setData(Qt.ItemDataRole.UserRole, key)
            self.neighbors_table.setItem(row, col, item)

    def _on_neighbor_selected(self):
        """Handle neighbor selection in table."""
        selected_rows = self.neighbors_table.selectedItems()
        if not selected_rows:
            self.general_info.clear()
            self.version_info.clear()
            self.raw_info.clear()
            return

        # Get the key from the first column
        row = selected_rows[0].row()
        key_item = self.neighbors_table.item(row, 0)
        if not key_item:
            return

        key = key_item.data(Qt.ItemDataRole.UserRole)
        neighbor = self.neighbors.get(key)

        if not neighbor:
            return

        # Update general info
        general_text = f"""Device ID: {neighbor.device_id}
Platform: {neighbor.platform}
Port ID: {neighbor.port_id}

IP Addresses: {', '.join(neighbor.ip_addresses) if neighbor.ip_addresses else 'N/A'}
Management Addresses: {', '.join(neighbor.mgmt_addresses) if neighbor.mgmt_addresses else 'N/A'}

Capabilities: {', '.join(neighbor.capabilities) if neighbor.capabilities else 'N/A'}
Native VLAN: {neighbor.native_vlan if neighbor.native_vlan else 'N/A'}
Voice VLAN: {neighbor.voice_vlan if neighbor.voice_vlan else 'N/A'}
Duplex: {neighbor.duplex if neighbor.duplex else 'N/A'}
VTP Domain: {neighbor.vtp_domain if neighbor.vtp_domain else 'N/A'}

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
        for key, value in neighbor.to_dict().items():
            raw_text += f"{key}: {value}\n"
        self.raw_info.setPlainText(raw_text)

    def _clear_results(self):
        """Clear all results."""
        self.neighbors.clear()
        self.neighbors_table.setRowCount(0)
        self.neighbor_count_label.setText("Neighbors: 0")
        self.general_info.clear()
        self.version_info.clear()
        self.raw_info.clear()

        if self.capture:
            self.capture.clear_all_neighbors()

        self.status_bar.showMessage("Results cleared")

    def _update_capture_status(self):
        """Update capture status periodically."""
        if self.capture and self.capture.is_running():
            elapsed = "Running..."
            self.status_bar.showMessage(
                f"Capturing... {len(self.neighbors)} neighbors discovered"
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
            "cdp_neighbors.txt",
            "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)",
        )

        if filename:
            try:
                with open(filename, "w") as f:
                    if filename.endswith(".csv"):
                        # CSV format
                        headers = [
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
                            row = [
                                neighbor.device_id,
                                "|".join(neighbor.ip_addresses),
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
                        # Text format
                        f.write("CDP Neighbors Report\n")
                        f.write("=" * 60 + "\n")
                        f.write(
                            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        )
                        f.write(f"Total Neighbors: {len(self.neighbors)}\n")
                        f.write("=" * 60 + "\n\n")

                        for neighbor in self.neighbors.values():
                            f.write(f"Device: {neighbor.device_id}\n")
                            for key, value in neighbor.to_dict().items():
                                f.write(f"  {key}: {value}\n")
                            f.write("\n")

                self.status_bar.showMessage(f"Results exported to {filename}")

            except Exception as e:
                self._show_error(f"Export failed: {e}")

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About CDP Listener",
            """<h2>CDP Listener</h2>
            <p>Version 1.0</p>
            <p>A cross-platform application for listening to Cisco Discovery Protocol (CDP) packets.</p>
            <p><b>Features:</b></p>
            <ul>
                <li>Multi-interface capture support</li>
                <li>Real-time CDP neighbor discovery</li>
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

    # Set application style
    app.setStyle("Fusion")

    # Create and show main window
    window = CDPListenerWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
