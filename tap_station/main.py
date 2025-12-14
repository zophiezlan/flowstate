"""Main tap station service - ties everything together"""

import sys
import logging
import signal
import time
from pathlib import Path
from logging.handlers import RotatingFileHandler

from tap_station.config import Config
from tap_station.database import Database
from tap_station.nfc_reader import NFCReader, MockNFCReader
from tap_station.feedback import FeedbackController


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
            db_path=self.config.database_path,
            wal_mode=self.config.wal_mode
        )

        if mock_nfc:
            self.nfc = MockNFCReader(
                i2c_bus=self.config.i2c_bus,
                address=self.config.i2c_address,
                timeout=self.config.nfc_timeout,
                retries=self.config.nfc_retries,
                debounce_seconds=self.config.debounce_seconds
            )
        else:
            self.nfc = NFCReader(
                i2c_bus=self.config.i2c_bus,
                address=self.config.i2c_address,
                timeout=self.config.nfc_timeout,
                retries=self.config.nfc_retries,
                debounce_seconds=self.config.debounce_seconds
            )

        self.feedback = FeedbackController(
            buzzer_enabled=self.config.buzzer_enabled,
            led_enabled=self.config.led_enabled,
            gpio_buzzer=self.config.gpio_buzzer,
            gpio_led_green=self.config.gpio_led_green,
            gpio_led_red=self.config.gpio_led_red,
            beep_success=self.config.beep_success,
            beep_duplicate=self.config.beep_duplicate,
            beep_error=self.config.beep_error
        )

        # State
        self.running = False

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _setup_logging(self):
        """Setup logging to file and console"""
        # Ensure log directory exists
        log_path = Path(self.config.log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Get log level
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)

        # Create formatters
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # File handler (rotating)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=3
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
            token_id: Token ID
        """
        self.logger.info(f"Card tapped: UID={uid}, Token={token_id}")

        # Log to database
        success = self.db.log_event(
            token_id=token_id,
            uid=uid,
            stage=self.config.stage,
            device_id=self.config.device_id,
            session_id=self.config.session_id
        )

        # Provide feedback
        if success:
            self.feedback.success()
            self.logger.info(f"Event logged successfully")
        else:
            # Duplicate tap
            self.feedback.duplicate()
            self.logger.info(f"Duplicate tap ignored")

    def shutdown(self):
        """Cleanup and shutdown"""
        self.logger.info("Shutting down...")

        # Close database
        if self.db:
            self.db.close()

        # Cleanup GPIO
        if self.feedback:
            self.feedback.cleanup()

        self.logger.info("Shutdown complete")

    def get_stats(self) -> dict:
        """Get current station statistics"""
        return {
            'device_id': self.config.device_id,
            'stage': self.config.stage,
            'session_id': self.config.session_id,
            'total_events': self.db.get_event_count(self.config.session_id),
            'recent_events': self.db.get_recent_events(5)
        }


def main():
    """Entry point for tap station service"""
    import argparse

    parser = argparse.ArgumentParser(description='NFC Tap Station Service')
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    parser.add_argument(
        '--mock-nfc',
        action='store_true',
        help='Use mock NFC reader for testing'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics and exit'
    )

    args = parser.parse_args()

    try:
        station = TapStation(config_path=args.config, mock_nfc=args.mock_nfc)

        if args.stats:
            # Show stats and exit
            stats = station.get_stats()
            print(f"\nStation Statistics:")
            print(f"  Device ID: {stats['device_id']}")
            print(f"  Stage: {stats['stage']}")
            print(f"  Session: {stats['session_id']}")
            print(f"  Total Events: {stats['total_events']}")
            print(f"\nRecent Events:")
            for event in stats['recent_events']:
                print(f"  {event['timestamp']} - Token {event['token_id']} at {event['stage']}")
            return 0

        # Run station
        station.run()
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(f"Please create a config file at: {args.config}", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
