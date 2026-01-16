#!/usr/bin/env python3
"""
Enhanced Card Initialization Script with NDEF Support

Writes sequential token IDs (001-100) to NTAG215 cards with NDEF URLs.
Cards can be read by NFC Tools app for status checking.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import argparse
from tap_station.nfc_reader import NFCReader, MockNFCReader
from tap_station.ndef_writer import NDEFWriter, MockNDEFWriter


class NFCCardInitializer:
    """Initialize NFC cards with sequential token IDs and NDEF URLs"""

    def __init__(
        self,
        start_id: int = 1,
        end_id: int = 100,
        base_url: str = None,
        mock: bool = False,
    ):
        """
        Initialize card initializer

        Args:
            start_id: Starting token ID
            end_id: Ending token ID
            base_url: Base URL for status checking (e.g., "https://festival.example.com")
            mock: Use mock NFC reader
        """
        self.start_id = start_id
        self.end_id = end_id
        self.base_url = base_url
        self.current_id = start_id

        # Initialize NFC reader
        if mock:
            self.nfc = MockNFCReader()
            self.ndef = MockNDEFWriter(self.nfc)
            print("Using mock NFC reader (testing mode)")
        else:
            self.nfc = NFCReader()
            self.ndef = NDEFWriter(self.nfc)
            print("PN532 NFC reader initialized")

        self.initialized_cards = []
        self.failed_cards = []

    def run(self):
        """Run card initialization process"""
        total_cards = self.end_id - self.start_id + 1

        print(f"\n{'=' * 60}")
        print(f"Enhanced Card Initialization with NDEF")
        print(f"{'=' * 60}")
        print(
            f"Will initialize {total_cards} cards (ID {self.start_id:03d} to {self.end_id:03d})"
        )

        if self.base_url:
            print(f"NDEF URLs: {self.base_url}/check?token=XXX")
        else:
            print("NDEF URLs: Disabled (use --url to enable)")

        print(f"\nInstructions:")
        print(f"  1. Tap each card on the NFC reader")
        print(f"  2. Wait for confirmation message")
        print(f"  3. Remove card and tap next one")
        print(f"\nPress Ctrl+C to stop at any time\n")

        input("Press Enter to start...")

        try:
            while self.current_id <= self.end_id:
                token_id = f"{self.current_id:03d}"
                self._init_card(token_id)

        except KeyboardInterrupt:
            print("\n\nStopped by user")

        finally:
            self._print_summary()

    def _init_card(self, token_id: str):
        """
        Initialize a single card with NDEF

        Args:
            token_id: Token ID to write (e.g., "001")
        """
        print(
            f"\n[{self.current_id}/{self.end_id}] Waiting for card (Token ID: {token_id})...",
            end="",
            flush=True,
        )

        # Wait for card
        result = self.nfc.wait_for_card(timeout=None)

        if not result:
            print(" TIMEOUT")
            self.failed_cards.append(token_id)
            return

        uid, _ = result
        print(f" Card detected (UID: {uid})")

        # Write NDEF URL if base_url provided
        if self.base_url:
            url = self.ndef.format_status_url(self.base_url, token_id)
            print(f"  Writing NDEF URL: {url}...", end="", flush=True)

            ndef_success = self.ndef.write_url(url, token_id)

            if ndef_success:
                print(" ✓")
            else:
                print(" FAILED")
                self.failed_cards.append(token_id)
                return
        else:
            print("  Skipping NDEF (no URL configured)")

        # Record the mapping
        print(f"  Recording token ID '{token_id}'...", end="", flush=True)

        self.initialized_cards.append(
            {
                "token_id": token_id,
                "uid": uid,
                "url": (
                    self.ndef.format_status_url(self.base_url, token_id)
                    if self.base_url
                    else None
                ),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        self.current_id += 1

        # Save mapping to file
        self._save_mapping()
        print(" ✓")

        # Wait for card removal
        print("  Remove card to continue...", end="", flush=True)
        time.sleep(2)  # Give user time to remove card
        print(" OK")

    def _save_mapping(self):
        """Save UID to token ID mapping to CSV file"""
        mapping_file = "data/card_mapping.csv"

        # Ensure directory exists
        os.makedirs(os.path.dirname(mapping_file), exist_ok=True)

        # Write mapping
        with open(mapping_file, "w") as f:
            if self.base_url:
                f.write("token_id,uid,url,initialized_at\n")
                for card in self.initialized_cards:
                    f.write(
                        f"{card['token_id']},{card['uid']},{card['url']},{card['timestamp']}\n"
                    )
            else:
                f.write("token_id,uid,initialized_at\n")
                for card in self.initialized_cards:
                    f.write(f"{card['token_id']},{card['uid']},{card['timestamp']}\n")

    def _print_summary(self):
        """Print initialization summary"""
        total_attempted = len(self.initialized_cards) + len(self.failed_cards)
        success_count = len(self.initialized_cards)
        fail_count = len(self.failed_cards)

        print(f"\n{'=' * 60}")
        print(f"Initialization Summary")
        print(f"{'=' * 60}")
        print(f"Total attempted: {total_attempted}")
        print(f"Successful:      {success_count} ✓")
        print(f"Failed:          {fail_count} ✗")

        if self.base_url:
            print(f"\nNDEF URLs written: {success_count}")
            print(f"URL format: {self.base_url}/check?token=XXX")

        if fail_count > 0:
            print(f"\nFailed token IDs: {', '.join(self.failed_cards)}")

        print(f"\nCard mapping saved to: data/card_mapping.csv")

        if self.base_url:
            print(f"\n📱 To test with NFC Tools app:")
            print(f"  1. Install NFC Tools (free, iOS/Android)")
            print(f"  2. Tap a card with your phone")
            print(f"  3. Should see URL: {self.base_url}/check?token=XXX")
            print(f"  4. Tap URL to open in browser")

        print(f"{'=' * 60}\n")


def main():
    """Entry point for enhanced card initialization"""
    parser = argparse.ArgumentParser(
        description="Initialize NFC cards with token IDs and NDEF URLs"
    )
    parser.add_argument(
        "--start", type=int, default=1, help="Starting token ID (default: 1)"
    )
    parser.add_argument(
        "--end", type=int, default=100, help="Ending token ID (default: 100)"
    )
    parser.add_argument(
        "--url",
        type=str,
        help="Base URL for status checking (e.g., https://festival.example.com)",
    )
    parser.add_argument(
        "--mock", action="store_true", help="Use mock NFC reader for testing"
    )

    args = parser.parse_args()

    # Validate range
    if args.start < 1 or args.end < args.start:
        print("Error: Invalid token ID range", file=sys.stderr)
        return 1

    # Validate URL if provided
    if args.url:
        if not (args.url.startswith("http://") or args.url.startswith("https://")):
            print("Error: URL must start with http:// or https://", file=sys.stderr)
            return 1

    try:
        initializer = NFCCardInitializer(
            start_id=args.start, end_id=args.end, base_url=args.url, mock=args.mock
        )
        initializer.run()
        return 0

    except Exception as e:
        print(f"\nFatal error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
