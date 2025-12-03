"""
LLDP (Link Layer Discovery Protocol) Packet Parser
Handles parsing of LLDP packets captured from the network.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
import struct


# LLDP TLV Types
LLDP_TLV_END = 0
LLDP_TLV_CHASSIS_ID = 1
LLDP_TLV_PORT_ID = 2
LLDP_TLV_TTL = 3
LLDP_TLV_PORT_DESCRIPTION = 4
LLDP_TLV_SYSTEM_NAME = 5
LLDP_TLV_SYSTEM_DESCRIPTION = 6
LLDP_TLV_SYSTEM_CAPABILITIES = 7
LLDP_TLV_MANAGEMENT_ADDRESS = 8
LLDP_TLV_ORGANIZATIONALLY_SPECIFIC = 127

# Chassis ID subtypes
CHASSIS_ID_SUBTYPE_CHASSIS_COMPONENT = 1
CHASSIS_ID_SUBTYPE_INTERFACE_ALIAS = 2
CHASSIS_ID_SUBTYPE_PORT_COMPONENT = 3
CHASSIS_ID_SUBTYPE_MAC_ADDRESS = 4
CHASSIS_ID_SUBTYPE_NETWORK_ADDRESS = 5
CHASSIS_ID_SUBTYPE_INTERFACE_NAME = 6
CHASSIS_ID_SUBTYPE_LOCAL = 7

# Port ID subtypes
PORT_ID_SUBTYPE_INTERFACE_ALIAS = 1
PORT_ID_SUBTYPE_PORT_COMPONENT = 2
PORT_ID_SUBTYPE_MAC_ADDRESS = 3
PORT_ID_SUBTYPE_NETWORK_ADDRESS = 4
PORT_ID_SUBTYPE_INTERFACE_NAME = 5
PORT_ID_SUBTYPE_AGENT_CIRCUIT_ID = 6
PORT_ID_SUBTYPE_LOCAL = 7

# System Capabilities
CAPABILITY_OTHER = 0x0001
CAPABILITY_REPEATER = 0x0002
CAPABILITY_BRIDGE = 0x0004
CAPABILITY_WLAN_AP = 0x0008
CAPABILITY_ROUTER = 0x0010
CAPABILITY_TELEPHONE = 0x0020
CAPABILITY_DOCSIS = 0x0040
CAPABILITY_STATION = 0x0080
CAPABILITY_CVLAN = 0x0100
CAPABILITY_SVLAN = 0x0200
CAPABILITY_TPMR = 0x0400

# IEEE 802.1 OUI for VLAN TLVs
IEEE_802_1_OUI = b"\x00\x80\xc2"
IEEE_802_1_SUBTYPE_PORT_VLAN_ID = 1
IEEE_802_1_SUBTYPE_VLAN_NAME = 3

# IEEE 802.3 OUI for MAC/PHY TLVs
IEEE_802_3_OUI = b"\x00\x12\x0f"
IEEE_802_3_SUBTYPE_MAC_PHY = 1


@dataclass
class LLDPNeighbor:
    """Represents an LLDP neighbor discovered on the network."""

    chassis_id: str = ""
    port_id: str = ""
    port_description: str = ""
    system_name: str = ""
    system_description: str = ""
    capabilities: List[str] = field(default_factory=list)
    enabled_capabilities: List[str] = field(default_factory=list)
    mgmt_addresses: List[str] = field(default_factory=list)
    vlan_id: Optional[int] = None
    vlan_name: str = ""

    # Metadata
    source_mac: str = ""
    local_interface: str = ""
    local_port_speed: str = ""
    last_seen: datetime = field(default_factory=datetime.now)
    ttl: int = 120
    protocol: str = "LLDP"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for display."""
        return {
            "Protocol": self.protocol,
            "System Name": self.system_name or "N/A",
            "Chassis ID": self.chassis_id,
            "Port ID": self.port_id,
            "Port Description": self.port_description or "N/A",
            "System Description": (
                (
                    self.system_description[:100] + "..."
                    if len(self.system_description) > 100
                    else self.system_description
                )
                if self.system_description
                else "N/A"
            ),
            "Capabilities": (
                ", ".join(self.capabilities) if self.capabilities else "N/A"
            ),
            "Enabled Capabilities": (
                ", ".join(self.enabled_capabilities)
                if self.enabled_capabilities
                else "N/A"
            ),
            "Management Addresses": (
                ", ".join(self.mgmt_addresses) if self.mgmt_addresses else "N/A"
            ),
            "VLAN ID": str(self.vlan_id) if self.vlan_id else "N/A",
            "VLAN Name": self.vlan_name or "N/A",
            "Source MAC": self.source_mac,
            "Local Interface": self.local_interface,
            "Local Port Speed": self.local_port_speed or "N/A",
            "Last Seen": self.last_seen.strftime("%Y-%m-%d %H:%M:%S"),
            "TTL": f"{self.ttl}s",
        }


class LLDPParser:
    """Parser for LLDP packets."""

    # LLDP multicast MAC addresses
    LLDP_MULTICAST_MACS = [
        "01:80:c2:00:00:0e",  # Nearest bridge
        "01:80:c2:00:00:03",  # Nearest non-TPMR bridge
        "01:80:c2:00:00:00",  # Nearest customer bridge
    ]

    # LLDP EtherType
    LLDP_ETHERTYPE = 0x88CC

    @staticmethod
    def parse_capabilities(cap_value: int) -> List[str]:
        """Parse capability flags into human-readable list."""
        capabilities = []
        if cap_value & CAPABILITY_OTHER:
            capabilities.append("Other")
        if cap_value & CAPABILITY_REPEATER:
            capabilities.append("Repeater")
        if cap_value & CAPABILITY_BRIDGE:
            capabilities.append("Bridge")
        if cap_value & CAPABILITY_WLAN_AP:
            capabilities.append("WLAN AP")
        if cap_value & CAPABILITY_ROUTER:
            capabilities.append("Router")
        if cap_value & CAPABILITY_TELEPHONE:
            capabilities.append("Telephone")
        if cap_value & CAPABILITY_DOCSIS:
            capabilities.append("DOCSIS")
        if cap_value & CAPABILITY_STATION:
            capabilities.append("Station")
        if cap_value & CAPABILITY_CVLAN:
            capabilities.append("C-VLAN")
        if cap_value & CAPABILITY_SVLAN:
            capabilities.append("S-VLAN")
        if cap_value & CAPABILITY_TPMR:
            capabilities.append("TPMR")
        return capabilities

    @staticmethod
    def parse_chassis_id(subtype: int, data: bytes) -> str:
        """Parse chassis ID based on subtype."""
        if subtype == CHASSIS_ID_SUBTYPE_MAC_ADDRESS and len(data) == 6:
            return ":".join(f"{b:02x}" for b in data)
        elif subtype == CHASSIS_ID_SUBTYPE_NETWORK_ADDRESS and len(data) >= 2:
            addr_family = data[0]
            if addr_family == 1 and len(data) >= 5:  # IPv4
                return ".".join(str(b) for b in data[1:5])
            elif addr_family == 2 and len(data) >= 17:  # IPv6
                return ":".join(
                    f"{data[i]:02x}{data[i+1]:02x}" for i in range(1, 17, 2)
                )

        # Try to decode as string
        try:
            return data.decode("utf-8", errors="ignore").strip("\x00")
        except:
            return data.hex()

    @staticmethod
    def parse_port_id(subtype: int, data: bytes) -> str:
        """Parse port ID based on subtype."""
        if subtype == PORT_ID_SUBTYPE_MAC_ADDRESS and len(data) == 6:
            return ":".join(f"{b:02x}" for b in data)
        elif subtype == PORT_ID_SUBTYPE_NETWORK_ADDRESS and len(data) >= 2:
            addr_family = data[0]
            if addr_family == 1 and len(data) >= 5:  # IPv4
                return ".".join(str(b) for b in data[1:5])

        # Try to decode as string
        try:
            return data.decode("utf-8", errors="ignore").strip("\x00")
        except:
            return data.hex()

    @staticmethod
    def parse_mgmt_address(data: bytes) -> Optional[str]:
        """Parse management address TLV."""
        try:
            if len(data) < 3:
                return None

            addr_len = data[0]
            if addr_len < 2 or len(data) < addr_len + 1:
                return None

            addr_subtype = data[1]
            addr_data = data[2 : addr_len + 1]

            if addr_subtype == 1 and len(addr_data) >= 4:  # IPv4
                return ".".join(str(b) for b in addr_data[:4])
            elif addr_subtype == 2 and len(addr_data) >= 16:  # IPv6
                return ":".join(
                    f"{addr_data[i]:02x}{addr_data[i+1]:02x}" for i in range(0, 16, 2)
                )

        except Exception:
            pass
        return None

    @classmethod
    def parse_lldp_packet(cls, packet) -> Optional[LLDPNeighbor]:
        """
        Parse an LLDP packet and return an LLDPNeighbor object.
        Uses raw byte parsing for reliability across platforms.

        Args:
            packet: Scapy packet object

        Returns:
            LLDPNeighbor object or None if parsing fails
        """
        try:
            raw_data = bytes(packet)

            # Get source MAC from the packet
            source_mac = ""
            if len(raw_data) >= 12:
                src_mac_bytes = raw_data[6:12]
                source_mac = ":".join(f"{b:02x}" for b in src_mac_bytes)

            return cls.parse_raw_lldp(raw_data, source_mac)

        except Exception as e:
            print(f"Error parsing LLDP packet: {e}")
            import traceback

            traceback.print_exc()
            return None

    @classmethod
    def parse_raw_lldp(
        cls, raw_data: bytes, source_mac: str = ""
    ) -> Optional[LLDPNeighbor]:
        """
        Parse raw LLDP packet data.

        Args:
            raw_data: Raw packet bytes
            source_mac: Source MAC address

        Returns:
            LLDPNeighbor object or None if parsing fails
        """
        try:
            neighbor = LLDPNeighbor()
            neighbor.source_mac = source_mac
            neighbor.last_seen = datetime.now()
            neighbor.protocol = "LLDP"

            # Ethernet header is 14 bytes (dest MAC 6 + src MAC 6 + EtherType 2)
            # Check EtherType is LLDP (0x88CC)
            if len(raw_data) < 14:
                return None

            ethertype = struct.unpack(">H", raw_data[12:14])[0]
            if ethertype != cls.LLDP_ETHERTYPE:
                print(f"[DEBUG] Not an LLDP packet, EtherType: 0x{ethertype:04x}")
                return None

            # LLDP data starts after Ethernet header
            offset = 14

            # Parse TLVs
            while offset + 2 <= len(raw_data):
                # TLV header: 7 bits type + 9 bits length
                tlv_header = struct.unpack(">H", raw_data[offset : offset + 2])[0]
                tlv_type = (tlv_header >> 9) & 0x7F
                tlv_len = tlv_header & 0x01FF
                offset += 2

                if tlv_type == LLDP_TLV_END:
                    break

                if offset + tlv_len > len(raw_data):
                    break

                tlv_data = raw_data[offset : offset + tlv_len]

                if tlv_type == LLDP_TLV_CHASSIS_ID and tlv_len >= 2:
                    subtype = tlv_data[0]
                    neighbor.chassis_id = cls.parse_chassis_id(subtype, tlv_data[1:])

                elif tlv_type == LLDP_TLV_PORT_ID and tlv_len >= 2:
                    subtype = tlv_data[0]
                    neighbor.port_id = cls.parse_port_id(subtype, tlv_data[1:])

                elif tlv_type == LLDP_TLV_TTL and tlv_len >= 2:
                    neighbor.ttl = struct.unpack(">H", tlv_data[:2])[0]

                elif tlv_type == LLDP_TLV_PORT_DESCRIPTION:
                    neighbor.port_description = tlv_data.decode(
                        "utf-8", errors="ignore"
                    ).strip("\x00")

                elif tlv_type == LLDP_TLV_SYSTEM_NAME:
                    neighbor.system_name = tlv_data.decode(
                        "utf-8", errors="ignore"
                    ).strip("\x00")

                elif tlv_type == LLDP_TLV_SYSTEM_DESCRIPTION:
                    neighbor.system_description = tlv_data.decode(
                        "utf-8", errors="ignore"
                    ).strip("\x00")

                elif tlv_type == LLDP_TLV_SYSTEM_CAPABILITIES and tlv_len >= 4:
                    sys_cap = struct.unpack(">H", tlv_data[0:2])[0]
                    enabled_cap = struct.unpack(">H", tlv_data[2:4])[0]
                    neighbor.capabilities = cls.parse_capabilities(sys_cap)
                    neighbor.enabled_capabilities = cls.parse_capabilities(enabled_cap)

                elif tlv_type == LLDP_TLV_MANAGEMENT_ADDRESS and tlv_len >= 3:
                    addr = cls.parse_mgmt_address(tlv_data)
                    if addr:
                        neighbor.mgmt_addresses.append(addr)

                elif tlv_type == LLDP_TLV_ORGANIZATIONALLY_SPECIFIC and tlv_len >= 4:
                    oui = tlv_data[0:3]
                    subtype = tlv_data[3]
                    org_data = tlv_data[4:]

                    # IEEE 802.1 TLVs
                    if oui == IEEE_802_1_OUI:
                        if (
                            subtype == IEEE_802_1_SUBTYPE_PORT_VLAN_ID
                            and len(org_data) >= 2
                        ):
                            neighbor.vlan_id = struct.unpack(">H", org_data[0:2])[0]
                        elif (
                            subtype == IEEE_802_1_SUBTYPE_VLAN_NAME
                            and len(org_data) >= 3
                        ):
                            vlan_id = struct.unpack(">H", org_data[0:2])[0]
                            name_len = org_data[2]
                            if len(org_data) >= 3 + name_len:
                                neighbor.vlan_name = org_data[3 : 3 + name_len].decode(
                                    "utf-8", errors="ignore"
                                )
                            if not neighbor.vlan_id:
                                neighbor.vlan_id = vlan_id

                offset += tlv_len

            return neighbor

        except Exception as e:
            print(f"Error parsing raw LLDP packet: {e}")
            import traceback

            traceback.print_exc()
            return None
