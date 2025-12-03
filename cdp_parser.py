"""
CDP (Cisco Discovery Protocol) Packet Parser
Handles parsing of CDP packets captured from the network.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
import struct


# CDP TLV Type codes
CDP_TLV_DEVICE_ID = 0x0001
CDP_TLV_ADDRESS = 0x0002
CDP_TLV_PORT_ID = 0x0003
CDP_TLV_CAPABILITIES = 0x0004
CDP_TLV_VERSION = 0x0005
CDP_TLV_PLATFORM = 0x0006
CDP_TLV_IP_PREFIX = 0x0007
CDP_TLV_VTP_MGMT_DOMAIN = 0x0009
CDP_TLV_NATIVE_VLAN = 0x000A
CDP_TLV_DUPLEX = 0x000B
CDP_TLV_VOICE_VLAN = 0x000E  # Appliance VLAN-ID (Voice VLAN)
CDP_TLV_TRUST_BITMAP = 0x0012
CDP_TLV_UNTRUSTED_COS = 0x0013
CDP_TLV_MGMT_ADDRESS = 0x0016
CDP_TLV_POWER_AVAILABLE = 0x001A

# Capability flags
CAPABILITY_ROUTER = 0x01
CAPABILITY_TRANS_BRIDGE = 0x02
CAPABILITY_SOURCE_BRIDGE = 0x04
CAPABILITY_SWITCH = 0x08
CAPABILITY_HOST = 0x10
CAPABILITY_IGMP = 0x20
CAPABILITY_REPEATER = 0x40


@dataclass
class CDPNeighbor:
    """Represents a CDP neighbor discovered on the network."""

    device_id: str = ""
    ip_addresses: list = field(default_factory=list)
    port_id: str = ""
    capabilities: list = field(default_factory=list)
    software_version: str = ""
    platform: str = ""
    native_vlan: Optional[int] = None
    voice_vlan: Optional[int] = None
    duplex: Optional[str] = None
    vtp_domain: str = ""
    mgmt_addresses: list = field(default_factory=list)

    # Metadata
    source_mac: str = ""
    local_interface: str = ""
    local_port_speed: str = ""  # Local port speed (e.g., "1G", "100M")
    last_seen: datetime = field(default_factory=datetime.now)
    ttl: int = 180
    protocol: str = "CDP"  # Protocol identifier

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for display."""
        return {
            "Protocol": self.protocol,
            "Device ID": self.device_id,
            "IP Addresses": (
                ", ".join(self.ip_addresses) if self.ip_addresses else "N/A"
            ),
            "Port ID": self.port_id,
            "Platform": self.platform,
            "Capabilities": (
                ", ".join(self.capabilities) if self.capabilities else "N/A"
            ),
            "Software Version": (
                self.software_version[:100] + "..."
                if len(self.software_version) > 100
                else self.software_version
            ),
            "Native VLAN": str(self.native_vlan) if self.native_vlan else "N/A",
            "Voice VLAN": str(self.voice_vlan) if self.voice_vlan else "N/A",
            "Duplex": self.duplex or "N/A",
            "VTP Domain": self.vtp_domain or "N/A",
            "Management Addresses": (
                ", ".join(self.mgmt_addresses) if self.mgmt_addresses else "N/A"
            ),
            "Source MAC": self.source_mac,
            "Local Interface": self.local_interface,
            "Local Port Speed": self.local_port_speed or "N/A",
            "Last Seen": self.last_seen.strftime("%Y-%m-%d %H:%M:%S"),
            "TTL": f"{self.ttl}s",
        }


class CDPParser:
    """Parser for CDP packets."""

    # CDP multicast MAC address
    CDP_MULTICAST_MAC = "01:00:0c:cc:cc:cc"

    @staticmethod
    def parse_capabilities(cap_value: int) -> list:
        """Parse capability flags into human-readable list."""
        capabilities = []
        if cap_value & CAPABILITY_ROUTER:
            capabilities.append("Router")
        if cap_value & CAPABILITY_TRANS_BRIDGE:
            capabilities.append("Trans-Bridge")
        if cap_value & CAPABILITY_SOURCE_BRIDGE:
            capabilities.append("Source-Bridge")
        if cap_value & CAPABILITY_SWITCH:
            capabilities.append("Switch")
        if cap_value & CAPABILITY_HOST:
            capabilities.append("Host")
        if cap_value & CAPABILITY_IGMP:
            capabilities.append("IGMP")
        if cap_value & CAPABILITY_REPEATER:
            capabilities.append("Repeater")
        return capabilities

    @staticmethod
    def parse_address(data: bytes) -> list:
        """Parse CDP address TLV."""
        addresses = []
        try:
            if len(data) < 4:
                return addresses

            num_addresses = struct.unpack(">I", data[:4])[0]
            offset = 4

            for _ in range(num_addresses):
                if offset + 2 > len(data):
                    break

                proto_type = data[offset]
                proto_len = data[offset + 1]
                offset += 2

                if offset + proto_len > len(data):
                    break

                # Skip protocol field
                offset += proto_len

                if offset + 2 > len(data):
                    break

                addr_len = struct.unpack(">H", data[offset : offset + 2])[0]
                offset += 2

                if offset + addr_len > len(data):
                    break

                # Parse IPv4 address
                if addr_len == 4:
                    addr_bytes = data[offset : offset + addr_len]
                    ip = ".".join(str(b) for b in addr_bytes)
                    addresses.append(ip)

                offset += addr_len

        except Exception:
            pass

        return addresses

    @classmethod
    def parse_cdp_packet(cls, packet) -> Optional[CDPNeighbor]:
        """
        Parse a CDP packet and return a CDPNeighbor object.
        Uses raw byte parsing for reliability across platforms.

        Args:
            packet: Scapy packet object

        Returns:
            CDPNeighbor object or None if parsing fails
        """
        try:
            # Get raw bytes from the packet
            raw_data = bytes(packet)

            # Get source MAC from the packet
            source_mac = ""
            if len(raw_data) >= 12:
                src_mac_bytes = raw_data[6:12]
                source_mac = ":".join(f"{b:02x}" for b in src_mac_bytes)

            # Use raw parsing which is more reliable
            neighbor = cls.parse_raw_cdp(raw_data, source_mac)
            return neighbor

        except Exception as e:
            print(f"Error parsing CDP packet: {e}")
            import traceback

            traceback.print_exc()
            return None

    @classmethod
    def parse_raw_cdp(
        cls, raw_data: bytes, source_mac: str = ""
    ) -> Optional[CDPNeighbor]:
        """
        Parse raw CDP packet data manually (fallback method).

        Args:
            raw_data: Raw packet bytes
            source_mac: Source MAC address

        Returns:
            CDPNeighbor object or None if parsing fails
        """
        try:
            neighbor = CDPNeighbor()
            neighbor.source_mac = source_mac
            neighbor.last_seen = datetime.now()

            # Find the CDP data start by looking for the CDP header pattern
            # CDP frame structure:
            # - Ethernet 802.3: Dest MAC (6) + Src MAC (6) + Length (2) = 14 bytes
            # - LLC: DSAP (1) + SSAP (1) + Control (1) = 3 bytes (0xAA, 0xAA, 0x03)
            # - SNAP: OUI (3) + Protocol ID (2) = 5 bytes (0x00, 0x00, 0x0C, 0x20, 0x00)
            # - CDP starts at offset 22

            # But some captures might have different header structures
            # Let's search for the LLC/SNAP + CDP signature

            cdp_start = -1

            # Method 1: Standard 802.3 + LLC/SNAP (offset 22)
            if len(raw_data) >= 26:
                # Check for LLC header (0xAA, 0xAA, 0x03) at offset 14
                if raw_data[14:17] == b"\xaa\xaa\x03":
                    # Check for Cisco OUI and CDP protocol
                    if (
                        raw_data[17:20] == b"\x00\x00\x0c"
                        and raw_data[20:22] == b"\x20\x00"
                    ):
                        cdp_start = 22

            # Method 2: Search for CDP version byte pattern
            if cdp_start == -1:
                # CDP version is typically 0x01 or 0x02, followed by TTL
                for i in range(14, min(50, len(raw_data) - 4)):
                    if (
                        raw_data[i] in (0x01, 0x02)
                        and raw_data[i + 1] > 0
                        and raw_data[i + 1] <= 255
                    ):
                        # Check if this looks like a valid TLV start after the 4-byte header
                        if i + 8 <= len(raw_data):
                            potential_tlv_type = struct.unpack(
                                ">H", raw_data[i + 4 : i + 6]
                            )[0]
                            potential_tlv_len = struct.unpack(
                                ">H", raw_data[i + 6 : i + 8]
                            )[0]
                            # Device ID TLV is usually first and type 0x0001
                            if (
                                potential_tlv_type == 0x0001
                                and 4 < potential_tlv_len < 256
                            ):
                                cdp_start = i
                                break

            if cdp_start == -1:
                print(
                    f"Could not find CDP header in packet. Raw data (first 60 bytes): {raw_data[:60].hex()}"
                )
                return None

            if len(raw_data) < cdp_start + 4:
                return None

            # CDP Header: version (1), TTL (1), checksum (2)
            cdp_version = raw_data[cdp_start]
            neighbor.ttl = raw_data[cdp_start + 1]
            offset = cdp_start + 4

            # Parse TLVs
            while offset + 4 <= len(raw_data):
                tlv_type = struct.unpack(">H", raw_data[offset : offset + 2])[0]
                tlv_len = struct.unpack(">H", raw_data[offset + 2 : offset + 4])[0]

                if tlv_len < 4 or offset + tlv_len > len(raw_data):
                    break

                # TLV data starts after the 4-byte header (type + length)
                tlv_data = raw_data[offset + 4 : offset + tlv_len]

                if tlv_type == CDP_TLV_DEVICE_ID:
                    neighbor.device_id = tlv_data.decode(
                        "utf-8", errors="ignore"
                    ).strip("\x00")
                elif tlv_type == CDP_TLV_ADDRESS:
                    neighbor.ip_addresses = cls.parse_address(tlv_data)
                elif tlv_type == CDP_TLV_PORT_ID:
                    neighbor.port_id = tlv_data.decode("utf-8", errors="ignore").strip(
                        "\x00"
                    )
                elif tlv_type == CDP_TLV_CAPABILITIES and len(tlv_data) >= 4:
                    cap_value = struct.unpack(">I", tlv_data[:4])[0]
                    neighbor.capabilities = cls.parse_capabilities(cap_value)
                elif tlv_type == CDP_TLV_VERSION:
                    neighbor.software_version = tlv_data.decode(
                        "utf-8", errors="ignore"
                    ).strip("\x00")
                elif tlv_type == CDP_TLV_PLATFORM:
                    neighbor.platform = tlv_data.decode("utf-8", errors="ignore").strip(
                        "\x00"
                    )
                elif tlv_type == CDP_TLV_NATIVE_VLAN and len(tlv_data) >= 2:
                    neighbor.native_vlan = struct.unpack(">H", tlv_data[:2])[0]
                elif tlv_type == CDP_TLV_VOICE_VLAN and len(tlv_data) >= 2:
                    # Voice VLAN has a 1-byte flag followed by 2-byte VLAN ID
                    if len(tlv_data) >= 3:
                        neighbor.voice_vlan = struct.unpack(">H", tlv_data[1:3])[0]
                    else:
                        neighbor.voice_vlan = struct.unpack(">H", tlv_data[:2])[0]
                elif tlv_type == CDP_TLV_DUPLEX and len(tlv_data) >= 1:
                    neighbor.duplex = "Full" if tlv_data[0] else "Half"
                elif tlv_type == CDP_TLV_VTP_MGMT_DOMAIN:
                    neighbor.vtp_domain = tlv_data.decode(
                        "utf-8", errors="ignore"
                    ).strip("\x00")
                elif tlv_type == CDP_TLV_MGMT_ADDRESS:
                    neighbor.mgmt_addresses = cls.parse_address(tlv_data)

                offset += tlv_len

            return neighbor

        except Exception as e:
            print(f"Error parsing raw CDP packet: {e}")
            import traceback

            traceback.print_exc()
            return None
