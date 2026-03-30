"""Main tap station service - ties everything together"""

import logging
import signal
import sys
import threading
import time
from logging.handlers import RotatingFileHandler

from tap_station.config import Config
from tap_station.database import Database
from tap_station.feedback import FeedbackController
from tap_station.nfc_reader import MockNFCReader, NFCReader
from tap_station.path_utils import ensure_parent_dir
from tap_station.validation import TokenValidator


class TapStation:
    """Main tap station service"""

    def __init__(
        self, config_path: str = "config.yaml", mock_nfc: bool = False
    ):
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
        self.logger.info("FlowState Station Starting")
        self.logger.info("Device: %s", self.config.device_id)
        self.logger.info("Stage: %s", self.config.stage)
        self.logger.info("Session: %s", self.config.session_id)
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
                    feedback_controller=self.feedback,  # Pass feedback controller
                )
                self.logger.info("Shutdown button handler initialized")
            except Exception as e:
                self.logger.error(
                    "Failed to initialize shutdown button: %s", e, exc_info=True
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
                    "Web server started on %s:%s",
                    self.config.web_server_host, self.config.web_server_port
                )
            except Exception as e:
                self.logger.error(
                    "Failed to start web server: %s", e, exc_info=True
                )

        # Consolidated v1 runtime: disable on-site platform helpers.
        self.onsite_manager = None

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
        log_level = getattr(
            logging, self.config.log_level.upper(), logging.INFO
        )

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
        self.logger.info("Received signal %s, shutting down...", signum)
        self.running = False

    def run(self):
        """Main service loop"""
        self.running = True

        # Startup feedback
        self.feedback.startup()
        self.logger.info("Station ready - waiting for cards...")

        # Set ready state after startup (solid green)
        if self.feedback.led_enabled:
            self.feedback.set_ready_state()

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
            self.logger.error(
                "Unexpected error in main loop: %s", e, exc_info=True
            )

        finally:
            self.shutdown()

    def _handle_tap(self, uid: str, token_id: str):
        """
        Handle a card tap event

        Args:
            uid: Card UID
            token_id: Token ID (may be UID-derived if not initialized)
        """
        self.logger.info("Card tapped: UID=%s, Token=%s", uid, token_id)

        # Fixed-stage station in consolidated v1 model.
        stage = self.config.stage

        # Check if auto-initialization is enabled and card appears uninitialized
        # Uninitialized cards will have token_id that looks like a UID (8+ hex chars)
        if self.config.auto_init_cards and self._is_uninitialized_card(
            token_id
        ):
            # This looks like an uninitialized card (UID being used as token_id)
            # Use get_or_create_token_for_uid to prevent duplicate assignments
            # if the same card is tapped again after a failed write
            new_token_id, is_new = self.db.get_or_create_token_for_uid(
                uid=uid,
                session_id=self.config.session_id,
                start_id=self.config.auto_init_start_id,
            )

            if is_new:
                self.logger.info(
                    "Auto-initializing card UID=%s with token ID %s", uid, new_token_id
                )
            else:
                self.logger.info(
                    "Reusing previously assigned token %s for UID=%s", new_token_id, uid
                )

            # Try to write the new token ID to the card
            try:
                write_success = self.nfc.write_token_id(new_token_id)
                if write_success:
                    self.logger.info(
                        "Successfully wrote token ID %s to card", new_token_id
                    )
                    # Update mapping to record successful write
                    self.db.update_uid_token_mapping_write_success(
                        uid, self.config.session_id
                    )
                else:
                    self.logger.warning(
                        "Failed to write token ID to card, will use auto-assigned ID anyway"
                    )
            except Exception as e:
                self.logger.warning(
                    "Exception writing token ID to card: %s, will use auto-assigned ID anyway", e
                )

            token_id = new_token_id

        # Log to database using this station's fixed assigned stage.
        result = self.db.log_event(
            token_id=token_id,
            uid=uid,
            stage=stage,
            device_id=self.config.device_id,
            session_id=self.config.session_id,
        )

        # Provide feedback based on result
        if result["success"]:
            if result["out_of_order"]:
                self.feedback.warning()
                self.logger.warning(
                    "Event logged with warning: %s. Suggestion: %s",
                    result['warning'], result.get('suggestion', 'N/A')
                )
            else:
                self.feedback.success()
                self.logger.info("Event logged successfully")
        elif result["duplicate"]:
            # Duplicate tap
            self.feedback.duplicate()  # Double beep + yellow flash
            self.logger.info("Duplicate tap ignored: %s", result['warning'])
        else:
            # Some other error
            self.feedback.error()  # Long beep + red flash
            self.logger.error(
                "Failed to log event: %s", result.get('warning', 'Unknown error')
            )

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

        return stats


def main():
    """Entry point for tap station service"""
    import argparse

    parser = argparse.ArgumentParser(description="FlowState Station Service")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--mock-nfc",
        action="store_true",
        help="Use mock NFC reader for testing",
    )
    parser.add_argument(
        "--stats", action="store_true", help="Show statistics and exit"
    )

    args = parser.parse_args()

    # Setup basic logging for CLI mode
    cli_logger = logging.getLogger(__name__)

    try:
        station = TapStation(config_path=args.config, mock_nfc=args.mock_nfc)

        if args.stats:
            # Show stats and exit
            stats = station.get_stats()
            cli_logger.info("\nStation Statistics:")
            cli_logger.info("  Device ID: %s", stats['device_id'])
            cli_logger.info("  Stage: %s", stats['stage'])
            cli_logger.info("  Session: %s", stats['session_id'])
            cli_logger.info("  Total Events: %s", stats['total_events'])
            cli_logger.info("\nRecent Events:")
            for event in stats["recent_events"]:
                cli_logger.info(
                    "  %s - Token %s at %s",
                    event['timestamp'], event['token_id'], event['stage']
                )
            return 0

        # Run station
        station.run()
        return 0

    except FileNotFoundError as e:
        cli_logger.error("Error: %s", e)
        cli_logger.error("Please create a config file at: %s", args.config)
        return 1

    except Exception as e:
        cli_logger.error("Fatal error: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
