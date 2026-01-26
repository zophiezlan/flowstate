"""
mDNS/Avahi service for auto-discovery of tap stations

Provides zero-configuration network discovery so stations can be accessed via:
- tapstation-queue.local
- tapstation-exit.local
- tapstation-<device_id>.local

No need to hunt for IP addresses!
"""

import logging
import subprocess
import socket
from typing import Optional

logger = logging.getLogger(__name__)


class MDNSService:
    """
    Manages mDNS/Avahi service registration for tap station discovery.

    This allows stations to be accessed via friendly hostnames like
    'tapstation-queue.local' instead of IP addresses.
    """

    def __init__(self, device_id: str, port: int = 8080):
        """
        Initialize mDNS service

        Args:
            device_id: Station device ID (e.g., "station1", "queue", "exit")
            port: Web server port (default: 8080)
        """
        self.device_id = device_id
        self.port = port
        self.hostname = self._generate_hostname()
        self.service_name = f"TapStation-{device_id}"
        self._avahi_available = self._check_avahi()

    def _generate_hostname(self) -> str:
        """
        Generate mDNS hostname from device ID

        Returns:
            Hostname (e.g., "tapstation-queue")
        """
        # Normalize device_id for hostname
        # Convert common patterns to friendly names
        device_lower = self.device_id.lower()

        if "queue" in device_lower or "join" in device_lower:
            return "tapstation-queue"
        elif "exit" in device_lower or "leave" in device_lower:
            return "tapstation-exit"
        elif "service" in device_lower or "start" in device_lower:
            return "tapstation-service"
        elif "return" in device_lower or "substance" in device_lower:
            return "tapstation-return"
        else:
            # Generic: tapstation-<device_id>
            safe_id = device_lower.replace("_", "-").replace(" ", "-")
            return f"tapstation-{safe_id}"

    def _check_avahi(self) -> bool:
        """
        Check if Avahi daemon is available

        Returns:
            True if avahi-daemon is running
        """
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "avahi-daemon"],
                capture_output=True,
                text=True,
                timeout=2
            )
            is_active = result.returncode == 0

            if is_active:
                logger.info("Avahi daemon is available")
            else:
                logger.warning("Avahi daemon is not running - mDNS will not work")
                logger.info("Install with: sudo apt install avahi-daemon")

            return is_active

        except (subprocess.TimeoutExpired, FileNotFoundError):
            logger.warning("Could not check avahi-daemon status")
            return False

    def start(self) -> bool:
        """
        Start mDNS service advertisement

        Returns:
            True if successful, False otherwise
        """
        if not self._avahi_available:
            logger.warning("Avahi not available, skipping mDNS registration")
            return False

        # Set system hostname if we have permission
        try:
            current_hostname = socket.gethostname()

            if current_hostname != self.hostname:
                logger.info(f"Attempting to set hostname to {self.hostname}")

                # Try to set hostname (requires root/sudo)
                try:
                    subprocess.run(
                        ["sudo", "hostnamectl", "set-hostname", self.hostname],
                        check=True,
                        timeout=5
                    )
                    logger.info(f"System hostname set to {self.hostname}")
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    logger.info(f"Could not set system hostname (OK if not root): {e}")
                    logger.info(f"Station will use existing hostname: {current_hostname}")
            else:
                logger.info(f"Hostname already set to {self.hostname}")

        except Exception as e:
            logger.warning(f"Error checking hostname: {e}")

        # Avahi will automatically advertise the hostname.local
        # We don't need to manually register with avahi-publish since
        # the system hostname + avahi-daemon handles it automatically

        logger.info(f"mDNS service ready:")
        logger.info(f"  Access via: http://{self.hostname}.local:{self.port}")
        logger.info(f"  Service name: {self.service_name}")

        return True

    def get_access_url(self) -> str:
        """
        Get the mDNS access URL for this station

        Returns:
            URL string (e.g., "http://tapstation-queue.local:8080")
        """
        return f"http://{self.hostname}.local:{self.port}"

    def stop(self):
        """Stop mDNS service (cleanup)"""
        # Nothing to clean up - avahi-daemon handles everything
        logger.info("mDNS service stopped")


def setup_mdns(device_id: str, port: int = 8080) -> Optional[MDNSService]:
    """
    Convenience function to setup mDNS service

    Args:
        device_id: Station device ID
        port: Web server port

    Returns:
        MDNSService instance if successful, None otherwise
    """
    try:
        mdns = MDNSService(device_id, port)
        if mdns.start():
            return mdns
        return None
    except Exception as e:
        logger.error(f"Failed to setup mDNS: {e}", exc_info=True)
        return None
