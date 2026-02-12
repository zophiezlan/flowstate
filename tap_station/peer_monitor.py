"""
Peer Station Health Monitoring

Monitors peer station health and triggers failover when peer fails.
Enables automatic role switching for high reliability.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Callable, Dict, Optional

import requests

logger = logging.getLogger(__name__)


class PeerMonitor:
    """
    Monitors peer station health via HTTP health checks

    Features:
    - Periodic health checks (every 30s)
    - Configurable timeout and retry
    - Automatic failover detection
    - Peer recovery detection
    """

    def __init__(
        self,
        peer_hostname: str,
        peer_port: int = 8080,
        check_interval: int = 30,
        timeout: int = 5,
        failure_threshold: int = 2,
        on_peer_down: Optional[Callable] = None,
        on_peer_up: Optional[Callable] = None,
    ):
        """
        Initialize peer monitor

        Args:
            peer_hostname: Peer hostname or IP (e.g., "tapstation-exit.local")
            peer_port: Peer web server port
            check_interval: Seconds between health checks
            timeout: HTTP request timeout in seconds
            failure_threshold: Number of failures before declaring peer down
            on_peer_down: Callback when peer goes down
            on_peer_up: Callback when peer comes back up
        """
        self.peer_hostname = peer_hostname
        self.peer_port = peer_port
        self.check_interval = check_interval
        self.timeout = timeout
        self.failure_threshold = failure_threshold

        self.on_peer_down = on_peer_down
        self.on_peer_up = on_peer_up

        # State
        self.peer_healthy = True
        self.consecutive_failures = 0
        self.last_check_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None

        # Monitoring
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def peer_url(self) -> str:
        """Get peer health check URL"""
        return f"http://{self.peer_hostname}:{self.peer_port}/health"

    def start(self):
        """Start monitoring peer station"""
        if self._running:
            logger.warning("Peer monitor already running")
            return

        logger.info(
            "Starting peer monitor for %s:%s", self.peer_hostname, self.peer_port
        )

        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True
        )
        self._monitor_thread.start()

    def stop(self):
        """Stop monitoring peer station"""
        if not self._running:
            return

        logger.info("Stopping peer monitor")
        self._running = False

        if self._monitor_thread:
            self._monitor_thread.join(timeout=self.check_interval + 5)

    def _monitor_loop(self):
        """Main monitoring loop"""
        logger.info(
            "Peer monitoring started (check every %ss)", self.check_interval
        )

        while self._running:
            try:
                self._check_peer_health()
                time.sleep(self.check_interval)

            except Exception as e:
                logger.error("Error in peer monitor loop: %s", e, exc_info=True)
                time.sleep(5)

    def _check_peer_health(self) -> bool:
        """
        Check peer station health

        Returns:
            True if peer is healthy
        """
        self.last_check_time = datetime.now()

        try:
            # Try to reach peer health endpoint
            response = requests.get(self.peer_url, timeout=self.timeout)

            # Check if response is successful
            if response.status_code == 200:
                self._handle_success()
                return True
            else:
                logger.warning("Peer returned status %s", response.status_code)
                self._handle_failure()
                return False

        except requests.exceptions.Timeout:
            logger.warning("Peer health check timeout (%ss)", self.timeout)
            self._handle_failure()
            return False

        except requests.exceptions.ConnectionError:
            logger.warning("Cannot connect to peer at %s", self.peer_url)
            self._handle_failure()
            return False

        except Exception as e:
            logger.warning("Peer health check failed: %s", e)
            self._handle_failure()
            return False

    def _handle_success(self):
        """Handle successful health check"""
        self.last_success_time = datetime.now()
        self.consecutive_failures = 0

        # If peer was down and is now up, trigger recovery
        if not self.peer_healthy:
            logger.info("🎉 Peer station has recovered!")
            self.peer_healthy = True

            if self.on_peer_up:
                # Execute callback in separate thread to avoid blocking monitor loop
                def _run_callback():
                    try:
                        self.on_peer_up()
                    except Exception as e:
                        logger.error("Error in peer_up callback: %s", e)

                peer_up_thread = threading.Thread(
                    target=_run_callback, daemon=True
                )
                peer_up_thread.start()

    def _handle_failure(self):
        """Handle failed health check"""
        self.consecutive_failures += 1

        logger.debug(
            "Peer check failed (%s/%s)",
            self.consecutive_failures, self.failure_threshold
        )

        # If we've reached failure threshold, declare peer down
        if self.consecutive_failures >= self.failure_threshold:
            if self.peer_healthy:
                logger.warning(
                    "⚠️  Peer station is DOWN (%s consecutive failures)",
                    self.consecutive_failures
                )
                self.peer_healthy = False

                if self.on_peer_down:
                    # Execute callback in separate thread to avoid blocking monitor loop
                    def _run_callback():
                        try:
                            self.on_peer_down()
                        except Exception as e:
                            logger.error("Error in peer_down callback: %s", e)

                    peer_down_thread = threading.Thread(
                        target=_run_callback, daemon=True
                    )
                    peer_down_thread.start()

    def get_status(self) -> Dict:
        """
        Get current peer monitoring status

        Returns:
            Status dictionary
        """
        return {
            "peer_hostname": self.peer_hostname,
            "peer_port": self.peer_port,
            "peer_healthy": self.peer_healthy,
            "consecutive_failures": self.consecutive_failures,
            "last_check_time": (
                self.last_check_time.isoformat()
                if self.last_check_time
                else None
            ),
            "last_success_time": (
                self.last_success_time.isoformat()
                if self.last_success_time
                else None
            ),
            "monitoring_enabled": self._running,
        }

    def force_check(self) -> bool:
        """
        Force immediate health check

        Returns:
            True if peer is healthy
        """
        logger.info("Forcing peer health check")
        return self._check_peer_health()
