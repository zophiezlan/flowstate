"""Tests for peer monitor"""

import pytest
import time
from unittest.mock import Mock, patch
from tap_station.peer_monitor import PeerMonitor


class TestPeerMonitor:
    """Test peer health monitoring functionality"""

    def test_initialization(self):
        """Test peer monitor initialization"""
        monitor = PeerMonitor(
            peer_hostname="peer-station.local",
            peer_port=8080,
            check_interval=10,
            failure_threshold=3,
        )

        assert monitor.peer_hostname == "peer-station.local"
        assert monitor.peer_port == 8080
        assert monitor.check_interval == 10
        assert monitor.failure_threshold == 3
        assert monitor.peer_healthy is True  # Optimistic start
        assert monitor.consecutive_failures == 0
        assert monitor._running is False

    @patch("tap_station.peer_monitor.requests.get")
    def test_check_health_success(self, mock_get):
        """Test successful health check"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_get.return_value = mock_response

        monitor = PeerMonitor(peer_hostname="peer-station.local", check_interval=10)

        result = monitor.force_check()

        assert result is True
        assert monitor.peer_healthy is True
        assert monitor.consecutive_failures == 0
        mock_get.assert_called_once_with(
            "http://peer-station.local:8080/health", timeout=5
        )

    @patch("tap_station.peer_monitor.requests.get")
    def test_check_health_failure(self, mock_get):
        """Test failed health check"""
        mock_get.side_effect = Exception("Connection refused")

        monitor = PeerMonitor(
            peer_hostname="peer-station.local", check_interval=10, failure_threshold=2
        )

        # First failure - not yet declared down
        result = monitor.force_check()
        assert result is False
        assert monitor.peer_healthy is True  # Still considered healthy
        assert monitor.consecutive_failures == 1

        # Second failure - now declared down
        result = monitor.force_check()
        assert result is False
        assert monitor.peer_healthy is False  # Now declared unhealthy
        assert monitor.consecutive_failures == 2

    @patch("tap_station.peer_monitor.requests.get")
    def test_peer_down_callback(self, mock_get):
        """Test peer down callback is triggered"""
        mock_get.side_effect = Exception("Connection refused")

        callback_called = []

        def on_peer_down():
            callback_called.append(True)

        monitor = PeerMonitor(
            peer_hostname="peer-station.local",
            check_interval=10,
            failure_threshold=2,
            on_peer_down=on_peer_down,
        )

        # Trigger failures to reach threshold
        monitor.force_check()  # 1st failure
        assert len(callback_called) == 0  # Not yet called

        monitor.force_check()  # 2nd failure - should trigger callback

        # Give the callback thread a moment to execute
        time.sleep(0.1)

        assert len(callback_called) == 1

    @patch("tap_station.peer_monitor.requests.get")
    def test_peer_up_callback(self, mock_get):
        """Test peer recovery callback is triggered"""
        callback_called = []

        def on_peer_up():
            callback_called.append(True)

        monitor = PeerMonitor(
            peer_hostname="peer-station.local",
            check_interval=10,
            failure_threshold=1,
            on_peer_up=on_peer_up,
        )

        # First, make peer go down
        mock_get.side_effect = Exception("Connection refused")
        monitor.force_check()
        assert monitor.peer_healthy is False

        # Now peer recovers
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_get.side_effect = None
        mock_get.return_value = mock_response

        monitor.force_check()

        # Give the callback thread a moment to execute
        time.sleep(0.1)

        assert monitor.peer_healthy is True
        assert len(callback_called) == 1

    @patch("tap_station.peer_monitor.requests.get")
    def test_consecutive_failures_reset_on_success(self, mock_get):
        """Test that consecutive failures reset after success"""
        monitor = PeerMonitor(
            peer_hostname="peer-station.local", check_interval=10, failure_threshold=3
        )

        # Fail twice
        mock_get.side_effect = Exception("Connection refused")
        monitor.force_check()
        monitor.force_check()
        assert monitor.consecutive_failures == 2
        assert monitor.peer_healthy is True  # Still healthy (threshold is 3)

        # Then succeed
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_get.side_effect = None
        mock_get.return_value = mock_response

        monitor.force_check()

        assert monitor.consecutive_failures == 0  # Reset
        assert monitor.peer_healthy is True

    def test_get_status(self):
        """Test status reporting"""
        monitor = PeerMonitor(
            peer_hostname="peer-station.local", check_interval=10, failure_threshold=3
        )

        status = monitor.get_status()

        assert status["peer_hostname"] == "peer-station.local"
        assert status["peer_healthy"] is True
        assert status["consecutive_failures"] == 0
        assert "last_success_time" in status

    def test_start_stop_monitoring(self):
        """Test starting and stopping background monitoring"""
        monitor = PeerMonitor(
            peer_hostname="peer-station.local",
            check_interval=0.1,  # Very short interval for testing
        )

        # Start monitoring
        monitor.start()
        assert monitor._running is True
        assert monitor._monitor_thread is not None
        assert monitor._monitor_thread.is_alive()

        # Stop monitoring
        monitor.stop()
        time.sleep(0.2)  # Give thread time to stop
        assert monitor._running is False

    @patch("tap_station.peer_monitor.requests.get")
    def test_monitoring_loop_checks_health(self, mock_get):
        """Test that monitoring loop periodically checks health"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_get.return_value = mock_response

        monitor = PeerMonitor(
            peer_hostname="peer-station.local", check_interval=0.1  # Check every 100ms
        )

        monitor.start()
        time.sleep(0.3)  # Let it run for 300ms (should check 2-3 times)
        monitor.stop()

        # Should have called health check at least twice
        assert mock_get.call_count >= 2
