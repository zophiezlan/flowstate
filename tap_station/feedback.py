"""Feedback system for buzzer and LED control"""

import time
import logging
from typing import List

from .gpio_manager import get_gpio_manager

logger = logging.getLogger(__name__)


class FeedbackController:
    """Control buzzer and LEDs for user feedback"""

    def __init__(
        self,
        buzzer_enabled: bool = False,
        led_enabled: bool = False,
        gpio_buzzer: int = 17,
        gpio_led_green: int = 27,
        gpio_led_red: int = 22,
        beep_success: List[float] = None,
        beep_duplicate: List[float] = None,
        beep_error: List[float] = None,
    ):
        """
        Initialize feedback controller

        Args:
            buzzer_enabled: Enable buzzer feedback
            led_enabled: Enable LED feedback
            gpio_buzzer: GPIO pin for buzzer
            gpio_led_green: GPIO pin for green LED
            gpio_led_red: GPIO pin for red LED
            beep_success: Success beep pattern (on/off times)
            beep_duplicate: Duplicate beep pattern
            beep_error: Error beep pattern
        """
        self.buzzer_enabled = buzzer_enabled
        self.led_enabled = led_enabled

        self.gpio_buzzer = gpio_buzzer
        self.gpio_led_green = gpio_led_green
        self.gpio_led_red = gpio_led_red

        self.beep_success = beep_success or [0.1]
        self.beep_duplicate = beep_duplicate or [0.1, 0.05, 0.1]
        self.beep_error = beep_error or [0.3]

        self._gpio = get_gpio_manager()
        self._setup_pins()

    def _setup_pins(self):
        """Setup GPIO pins for buzzer and LEDs"""
        if not (self.buzzer_enabled or self.led_enabled):
            logger.info("Feedback disabled (no buzzer or LED)")
            return

        if not self._gpio.available:
            logger.warning("GPIO not available - feedback disabled")
            self.buzzer_enabled = False
            self.led_enabled = False
            return

        if self.buzzer_enabled:
            if self._gpio.setup_output(self.gpio_buzzer, initial_state=False):
                logger.info(f"Buzzer enabled on GPIO {self.gpio_buzzer}")
            else:
                self.buzzer_enabled = False

        if self.led_enabled:
            green_ok = self._gpio.setup_output(self.gpio_led_green, initial_state=False)
            red_ok = self._gpio.setup_output(self.gpio_led_red, initial_state=False)
            if green_ok and red_ok:
                logger.info(
                    f"LEDs enabled on GPIO {self.gpio_led_green}, {self.gpio_led_red}"
                )
            else:
                self.led_enabled = False

    def _beep_pattern(self, pattern: List[float]):
        """
        Execute a beep pattern

        Args:
            pattern: List of on/off durations in seconds
        """
        if not self.buzzer_enabled or not self._gpio.available:
            return

        for i, duration in enumerate(pattern):
            # Even indices = on, odd indices = off
            state = i % 2 == 0
            self._gpio.output(self.gpio_buzzer, state)
            time.sleep(duration)

        # Ensure buzzer is off
        self._gpio.output(self.gpio_buzzer, False)

    def _flash_led(self, led_pin: int, duration: float = 0.1):
        """
        Flash an LED briefly

        Args:
            led_pin: GPIO pin number
            duration: Flash duration in seconds
        """
        if not self.led_enabled or not self._gpio.available:
            return

        self._gpio.output(led_pin, True)
        time.sleep(duration)
        self._gpio.output(led_pin, False)

    def success(self):
        """Signal successful tap"""
        logger.debug("Feedback: SUCCESS")

        if self.buzzer_enabled:
            self._beep_pattern(self.beep_success)

        if self.led_enabled:
            self._flash_led(self.gpio_led_green, 0.2)

    def duplicate(self):
        """Signal duplicate tap"""
        logger.debug("Feedback: DUPLICATE")

        if self.buzzer_enabled:
            self._beep_pattern(self.beep_duplicate)

        if self.led_enabled:
            # Flash red twice
            self._flash_led(self.gpio_led_red, 0.1)
            time.sleep(0.05)
            self._flash_led(self.gpio_led_red, 0.1)

    def error(self):
        """Signal error"""
        logger.debug("Feedback: ERROR")

        if self.buzzer_enabled:
            self._beep_pattern(self.beep_error)

        if self.led_enabled:
            self._flash_led(self.gpio_led_red, 0.3)

    def startup(self):
        """Signal system startup (quick double beep)"""
        logger.debug("Feedback: STARTUP")

        if self.buzzer_enabled:
            self._beep_pattern([0.05, 0.05, 0.05])

        if self.led_enabled:
            self._flash_led(self.gpio_led_green, 0.05)
            time.sleep(0.05)
            self._flash_led(self.gpio_led_green, 0.05)

    def cleanup(self):
        """Cleanup GPIO on shutdown"""
        pins_to_cleanup = []
        if self.buzzer_enabled:
            pins_to_cleanup.append(self.gpio_buzzer)
        if self.led_enabled:
            pins_to_cleanup.extend([self.gpio_led_green, self.gpio_led_red])

        if pins_to_cleanup:
            self._gpio.cleanup(pins_to_cleanup)
            logger.info("Feedback GPIO cleaned up")
