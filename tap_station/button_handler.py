"""Shutdown button handler for safe system shutdown"""

import time
import logging
import threading
import subprocess

logger = logging.getLogger(__name__)


class ButtonHandler:
    """Handle shutdown button with press-and-hold detection"""

    def __init__(
        self,
        enabled: bool = False,
        gpio_pin: int = 26,
        hold_time: float = 3.0,
        shutdown_callback=None,
    ):
        """
        Initialize button handler

        Args:
            enabled: Enable button monitoring
            gpio_pin: GPIO pin for button (BCM numbering)
            hold_time: Seconds to hold button for shutdown (default: 3.0)
            shutdown_callback: Optional callback to execute before shutdown
        """
        self.enabled = enabled
        self.gpio_pin = gpio_pin
        self.hold_time = hold_time
        self.shutdown_callback = shutdown_callback

        self.GPIO = None
        self.monitor_thread = None
        self.running = False

        if self.enabled:
            self._setup_gpio()
            self._start_monitoring()

    def _setup_gpio(self):
        """Setup GPIO pin for button with pull-up resistor"""
        if not self.enabled:
            return

        try:
            import RPi.GPIO as GPIO

            self.GPIO = GPIO

            # Use BCM pin numbering
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Setup button pin with internal pull-up
            # Button connects pin to GND when pressed
            GPIO.setup(self.gpio_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            logger.info(
                f"Shutdown button enabled on GPIO {self.gpio_pin} "
                f"(hold for {self.hold_time}s)"
            )

        except (ImportError, RuntimeError) as e:
            logger.warning(f"GPIO not available (not on Pi?): {e}")
            self.enabled = False

    def _start_monitoring(self):
        """Start background thread to monitor button"""
        if not self.enabled or not self.GPIO:
            return

        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_button, daemon=True
        )
        self.monitor_thread.start()
        logger.info("Button monitoring started")

    def _monitor_button(self):
        """Monitor button in background thread"""
        while self.running:
            try:
                # Check if button is pressed (LOW = pressed, HIGH = released)
                if self.GPIO.input(self.gpio_pin) == self.GPIO.LOW:
                    logger.info("Shutdown button pressed, checking hold time...")

                    # Track how long button is held
                    press_start = time.time()

                    # Wait while button is held
                    while (
                        self.GPIO.input(self.gpio_pin) == self.GPIO.LOW
                        and self.running
                    ):
                        elapsed = time.time() - press_start

                        # Check if hold time reached
                        if elapsed >= self.hold_time:
                            logger.warning(
                                f"Shutdown button held for {self.hold_time}s - "
                                "initiating shutdown"
                            )
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
        """Execute shutdown sequence"""
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
            # Use shutdown command with 1 minute delay for safety
            subprocess.run(
                ["sudo", "shutdown", "-h", "+1", "Shutdown triggered by button"],
                check=True,
            )
            logger.warning("Shutdown scheduled in 1 minute (cancel with: sudo shutdown -c)")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to execute shutdown command: {e}")
        except FileNotFoundError:
            logger.error("shutdown command not found (not on Linux?)")

    def stop(self):
        """Stop button monitoring"""
        if self.running:
            logger.info("Stopping button monitoring...")
            self.running = False

            if self.monitor_thread:
                self.monitor_thread.join(timeout=2)

    def cleanup(self):
        """Cleanup GPIO on shutdown"""
        self.stop()

        if self.GPIO:
            try:
                self.GPIO.cleanup(self.gpio_pin)
                logger.info("Button GPIO cleaned up")
            except Exception as e:
                logger.warning(f"Error cleaning up GPIO: {e}")
