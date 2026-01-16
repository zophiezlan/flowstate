#!/usr/bin/env python3
"""
Card Initialization Script

Writes sequential token IDs (001-100) to NTAG215 cards.
Shows progress as cards are tapped.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import argparse
from datetime import datetime
from pathlib import Path
import subprocess
import shutil
from tap_station.nfc_reader import NFCReader, MockNFCReader
from tap_station.feedback import FeedbackController


class ErrorType:
    """Error type categorization"""

    TIMEOUT = "timeout"
    IO_ERROR = "io_error"
    CARD_REMOVED = "card_removed"
    WRITE_FAILED = "write_failed"
    UNKNOWN = "unknown"


def check_service_status():
    """Check if tap-station service is running"""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "tap-station"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() == "active"
    except Exception:
        return False


def stop_service():
    """Stop the tap-station service"""
    try:
        print("Stopping tap-station service...")
        result = subprocess.run(
            ["sudo", "systemctl", "stop", "tap-station"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            time.sleep(1)  # Give it a moment to fully stop
            print("✓ Service stopped")
            return True
        else:
            print(f"✗ Failed to stop service: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ Error stopping service: {e}")
        return False


def start_service():
    """Start the tap-station service"""
    try:
        print("\nRestarting tap-station service...")
        result = subprocess.run(
            ["sudo", "systemctl", "start", "tap-station"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print("✓ Service restarted")
            return True
        else:
            print(f"✗ Failed to restart service: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ Error restarting service: {e}")
        return False


class CardInitializer:
    """Initialize NFC cards with sequential token IDs"""

    def __init__(
        self,
        start_id: int = 1,
        end_id: int = 100,
        mock: bool = False,
        auto_mode: bool = False,
        enable_audio: bool = True,
        resume: bool = False,
        verify: bool = False,
    ):
        """
        Initialize card initializer

        Args:
            start_id: Starting token ID
            end_id: Ending token ID
            mock: Use mock NFC reader
            auto_mode: If True, automatically proceed between cards (no user confirmation)
            enable_audio: Enable buzzer feedback
            resume: Resume from last completed card
            verify: If True, re-read card after write to verify
        """
        self.start_id = start_id
        self.end_id = end_id
        self.current_id = start_id
        self.auto_mode = auto_mode
        self.verify = verify
        self.mapping_file = "data/card_mapping.csv"

        # Load existing cards for duplicate detection and resume
        self.existing_cards = self._load_existing_cards()

        # Resume from last card if requested
        if resume and self.existing_cards:
            last_id = max(
                int(card["token_id"]) for card in self.existing_cards.values()
            )
            if last_id >= self.start_id:
                self.current_id = last_id + 1
                print(
                    f"Resuming from card {self.current_id:03d} (last completed: {last_id:03d})"
                )

        # Initialize NFC reader
        if mock:
            self.nfc = MockNFCReader()
            print("Using mock NFC reader (testing mode)")
        else:
            self.nfc = NFCReader()
            print("PN532 NFC reader initialized")

        # Initialize feedback controller
        try:
            self.feedback = FeedbackController(
                buzzer_enabled=enable_audio,
                led_enabled=False,  # No LEDs during init
                beep_success=[0.1],  # Short beep
                beep_duplicate=[0.1, 0.05, 0.1],  # Double beep
                beep_error=[0.3],  # Long beep
            )
            if enable_audio:
                print("Audio feedback enabled")
        except Exception as e:
            print(f"Warning: Could not enable audio feedback: {e}")
            self.feedback = None

        # Statistics tracking
        self.initialized_cards = []
        self.failed_cards = []  # List of dicts with token_id, error_type, error_msg
        self.duplicate_cards = []
        self.start_time = None
        self.retry_count = 0  # Track retry attempts

    def _load_existing_cards(self) -> dict:
        """Load existing card mappings from CSV"""
        existing = {}
        mapping_path = Path(self.mapping_file)

        if not mapping_path.exists():
            return existing

        try:
            with open(mapping_path, "r") as f:
                # Skip header
                next(f)
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) >= 2:
                        token_id = parts[0]
                        uid = parts[1]
                        existing[uid] = {"token_id": token_id, "uid": uid}
        except Exception as e:
            print(f"Warning: Could not load existing cards: {e}")

        if existing:
            print(f"Loaded {len(existing)} existing card(s) from {self.mapping_file}")

        return existing

    def _get_progress_bar(self, current: int, total: int, width: int = 30) -> str:
        """Generate a text progress bar"""
        completed = self.current_id - self.start_id
        progress = completed / total if total > 0 else 0
        filled = int(width * progress)
        bar = "█" * filled + "░" * (width - filled)
        percent = int(progress * 100)
        return f"[{bar}] {percent}%"

    def _get_statistics(self) -> str:
        """Generate statistics string"""
        if not self.start_time:
            return ""

        elapsed = (datetime.now() - self.start_time).total_seconds()
        completed = self.current_id - self.start_id

        if completed == 0 or elapsed == 0:
            return ""

        # Cards per minute
        rate = (completed / elapsed) * 60

        # Estimated time remaining
        remaining = self.end_id - self.current_id + 1
        eta_seconds = (remaining / rate) * 60 if rate > 0 else 0
        eta_min = int(eta_seconds / 60)

        elapsed_min = int(elapsed / 60)
        elapsed_sec = int(elapsed % 60)

        stats = f"  Time: {elapsed_min}m {elapsed_sec}s"
        stats += f" | Rate: {rate:.1f} cards/min"
        if eta_min > 0:
            stats += f" | ETA: {eta_min}m"

        return stats

    def run(self):
        """Run card initialization process"""
        total_cards = self.end_id - self.start_id + 1

        print(f"\n{'=' * 60}")
        print(f"Card Initialization")
        print(f"{'=' * 60}")
        print(
            f"Will initialize {total_cards} cards (ID {self.start_id:03d} to {self.end_id:03d})"
        )

        if self.auto_mode:
            print(f"\nMode: AUTOMATIC (will proceed between cards automatically)")
            print(f"\nInstructions:")
            print(f"  1. Tap card on the NFC reader")
            print(f"  2. Wait for confirmation message")
            print(f"  3. Remove card when prompted")
            print(f"  4. System will wait 3 seconds before next card")
        else:
            print(f"\nMode: MANUAL (will wait for confirmation between cards)")
            print(f"\nInstructions:")
            print(f"  1. Tap card on the NFC reader")
            print(f"  2. Wait for confirmation message")
            print(f"  3. Remove card when prompted")
            print(f"  4. Press Enter when ready with next card")

        print(f"\nPress Ctrl+C to stop at any time\n")

        input("Press Enter to start...")

        # Startup beep
        if self.feedback:
            self.feedback.startup()

        # Start timer
        self.start_time = datetime.now()

        try:
            while self.current_id <= self.end_id:
                token_id = f"{self.current_id:03d}"

                # Show progress
                total_cards = self.end_id - self.start_id + 1
                progress_bar = self._get_progress_bar(self.current_id, total_cards)
                stats = self._get_statistics()
                print(f"\n{progress_bar}{stats}")

                self._init_card(token_id)

        except KeyboardInterrupt:
            print("\n\nStopped by user")

        finally:
            # Offer to retry failed cards
            if self.failed_cards:
                self._retry_failed_cards()

            self._print_summary()

    def _init_card(self, token_id: str, is_retry: bool = False):
        """
        Initialize a single card

        Args:
            token_id: Token ID to write (e.g., "001")
            is_retry: Whether this is a retry attempt
        """
        retry_label = " (RETRY)" if is_retry else ""
        print(
            f"[{self.current_id}/{self.end_id}] "
            f"Waiting for card (Token ID: {token_id}){retry_label}..."
        )

        # Wait for card with no timeout
        try:
            result = self.nfc.wait_for_card(timeout=None)
        except Exception as e:
            error_msg = str(e)
            print(f"  ✗ I/O ERROR: {error_msg}")
            if self.feedback:
                self.feedback.error()
            self._record_failure(token_id, ErrorType.IO_ERROR, error_msg)
            return

        if not result:
            print("  ✗ TIMEOUT (no card detected)")
            if self.feedback:
                self.feedback.error()
            self._record_failure(token_id, ErrorType.TIMEOUT, "No card detected")
            return

        uid, _ = result
        print(f"  ✓ Card detected (UID: {uid})")

        # Check for duplicates
        if uid in self.existing_cards:
            existing_token = self.existing_cards[uid]["token_id"]
            print(f"  ⚠ DUPLICATE! This card is already token ID {existing_token}")
            if self.feedback:
                self.feedback.duplicate()
            self.duplicate_cards.append(
                {
                    "new_token_id": token_id,
                    "existing_token_id": existing_token,
                    "uid": uid,
                }
            )

            # Ask user what to do
            response = input("  Skip this card? (y/n): ").strip().lower()
            if response == "y":
                print("  Skipping duplicate card")
                return
            else:
                print(f"  Overwriting token ID {existing_token} → {token_id}")

        # Write token ID to card
        print(f"  Writing token ID '{token_id}'...", end="", flush=True)

        success = self.nfc.write_token_id(token_id)

        if success:
            print(" SUCCESS ✓")

            # Verify if requested
            if self.verify:
                print("  Verifying card...", end="", flush=True)
                time.sleep(0.3)  # Brief delay before re-reading

                try:
                    verify_result = self.nfc.wait_for_card(timeout=5)
                    if verify_result:
                        verify_uid, verify_token = verify_result
                        # Check both UID and token ID match
                        if verify_uid != uid:
                            print(f" UID MISMATCH! (got {verify_uid})")
                            self._record_failure(
                                token_id,
                                ErrorType.WRITE_FAILED,
                                f"Verification UID mismatch: {uid} != {verify_uid}",
                            )
                            if self.feedback:
                                self.feedback.error()
                            return
                        elif verify_token != token_id:
                            print(
                                f" TOKEN MISMATCH! (wrote {token_id}, read {verify_token})"
                            )
                            self._record_failure(
                                token_id,
                                ErrorType.WRITE_FAILED,
                                f"Verification token mismatch: "
                                f"wrote {token_id}, read {verify_token}",
                            )
                            if self.feedback:
                                self.feedback.error()
                            return
                        else:
                            print(" VERIFIED ✓")
                    else:
                        print(" TIMEOUT (could not re-read)")
                        self._record_failure(
                            token_id,
                            ErrorType.CARD_REMOVED,
                            "Card removed before verification",
                        )
                        if self.feedback:
                            self.feedback.error()
                        return
                except Exception as e:
                    print(f" ERROR: {e}")
                    self._record_failure(
                        token_id, ErrorType.UNKNOWN, f"Verification error: {e}"
                    )
                    if self.feedback:
                        self.feedback.error()
                    return

            # Success beep
            if self.feedback:
                self.feedback.success()

            self.initialized_cards.append(
                {
                    "token_id": token_id,
                    "uid": uid,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

            # Update existing cards dict
            self.existing_cards[uid] = {"token_id": token_id, "uid": uid}

            # Save mapping to file
            self._save_mapping()

            # Wait for card removal with actual detection
            print("  Please remove card...", end="", flush=True)
            removed = self.nfc.wait_for_card_removal(timeout=15.0)

            if removed:
                print(" OK ✓")

                # CRITICAL: Only increment current_id AFTER successful removal
                # This prevents skipping token IDs if removal times out
                self.current_id += 1

                # Reset reader to clear state
                self.nfc.reset_reader()

                # Give extra time for physical handling and reader reset
                if self.auto_mode:
                    # In auto mode, visual countdown
                    for i in range(3, 0, -1):
                        print(f"  Next card in: {i}...", end="\r", flush=True)
                        time.sleep(1)
                    print(" " * 40, end="\r")  # Clear countdown line
                else:
                    # In manual mode, wait for user confirmation
                    input("  Press Enter when ready with next card...")

            else:
                print(" TIMEOUT (card still present)")
                print(
                    f"  ⚠ Card successfully written as token {token_id}, but not removed"
                )
                print(f"  ⚠ Please remove card manually before continuing")
                if self.feedback:
                    self.feedback.error()
                # Increment here too since write succeeded - token ID has been used
                self.current_id += 1
                # Don't record as failure since write was successful

        else:
            print(" FAILED ✗")
            if self.feedback:
                self.feedback.error()
            self._record_failure(
                token_id, ErrorType.WRITE_FAILED, "Write operation failed"
            )

    def _record_failure(self, token_id: str, error_type: str, error_msg: str):
        """Record a failed card initialization"""
        self.failed_cards.append(
            {
                "token_id": token_id,
                "error_type": error_type,
                "error_msg": error_msg,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    def _retry_failed_cards(self):
        """Offer to retry all failed cards"""
        if not self.failed_cards:
            return

        print(f"\n{'=' * 60}")
        print(f"Failed Cards Retry")
        print(f"{'=' * 60}")
        print(f"Found {len(self.failed_cards)} failed card(s)")

        # Show what failed and why
        for fail in self.failed_cards:
            error_type = fail["error_type"]
            token_id = fail["token_id"]
            print(f"  {token_id}: {self._format_error_type(error_type)}")

        response = input(f"\nRetry these cards now? (y/n): ").strip().lower()

        if response != "y":
            print("Skipping retry")
            return

        # Retry loop
        failed_copy = self.failed_cards.copy()
        self.failed_cards = []  # Clear for retry
        self.retry_count += 1

        print(f"\nRetrying {len(failed_copy)} card(s)...")

        for i, fail in enumerate(failed_copy, 1):
            token_id = fail["token_id"]
            print(f"\n[{i}/{len(failed_copy)}] Retrying token ID: {token_id}")

            # Temporarily set current_id for progress display
            old_current = self.current_id
            self.current_id = int(token_id)

            self._init_card(token_id, is_retry=True)

            # Restore current_id
            self.current_id = old_current

        # If still have failures, ask to retry again
        if self.failed_cards and self.retry_count < 3:
            self._retry_failed_cards()
        elif self.failed_cards and self.retry_count >= 3:
            print(f"\nMax retry attempts ({self.retry_count}) reached")

    def _format_error_type(self, error_type: str) -> str:
        """Format error type for display"""
        error_descriptions = {
            ErrorType.TIMEOUT: "Timeout (no card detected)",
            ErrorType.IO_ERROR: "I/O Error (reader communication issue)",
            ErrorType.CARD_REMOVED: "Card removed early",
            ErrorType.WRITE_FAILED: "Write failed",
            ErrorType.UNKNOWN: "Unknown error",
        }
        return error_descriptions.get(error_type, error_type)

    def _save_mapping(self):
        """Save UID to token ID mapping to CSV file (atomic write)"""
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.mapping_file), exist_ok=True)

        # Combine existing cards with new initialized cards
        all_cards = {}

        # Add existing cards first
        for uid, card in self.existing_cards.items():
            all_cards[uid] = card

        # Add/update with newly initialized cards
        for card in self.initialized_cards:
            all_cards[card["uid"]] = card

        # Write to temp file first (atomic operation)
        temp_file = self.mapping_file + ".tmp"
        try:
            with open(temp_file, "w") as f:
                f.write("token_id,uid,initialized_at\n")
                for card in sorted(all_cards.values(), key=lambda x: x["token_id"]):
                    timestamp = card.get("timestamp", "unknown")
                    f.write(f"{card['token_id']},{card['uid']},{timestamp}\n")

            # Atomic rename (replace old file)
            os.replace(temp_file, self.mapping_file)
        except Exception as e:
            # Clean up temp file if it exists
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise e

    def _print_summary(self):
        """Print initialization summary"""
        # Calculate final statistics
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            elapsed_min = int(elapsed / 60)
            elapsed_sec = int(elapsed % 60)
        else:
            elapsed_min = 0
            elapsed_sec = 0

        success_count = len(self.initialized_cards)
        fail_count = len(self.failed_cards)
        duplicate_count = len(self.duplicate_cards)
        total_attempted = success_count + fail_count

        print(f"\n{'=' * 60}")
        print(f"Initialization Summary")
        print(f"{'=' * 60}")
        print(f"Total time:      {elapsed_min}m {elapsed_sec}s")
        print(f"Total attempted: {total_attempted}")
        print(f"Successful:      {success_count} ✓")
        print(f"Failed:          {fail_count} ✗")
        print(f"Duplicates:      {duplicate_count} ⚠")

        if fail_count > 0:
            print(f"\nFailed Cards by Error Type:")
            # Group by error type
            error_groups = {}
            for fail in self.failed_cards:
                error_type = fail["error_type"]
                if error_type not in error_groups:
                    error_groups[error_type] = []
                error_groups[error_type].append(fail["token_id"])

            for error_type, token_ids in error_groups.items():
                error_desc = self._format_error_type(error_type)
                print(f"  {error_desc}: {', '.join(token_ids)}")

        if duplicate_count > 0:
            print(f"\nDuplicate cards detected:")
            for dup in self.duplicate_cards:
                print(
                    f"  Token {dup['new_token_id']} → "
                    f"Already exists as {dup['existing_token_id']} "
                    f"(UID: {dup['uid']})"
                )

        # Show overall progress
        total_cards = self.end_id - self.start_id + 1
        completed = self.current_id - self.start_id
        progress_percent = int((completed / total_cards) * 100)
        print(f"\nOverall progress: {completed}/{total_cards} ({progress_percent}%)")

        print(f"\nCard mapping saved to: {self.mapping_file}")

        # Generate report
        report_path = self._generate_report()
        if report_path:
            print(f"Detailed report saved to: {report_path}")

        print(f"{'=' * 60}\n")

        # Cleanup feedback
        if self.feedback:
            self.feedback.cleanup()

    def _generate_report(self) -> str:
        """Generate detailed initialization report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"data/init_report_{timestamp}.txt"

        try:
            os.makedirs(os.path.dirname(report_file), exist_ok=True)

            with open(report_file, "w") as f:
                f.write("=" * 60 + "\n")
                f.write("Card Initialization Report\n")
                f.write("=" * 60 + "\n\n")

                f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Token ID Range: {self.start_id:03d} - {self.end_id:03d}\n")

                if self.start_time:
                    elapsed = (datetime.now() - self.start_time).total_seconds()
                    elapsed_min = int(elapsed / 60)
                    elapsed_sec = int(elapsed % 60)
                    f.write(f"Total Time: {elapsed_min}m {elapsed_sec}s\n")

                f.write("\n" + "=" * 60 + "\n")
                f.write("Summary Statistics\n")
                f.write("=" * 60 + "\n\n")

                f.write(f"Successful: {len(self.initialized_cards)}\n")
                f.write(f"Failed: {len(self.failed_cards)}\n")
                f.write(f"Duplicates: {len(self.duplicate_cards)}\n")
                f.write(f"Retry Attempts: {self.retry_count}\n")

                # Successful cards
                if self.initialized_cards:
                    f.write("\n" + "=" * 60 + "\n")
                    f.write("Successful Initializations\n")
                    f.write("=" * 60 + "\n\n")
                    f.write("Token ID | UID              | Timestamp\n")
                    f.write("-" * 60 + "\n")
                    for card in self.initialized_cards:
                        f.write(
                            f"{card['token_id']:8} | {card['uid']:16} | {card['timestamp']}\n"
                        )

                # Failed cards
                if self.failed_cards:
                    f.write("\n" + "=" * 60 + "\n")
                    f.write("Failed Initializations\n")
                    f.write("=" * 60 + "\n\n")

                    # Group by error type
                    error_groups = {}
                    for fail in self.failed_cards:
                        error_type = fail["error_type"]
                        if error_type not in error_groups:
                            error_groups[error_type] = []
                        error_groups[error_type].append(fail)

                    for error_type, failures in error_groups.items():
                        f.write(f"\n{self._format_error_type(error_type)}:\n")
                        f.write(
                            "Token ID | Error Message                    | Timestamp\n"
                        )
                        f.write("-" * 60 + "\n")
                        for fail in failures:
                            f.write(
                                f"{fail['token_id']:8} | "
                                f"{fail['error_msg']:32} | "
                                f"{fail['timestamp']}\n"
                            )

                # Duplicates
                if self.duplicate_cards:
                    f.write("\n" + "=" * 60 + "\n")
                    f.write("Duplicate Cards\n")
                    f.write("=" * 60 + "\n\n")
                    f.write("New ID | Existing ID | UID\n")
                    f.write("-" * 60 + "\n")
                    for dup in self.duplicate_cards:
                        f.write(
                            f"{dup['new_token_id']:6} | "
                            f"{dup['existing_token_id']:11} | "
                            f"{dup['uid']}\n"
                        )

                # Recommendations
                f.write("\n" + "=" * 60 + "\n")
                f.write("Recommendations\n")
                f.write("=" * 60 + "\n\n")

                if self.failed_cards:
                    f.write("Failed cards detected:\n")
                    error_groups = {}
                    for fail in self.failed_cards:
                        error_type = fail["error_type"]
                        if error_type not in error_groups:
                            error_groups[error_type] = []
                        error_groups[error_type].append(fail)

                    if ErrorType.TIMEOUT in error_groups:
                        f.write(
                            "- Timeout errors: Check NFC reader position and card placement\n"
                        )
                    if ErrorType.IO_ERROR in error_groups:
                        f.write("- I/O errors: Check I2C connection and power supply\n")
                        f.write("  Run: sudo i2cdetect -y 1\n")
                    if ErrorType.CARD_REMOVED in error_groups:
                        f.write("- Card removed early: Hold cards longer on reader\n")

                if not self.failed_cards and not self.duplicate_cards:
                    f.write("All cards initialized successfully! ✓\n")

            return report_file

        except Exception as e:
            print(f"Warning: Could not generate report: {e}")
            return None


def main():
    """Entry point for card initialization"""
    parser = argparse.ArgumentParser(description="Initialize NFC cards with token IDs")
    parser.add_argument(
        "--start", type=int, default=1, help="Starting token ID (default: 1)"
    )
    parser.add_argument(
        "--end", type=int, default=100, help="Ending token ID (default: 100)"
    )
    parser.add_argument(
        "--mock", action="store_true", help="Use mock NFC reader for testing"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Automatic mode: proceed between cards without user confirmation",
    )
    parser.add_argument(
        "--resume", action="store_true", help="Resume from last completed card"
    )
    parser.add_argument(
        "--no-audio", action="store_true", help="Disable audio feedback (buzzer)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify each card after writing (re-read to confirm)",
    )
    parser.add_argument(
        "--no-service-check",
        action="store_true",
        help="Skip service status check and management",
    )

    args = parser.parse_args()

    # Validate range
    if args.start < 1 or args.end < args.start:
        print("Error: Invalid token ID range", file=sys.stderr)
        return 1

    # Check if systemctl is available
    has_systemctl = shutil.which("systemctl") is not None
    service_was_running = False

    # Check and manage service (unless in mock mode or disabled)
    if not args.mock and not args.no_service_check and has_systemctl:
        if check_service_status():
            service_was_running = True
            print("\n⚠️  WARNING: tap-station service is currently running")
            print("   The service must be stopped to initialize cards.\n")

            response = input("Stop the service now? [Y/n]: ").strip().lower()
            if response in ("", "y", "yes"):
                if not stop_service():
                    print("\nCannot proceed without stopping the service.")
                    print(
                        "You can manually stop it with: sudo systemctl stop tap-station"
                    )
                    return 1
            else:
                print("\nCannot initialize cards while service is running.")
                print("Please stop it manually: sudo systemctl stop tap-station")
                return 1

    try:
        initializer = CardInitializer(
            start_id=args.start,
            end_id=args.end,
            mock=args.mock,
            auto_mode=args.auto,
            enable_audio=not args.no_audio,
            resume=args.resume,
            verify=args.verify,
        )
        result = initializer.run()

        # Restart service if we stopped it
        if service_was_running and has_systemctl:
            start_service()

        return result if result is not None else 0

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        # Restart service if we stopped it
        if service_was_running and has_systemctl:
            start_service()
        return 130

    except Exception as e:
        print(f"\nFatal error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()

        # Restart service if we stopped it
        if service_was_running and has_systemctl:
            start_service()

        return 1


if __name__ == "__main__":
    sys.exit(main())
