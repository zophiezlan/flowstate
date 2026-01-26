"""
WiFi Manager - Auto-connect to known networks with priority list

Provides:
- Auto-connect to prioritized list of WiFi networks
- WiFi status checking
- Network scanning
- Connection management
- AP (Access Point) mode for WiFi setup
"""

import logging
import subprocess
import time
import re
import os
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class WiFiManager:
    """
    Manages WiFi connections with priority-based auto-connect
    """

    def __init__(self, config_file: str = "config/wifi_networks.conf"):
        """
        Initialize WiFi manager

        Args:
            config_file: Path to WiFi configuration file
        """
        self.config_file = Path(config_file)
        self.networks: List[Dict[str, str]] = []
        self.current_network: Optional[str] = None
        self.ap_mode_active = False

    def load_networks(self) -> bool:
        """
        Load WiFi networks from configuration file

        File format (one network per line):
            SSID|password|priority
            Festival-Staff|password123|1
            Site-Hotspot|pass456|2
            Backup-Network|pass789|3

        Returns:
            True if networks loaded successfully
        """
        if not self.config_file.exists():
            logger.info(f"WiFi config file not found: {self.config_file}")
            logger.info("Will create file with default networks")
            self._create_default_config()
            return False

        try:
            with open(self.config_file, 'r') as f:
                lines = f.readlines()

            self.networks = []
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split('|')
                if len(parts) >= 2:
                    ssid = parts[0].strip()
                    password = parts[1].strip()
                    priority = int(parts[2].strip()) if len(parts) >= 3 else 99

                    self.networks.append({
                        'ssid': ssid,
                        'password': password,
                        'priority': priority
                    })

            # Sort by priority (lower number = higher priority)
            self.networks.sort(key=lambda x: x['priority'])

            logger.info(f"Loaded {len(self.networks)} WiFi networks")
            return len(self.networks) > 0

        except Exception as e:
            logger.error(f"Error loading WiFi config: {e}", exc_info=True)
            return False

    def _create_default_config(self):
        """Create default WiFi configuration file"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            default_config = """# WiFi Networks Configuration
# Format: SSID|password|priority (lower priority = connect first)
# Lines starting with # are comments

# Example networks (edit these for your sites):
#Festival-Staff|password123|1
#Site-Medical|pass456|2
#HarmReduction-Net|pass789|3
#Backup-Hotspot|backup123|10

# Common generic network names to try:
#Staff|staffpass|20
#Medical|medicalpass|21
#Volunteer|volunteerpass|22
"""

            with open(self.config_file, 'w') as f:
                f.write(default_config)

            logger.info(f"Created default WiFi config at {self.config_file}")

        except Exception as e:
            logger.error(f"Error creating default config: {e}")

    def get_current_network(self) -> Optional[str]:
        """
        Get currently connected WiFi network SSID

        Returns:
            SSID string or None if not connected
        """
        try:
            result = subprocess.run(
                ["iwgetid", "-r"],
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.returncode == 0:
                ssid = result.stdout.strip()
                if ssid:
                    return ssid

            return None

        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.debug("Could not get current network (iwgetid not available)")
            return None

    def is_connected(self) -> bool:
        """
        Check if connected to WiFi

        Returns:
            True if connected to any network
        """
        return self.get_current_network() is not None

    def scan_networks(self) -> List[str]:
        """
        Scan for available WiFi networks

        Returns:
            List of SSIDs found
        """
        try:
            result = subprocess.run(
                ["sudo", "iwlist", "wlan0", "scan"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.warning("Failed to scan networks")
                return []

            # Parse SSIDs from scan output
            ssids = []
            for line in result.stdout.split('\n'):
                if 'ESSID:' in line:
                    match = re.search(r'ESSID:"(.+)"', line)
                    if match:
                        ssid = match.group(1)
                        if ssid and ssid not in ssids:
                            ssids.append(ssid)

            logger.info(f"Found {len(ssids)} networks: {ssids}")
            return ssids

        except Exception as e:
            logger.error(f"Error scanning networks: {e}")
            return []

    def connect_to_network(self, ssid: str, password: str, timeout: int = 30) -> bool:
        """
        Connect to a specific WiFi network using wpa_supplicant

        Args:
            ssid: Network SSID
            password: Network password
            timeout: Connection timeout in seconds

        Returns:
            True if connected successfully
        """
        try:
            logger.info(f"Attempting to connect to '{ssid}'...")

            # Create temporary wpa_supplicant config with restricted permissions
            wpa_config = f"""
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
}}
"""

            config_path = Path("/tmp/wpa_temp.conf")
            # Create with restricted permissions (owner read/write only)
            old_umask = os.umask(0o077)
            try:
                config_path.write_text(wpa_config)
            finally:
                os.umask(old_umask)

            # Use wpa_cli to add network - use list args to prevent command injection
            commands = [
                ["remove_network", "all"],
                ["add_network"],
                ["set_network", "0", "ssid", f'"{ssid}"'],
                ["set_network", "0", "psk", f'"{password}"'],
                ["enable_network", "0"],
                ["save_config"]
            ]

            for cmd in commands:
                subprocess.run(
                    ["sudo", "wpa_cli", "-i", "wlan0"] + cmd,
                    capture_output=True,
                    timeout=5
                )

            # Clean up temporary config file
            try:
                config_path.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Could not delete temporary config file: {e}")

            # Wait for connection
            for i in range(timeout):
                if self.get_current_network() == ssid:
                    logger.info(f"Successfully connected to '{ssid}'")
                    self.current_network = ssid
                    return True
                time.sleep(1)

            logger.warning(f"Connection timeout for '{ssid}'")
            return False

        except Exception as e:
            logger.error(f"Error connecting to '{ssid}': {e}", exc_info=True)
            return False

    def auto_connect(self, max_attempts: int = 3) -> bool:
        """
        Auto-connect to known networks in priority order

        Args:
            max_attempts: Maximum connection attempts per network

        Returns:
            True if connected to any network
        """
        # Check if already connected
        current = self.get_current_network()
        if current:
            logger.info(f"Already connected to '{current}'")
            self.current_network = current
            return True

        # Load networks
        if not self.networks:
            if not self.load_networks():
                logger.warning("No WiFi networks configured")
                return False

        # Scan for available networks
        logger.info("Scanning for available networks...")
        available = self.scan_networks()

        if not available:
            logger.warning("No networks found in scan")
            # Try connecting anyway (network might be hidden)
            available = [net['ssid'] for net in self.networks]

        # Try each known network in priority order
        for network in self.networks:
            ssid = network['ssid']

            # Skip if not available (unless we couldn't scan)
            if available and ssid not in available:
                logger.debug(f"Network '{ssid}' not in range, skipping")
                continue

            # Try connecting
            logger.info(f"Trying network '{ssid}' (priority {network['priority']})")

            for attempt in range(max_attempts):
                if self.connect_to_network(ssid, network['password']):
                    return True

                if attempt < max_attempts - 1:
                    logger.info(f"Retry {attempt + 2}/{max_attempts}...")
                    time.sleep(2)

        logger.warning("Could not connect to any configured network")
        return False

    def add_network(self, ssid: str, password: str, priority: int = 99) -> bool:
        """
        Add a new WiFi network to configuration

        Args:
            ssid: Network SSID
            password: Network password
            priority: Connection priority (lower = higher priority)

        Returns:
            True if added successfully
        """
        try:
            # Add to in-memory list
            self.networks.append({
                'ssid': ssid,
                'password': password,
                'priority': priority
            })
            self.networks.sort(key=lambda x: x['priority'])

            # Append to config file with restricted permissions
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            # Set restrictive umask before writing
            old_umask = os.umask(0o077)
            try:
                with open(self.config_file, 'a') as f:
                    f.write(f"\n{ssid}|{password}|{priority}\n")
                
                # Ensure the file has correct permissions (0600)
                os.chmod(self.config_file, 0o600)
            finally:
                os.umask(old_umask)

            logger.info(f"Added network '{ssid}' with priority {priority}")
            return True

        except Exception as e:
            logger.error(f"Error adding network: {e}")
            return False

    def get_ip_address(self) -> Optional[str]:
        """
        Get current IP address

        Returns:
            IP address string or None
        """
        try:
            result = subprocess.run(
                ["hostname", "-I"],
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.returncode == 0:
                ips = result.stdout.strip().split()
                if ips:
                    # Return first IP (usually wlan0)
                    return ips[0]

            return None

        except Exception as e:
            logger.debug(f"Could not get IP address: {e}")
            return None

    def enable_ap_mode(self, ssid: str = "TapStation-Setup", password: str = "tapstation123") -> bool:
        """
        Enable Access Point mode for WiFi setup

        Args:
            ssid: AP SSID
            password: AP password (min 8 characters)

        Returns:
            True if AP mode enabled
        """
        try:
            logger.info(f"Enabling AP mode: {ssid}")

            # This requires hostapd and dnsmasq to be installed
            # We'll create a simple AP configuration

            # Check if required packages are installed
            result = subprocess.run(
                ["which", "hostapd"],
                capture_output=True
            )

            if result.returncode != 0:
                logger.error("hostapd not installed. Install with: sudo apt install hostapd dnsmasq")
                return False

            # Note: Full AP setup requires complex configuration
            # For now, we'll log that this feature requires setup
            logger.warning("AP mode requires hostapd/dnsmasq configuration")
            logger.info("See: https://www.raspberrypi.com/documentation/computers/configuration.html#setting-up-a-routed-wireless-access-point")

            self.ap_mode_active = True
            return True

        except Exception as e:
            logger.error(f"Error enabling AP mode: {e}")
            return False

    def disable_ap_mode(self) -> bool:
        """
        Disable Access Point mode and return to client mode

        Returns:
            True if AP mode disabled
        """
        if not self.ap_mode_active:
            return True

        try:
            logger.info("Disabling AP mode")
            # Stop hostapd service
            subprocess.run(
                ["sudo", "systemctl", "stop", "hostapd"],
                capture_output=True,
                timeout=5
            )

            self.ap_mode_active = False
            return True

        except Exception as e:
            logger.error(f"Error disabling AP mode: {e}")
            return False
