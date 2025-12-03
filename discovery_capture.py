"""
Discovery Protocol Capture Module
Handles capturing both CDP and LLDP packets from network interfaces.
"""

import threading
from typing import Callable, Optional, List, Dict, Union
from datetime import datetime
from queue import Queue

from cdp_parser import CDPParser, CDPNeighbor
from lldp_parser import LLDPParser, LLDPNeighbor
from neighbor import DiscoveryNeighbor
from nic_detector import NICDetector, NetworkInterface


class DiscoveryCapture:
    """
    Unified CDP/LLDP packet capture handler using Scapy.
    Runs capture in a separate thread to avoid blocking the GUI.
    """

    # Filter for both CDP and LLDP packets
    # CDP: destination MAC 01:00:0c:cc:cc:cc
    # LLDP: destination MACs 01:80:c2:00:00:0e, 01:80:c2:00:00:03, 01:80:c2:00:00:00
    # Also filter by EtherType 0x88CC for LLDP
    DISCOVERY_FILTER = "(ether dst 01:00:0c:cc:cc:cc) or (ether proto 0x88cc) or (ether dst 01:80:c2:00:00:0e) or (ether dst 01:80:c2:00:00:03) or (ether dst 01:80:c2:00:00:00)"

    def __init__(self, interface: str, callback: Callable[[DiscoveryNeighbor], None]):
        """
        Initialize the discovery capture.

        Args:
            interface: Network interface name to capture on
            callback: Function to call when a discovery packet is received
        """
        self.interface = interface
        self.callback = callback
        self._stop_event = threading.Event()
        self._capture_thread: Optional[threading.Thread] = None
        self._neighbors: dict = {}
        self._packet_queue: Queue = Queue()
        self._cdp_parser = CDPParser()
        self._lldp_parser = LLDPParser()

    def start(self):
        """Start capturing discovery packets."""
        if self._capture_thread and self._capture_thread.is_alive():
            return

        self._stop_event.clear()
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

    def stop(self):
        """Stop capturing packets."""
        self._stop_event.set()
        if self._capture_thread:
            self._capture_thread.join(timeout=2.0)
            self._capture_thread = None

    def is_running(self) -> bool:
        """Check if capture is currently running."""
        return self._capture_thread is not None and self._capture_thread.is_alive()

    def get_neighbors(self) -> List[DiscoveryNeighbor]:
        """Get list of discovered neighbors."""
        return list(self._neighbors.values())

    def clear_neighbors(self):
        """Clear the list of discovered neighbors."""
        self._neighbors.clear()

    def _detect_protocol(self, raw_bytes: bytes) -> str:
        """
        Detect if packet is CDP or LLDP.

        Args:
            raw_bytes: Raw packet bytes

        Returns:
            "CDP", "LLDP", or "UNKNOWN"
        """
        if len(raw_bytes) < 14:
            return "UNKNOWN"

        # Check destination MAC
        dest_mac = raw_bytes[0:6]

        # CDP destination MAC: 01:00:0c:cc:cc:cc
        if dest_mac == b"\x01\x00\x0c\xcc\xcc\xcc":
            return "CDP"

        # LLDP destination MACs
        lldp_macs = [
            b"\x01\x80\xc2\x00\x00\x0e",
            b"\x01\x80\xc2\x00\x00\x03",
            b"\x01\x80\xc2\x00\x00\x00",
        ]
        if dest_mac in lldp_macs:
            return "LLDP"

        # Check EtherType for LLDP (0x88CC)
        ethertype = (raw_bytes[12] << 8) | raw_bytes[13]
        if ethertype == 0x88CC:
            return "LLDP"

        return "UNKNOWN"

    def _capture_loop(self):
        """Main capture loop running in a separate thread."""
        try:
            from scapy.all import sniff, conf
            from scapy.contrib import cdp  # Load CDP layer

            conf.verb = 0

            def packet_handler(packet):
                """Handle captured packets."""
                if self._stop_event.is_set():
                    return

                try:
                    raw_bytes = bytes(packet)
                    protocol = self._detect_protocol(raw_bytes)

                    print(f"[DEBUG] Received {protocol} packet: {len(raw_bytes)} bytes")
                    print(f"[DEBUG] First 60 bytes (hex): {raw_bytes[:60].hex()}")

                    neighbor = None

                    if protocol == "CDP":
                        cdp_neighbor = self._cdp_parser.parse_cdp_packet(packet)
                        if cdp_neighbor:
                            cdp_neighbor.local_interface = self.interface
                            neighbor = DiscoveryNeighbor.from_cdp(cdp_neighbor)
                            print(f"[DEBUG] Parsed CDP neighbor: {neighbor.device_id}")

                    elif protocol == "LLDP":
                        lldp_neighbor = self._lldp_parser.parse_lldp_packet(packet)
                        if lldp_neighbor:
                            lldp_neighbor.local_interface = self.interface
                            neighbor = DiscoveryNeighbor.from_lldp(lldp_neighbor)
                            print(f"[DEBUG] Parsed LLDP neighbor: {neighbor.device_id}")

                    if neighbor:
                        self._update_neighbor(neighbor)
                    else:
                        print(f"[DEBUG] Failed to parse {protocol} packet")

                except Exception as e:
                    print(f"Error processing packet: {e}")
                    import traceback

                    traceback.print_exc()

            sniff(
                iface=self.interface,
                filter=self.DISCOVERY_FILTER,
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
            import traceback

            traceback.print_exc()

    def _update_neighbor(self, neighbor: DiscoveryNeighbor):
        """Update the neighbor list and call the callback."""
        key = f"{neighbor.protocol}:{neighbor.local_interface}:{neighbor.device_id}:{neighbor.port_id}"

        self._neighbors[key] = neighbor

        if self.callback:
            self.callback(neighbor)


class MultiInterfaceDiscoveryCapture:
    """
    Manages discovery protocol capture on multiple interfaces simultaneously.
    Supports both CDP and LLDP.
    """

    def __init__(self, callback: Callable[[DiscoveryNeighbor], None]):
        """
        Initialize multi-interface capture.

        Args:
            callback: Function to call when a discovery packet is received
        """
        self.callback = callback
        self._captures: Dict[str, DiscoveryCapture] = {}
        self._all_neighbors: Dict[str, DiscoveryNeighbor] = {}
        self._interface_info: Dict[str, NetworkInterface] = {}
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
            capture = DiscoveryCapture(interface, self._on_neighbor_discovered)
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

    def get_all_neighbors(self) -> List[DiscoveryNeighbor]:
        """Get all discovered neighbors from all interfaces."""
        return list(self._all_neighbors.values())

    def clear_all_neighbors(self):
        """Clear all discovered neighbors."""
        self._all_neighbors.clear()
        for capture in self._captures.values():
            capture.clear_neighbors()

    def _on_neighbor_discovered(self, neighbor: DiscoveryNeighbor):
        """Internal callback when a neighbor is discovered."""
        key = f"{neighbor.protocol}:{neighbor.local_interface}:{neighbor.device_id}:{neighbor.port_id}"

        # Set the local port speed
        neighbor.local_port_speed = self.get_interface_speed(neighbor.local_interface)

        self._all_neighbors[key] = neighbor

        if self.callback:
            self.callback(neighbor)
