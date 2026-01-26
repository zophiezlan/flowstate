"""Tests for status LED manager"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from tap_station.status_leds import StatusLEDManager, LEDPattern


class TestStatusLEDManager:
    """Test status LED functionality"""

    @patch("tap_station.status_leds.get_gpio_manager")
    def test_initialization_disabled(self, mock_gpio):
        """Test LED manager when disabled"""
        mock_gpio_inst = MagicMock()
        mock_gpio.return_value = mock_gpio_inst

        led_mgr = StatusLEDManager(enabled=False)

        assert led_mgr.enabled is False
        # GPIO should be initialized but not configured when disabled
        assert mock_gpio_inst.setup_output.call_count == 0

    @patch("tap_station.status_leds.get_gpio_manager")
    def test_initialization_enabled(self, mock_gpio):
        """Test LED manager initialization"""
        mock_gpio_inst = MagicMock()
        mock_gpio_inst.available = True
        mock_gpio_inst.setup_output.return_value = True
        mock_gpio.return_value = mock_gpio_inst

        led_mgr = StatusLEDManager(enabled=True, gpio_green=27, gpio_red=22)

        assert led_mgr.enabled is True
        assert led_mgr.gpio_green == 27
        assert led_mgr.gpio_red == 22

        # Should have set up both LED pins
        assert mock_gpio_inst.setup_output.call_count == 2

    @patch("tap_station.status_leds.get_gpio_manager")
    def test_gpio_not_available(self, mock_gpio):
        """Test LED manager when GPIO not available"""
        mock_gpio_inst = MagicMock()
        mock_gpio_inst.available = False
        mock_gpio.return_value = mock_gpio_inst

        led_mgr = StatusLEDManager(enabled=True)

        # Should be disabled when GPIO not available
        assert led_mgr.enabled is False

    @patch("tap_station.status_leds.get_gpio_manager")
    def test_set_pattern_when_disabled(self, mock_gpio):
        """Test that set_pattern does nothing when disabled"""
        led_mgr = StatusLEDManager(enabled=False)

        # Should not raise error, just return
        led_mgr.set_pattern(LEDPattern.READY)

        assert led_mgr._current_pattern is None
        assert led_mgr._pattern_thread is None

    @patch("tap_station.status_leds.get_gpio_manager")
    def test_set_pattern(self, mock_gpio):
        """Test setting LED pattern"""
        mock_gpio_inst = MagicMock()
        mock_gpio_inst.available = True
        mock_gpio_inst.setup_output.return_value = True
        mock_gpio.return_value = mock_gpio_inst

        led_mgr = StatusLEDManager(enabled=True)

        # Set a pattern
        led_mgr.set_pattern(LEDPattern.SLOW_BLINK)

        # Give thread a moment to start
        time.sleep(0.05)

        assert led_mgr._current_pattern == LEDPattern.SLOW_BLINK
        assert led_mgr._running is True
        assert led_mgr._pattern_thread is not None
        # Thread should be alive (or have just finished if pattern was very short)
        # Just check that it was created

        # Cleanup
        led_mgr.stop_pattern()

    @patch("tap_station.status_leds.get_gpio_manager")
    def test_stop_pattern(self, mock_gpio):
        """Test stopping LED pattern"""
        mock_gpio_inst = MagicMock()
        mock_gpio_inst.available = True
        mock_gpio_inst.setup_output.return_value = True
        mock_gpio.return_value = mock_gpio_inst

        led_mgr = StatusLEDManager(enabled=True)

        # Start a pattern
        led_mgr.set_pattern(LEDPattern.SLOW_BLINK)
        assert led_mgr._running is True

        # Stop it
        led_mgr.stop_pattern()

        assert led_mgr._running is False
        # Give thread time to stop
        time.sleep(0.1)

    @patch("tap_station.status_leds.get_gpio_manager")
    def test_pattern_switching(self, mock_gpio):
        """Test switching between patterns"""
        mock_gpio_inst = MagicMock()
        mock_gpio_inst.available = True
        mock_gpio_inst.setup_output.return_value = True
        mock_gpio.return_value = mock_gpio_inst

        led_mgr = StatusLEDManager(enabled=True)

        # Set first pattern
        led_mgr.set_pattern(LEDPattern.READY)
        time.sleep(0.05)
        assert led_mgr._current_pattern == LEDPattern.READY

        # Switch to different pattern
        led_mgr.set_pattern(LEDPattern.ERROR)
        time.sleep(0.05)
        assert led_mgr._current_pattern == LEDPattern.ERROR

        # Cleanup
        led_mgr.stop_pattern()

    @patch("tap_station.status_leds.get_gpio_manager")
    def test_cleanup(self, mock_gpio):
        """Test cleanup releases resources"""
        mock_gpio_inst = MagicMock()
        mock_gpio_inst.available = True
        mock_gpio_inst.setup_output.return_value = True
        mock_gpio_inst.cleanup.return_value = None
        mock_gpio.return_value = mock_gpio_inst

        led_mgr = StatusLEDManager(enabled=True)
        led_mgr.set_pattern(LEDPattern.READY)

        # Cleanup
        led_mgr.cleanup()

        assert led_mgr._running is False
        # GPIO cleanup should be called
        mock_gpio_inst.cleanup.assert_called_once()

    @patch("tap_station.status_leds.get_gpio_manager")
    def test_thread_safety_pattern_switching(self, mock_gpio):
        """Test that pattern switching is thread-safe (no race conditions)"""
        mock_gpio_inst = MagicMock()
        mock_gpio_inst.available = True
        mock_gpio_inst.setup_output.return_value = True
        mock_gpio.return_value = mock_gpio_inst

        led_mgr = StatusLEDManager(enabled=True)

        # Rapidly switch patterns - should handle without error
        for i in range(5):
            led_mgr.set_pattern(
                LEDPattern.SLOW_BLINK if i % 2 == 0 else LEDPattern.FAST_BLINK
            )
            time.sleep(0.01)

        # Should still have a running pattern
        assert led_mgr._running is True

        # Cleanup
        led_mgr.stop_pattern()
