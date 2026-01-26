"""
Status LED Manager - Visual feedback for system states

Provides LED patterns for:
- WiFi status (connected/searching/AP mode)
- System status (ready/error/failover)
- Boot sequence
- Operation modes
"""

import logging
import threading
import time
from enum import Enum
from typing import Optional
from .gpio_manager import get_gpio_manager

logger = logging.getLogger(__name__)


class LEDPattern(Enum):
    """LED display patterns for different system states"""

    # System states
    OFF = "off"
    SOLID = "solid"
    SLOW_BLINK = "slow_blink"  # 1 Hz
    FAST_BLINK = "fast_blink"  # 4 Hz
    PULSE = "pulse"  # Breathing effect

    # Special patterns
    BOOTING = "booting"  # Rainbow/alternating
    READY = "ready"  # Green solid
    ERROR = "error"  # Red blink
    WARNING = "warning"  # Yellow (both LEDs)

    # WiFi patterns
    WIFI_CONNECTED = "wifi_connected"  # Green solid
    WIFI_CONNECTING = "wifi_connecting"  # Green blink
    WIFI_AP_MODE = "wifi_ap_mode"  # Blue blink (both LEDs alternating)
    WIFI_FAILED = "wifi_failed"  # Red fast blink

    # Failover patterns
    FAILOVER_MODE = "failover_mode"  # Yellow blink
    DUAL_MODE = "dual_mode"  # Alternating green/red


class StatusLEDManager:
    """
    Manages status LEDs for visual system feedback

    Uses existing feedback LEDs (green/red) but adds new patterns
    for system status indication.
    """

    def __init__(
        self,
        enabled: bool = True,
        gpio_green: int = 27,
        gpio_red: int = 22,
        gpio_blue: Optional[int] = None  # Optional third LED for WiFi
    ):
        """
        Initialize status LED manager

        Args:
            enabled: Enable LED status indicators
            gpio_green: GPIO pin for green LED
            gpio_red: GPIO pin for red LED
            gpio_blue: Optional GPIO pin for blue LED (WiFi indicator)
        """
        self.enabled = enabled
        self.gpio_green = gpio_green
        self.gpio_red = gpio_red
        self.gpio_blue = gpio_blue

        self._gpio = get_gpio_manager()
        self._pattern_thread: Optional[threading.Thread] = None
        self._running = False
        self._current_pattern: Optional[LEDPattern] = None

        if self.enabled:
            self._setup_leds()

    def _setup_leds(self):
        """Setup GPIO pins for status LEDs"""
        if not self._gpio.available:
            logger.warning("GPIO not available - status LEDs disabled")
            self.enabled = False
            return

        # Setup output pins
        success = True
        success &= self._gpio.setup_output(self.gpio_green, initial_state=False)
        success &= self._gpio.setup_output(self.gpio_red, initial_state=False)

        if self.gpio_blue:
            success &= self._gpio.setup_output(self.gpio_blue, initial_state=False)
            logger.info(f"Status LEDs enabled: Green={self.gpio_green}, Red={self.gpio_red}, Blue={self.gpio_blue}")
        else:
            logger.info(f"Status LEDs enabled: Green={self.gpio_green}, Red={self.gpio_red}")

        if not success:
            logger.warning("Failed to setup some status LEDs")
            self.enabled = False

    def set_pattern(self, pattern: LEDPattern):
        """
        Set the current LED pattern

        Args:
            pattern: LEDPattern to display
        """
        if not self.enabled:
            return

        # Stop current pattern
        self.stop_pattern()

        # Start new pattern
        self._current_pattern = pattern
        self._running = True
        self._pattern_thread = threading.Thread(
            target=self._run_pattern,
            args=(pattern,),
            daemon=True
        )
        self._pattern_thread.start()

        logger.debug(f"LED pattern set to: {pattern.value}")

    def stop_pattern(self):
        """Stop the current LED pattern"""
        if self._running:
            self._running = False
            if self._pattern_thread:
                self._pattern_thread.join(timeout=1)

        # Turn off all LEDs
        self._set_leds(False, False, False)

    def _set_leds(self, green: bool, red: bool, blue: bool = False):
        """
        Set LED states directly

        Args:
            green: Green LED state
            red: Red LED state
            blue: Blue LED state
        """
        if not self.enabled or not self._gpio.available:
            return

        self._gpio.output(self.gpio_green, green)
        self._gpio.output(self.gpio_red, red)

        if self.gpio_blue:
            self._gpio.output(self.gpio_blue, blue)

    def _run_pattern(self, pattern: LEDPattern):
        """
        Execute LED pattern in background thread

        Args:
            pattern: Pattern to run
        """
        try:
            if pattern == LEDPattern.OFF:
                self._set_leds(False, False, False)

            elif pattern == LEDPattern.SOLID:
                self._set_leds(True, False, False)

            elif pattern == LEDPattern.READY or pattern == LEDPattern.WIFI_CONNECTED:
                # Green solid
                self._set_leds(True, False, False)

            elif pattern == LEDPattern.ERROR or pattern == LEDPattern.WIFI_FAILED:
                # Red fast blink
                while self._running:
                    self._set_leds(False, True, False)
                    time.sleep(0.125)
                    self._set_leds(False, False, False)
                    time.sleep(0.125)

            elif pattern == LEDPattern.WARNING:
                # Yellow (both LEDs) slow blink
                while self._running:
                    self._set_leds(True, True, False)
                    time.sleep(0.5)
                    self._set_leds(False, False, False)
                    time.sleep(0.5)

            elif pattern == LEDPattern.WIFI_CONNECTING:
                # Green blink
                while self._running:
                    self._set_leds(True, False, False)
                    time.sleep(0.5)
                    self._set_leds(False, False, False)
                    time.sleep(0.5)

            elif pattern == LEDPattern.WIFI_AP_MODE:
                # Blue blink (or alternating if no blue LED)
                while self._running:
                    if self.gpio_blue:
                        self._set_leds(False, False, True)
                        time.sleep(0.5)
                        self._set_leds(False, False, False)
                        time.sleep(0.5)
                    else:
                        # Alternate green/red for "blue"
                        self._set_leds(True, False, False)
                        time.sleep(0.25)
                        self._set_leds(False, True, False)
                        time.sleep(0.25)

            elif pattern == LEDPattern.BOOTING:
                # Alternating pattern during boot
                for _ in range(6):
                    if not self._running:
                        break
                    self._set_leds(True, False, False)
                    time.sleep(0.2)
                    self._set_leds(False, True, False)
                    time.sleep(0.2)

            elif pattern == LEDPattern.FAILOVER_MODE or pattern == LEDPattern.DUAL_MODE:
                # Yellow blink (warning state)
                while self._running:
                    self._set_leds(True, True, False)  # Yellow
                    time.sleep(0.5)
                    self._set_leds(False, False, False)
                    time.sleep(0.5)

            elif pattern == LEDPattern.SLOW_BLINK:
                # Slow blink
                while self._running:
                    self._set_leds(True, False, False)
                    time.sleep(1)
                    self._set_leds(False, False, False)
                    time.sleep(1)

            elif pattern == LEDPattern.FAST_BLINK:
                # Fast blink
                while self._running:
                    self._set_leds(True, False, False)
                    time.sleep(0.25)
                    self._set_leds(False, False, False)
                    time.sleep(0.25)

        except Exception as e:
            logger.error(f"Error in LED pattern: {e}")

    def show_boot_sequence(self):
        """Show boot sequence pattern"""
        self.set_pattern(LEDPattern.BOOTING)
        time.sleep(1.5)
        self.stop_pattern()

    def show_ready(self):
        """Show ready pattern (green solid)"""
        self.set_pattern(LEDPattern.READY)

    def show_wifi_status(self, connected: bool, connecting: bool = False, ap_mode: bool = False):
        """
        Show WiFi status pattern

        Args:
            connected: True if connected to WiFi
            connecting: True if currently connecting
            ap_mode: True if in AP mode
        """
        if ap_mode:
            self.set_pattern(LEDPattern.WIFI_AP_MODE)
        elif connected:
            self.set_pattern(LEDPattern.WIFI_CONNECTED)
        elif connecting:
            self.set_pattern(LEDPattern.WIFI_CONNECTING)
        else:
            self.set_pattern(LEDPattern.WIFI_FAILED)

    def show_error(self):
        """Show error pattern (red blink)"""
        self.set_pattern(LEDPattern.ERROR)

    def show_failover(self):
        """Show failover mode pattern (yellow blink)"""
        self.set_pattern(LEDPattern.FAILOVER_MODE)

    def cleanup(self):
        """Cleanup and turn off LEDs"""
        self.stop_pattern()

        if self._gpio.available:
            pins = [self.gpio_green, self.gpio_red]
            if self.gpio_blue:
                pins.append(self.gpio_blue)
            self._gpio.cleanup(pins)

        logger.info("Status LEDs cleaned up")
