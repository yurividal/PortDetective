"""
CDP Packet Capture Module
Handles capturing CDP packets from network interfaces using Scapy.
"""

import threading
from typing import Callable, Optional, List, Dict
from datetime import datetime
from queue import Queue

from cdp_parser import CDPParser, CDPNeighbor
from nic_detector import NICDetector, NetworkInterface


class CDPCapture:
    """
    CDP packet capture handler using Scapy.
    Runs capture in a separate thread to avoid blocking the GUI.
    """

    # CDP uses LLC/SNAP with this destination MAC
    CDP_FILTER = "ether dst 01:00:0c:cc:cc:cc"

    def __init__(self, interface: str, callback: Callable[[CDPNeighbor], None]):
        """
        Initialize the CDP capture.

        Args:
            interface: Network interface name to capture on
            callback: Function to call when a CDP packet is received
        """
        self.interface = interface
        self.callback = callback
        self._stop_event = threading.Event()
        self._capture_thread: Optional[threading.Thread] = None
        self._neighbors: dict = {}  # Key: device_id, Value: CDPNeighbor
        self._packet_queue: Queue = Queue()
        self._parser = CDPParser()

    def start(self):
        """Start capturing CDP packets."""
        if self._capture_thread and self._capture_thread.is_alive():
            return

        self._stop_event.clear()
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

    def stop(self):
        """Stop capturing CDP packets."""
        self._stop_event.set()
        if self._capture_thread:
            self._capture_thread.join(timeout=2.0)
            self._capture_thread = None

    def is_running(self) -> bool:
        """Check if capture is currently running."""
        return self._capture_thread is not None and self._capture_thread.is_alive()

    def get_neighbors(self) -> List[CDPNeighbor]:
        """Get list of discovered CDP neighbors."""
        return list(self._neighbors.values())

    def clear_neighbors(self):
        """Clear the list of discovered neighbors."""
        self._neighbors.clear()

    def _capture_loop(self):
        """Main capture loop running in a separate thread."""
        try:
            # Import scapy here to handle import errors gracefully
            from scapy.all import sniff, conf
            from scapy.contrib import cdp  # Load CDP layer

            # Configure scapy
            conf.verb = 0  # Disable verbose output

            def packet_handler(packet):
                """Handle captured packets."""
                if self._stop_event.is_set():
                    return

                try:
                    # Debug: print raw packet info
                    raw_bytes = bytes(packet)
                    print(f"[DEBUG] Received packet: {len(raw_bytes)} bytes")
                    print(f"[DEBUG] First 80 bytes (hex): {raw_bytes[:80].hex()}")

                    neighbor = self._parser.parse_cdp_packet(packet)
                    if neighbor:
                        neighbor.local_interface = self.interface
                        print(
                            f"[DEBUG] Parsed neighbor: {neighbor.device_id}, Platform: {neighbor.platform}"
                        )
                        self._update_neighbor(neighbor)
                    else:
                        print("[DEBUG] Failed to parse neighbor from packet")
                except Exception as e:
                    print(f"Error processing packet: {e}")
                    import traceback

                    traceback.print_exc()

            # Start sniffing with the CDP filter
            # Using store=0 to not store packets in memory
            # Using stop_filter to check for stop event
            sniff(
                iface=self.interface,
                filter=self.CDP_FILTER,
                prn=packet_handler,
                store=0,
                stop_filter=lambda x: self._stop_event.is_set(),
            )

        except ImportError as e:
            print(f"Scapy import error: {e}")
            print("Please install scapy: pip install scapy")
        except PermissionError:
            print("Permission denied. Please run with administrator/root privileges.")
        except Exception as e:
            print(f"Capture error: {e}")

    def _update_neighbor(self, neighbor: CDPNeighbor):
        """
        Update the neighbor list and call the callback.

        Args:
            neighbor: CDPNeighbor object to add/update
        """
        # Use device_id + port_id as unique key
        key = f"{neighbor.device_id}:{neighbor.port_id}"

        is_new = key not in self._neighbors
        self._neighbors[key] = neighbor

        # Call the callback on the main thread
        if self.callback:
            self.callback(neighbor)


class MultiInterfaceCapture:
    """
    Manages CDP capture on multiple interfaces simultaneously.
    """

    def __init__(self, callback: Callable[[CDPNeighbor], None]):
        """
        Initialize multi-interface capture.

        Args:
            callback: Function to call when a CDP packet is received
        """
        self.callback = callback
        self._captures: dict = {}  # interface_name -> CDPCapture
        self._all_neighbors: dict = {}  # unique_key -> CDPNeighbor
        self._interface_info: Dict[str, NetworkInterface] = (
            {}
        )  # interface_name -> NetworkInterface
        self._nic_detector = NICDetector()
        self._load_interface_info()

    def _load_interface_info(self):
        """Load interface information for speed lookup."""
        interfaces = self._nic_detector.get_all_interfaces()
        self._interface_info = {iface.name: iface for iface in interfaces}

    def get_interface_speed(self, interface_name: str) -> str:
        """Get the speed of an interface as a display string."""
        iface = self._interface_info.get(interface_name)
        if iface:
            return iface.get_speed_display()
        return "Unknown"

    def add_interface(self, interface: str):
        """Add an interface to capture on."""
        if interface not in self._captures:
            capture = CDPCapture(interface, self._on_neighbor_discovered)
            self._captures[interface] = capture

    def remove_interface(self, interface: str):
        """Remove an interface from capture."""
        if interface in self._captures:
            self._captures[interface].stop()
            del self._captures[interface]

    def start_all(self):
        """Start capture on all interfaces."""
        for capture in self._captures.values():
            capture.start()

    def stop_all(self):
        """Stop capture on all interfaces."""
        for capture in self._captures.values():
            capture.stop()

    def start_interface(self, interface: str):
        """Start capture on a specific interface."""
        if interface in self._captures:
            self._captures[interface].start()

    def stop_interface(self, interface: str):
        """Stop capture on a specific interface."""
        if interface in self._captures:
            self._captures[interface].stop()

    def is_running(self, interface: str = None) -> bool:
        """Check if capture is running."""
        if interface:
            return (
                interface in self._captures and self._captures[interface].is_running()
            )
        return any(c.is_running() for c in self._captures.values())

    def get_all_neighbors(self) -> List[CDPNeighbor]:
        """Get all discovered neighbors from all interfaces."""
        return list(self._all_neighbors.values())

    def clear_all_neighbors(self):
        """Clear all discovered neighbors."""
        self._all_neighbors.clear()
        for capture in self._captures.values():
            capture.clear_neighbors()

    def _on_neighbor_discovered(self, neighbor: CDPNeighbor):
        """Internal callback when a neighbor is discovered."""
        key = f"{neighbor.local_interface}:{neighbor.device_id}:{neighbor.port_id}"

        # Set the local port speed
        neighbor.local_port_speed = self.get_interface_speed(neighbor.local_interface)

        self._all_neighbors[key] = neighbor

        if self.callback:
            self.callback(neighbor)
