"""
WiFi Setup Button Handler

Handles physical button press to enter WiFi setup mode with captive portal.
Press the button to enable AP mode for easy WiFi configuration.
"""

import logging
import threading
import time
from typing import Callable, Optional
from .gpio_manager import get_gpio_manager

logger = logging.getLogger(__name__)


class WiFiSetupButton:
    """
    Handles WiFi setup button with press detection

    Features:
    - Single press: Enter WiFi setup mode (AP mode)
    - Hold for 3s: Force WiFi rescan and auto-connect
    """

    def __init__(
        self,
        enabled: bool = True,
        gpio_pin: int = 23,
        hold_time: float = 3.0,
        setup_callback: Optional[Callable] = None,
        rescan_callback: Optional[Callable] = None,
    ):
        """
        Initialize WiFi setup button handler

        Args:
            enabled: Enable button monitoring
            gpio_pin: GPIO pin for button (BCM numbering)
            hold_time: Seconds to hold button for rescan (default: 3.0)
            setup_callback: Callback to enter WiFi setup mode
            rescan_callback: Callback to force WiFi rescan
        """
        self.enabled = enabled
        self.gpio_pin = gpio_pin
        self.hold_time = hold_time
        self.setup_callback = setup_callback
        self.rescan_callback = rescan_callback

        self._gpio = get_gpio_manager()
        self.monitor_thread = None
        self.running = False

        if self.enabled:
            self._setup_button()
            if self.enabled:  # Re-check in case setup failed
                self._start_monitoring()

    def _setup_button(self):
        """Setup GPIO pin for button with pull-up resistor"""
        if not self.enabled:
            return

        if not self._gpio.available:
            logger.warning("GPIO not available - WiFi setup button disabled")
            self.enabled = False
            return

        if self._gpio.setup_input(self.gpio_pin, pull_up=True):
            logger.info(f"WiFi setup button enabled on GPIO {self.gpio_pin}")
        else:
            logger.warning("Failed to setup WiFi button GPIO - button disabled")
            self.enabled = False

    def _start_monitoring(self):
        """Start background thread to monitor button"""
        if not self.enabled or not self._gpio.available:
            return

        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_button, daemon=True)
        self.monitor_thread.start()
        logger.info("WiFi setup button monitoring started")

    def _monitor_button(self):
        """Monitor button in background thread"""
        while self.running:
            try:
                # Check if button is pressed (LOW = pressed due to pull-up)
                if self._gpio.is_low(self.gpio_pin):
                    logger.info("WiFi setup button pressed...")

                    # Track how long button is held
                    press_start = time.time()
                    held_long_enough = False

                    # Wait while button is held
                    while self._gpio.is_low(self.gpio_pin) and self.running:
                        elapsed = time.time() - press_start

                        # Check if hold time reached
                        if elapsed >= self.hold_time and not held_long_enough:
                            logger.info(
                                f"Button held for {self.hold_time}s - triggering rescan"
                            )
                            held_long_enough = True
                            self._trigger_rescan()

                        time.sleep(0.1)

                    # Button released
                    elapsed = time.time() - press_start

                    if not held_long_enough:
                        # Short press: enter WiFi setup mode
                        if elapsed < self.hold_time:
                            logger.info("Button released - entering WiFi setup mode")
                            self._trigger_setup()

                # Poll every 100ms when button not pressed
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in WiFi button monitoring: {e}")
                time.sleep(1)

    def _trigger_setup(self):
        """Trigger WiFi setup mode (AP mode with captive portal)"""
        logger.info("WIFI SETUP MODE TRIGGERED")

        if self.setup_callback:
            try:
                self.setup_callback()
            except Exception as e:
                logger.error(f"Error in setup callback: {e}")
        else:
            logger.warning("No setup callback configured")

    def _trigger_rescan(self):
        """Trigger WiFi rescan and auto-connect"""
        logger.info("WIFI RESCAN TRIGGERED")

        if self.rescan_callback:
            try:
                self.rescan_callback()
            except Exception as e:
                logger.error(f"Error in rescan callback: {e}")
        else:
            logger.warning("No rescan callback configured")

    def stop(self):
        """Stop button monitoring"""
        if self.running:
            logger.info("Stopping WiFi button monitoring...")
            self.running = False

            if self.monitor_thread:
                self.monitor_thread.join(timeout=2)
                if self.monitor_thread.is_alive():
                    logger.warning("WiFi button thread did not stop within timeout")

    def cleanup(self):
        """Cleanup GPIO on shutdown"""
        self.stop()

        if self._gpio.available:
            self._gpio.cleanup([self.gpio_pin])
            logger.info("WiFi button GPIO cleaned up")
