"""Shutdown button handler for safe system shutdown"""

import time
import logging
import threading
import subprocess

from .gpio_manager import get_gpio_manager

logger = logging.getLogger(__name__)


class ButtonHandler:
    """Handle shutdown button with press-and-hold detection"""

    def __init__(
        self,
        enabled: bool = False,
        gpio_pin: int = 26,
        hold_time: float = 3.0,
        shutdown_callback=None,
        shutdown_delay_minutes: int = 1,
        feedback_controller=None,
    ):
        """
        Initialize button handler

        Args:
            enabled: Enable button monitoring
            gpio_pin: GPIO pin for button (BCM numbering)
            hold_time: Seconds to hold button for shutdown (default: 3.0)
            shutdown_callback: Optional callback to execute before shutdown
            shutdown_delay_minutes: Minutes delay before shutdown (default: 1)
                                   Set to 0 for immediate shutdown
            feedback_controller: Optional FeedbackController for button feedback
        """
        self.enabled = enabled
        self.gpio_pin = gpio_pin
        self.hold_time = hold_time
        self.shutdown_callback = shutdown_callback
        self.shutdown_delay_minutes = shutdown_delay_minutes
        self.feedback = feedback_controller

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
            logger.warning("GPIO not available - button monitoring disabled")
            self.enabled = False
            return

        if self._gpio.setup_input(self.gpio_pin, pull_up=True):
            logger.info(
                f"Shutdown button enabled on GPIO {self.gpio_pin} "
                f"(hold for {self.hold_time}s)"
            )
        else:
            logger.warning("Failed to setup button GPIO - button monitoring disabled")
            self.enabled = False

    def _start_monitoring(self):
        """Start background thread to monitor button"""
        if not self.enabled or not self._gpio.available:
            return

        self.running = True
        # Use daemon thread - main service has signal handlers for proper shutdown
        self.monitor_thread = threading.Thread(target=self._monitor_button, daemon=True)
        self.monitor_thread.start()
        logger.info("Button monitoring started")

    def _monitor_button(self):
        """Monitor button in background thread"""
        while self.running:
            try:
                # Check if button is pressed (LOW = pressed due to pull-up)
                if self._gpio.is_low(self.gpio_pin):
                    logger.info("Shutdown button pressed, checking hold time...")

                    # Immediate feedback on button press
                    if self.feedback:
                        self.feedback.button_press()

                    # Track how long button is held
                    press_start = time.time()

                    # Wait while button is held
                    while self._gpio.is_low(self.gpio_pin) and self.running:
                        elapsed = time.time() - press_start

                        # Check if hold time reached
                        if elapsed >= self.hold_time:
                            logger.warning(
                                f"Shutdown button held for {self.hold_time}s - "
                                "initiating shutdown"
                            )

                            # Confirmation feedback
                            if self.feedback:
                                self.feedback.button_hold_confirm()

                            self._trigger_shutdown()
                            return  # Exit monitoring after shutdown triggered

                        time.sleep(0.1)

                    # Button released before hold time
                    elapsed = time.time() - press_start
                    if elapsed < self.hold_time:
                        logger.info(
                            f"Button released after {elapsed:.1f}s "
                            f"(need {self.hold_time}s to shutdown)"
                        )

                # Poll every 100ms when button not pressed
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in button monitoring: {e}")
                time.sleep(1)

    def _trigger_shutdown(self):
        """
        Execute shutdown sequence

        Security Note: This uses 'sudo shutdown' which requires passwordless sudo
        for the shutdown command. Configure in /etc/sudoers.d/tap-station:

            # Allow tap-station user to shutdown without password
            username ALL=(ALL) NOPASSWD: /sbin/shutdown

        Replace 'username' with your actual username (e.g., 'pi').
        """
        logger.warning("SHUTDOWN TRIGGERED BY BUTTON")

        # Call shutdown callback if provided (e.g., cleanup)
        if self.shutdown_callback:
            try:
                logger.info("Running shutdown callback...")
                self.shutdown_callback()
            except Exception as e:
                logger.error(f"Error in shutdown callback: {e}")

        # Trigger system shutdown
        try:
            logger.warning("Executing system shutdown command...")
            # This requires passwordless sudo for /sbin/shutdown

            # Validate shutdown delay
            if (
                not isinstance(self.shutdown_delay_minutes, int)
                or self.shutdown_delay_minutes < 0
            ):
                logger.error(
                    f"Invalid shutdown_delay_minutes: {self.shutdown_delay_minutes}. "
                    "Using default of 1 minute."
                )
                self.shutdown_delay_minutes = 1

            if self.shutdown_delay_minutes == 0:
                # Immediate shutdown
                shutdown_time = "now"
                delay_msg = "immediately"
            else:
                # Delayed shutdown for safety
                shutdown_time = f"+{self.shutdown_delay_minutes}"
                delay_msg = (
                    f"in {self.shutdown_delay_minutes} minute(s) "
                    "(cancel with: sudo shutdown -c)"
                )

            subprocess.run(
                [
                    "sudo",
                    "shutdown",
                    "-h",
                    shutdown_time,
                    "Shutdown triggered by button",
                ],
                check=True,
            )
            logger.warning(f"Shutdown scheduled {delay_msg}")
        except subprocess.CalledProcessError as e:
            logger.error(
                f"Failed to execute shutdown command: {e}. "
                "Ensure passwordless sudo is configured for shutdown."
            )
        except FileNotFoundError:
            logger.error("shutdown command not found (not on Linux?)")

    def stop(self):
        """Stop button monitoring"""
        if self.running:
            logger.info("Stopping button monitoring...")
            self.running = False

            if self.monitor_thread:
                # Wait up to 2 seconds for thread to finish
                # This is generous given the 0.1s polling interval
                self.monitor_thread.join(timeout=2)
                if self.monitor_thread.is_alive():
                    logger.warning(
                        "Button monitoring thread did not stop within timeout"
                    )

    def cleanup(self):
        """Cleanup GPIO on shutdown"""
        self.stop()

        if self._gpio.available:
            self._gpio.cleanup([self.gpio_pin])
            logger.info("Button GPIO cleaned up")
