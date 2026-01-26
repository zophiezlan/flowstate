"""Main tap station service - ties everything together"""

import sys
import logging
import signal
import time
from pathlib import Path
from logging.handlers import RotatingFileHandler
import threading

from tap_station.config import Config
from tap_station.database import Database
from tap_station.nfc_reader import NFCReader, MockNFCReader
from tap_station.feedback import FeedbackController
from tap_station.validation import TokenValidator
from tap_station.path_utils import ensure_parent_dir
from tap_station.onsite_manager import OnSiteManager


class TapStation:
    """Main tap station service"""

    def __init__(self, config_path: str = "config.yaml", mock_nfc: bool = False):
        """
        Initialize tap station

        Args:
            config_path: Path to configuration file
            mock_nfc: Use mock NFC reader (for testing)
        """
        # Load configuration
        self.config = Config(config_path)

        # Setup logging
        self._setup_logging()

        self.logger = logging.getLogger(__name__)
        self.logger.info("=" * 60)
        self.logger.info("NFC Tap Station Starting")
        self.logger.info(f"Device: {self.config.device_id}")
        self.logger.info(f"Stage: {self.config.stage}")
        self.logger.info(f"Session: {self.config.session_id}")
        self.logger.info("=" * 60)

        # Initialize components
        self.db = Database(
            db_path=self.config.database_path, wal_mode=self.config.wal_mode
        )

        if mock_nfc:
            self.nfc = MockNFCReader(
                i2c_bus=self.config.i2c_bus,
                address=self.config.i2c_address,
                timeout=self.config.nfc_timeout,
                retries=self.config.nfc_retries,
                debounce_seconds=self.config.debounce_seconds,
            )
        else:
            self.nfc = NFCReader(
                i2c_bus=self.config.i2c_bus,
                address=self.config.i2c_address,
                timeout=self.config.nfc_timeout,
                retries=self.config.nfc_retries,
                debounce_seconds=self.config.debounce_seconds,
            )

        self.feedback = FeedbackController(
            buzzer_enabled=self.config.buzzer_enabled,
            led_enabled=self.config.led_enabled,
            gpio_buzzer=self.config.gpio_buzzer,
            gpio_led_green=self.config.gpio_led_green,
            gpio_led_red=self.config.gpio_led_red,
            beep_success=self.config.beep_success,
            beep_duplicate=self.config.beep_duplicate,
            beep_error=self.config.beep_error,
        )

        # Initialize shutdown button handler
        self.button_handler = None
        if self.config.shutdown_button_enabled:
            try:
                from tap_station.button_handler import ButtonHandler

                self.button_handler = ButtonHandler(
                    enabled=self.config.shutdown_button_enabled,
                    gpio_pin=self.config.shutdown_button_gpio,
                    hold_time=self.config.shutdown_button_hold_time,
                    shutdown_callback=self._shutdown_callback,
                    shutdown_delay_minutes=self.config.shutdown_button_delay_minutes,
                )
                self.logger.info("Shutdown button handler initialized")
            except Exception as e:
                self.logger.error(
                    f"Failed to initialize shutdown button: {e}", exc_info=True
                )

        self.web_server = None
        self.web_thread = None
        if self.config.web_server_enabled:
            try:
                from tap_station.web_server import StatusWebServer

                self.web_server = StatusWebServer(self.config, self.db)
                self.web_thread = threading.Thread(
                    target=self.web_server.run,
                    kwargs={
                        "host": self.config.web_server_host,
                        "port": self.config.web_server_port,
                    },
                    daemon=True,
                )
                self.web_thread.start()
                self.logger.info(
                    f"Web server started on "
                    f"{self.config.web_server_host}:{self.config.web_server_port}"
                )
            except Exception as e:
                self.logger.error(f"Failed to start web server: {e}", exc_info=True)

        # Initialize on-site manager (WiFi, mDNS, failover, etc.)
        self.onsite_manager = None
        if self.config.onsite_enabled:
            try:
                self.onsite_manager = OnSiteManager(
                    device_id=self.config.device_id,
                    stage=self.config.stage,
                    web_port=self.config.web_server_port,
                    peer_hostname=self.config.onsite_failover_peer_hostname,
                    wifi_enabled=self.config.onsite_wifi_enabled,
                    failover_enabled=self.config.onsite_failover_enabled
                )
                self.logger.info("On-site manager initialized")
            except Exception as e:
                self.logger.warning(f"Failed to initialize on-site manager: {e}")

        # State
        self.running = False

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _setup_logging(self):
        """Setup logging to file and console"""
        # Ensure log directory exists
        log_path = ensure_parent_dir(self.config.log_path)

        # Get log level
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)

        # Create formatters
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # File handler (rotating)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=self.config.log_max_size_mb * 1024 * 1024,
            backupCount=self.config.log_backup_count,
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)

        # Root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def run(self):
        """Main service loop"""
        self.running = True

        # Start on-site manager (WiFi, mDNS, peer monitoring, etc.)
        if self.onsite_manager:
            try:
                self.onsite_manager.startup()
            except Exception as e:
                self.logger.error(f"On-site manager startup failed: {e}", exc_info=True)

        # Startup feedback
        self.feedback.startup()
        self.logger.info("Station ready - waiting for cards...")

        try:
            while self.running:
                # Wait for card tap
                result = self.nfc.read_card()

                if result:
                    uid, token_id = result
                    self._handle_tap(uid, token_id)

                # Small delay to prevent CPU spinning
                time.sleep(0.1)

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")

        except Exception as e:
            self.logger.error(f"Unexpected error in main loop: {e}", exc_info=True)

        finally:
            self.shutdown()

    def _handle_tap(self, uid: str, token_id: str):
        """
        Handle a card tap event

        Args:
            uid: Card UID
            token_id: Token ID (may be UID-derived if not initialized)
        """
        self.logger.info(f"Card tapped: UID={uid}, Token={token_id}")

        # Determine stage (may be overridden in failover mode)
        stage = self.config.stage
        use_alternate_beep = False

        # Check if in failover mode and determine appropriate stage
        if self.onsite_manager and self.onsite_manager.failover_manager:
            failover_mgr = self.onsite_manager.failover_manager
            
            if failover_mgr.failover_active:
                # Get participant's tap count to determine stage alternation
                tap_count = self.db.get_participant_tap_count(
                    token_id=token_id,
                    session_id=self.config.session_id
                )
                
                # Next tap will be tap_count + 1 (since we're about to log it)
                next_tap_number = tap_count + 1
                
                # Get the appropriate stage for this tap based on alternation logic
                stage = failover_mgr.get_stage_for_tap_number(next_tap_number)
                
                use_alternate_beep = True
                self.logger.info(
                    f"FAILOVER MODE: tap #{next_tap_number} → stage {stage} "
                    f"(alternating between {failover_mgr.primary_stage} and "
                    f"{failover_mgr.fallback_stages})"
                )

        # Check if auto-initialization is enabled and card appears uninitialized
        # Uninitialized cards will have token_id that looks like a UID (8+ hex chars)
        if self.config.auto_init_cards and self._is_uninitialized_card(token_id):
            # This looks like an uninitialized card (UID being used as token_id)
            # Auto-assign the next token ID
            _, new_token_id = self.db.get_next_auto_init_token_id(
                session_id=self.config.session_id,
                start_id=self.config.auto_init_start_id,
            )

            self.logger.info(
                f"Auto-initializing card UID={uid} with token ID {new_token_id}"
            )

            # Try to write the new token ID to the card
            try:
                write_success = self.nfc.write_token_id(new_token_id)
                if write_success:
                    self.logger.info(
                        f"Successfully wrote token ID {new_token_id} to card"
                    )
                else:
                    self.logger.warning(
                        f"Failed to write token ID to card, will use auto-assigned ID anyway"
                    )
            except Exception as e:
                self.logger.warning(
                    f"Exception writing token ID to card: {e}, will use auto-assigned ID anyway"
                )

            token_id = new_token_id

        # Log to database - use the determined stage (which may be from failover logic)
        result = self.db.log_event(
            token_id=token_id,
            uid=uid,
            stage=stage,  # Use failover-determined stage, not self.config.stage
            device_id=self.config.device_id,
            session_id=self.config.session_id,
        )

        # Provide feedback based on result
        if result["success"]:
            if result["out_of_order"]:
                # Logged but with sequence warning
                self.feedback.duplicate()  # Use duplicate beep to indicate issue
                self.logger.warning(
                    f"Event logged with warning: {result['warning']}. "
                    f"Suggestion: {result.get('suggestion', 'N/A')}"
                )
            else:
                # Success with no issues
                # Use alternate beep pattern in failover mode
                if use_alternate_beep:
                    self.feedback.duplicate()  # Different pattern for failover
                    self.logger.info("Event logged successfully (FAILOVER MODE)")
                else:
                    self.feedback.success()
                    self.logger.info("Event logged successfully")
        elif result["duplicate"]:
            # Duplicate tap
            self.feedback.duplicate()
            self.logger.info(f"Duplicate tap ignored: {result['warning']}")
        else:
            # Some other error
            self.feedback.error()
            self.logger.error(
                f"Failed to log event: {result.get('warning', 'Unknown error')}"
            )

        # Record tap in failover manager
        if self.onsite_manager and self.onsite_manager.failover_manager:
            self.onsite_manager.failover_manager.record_tap(stage)

    def _is_uninitialized_card(self, token_id: str) -> bool:
        """
        Check if a token ID looks like an uninitialized card (UID)

        Args:
            token_id: Token ID to check

        Returns:
            True if token_id looks like a UID (8+ hex chars), False otherwise
        """
        # Use centralized TokenValidator for consistent UID detection
        return TokenValidator.looks_like_uid(token_id)

    def shutdown(self):
        """Cleanup and shutdown"""
        self.logger.info("Shutting down...")

        # Stop on-site manager
        if self.onsite_manager:
            self.onsite_manager.shutdown()

        # Stop button handler
        if self.button_handler:
            self.button_handler.cleanup()

        # Close database
        if self.db:
            self.db.close()

        # Cleanup GPIO
        if self.feedback:
            self.feedback.cleanup()

        self.logger.info("Shutdown complete")

    def _shutdown_callback(self):
        """Callback executed when shutdown button is pressed"""
        self.logger.warning("Shutdown button pressed - stopping service...")

        # Stop the main loop to allow graceful shutdown
        self.running = False

    def get_stats(self) -> dict:
        """Get current station statistics"""
        stats = {
            "device_id": self.config.device_id,
            "stage": self.config.stage,
            "session_id": self.config.session_id,
            "total_events": self.db.get_event_count(self.config.session_id),
            "recent_events": self.db.get_recent_events(5),
        }

        # Add on-site manager status if available
        if self.onsite_manager:
            stats["onsite"] = self.onsite_manager.get_status()

        return stats


def main():
    """Entry point for tap station service"""
    import argparse

    parser = argparse.ArgumentParser(description="NFC Tap Station Service")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--mock-nfc", action="store_true", help="Use mock NFC reader for testing"
    )
    parser.add_argument("--stats", action="store_true", help="Show statistics and exit")

    args = parser.parse_args()

    # Setup basic logging for CLI mode
    cli_logger = logging.getLogger(__name__)

    try:
        station = TapStation(config_path=args.config, mock_nfc=args.mock_nfc)

        if args.stats:
            # Show stats and exit
            stats = station.get_stats()
            cli_logger.info("\nStation Statistics:")
            cli_logger.info(f"  Device ID: {stats['device_id']}")
            cli_logger.info(f"  Stage: {stats['stage']}")
            cli_logger.info(f"  Session: {stats['session_id']}")
            cli_logger.info(f"  Total Events: {stats['total_events']}")
            cli_logger.info("\nRecent Events:")
            for event in stats["recent_events"]:
                cli_logger.info(
                    f"  {event['timestamp']} - "
                    f"Token {event['token_id']} at {event['stage']}"
                )
            return 0

        # Run station
        station.run()
        return 0

    except FileNotFoundError as e:
        cli_logger.error(f"Error: {e}")
        cli_logger.error(f"Please create a config file at: {args.config}")
        return 1

    except Exception as e:
        cli_logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
