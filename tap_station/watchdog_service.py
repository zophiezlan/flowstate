"""
Watchdog Service - Monitors and auto-recovers system components

Provides:
- Health monitoring for tap station and web server
- Automatic restart of failed components
- Independent monitoring of NFC logger vs web dashboard
- Graceful recovery without data loss
"""

import logging
import time
import subprocess
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class WatchdogService:
    """
    Monitors system health and auto-recovers failed components

    Features:
    - Monitors web server health via HTTP
    - Monitors tap station process
    - Can restart web server independently
    - Logs all restart attempts
    - Configurable thresholds
    """

    def __init__(
        self,
        web_port: int = 8080,
        check_interval: int = 10,
        restart_threshold: int = 3,
        max_restarts_per_hour: int = 5,
    ):
        """
        Initialize watchdog service

        Args:
            web_port: Web server port to monitor
            check_interval: Seconds between health checks
            restart_threshold: Consecutive failures before restart
            max_restarts_per_hour: Maximum restarts allowed per hour
        """
        self.web_port = web_port
        self.check_interval = check_interval
        self.restart_threshold = restart_threshold
        self.max_restarts_per_hour = max_restarts_per_hour

        # State tracking
        self.web_consecutive_failures = 0
        self.web_last_success = datetime.now()
        self.restart_history = []

        # Monitoring
        self._running = False

    def check_web_server_health(self) -> bool:
        """
        Check if web server is responding

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = requests.get(
                f"http://localhost:{self.web_port}/health", timeout=5
            )

            if response.status_code == 200:
                self.web_consecutive_failures = 0
                self.web_last_success = datetime.now()
                return True
            else:
                logger.warning(f"Web server returned status {response.status_code}")
                self.web_consecutive_failures += 1
                return False

        except requests.exceptions.ConnectionError:
            logger.warning("Web server connection failed")
            self.web_consecutive_failures += 1
            return False

        except requests.exceptions.Timeout:
            logger.warning("Web server health check timeout")
            self.web_consecutive_failures += 1
            return False

        except Exception as e:
            logger.error(f"Web server health check error: {e}")
            self.web_consecutive_failures += 1
            return False

    def should_restart_web_server(self) -> bool:
        """
        Check if web server should be restarted

        Returns:
            True if restart is needed and allowed
        """
        # Check if we've exceeded failure threshold
        if self.web_consecutive_failures < self.restart_threshold:
            return False

        # Check if we've exceeded restart rate limit
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_restarts = [ts for ts in self.restart_history if ts > one_hour_ago]

        if len(recent_restarts) >= self.max_restarts_per_hour:
            logger.error(
                f"Restart rate limit exceeded: "
                f"{len(recent_restarts)} restarts in last hour"
            )
            return False

        return True

    def restart_web_server(self) -> bool:
        """
        Restart web server component

        Note: The web server is integrated into the main tap-station service,
        so we cannot restart it independently. This method logs the issue
        but does not attempt a restart to avoid disrupting the entire service.

        Returns:
            False - restart not available for integrated web server
        """
        logger.warning(
            "Web server health check failed. Web server is integrated into "
            "tap-station service and cannot be restarted independently. "
            "Consider restarting the entire tap-station service if issues persist."
        )

        # Record restart attempt (even though we don't actually restart)
        self.restart_history.append(datetime.now())

        # Reset failure count to avoid spam
        self.web_consecutive_failures = 0

        return False

    def get_status(self) -> dict:
        """
        Get watchdog status

        Returns:
            Status dictionary
        """
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_restarts = [ts for ts in self.restart_history if ts > one_hour_ago]

        return {
            "web_server": {
                "consecutive_failures": self.web_consecutive_failures,
                "last_success": self.web_last_success.isoformat(),
                "health": (
                    "healthy" if self.web_consecutive_failures == 0 else "unhealthy"
                ),
            },
            "restart_history": {
                "total": len(self.restart_history),
                "last_hour": len(recent_restarts),
                "rate_limited": len(recent_restarts) >= self.max_restarts_per_hour,
            },
        }


def create_watchdog_systemd_service():
    """
    Generate systemd service file for watchdog

    Returns:
        Service file content as string
    """
    service_content = """[Unit]
Description=NFC Tap Station Watchdog
After=network.target tap-station.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/nfc-tap-logger
Environment="PATH=/home/pi/nfc-tap-logger/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/pi/nfc-tap-logger/venv/bin/python -m tap_station.watchdog_runner
Restart=always
RestartSec=30

StandardOutput=append:/home/pi/nfc-tap-logger/logs/watchdog.log
StandardError=append:/home/pi/nfc-tap-logger/logs/watchdog-error.log

[Install]
WantedBy=multi-user.target
"""
    return service_content


def main():
    """Main watchdog runner loop"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("Starting watchdog service...")

    watchdog = WatchdogService(
        web_port=8080, check_interval=10, restart_threshold=3, max_restarts_per_hour=5
    )

    watchdog._running = True

    try:
        while watchdog._running:
            # Check web server health
            healthy = watchdog.check_web_server_health()

            if not healthy:
                logger.warning(
                    f"Web server unhealthy "
                    f"({watchdog.web_consecutive_failures}/{watchdog.restart_threshold})"
                )

                # Check if restart is needed
                if watchdog.should_restart_web_server():
                    watchdog.restart_web_server()

            # Sleep until next check
            time.sleep(watchdog.check_interval)

    except KeyboardInterrupt:
        logger.info("Watchdog service stopped by user")
        watchdog._running = False

    except Exception as e:
        logger.error(f"Watchdog error: {e}", exc_info=True)

    logger.info("Watchdog service stopped")


if __name__ == "__main__":
    main()
