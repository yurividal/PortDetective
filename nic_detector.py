"""
Network Interface Detection Module
Cross-platform NIC detection and information retrieval.
"""

import psutil
import socket
from dataclasses import dataclass
from typing import List, Optional, Dict
import sys


@dataclass
class NetworkInterface:
    """Represents a network interface."""

    name: str
    display_name: str
    mac_address: str
    ip_addresses: List[str]
    is_up: bool
    is_loopback: bool
    mtu: Optional[int] = None
    speed: Optional[int] = None  # Speed in Mbps

    def get_speed_display(self) -> str:
        """Get human-readable speed string."""
        if self.speed is None or self.speed == 0:
            return "Unknown"
        elif self.speed >= 1000:
            return f"{self.speed // 1000}G"
        else:
            return f"{self.speed}M"

    def __str__(self) -> str:
        ips = ", ".join(self.ip_addresses) if self.ip_addresses else "No IP"
        return f"{self.display_name} ({self.name}) - {ips}"


class NICDetector:
    """Cross-platform network interface detector."""

    @staticmethod
    def get_all_interfaces() -> List[NetworkInterface]:
        """
        Get all available network interfaces.

        Returns:
            List of NetworkInterface objects
        """
        interfaces = []

        try:
            # Get interface addresses
            if_addrs = psutil.net_if_addrs()
            # Get interface stats
            if_stats = psutil.net_if_stats()

            for iface_name, addrs in if_addrs.items():
                mac_address = ""
                ip_addresses = []
                is_loopback = False

                for addr in addrs:
                    if addr.family == psutil.AF_LINK:  # MAC address
                        mac_address = addr.address
                    elif addr.family == socket.AF_INET:  # IPv4
                        ip_addresses.append(addr.address)
                        if addr.address.startswith("127."):
                            is_loopback = True
                    elif addr.family == socket.AF_INET6:  # IPv6
                        # Skip link-local IPv6 for cleaner display
                        if not addr.address.startswith("fe80"):
                            ip_addresses.append(addr.address)

                # Get stats for this interface
                stats = if_stats.get(iface_name)
                is_up = stats.isup if stats else False
                mtu = stats.mtu if stats else None
                speed = stats.speed if stats else None  # Speed in Mbps

                # Create display name
                display_name = NICDetector._get_display_name(iface_name)

                interface = NetworkInterface(
                    name=iface_name,
                    display_name=display_name,
                    mac_address=mac_address,
                    ip_addresses=ip_addresses,
                    is_up=is_up,
                    is_loopback=is_loopback,
                    mtu=mtu,
                    speed=speed,
                )

                interfaces.append(interface)

        except Exception as e:
            print(f"Error getting interfaces: {e}")

        return interfaces

    @staticmethod
    def _get_display_name(iface_name: str) -> str:
        """
        Get a user-friendly display name for the interface.

        Args:
            iface_name: System interface name

        Returns:
            User-friendly display name
        """
        # On Windows, interface names can be GUIDs or friendly names
        # On Linux/Mac, they're typically like eth0, en0, etc.

        if sys.platform == "win32":
            # Windows sometimes has long GUID-style names
            # Try to get a friendlier name
            try:
                import winreg

                # This path contains network adapter info
                reg_path = r"SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}"

                # Try to find the friendly name
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                    # Iterate through subkeys to find matching interface
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            subkey_path = f"{reg_path}\\{subkey_name}\\Connection"
                            try:
                                with winreg.OpenKey(
                                    winreg.HKEY_LOCAL_MACHINE, subkey_path
                                ) as conn_key:
                                    name, _ = winreg.QueryValueEx(conn_key, "Name")
                                    if (
                                        iface_name in subkey_name
                                        or subkey_name in iface_name
                                    ):
                                        return name
                            except (FileNotFoundError, OSError):
                                pass
                            i += 1
                        except OSError:
                            break
            except Exception:
                pass

        return iface_name

    @staticmethod
    def get_capture_interfaces() -> List[NetworkInterface]:
        """
        Get interfaces suitable for packet capture.
        Filters out loopback and down interfaces.

        Returns:
            List of NetworkInterface objects suitable for capture
        """
        all_interfaces = NICDetector.get_all_interfaces()

        # Filter to only include interfaces that are up and not loopback
        capture_interfaces = [
            iface for iface in all_interfaces if iface.is_up and not iface.is_loopback
        ]

        return capture_interfaces

    @staticmethod
    def get_interface_by_name(name: str) -> Optional[NetworkInterface]:
        """
        Get a specific interface by name.

        Args:
            name: Interface name to look up

        Returns:
            NetworkInterface object or None if not found
        """
        interfaces = NICDetector.get_all_interfaces()
        for iface in interfaces:
            if iface.name == name:
                return iface
        return None

    @staticmethod
    def get_scapy_interface_name(iface: NetworkInterface) -> str:
        """
        Get the interface name as expected by Scapy.

        Args:
            iface: NetworkInterface object

        Returns:
            Interface name string for Scapy
        """
        if sys.platform == "win32":
            # On Windows, Scapy might need the NPF device name
            # Try to use the name directly first
            return iface.name
        else:
            # On Linux/Mac, use the interface name directly
            return iface.name


def get_available_interfaces() -> Dict[str, NetworkInterface]:
    """
    Convenience function to get a dictionary of available interfaces.

    Returns:
        Dictionary mapping interface names to NetworkInterface objects
    """
    detector = NICDetector()
    interfaces = detector.get_capture_interfaces()
    return {iface.name: iface for iface in interfaces}


if __name__ == "__main__":
    # Test the module
    print("Available Network Interfaces:")
    print("-" * 50)

    detector = NICDetector()
    interfaces = detector.get_all_interfaces()

    for iface in interfaces:
        status = "UP" if iface.is_up else "DOWN"
        loopback = " (Loopback)" if iface.is_loopback else ""
        print(f"\n{iface.display_name}{loopback}")
        print(f"  System Name: {iface.name}")
        print(f"  Status: {status}")
        print(f"  MAC: {iface.mac_address}")
        print(
            f"  IPs: {', '.join(iface.ip_addresses) if iface.ip_addresses else 'None'}"
        )
        print(f"  MTU: {iface.mtu}")
        print(f"  Speed: {iface.get_speed_display()}")
