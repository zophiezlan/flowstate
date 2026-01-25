"""Tests for button handler module"""

import unittest
from unittest.mock import patch, MagicMock
import time
import sys

# Mock RPi.GPIO before importing button_handler
mock_gpio = MagicMock()
mock_gpio.BCM = 11
mock_gpio.IN = 1
mock_gpio.PUD_UP = 22
mock_gpio.LOW = 0
mock_gpio.HIGH = 1
sys.modules["RPi"] = MagicMock()
sys.modules["RPi.GPIO"] = mock_gpio

from tap_station.button_handler import ButtonHandler  # noqa: E402


class TestButtonHandler(unittest.TestCase):
    """Test ButtonHandler class"""

    @patch("tap_station.button_handler.subprocess")
    def test_button_handler_disabled(self, mock_subprocess):
        """Test button handler when disabled"""
        handler = ButtonHandler(enabled=False)

        self.assertFalse(handler.enabled)
        self.assertIsNone(handler.monitor_thread)

        # Cleanup should not raise error
        handler.cleanup()

    @patch("tap_station.button_handler.subprocess")
    def test_button_handler_initialization(self, mock_subprocess):
        """Test button handler initialization"""
        handler = ButtonHandler(enabled=True, gpio_pin=26, hold_time=3.0)

        self.assertTrue(handler.enabled)
        self.assertEqual(handler.gpio_pin, 26)
        self.assertEqual(handler.hold_time, 3.0)

        # Should start monitoring thread
        self.assertIsNotNone(handler.monitor_thread)
        self.assertTrue(handler.running)

        # Cleanup
        handler.cleanup()

    @patch("tap_station.button_handler.subprocess")
    def test_shutdown_callback(self, mock_subprocess):
        """Test shutdown callback is executed"""
        callback_called = []

        def test_callback():
            callback_called.append(True)

        handler = ButtonHandler(
            enabled=True, gpio_pin=26, hold_time=10.0, shutdown_callback=test_callback
        )

        # Stop the monitoring thread before testing _trigger_shutdown directly
        # This prevents race conditions with the monitoring thread
        handler.stop()

        # Trigger shutdown directly
        handler._trigger_shutdown()

        # Check callback was called
        self.assertTrue(callback_called)

        # Check shutdown command was executed
        mock_subprocess.run.assert_called_once()
        call_args = mock_subprocess.run.call_args[0][0]
        self.assertEqual(call_args[0], "sudo")
        self.assertEqual(call_args[1], "shutdown")

        # Cleanup
        handler.cleanup()

    @patch("tap_station.button_handler.subprocess")
    @patch("tap_station.button_handler.time")
    def test_button_press_short_release(self, mock_time, mock_subprocess):
        """Test short button press (released before hold time)"""
        # Mock time.time() to simulate button hold
        time_values = [0, 0, 0.5, 0.5, 1.0]  # Button pressed then released at 0.5s
        mock_time.time.side_effect = time_values
        mock_time.sleep = time.sleep  # Use real sleep

        # Mock button input - pressed then released
        mock_gpio.input.side_effect = [
            mock_gpio.LOW,  # Button pressed
            mock_gpio.LOW,  # Still pressed
            mock_gpio.HIGH,  # Released
            mock_gpio.HIGH,  # Still released
        ]

        handler = ButtonHandler(enabled=True, gpio_pin=26, hold_time=3.0)

        # Give monitoring thread time to detect press
        time.sleep(0.2)

        # Stop monitoring
        handler.stop()

        # Shutdown should NOT be triggered (button released too soon)
        mock_subprocess.run.assert_not_called()

    @patch("tap_station.button_handler.subprocess")
    def test_stop_and_cleanup(self, mock_subprocess):
        """Test stop and cleanup methods"""
        handler = ButtonHandler(enabled=True, gpio_pin=26)

        # Should be running
        self.assertTrue(handler.running)

        # Stop
        handler.stop()
        self.assertFalse(handler.running)

        # Cleanup should not raise error
        handler.cleanup()

    @patch("tap_station.button_handler.subprocess")
    def test_custom_gpio_pin_and_hold_time(self, mock_subprocess):
        """Test custom GPIO pin and hold time"""
        handler = ButtonHandler(enabled=True, gpio_pin=23, hold_time=5.0)

        self.assertEqual(handler.gpio_pin, 23)
        self.assertEqual(handler.hold_time, 5.0)
        self.assertTrue(handler.enabled)
        self.assertTrue(handler.running)

        handler.cleanup()


if __name__ == "__main__":
    unittest.main()
