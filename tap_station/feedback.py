"""Feedback system for buzzer and LED control"""

import time
import logging
import threading
from typing import List, Optional
from enum import Enum

from .gpio_manager import get_gpio_manager

logger = logging.getLogger(__name__)


class LEDState(Enum):
    """LED states for clear visual feedback"""

    OFF = "off"
    SOLID_GREEN = "solid_green"  # Ready/idle state
    SOLID_RED = "solid_red"  # Error/warning state
    SOLID_YELLOW = "solid_yellow"  # Warning/failover state
    FLASH_GREEN = "flash_green"  # Success event
    FLASH_RED = "flash_red"  # Error event
    FLASH_YELLOW = "flash_yellow"  # Warning event


class FeedbackController:
    """Control buzzer and LEDs for user feedback with improved patterns"""

    def __init__(
        self,
        buzzer_enabled: bool = False,
        led_enabled: bool = False,
        gpio_buzzer: int = 17,
        gpio_led_green: int = 27,
        gpio_led_red: int = 22,
        beep_success: Optional[List[float]] = None,
        beep_duplicate: Optional[List[float]] = None,
        beep_error: Optional[List[float]] = None,
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

        # Beep patterns - customizable
        self.beep_success = beep_success or [0.1]  # Short beep
        self.beep_duplicate = beep_duplicate or [0.1, 0.05, 0.1]  # Double beep
        self.beep_error = beep_error or [0.3]  # Long beep
        self.beep_button_press = [0.05]  # Very short beep for button
        self.beep_button_hold = [0.05, 0.05, 0.15]  # Confirmation pattern
        self.beep_warning = [0.15, 0.1, 0.15]  # Medium pattern

        # LED state management
        self._current_led_state = LEDState.OFF
        self._led_lock = threading.Lock()
        self._led_thread: Optional[threading.Thread] = None
        self._led_running = False

        self._gpio = get_gpio_manager()
        self._setup_pins()

        # Set initial ready state
        if self.led_enabled:
            self.set_ready_state()

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
                logger.warning(
                    f"Failed to setup buzzer on GPIO {self.gpio_buzzer} - buzzer disabled"
                )
                self.buzzer_enabled = False

        if self.led_enabled:
            green_ok = self._gpio.setup_output(self.gpio_led_green, initial_state=False)
            red_ok = self._gpio.setup_output(self.gpio_led_red, initial_state=False)
            if green_ok and red_ok:
                logger.info(
                    f"LEDs enabled on GPIO {self.gpio_led_green}, {self.gpio_led_red}"
                )
            else:
                logger.warning(
                    f"Failed to setup LEDs on GPIO {self.gpio_led_green}/{self.gpio_led_red} - LEDs disabled"
                )
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

    def _set_led_state_direct(self, green: bool, red: bool):
        """
        Set LED states directly (internal use)

        Args:
            green: Green LED state
            red: Red LED state
        """
        if not self.led_enabled or not self._gpio.available:
            return

        self._gpio.output(self.gpio_led_green, green)
        self._gpio.output(self.gpio_led_red, red)

    def _stop_led_pattern(self):
        """Stop any running LED pattern"""
        if self._led_running:
            self._led_running = False
            if self._led_thread:
                self._led_thread.join(timeout=1)

    def _run_led_pattern(self, state: LEDState):
        """
        Run LED pattern in background thread

        Args:
            state: LED state to display
        """
        try:
            if state == LEDState.OFF:
                self._set_led_state_direct(False, False)

            elif state == LEDState.SOLID_GREEN:
                self._set_led_state_direct(True, False)

            elif state == LEDState.SOLID_RED:
                self._set_led_state_direct(False, True)

            elif state == LEDState.SOLID_YELLOW:
                self._set_led_state_direct(True, True)

            elif state == LEDState.FLASH_GREEN:
                # Flash green 3 times, then return to solid green
                for _ in range(3):
                    if not self._led_running:
                        break
                    self._set_led_state_direct(False, False)
                    time.sleep(0.08)
                    self._set_led_state_direct(True, False)
                    time.sleep(0.08)
                # Return to solid green (ready state)
                self.set_led_state(LEDState.SOLID_GREEN)

            elif state == LEDState.FLASH_RED:
                # Flash red 3 times, then stay solid red for 1 second
                for _ in range(3):
                    if not self._led_running:
                        break
                    self._set_led_state_direct(False, False)
                    time.sleep(0.12)
                    self._set_led_state_direct(False, True)
                    time.sleep(0.12)
                # Solid red briefly to indicate error state
                self._set_led_state_direct(False, True)
                time.sleep(1.0)
                # Return to ready state
                self.set_led_state(LEDState.SOLID_GREEN)

            elif state == LEDState.FLASH_YELLOW:
                # Flash yellow (both) 2 times, then solid yellow briefly
                for _ in range(2):
                    if not self._led_running:
                        break
                    self._set_led_state_direct(False, False)
                    time.sleep(0.15)
                    self._set_led_state_direct(True, True)
                    time.sleep(0.15)
                # Solid yellow briefly
                self._set_led_state_direct(True, True)
                time.sleep(0.5)
                # Return to ready state
                self.set_led_state(LEDState.SOLID_GREEN)

        except Exception as e:
            logger.error(f"Error in LED pattern: {e}")
            # Ensure LEDs return to safe state
            self.set_led_state(LEDState.SOLID_GREEN)

    def set_led_state(self, state: LEDState):
        """
        Set LED state with proper thread management

        Args:
            state: LED state to set
        """
        if not self.led_enabled:
            return

        with self._led_lock:
            # Stop current pattern
            self._stop_led_pattern()

            # Update state
            self._current_led_state = state
            self._led_running = True

            # Start new pattern in thread
            self._led_thread = threading.Thread(
                target=self._run_led_pattern, args=(state,), daemon=True
            )
            self._led_thread.start()

        logger.debug(f"LED state set to: {state.value}")

    def set_ready_state(self):
        """Set LEDs to ready state (solid green)"""
        self.set_led_state(LEDState.SOLID_GREEN)
        logger.debug("Feedback: READY (solid green)")

    def set_error_state(self):
        """Set LEDs to error state (solid red)"""
        self.set_led_state(LEDState.SOLID_RED)
        logger.debug("Feedback: ERROR STATE (solid red)")

    def set_warning_state(self):
        """Set LEDs to warning state (solid yellow)"""
        self.set_led_state(LEDState.SOLID_YELLOW)
        logger.debug("Feedback: WARNING STATE (solid yellow)")

    def success(self):
        """Signal successful tap with flash and beep"""
        logger.debug("Feedback: SUCCESS")

        if self.buzzer_enabled:
            self._beep_pattern(self.beep_success)

        if self.led_enabled:
            self.set_led_state(LEDState.FLASH_GREEN)

    def duplicate(self):
        """Signal duplicate tap with warning flash and double beep"""
        logger.debug("Feedback: DUPLICATE")

        if self.buzzer_enabled:
            self._beep_pattern(self.beep_duplicate)

        if self.led_enabled:
            self.set_led_state(LEDState.FLASH_YELLOW)

    def error(self):
        """Signal error with red flash and long beep"""
        logger.debug("Feedback: ERROR")

        if self.buzzer_enabled:
            self._beep_pattern(self.beep_error)

        if self.led_enabled:
            self.set_led_state(LEDState.FLASH_RED)

    def button_press(self):
        """Signal button press with short beep"""
        logger.debug("Feedback: BUTTON PRESS")

        if self.buzzer_enabled:
            self._beep_pattern(self.beep_button_press)

    def button_hold_confirm(self):
        """Signal button hold confirmation with distinctive pattern"""
        logger.debug("Feedback: BUTTON HOLD CONFIRMED")

        if self.buzzer_enabled:
            self._beep_pattern(self.beep_button_hold)

        if self.led_enabled:
            # Flash red to indicate shutdown imminent
            self.set_led_state(LEDState.FLASH_RED)

    def warning(self):
        """Signal warning with yellow flash and beep"""
        logger.debug("Feedback: WARNING")

        if self.buzzer_enabled:
            self._beep_pattern(self.beep_warning)

        if self.led_enabled:
            self.set_led_state(LEDState.FLASH_YELLOW)

    def startup(self):
        """Signal system startup with ascending beep pattern"""
        logger.debug("Feedback: STARTUP")

        if self.buzzer_enabled:
            self._beep_pattern([0.05, 0.05, 0.05, 0.05, 0.1])

        if self.led_enabled:
            # Quick alternating pattern
            with self._led_lock:
                for _ in range(3):
                    self._set_led_state_direct(True, False)
                    time.sleep(0.1)
                    self._set_led_state_direct(False, True)
                    time.sleep(0.1)
                # End on solid green (ready)
                self.set_ready_state()

    def cleanup(self):
        """Cleanup GPIO on shutdown"""
        # Stop LED patterns
        self._stop_led_pattern()

        # Cleanup pins
        pins_to_cleanup = []
        if self.buzzer_enabled:
            pins_to_cleanup.append(self.gpio_buzzer)
        if self.led_enabled:
            pins_to_cleanup.extend([self.gpio_led_green, self.gpio_led_red])

        if pins_to_cleanup:
            self._gpio.cleanup(pins_to_cleanup)
            logger.info("Feedback GPIO cleaned up")
