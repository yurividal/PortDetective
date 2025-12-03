"""
Unified Neighbor Module
Provides a common interface for CDP and LLDP neighbors.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Union

from cdp_parser import CDPNeighbor
from lldp_parser import LLDPNeighbor


@dataclass
class DiscoveryNeighbor:
    """
    Unified neighbor representation that can hold either CDP or LLDP data.
    Provides a common interface for the GUI.
    """

    # Common fields
    protocol: str = ""  # "CDP" or "LLDP"
    device_id: str = ""  # CDP: device_id, LLDP: system_name or chassis_id
    port_id: str = ""
    platform: str = ""  # CDP: platform, LLDP: part of system_description
    capabilities: List[str] = field(default_factory=list)
    ip_addresses: List[str] = field(default_factory=list)
    mgmt_addresses: List[str] = field(default_factory=list)
    software_version: str = ""  # CDP: software_version, LLDP: system_description

    # VLAN info
    native_vlan: Optional[int] = None  # CDP: native_vlan, LLDP: vlan_id
    voice_vlan: Optional[int] = None  # CDP only
    vlan_name: str = ""  # LLDP only

    # CDP specific
    duplex: Optional[str] = None
    vtp_domain: str = ""

    # LLDP specific
    port_description: str = ""

    # Metadata
    source_mac: str = ""
    local_interface: str = ""
    local_port_speed: str = ""
    last_seen: datetime = field(default_factory=datetime.now)
    ttl: int = 120

    # Original neighbor object
    _original: Optional[Union[CDPNeighbor, LLDPNeighbor]] = field(
        default=None, repr=False
    )

    @classmethod
    def from_cdp(cls, cdp: CDPNeighbor) -> "DiscoveryNeighbor":
        """Create a DiscoveryNeighbor from a CDPNeighbor."""
        return cls(
            protocol="CDP",
            device_id=cdp.device_id,
            port_id=cdp.port_id,
            platform=cdp.platform,
            capabilities=cdp.capabilities.copy() if cdp.capabilities else [],
            ip_addresses=cdp.ip_addresses.copy() if cdp.ip_addresses else [],
            mgmt_addresses=cdp.mgmt_addresses.copy() if cdp.mgmt_addresses else [],
            software_version=cdp.software_version,
            native_vlan=cdp.native_vlan,
            voice_vlan=cdp.voice_vlan,
            duplex=cdp.duplex,
            vtp_domain=cdp.vtp_domain,
            source_mac=cdp.source_mac,
            local_interface=cdp.local_interface,
            local_port_speed=cdp.local_port_speed,
            last_seen=cdp.last_seen,
            ttl=cdp.ttl,
            _original=cdp,
        )

    @classmethod
    def from_lldp(cls, lldp: LLDPNeighbor) -> "DiscoveryNeighbor":
        """Create a DiscoveryNeighbor from an LLDPNeighbor."""
        # Use system_name as device_id, fall back to chassis_id
        device_id = lldp.system_name if lldp.system_name else lldp.chassis_id

        # Extract platform from system_description if possible
        platform = ""
        if lldp.system_description:
            # Try to extract first line or meaningful part
            lines = lldp.system_description.split("\n")
            platform = lines[0][:50] if lines else ""

        return cls(
            protocol="LLDP",
            device_id=device_id,
            port_id=lldp.port_id,
            platform=platform,
            capabilities=(
                lldp.enabled_capabilities.copy()
                if lldp.enabled_capabilities
                else lldp.capabilities.copy()
            ),
            ip_addresses=[],  # LLDP doesn't have a direct equivalent
            mgmt_addresses=lldp.mgmt_addresses.copy() if lldp.mgmt_addresses else [],
            software_version=lldp.system_description,
            native_vlan=lldp.vlan_id,
            vlan_name=lldp.vlan_name,
            port_description=lldp.port_description,
            source_mac=lldp.source_mac,
            local_interface=lldp.local_interface,
            local_port_speed=lldp.local_port_speed,
            last_seen=lldp.last_seen,
            ttl=lldp.ttl,
            _original=lldp,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for display."""
        result = {
            "Protocol": self.protocol,
            "Device ID": self.device_id or "N/A",
            "Port ID": self.port_id or "N/A",
            "Platform": self.platform or "N/A",
            "Capabilities": (
                ", ".join(self.capabilities) if self.capabilities else "N/A"
            ),
        }

        # Add IP addresses (combine both fields)
        all_ips = list(set(self.ip_addresses + self.mgmt_addresses))
        result["IP Addresses"] = ", ".join(all_ips) if all_ips else "N/A"

        # Software version
        if self.software_version:
            version = (
                self.software_version[:150] + "..."
                if len(self.software_version) > 150
                else self.software_version
            )
            result["Software/Description"] = version
        else:
            result["Software/Description"] = "N/A"

        # VLAN info
        result["Native VLAN"] = str(self.native_vlan) if self.native_vlan else "N/A"

        if self.protocol == "CDP":
            result["Voice VLAN"] = str(self.voice_vlan) if self.voice_vlan else "N/A"
            result["Duplex"] = self.duplex or "N/A"
            result["VTP Domain"] = self.vtp_domain or "N/A"
        else:  # LLDP
            result["VLAN Name"] = self.vlan_name or "N/A"
            result["Port Description"] = self.port_description or "N/A"

        # Metadata
        result["Source MAC"] = self.source_mac
        result["Local Interface"] = self.local_interface
        result["Local Port Speed"] = self.local_port_speed or "N/A"
        result["Last Seen"] = self.last_seen.strftime("%Y-%m-%d %H:%M:%S")
        result["TTL"] = f"{self.ttl}s"

        return result

    def get_display_ip(self) -> str:
        """Get the best IP address for display."""
        if self.ip_addresses:
            return self.ip_addresses[0]
        if self.mgmt_addresses:
            return self.mgmt_addresses[0]
        return "N/A"
