"""
On-Site Manager - Orchestrates all on-site setup features

Coordinates:
- WiFi auto-connect and setup
- mDNS discovery
- Peer monitoring and failover
- Status LEDs
- Physical buttons

This is the high-level coordinator for smooth on-site operation.
"""

import logging
from typing import Optional

from .wifi_manager import WiFiManager
from .mdns_service import MDNSService, setup_mdns
from .peer_monitor import PeerMonitor
from .status_leds import StatusLEDManager
from .wifi_setup_button import WiFiSetupButton
from .failover_manager import FailoverManager

logger = logging.getLogger(__name__)


class OnSiteManager:
    """
    Central coordinator for on-site setup and operation

    Handles the complete flow:
    1. Boot sequence with LED feedback
    2. WiFi auto-connect (or AP mode if failed)
    3. mDNS service registration
    4. Peer health monitoring
    5. Automatic failover when needed
    6. Physical button handling
    """

    def __init__(
        self,
        device_id: str,
        stage: str,
        web_port: int = 8080,
        peer_hostname: Optional[str] = None,
        wifi_enabled: bool = True,
        failover_enabled: bool = True,
    ):
        """
        Initialize on-site manager

        Args:
            device_id: Station device ID
            stage: Primary stage for this station
            web_port: Web server port
            peer_hostname: Peer station hostname (for monitoring)
            wifi_enabled: Enable WiFi management
            failover_enabled: Enable automatic failover
        """
        self.device_id = device_id
        self.stage = stage
        self.web_port = web_port
        self.peer_hostname = peer_hostname

        # Components
        self.status_leds: Optional[StatusLEDManager] = None
        self.wifi_manager: Optional[WiFiManager] = None
        self.mdns_service: Optional[MDNSService] = None
        self.peer_monitor: Optional[PeerMonitor] = None
        self.failover_manager: Optional[FailoverManager] = None
        self.wifi_button: Optional[WiFiSetupButton] = None

        # Initialize components
        self._init_status_leds()

        if wifi_enabled:
            self._init_wifi_management()

        self._init_mdns()

        if peer_hostname and failover_enabled:
            self._init_peer_monitoring()

    def _init_status_leds(self):
        """Initialize status LED manager"""
        try:
            self.status_leds = StatusLEDManager(
                enabled=True, gpio_green=27, gpio_red=22, gpio_blue=None  # Optional
            )
            logger.info("Status LEDs initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize status LEDs: {e}")

    def _init_wifi_management(self):
        """Initialize WiFi manager and setup button"""
        try:
            self.wifi_manager = WiFiManager()

            # Initialize WiFi setup button
            self.wifi_button = WiFiSetupButton(
                enabled=True,
                gpio_pin=23,
                setup_callback=self._enter_wifi_setup,
                rescan_callback=self._rescan_wifi,
            )

            logger.info("WiFi management initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize WiFi management: {e}")

    def _init_mdns(self):
        """Initialize mDNS service"""
        try:
            self.mdns_service = setup_mdns(self.device_id, self.web_port)

            if self.mdns_service:
                logger.info(f"mDNS initialized: {self.mdns_service.get_access_url()}")
            else:
                logger.warning("mDNS setup failed (avahi not available)")

        except Exception as e:
            logger.warning(f"Failed to initialize mDNS: {e}")

    def _init_peer_monitoring(self):
        """Initialize peer monitoring and failover"""
        try:
            # Determine fallback stages based on current stage
            fallback_stages = self._get_fallback_stages(self.stage)

            # Initialize failover manager
            self.failover_manager = FailoverManager(
                primary_stage=self.stage,
                fallback_stages=fallback_stages,
                on_failover_enable=self._on_failover_enable,
                on_failover_disable=self._on_failover_disable,
            )

            # Initialize peer monitor
            self.peer_monitor = PeerMonitor(
                peer_hostname=self.peer_hostname,
                peer_port=self.web_port,
                check_interval=30,
                timeout=5,
                failure_threshold=2,
                on_peer_down=self._on_peer_down,
                on_peer_up=self._on_peer_up,
            )

            logger.info(f"Peer monitoring initialized for {self.peer_hostname}")

        except Exception as e:
            logger.warning(f"Failed to initialize peer monitoring: {e}")

    def _get_fallback_stages(self, primary_stage: str) -> list:
        """
        Determine fallback stages based on primary stage

        Args:
            primary_stage: Current stage

        Returns:
            List of fallback stages
        """
        # Simple 2-stage workflow: QUEUE_JOIN <-> EXIT
        if "QUEUE" in primary_stage.upper() or "JOIN" in primary_stage.upper():
            return ["EXIT"]
        elif "EXIT" in primary_stage.upper() or "LEAVE" in primary_stage.upper():
            return ["QUEUE_JOIN"]

        # 4-stage workflow fallbacks
        elif "SERVICE_START" in primary_stage.upper():
            return ["SUBSTANCE_RETURNED"]
        elif "SUBSTANCE_RETURNED" in primary_stage.upper():
            return ["SERVICE_START"]

        # Default: no fallback
        return []

    def startup(self):
        """
        Execute startup sequence

        Returns:
            True if startup successful
        """
        logger.info("=" * 60)
        logger.info("ON-SITE MANAGER STARTING")
        logger.info("=" * 60)

        # Show boot sequence
        if self.status_leds:
            self.status_leds.show_boot_sequence()

        # Setup WiFi
        if self.wifi_manager:
            wifi_success = self._setup_wifi()

            if wifi_success:
                if self.status_leds:
                    self.status_leds.show_wifi_status(connected=True)
            else:
                logger.warning("WiFi setup failed or no connection")
                if self.status_leds:
                    self.status_leds.show_wifi_status(
                        connected=False,
                        ap_mode=(
                            self.wifi_manager.ap_mode_active
                            if self.wifi_manager
                            else False
                        ),
                    )

        # Start peer monitoring
        if self.peer_monitor:
            self.peer_monitor.start()

        # Show ready status
        if self.status_leds:
            self.status_leds.show_ready()

        logger.info("=" * 60)
        logger.info("ON-SITE MANAGER READY")
        logger.info(f"Device: {self.device_id}")
        logger.info(f"Stage: {self.stage}")

        if self.mdns_service:
            logger.info(f"Access: {self.mdns_service.get_access_url()}")

        if self.wifi_manager:
            ip = self.wifi_manager.get_ip_address()
            if ip:
                logger.info(f"IP: {ip}")

        logger.info("=" * 60)

        return True

    def _setup_wifi(self) -> bool:
        """
        Setup WiFi connection

        Returns:
            True if connected
        """
        if not self.wifi_manager:
            return False

        logger.info("Setting up WiFi...")

        if self.status_leds:
            self.status_leds.show_wifi_status(connected=False, connecting=True)

        # Try auto-connect
        connected = self.wifi_manager.auto_connect()

        if connected:
            network = self.wifi_manager.get_current_network()
            logger.info(f"✅ Connected to WiFi: {network}")
            return True
        else:
            logger.warning("⚠️  Could not connect to any WiFi network")
            logger.info("Press WiFi setup button to configure network")
            return False

    def _enter_wifi_setup(self):
        """Enter WiFi setup mode (triggered by button)"""
        logger.info("🔧 Entering WiFi setup mode...")

        if self.status_leds:
            self.status_leds.show_wifi_status(connected=False, ap_mode=True)

        if self.wifi_manager:
            # Generate AP password from device_id
            ap_ssid = f"TapStation-{self.device_id}"
            ap_password = "tapstation123"

            logger.info(f"Starting AP: {ap_ssid}")
            logger.info(f"Password: {ap_password}")

            success = self.wifi_manager.enable_ap_mode(ap_ssid, ap_password)

            if success:
                logger.info("📱 WiFi setup ready!")
                logger.info(f"1. Connect to: {ap_ssid}")
                logger.info(f"2. Password: {ap_password}")
                logger.info("3. Configure network via web portal")
            else:
                logger.error("Failed to enable AP mode")

    def _rescan_wifi(self):
        """Rescan and reconnect to WiFi (triggered by button hold)"""
        logger.info("🔍 Rescanning WiFi networks...")

        if self.status_leds:
            self.status_leds.show_wifi_status(connected=False, connecting=True)

        if self.wifi_manager:
            # Disable AP mode if active
            if self.wifi_manager.ap_mode_active:
                self.wifi_manager.disable_ap_mode()

            # Try to reconnect
            connected = self.wifi_manager.auto_connect(max_attempts=3)

            if connected:
                if self.status_leds:
                    self.status_leds.show_wifi_status(connected=True)
                logger.info("✅ WiFi reconnected")
            else:
                if self.status_leds:
                    self.status_leds.show_wifi_status(connected=False)
                logger.warning("⚠️  WiFi reconnect failed")

    def _on_peer_down(self):
        """Callback when peer station goes down"""
        logger.warning("⚠️  PEER STATION DOWN - Enabling failover mode")

        # Enable failover
        if self.failover_manager:
            self.failover_manager.enable_failover()

        # Update LED status
        if self.status_leds:
            self.status_leds.show_failover()

    def _on_peer_up(self):
        """Callback when peer station comes back up"""
        logger.info("✅ PEER STATION RECOVERED - Disabling failover mode")

        # Disable failover
        if self.failover_manager:
            self.failover_manager.disable_failover()

        # Restore normal LED status
        if self.status_leds:
            self.status_leds.show_ready()

    def _on_failover_enable(self):
        """Callback when failover mode is enabled"""
        logger.warning("🔄 FAILOVER MODE ACTIVE")

    def _on_failover_disable(self):
        """Callback when failover mode is disabled"""
        logger.info("✅ NORMAL MODE RESTORED")

    def shutdown(self):
        """Shutdown on-site manager"""
        logger.info("Shutting down on-site manager...")

        # Stop peer monitoring
        if self.peer_monitor:
            self.peer_monitor.stop()

        # Stop WiFi button
        if self.wifi_button:
            self.wifi_button.cleanup()

        # Cleanup status LEDs
        if self.status_leds:
            self.status_leds.cleanup()

        # Stop mDNS
        if self.mdns_service:
            self.mdns_service.stop()

        logger.info("On-site manager shutdown complete")

    def get_status(self) -> dict:
        """
        Get comprehensive on-site manager status

        Returns:
            Status dictionary
        """
        status = {
            "device_id": self.device_id,
            "stage": self.stage,
            "wifi": None,
            "peer": None,
            "failover": None,
            "mdns": None,
        }

        if self.wifi_manager:
            status["wifi"] = {
                "connected": self.wifi_manager.is_connected(),
                "network": self.wifi_manager.get_current_network(),
                "ip_address": self.wifi_manager.get_ip_address(),
                "ap_mode": self.wifi_manager.ap_mode_active,
            }

        if self.peer_monitor:
            status["peer"] = self.peer_monitor.get_status()

        if self.failover_manager:
            status["failover"] = self.failover_manager.get_status()

        if self.mdns_service:
            status["mdns"] = {
                "hostname": self.mdns_service.hostname,
                "url": self.mdns_service.get_access_url(),
            }

        return status
