"""
GPIO Manager - Centralized GPIO management for Raspberry Pi

This module provides a unified interface for GPIO operations, eliminating
duplicate setup code across modules and providing consistent error handling.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GPIOManager:
    """
    Centralized GPIO management with graceful fallback for non-Pi environments.

    This class handles:
    - BCM pin mode setup
    - Pin configuration (input/output)
    - Pull-up/pull-down resistors
    - Graceful degradation when GPIO is unavailable
    """

    _instance: Optional["GPIOManager"] = None
    _GPIO = None
    _initialized: bool = False
    _configured_pins: Dict[int, str] = {}  # pin -> mode (IN/OUT)

    def __new__(cls) -> "GPIOManager":
        """Singleton pattern - only one GPIO manager instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize GPIO manager (only runs once due to singleton)."""
        if not GPIOManager._initialized:
            self._setup_gpio()
            GPIOManager._initialized = True

    def _setup_gpio(self) -> None:
        """Initialize GPIO library if available."""
        try:
            import RPi.GPIO as GPIO

            GPIOManager._GPIO = GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            logger.info("GPIO initialized in BCM mode")

        except ImportError:
            logger.warning(
                "RPi.GPIO not installed - GPIO operations will be disabled"
            )
            GPIOManager._GPIO = None

        except RuntimeError as e:
            logger.warning("GPIO not available (not on Raspberry Pi?): %s", e)
            GPIOManager._GPIO = None

    @property
    def available(self) -> bool:
        """Check if GPIO is available."""
        return GPIOManager._GPIO is not None

    @property
    def GPIO(self):
        """Get the GPIO module (for direct access when needed)."""
        return GPIOManager._GPIO

    def setup_output(self, pin: int, initial_state: bool = False) -> bool:
        """
        Configure a pin as output.

        Args:
            pin: BCM pin number
            initial_state: Initial output state (False=LOW, True=HIGH)

        Returns:
            True if successful, False if GPIO unavailable
        """
        if not self.available:
            logger.debug(
                "GPIO unavailable, skipping output setup for pin %s", pin
            )
            return False

        try:
            initial = (
                GPIOManager._GPIO.HIGH
                if initial_state
                else GPIOManager._GPIO.LOW
            )
            GPIOManager._GPIO.setup(
                pin, GPIOManager._GPIO.OUT, initial=initial
            )
            GPIOManager._configured_pins[pin] = "OUT"
            logger.debug(
                "Configured GPIO %s as OUTPUT (initial: %s)", pin, 'HIGH' if initial_state else 'LOW'
            )
            return True

        except Exception as e:
            logger.error("Failed to setup GPIO %s as output: %s", pin, e)
            return False

    def setup_input(
        self, pin: int, pull_up: bool = False, pull_down: bool = False
    ) -> bool:
        """
        Configure a pin as input.

        Args:
            pin: BCM pin number
            pull_up: Enable internal pull-up resistor
            pull_down: Enable internal pull-down resistor

        Returns:
            True if successful, False if GPIO unavailable
        """
        if not self.available:
            logger.debug(
                "GPIO unavailable, skipping input setup for pin %s", pin
            )
            return False

        try:
            pud = GPIOManager._GPIO.PUD_OFF
            if pull_up:
                pud = GPIOManager._GPIO.PUD_UP
            elif pull_down:
                pud = GPIOManager._GPIO.PUD_DOWN

            GPIOManager._GPIO.setup(
                pin, GPIOManager._GPIO.IN, pull_up_down=pud
            )
            GPIOManager._configured_pins[pin] = "IN"
            logger.debug(
                "Configured GPIO %s as INPUT (pull_up=%s, pull_down=%s)", pin, pull_up, pull_down
            )
            return True

        except Exception as e:
            logger.error("Failed to setup GPIO %s as input: %s", pin, e)
            return False

    def output(self, pin: int, state: bool) -> bool:
        """
        Set output pin state.

        Args:
            pin: BCM pin number
            state: Output state (False=LOW, True=HIGH)

        Returns:
            True if successful, False if GPIO unavailable or error
        """
        if not self.available:
            return False

        try:
            value = GPIOManager._GPIO.HIGH if state else GPIOManager._GPIO.LOW
            GPIOManager._GPIO.output(pin, value)
            return True

        except Exception as e:
            logger.error("Failed to set GPIO %s output: %s", pin, e)
            return False

    def input(self, pin: int) -> Optional[bool]:
        """
        Read input pin state.

        Args:
            pin: BCM pin number

        Returns:
            True if HIGH, False if LOW, None if GPIO unavailable or error
        """
        if not self.available:
            return None

        try:
            value = GPIOManager._GPIO.input(pin)
            return value == GPIOManager._GPIO.HIGH

        except Exception as e:
            logger.error("Failed to read GPIO %s input: %s", pin, e)
            return None

    def is_low(self, pin: int) -> bool:
        """
        Check if input pin is LOW.

        Args:
            pin: BCM pin number

        Returns:
            True if LOW, False otherwise (including unavailable)
        """
        result = self.input(pin)
        return result is False  # Explicitly False, not None

    def is_high(self, pin: int) -> bool:
        """
        Check if input pin is HIGH.

        Args:
            pin: BCM pin number

        Returns:
            True if HIGH, False otherwise (including unavailable)
        """
        result = self.input(pin)
        return result is True

    def cleanup(self, pins: Optional[List[int]] = None) -> None:
        """
        Cleanup GPIO pins.

        Args:
            pins: List of pins to cleanup, or None for all configured pins
        """
        if not self.available:
            return

        try:
            if pins:
                for pin in pins:
                    GPIOManager._GPIO.cleanup(pin)
                    GPIOManager._configured_pins.pop(pin, None)
                logger.info("Cleaned up GPIO pins: %s", pins)
            else:
                GPIOManager._GPIO.cleanup()
                GPIOManager._configured_pins.clear()
                logger.info("Cleaned up all GPIO pins")

        except Exception as e:
            logger.warning("Error during GPIO cleanup: %s", e)

    def get_configured_pins(self) -> Dict[int, str]:
        """Get dictionary of configured pins and their modes."""
        return dict(GPIOManager._configured_pins)


# Global instance for convenience
_gpio_manager: Optional[GPIOManager] = None


def get_gpio_manager() -> GPIOManager:
    """
    Get the global GPIO manager instance.

    Returns:
        GPIOManager singleton instance
    """
    global _gpio_manager
    if _gpio_manager is None:
        _gpio_manager = GPIOManager()
    return _gpio_manager
