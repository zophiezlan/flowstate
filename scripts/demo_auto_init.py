#!/usr/bin/env python3
"""
Demo script to show auto-initialization feature in action

This script simulates the auto-init feature by:
1. Creating a test database
2. Simulating uninitialized card taps
3. Showing how sequential token IDs are assigned
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
from tap_station.database import Database


def demo_auto_init():
    """Demonstrate auto-initialization feature"""

    print("=" * 70)
    print("Auto-Initialize Cards on First Tap - Demo")
    print("=" * 70)
    print()

    # Create temporary database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        db = Database(db_path, wal_mode=False)
        session_id = "demo-festival-2026"

        print("Scenario: Festival event with auto-initialization enabled")
        print(f"Session: {session_id}")
        print()

        # Simulate uninitialized cards being tapped
        print("Simulating card taps:")
        print("-" * 70)

        cards = [
            ("04A32FB2C15080", "First participant - blank card"),
            ("05B43AC3D26091", "Second participant - blank card"),
            ("06C54AD4E37102", "Third participant - blank card"),
            ("07D65AE5F48213", "Fourth participant - blank card"),
            ("04112233445566", "Fifth participant - blank card"),
        ]

        assigned_tokens = []

        for i, (uid, description) in enumerate(cards, 1):
            # Get next auto-assigned token ID
            token_num, token_id = db.get_next_auto_init_token_id(
                session_id=session_id, start_id=1
            )

            assigned_tokens.append((uid, token_id, description))

            # Log the event
            db.log_event(
                token_id=token_id,
                uid=uid,
                stage="QUEUE_JOIN",
                device_id="station1",
                session_id=session_id,
            )

            print(f"Card {i}:")
            print(f"  Description: {description}")
            print(f"  UID: {uid}")
            print(f"  Assigned Token ID: {token_id}")
            print()

        print("-" * 70)
        print()

        # Show what happens with pre-initialized cards mixed in
        print("Now showing mixed scenario (pre-initialized + blank cards):")
        print("-" * 70)

        # Create a new session for clean demo
        session_id2 = "demo-mixed-2026"

        mixed_cards = [
            ("08E76BF6A59324", "050", "Pre-initialized card #050", False),
            ("09F87CA7B60435", "09F87CA7", "Blank card (will auto-init)", True),
            ("0AA98DA8C71546", "025", "Pre-initialized card #025", False),
            ("0BB09EA9D82657", "0BB09EA9", "Blank card (will auto-init)", True),
        ]

        # Start auto-init from 100 to avoid conflicts
        auto_init_counter = 100

        for i, (uid, token_id, description, is_blank) in enumerate(mixed_cards, 1):
            if is_blank:
                # Auto-assign
                _, new_token_id = db.get_next_auto_init_token_id(
                    session_id=session_id2, start_id=auto_init_counter
                )
                final_token_id = new_token_id
                status = "AUTO-ASSIGNED"
            else:
                # Keep pre-initialized ID
                final_token_id = token_id
                status = "PRE-INITIALIZED"

            db.log_event(
                token_id=final_token_id,
                uid=uid,
                stage="QUEUE_JOIN",
                device_id="station1",
                session_id=session_id2,
            )

            print(f"Card {i}:")
            print(f"  Description: {description}")
            print(f"  UID: {uid}")
            print(f"  Token ID: {final_token_id} ({status})")
            print()

        print("-" * 70)
        print()

        # Show summary
        print("Summary:")
        print(
            f"  Session 1 ({session_id}): {len(cards)} cards auto-initialized (001-005)"
        )
        print(
            f"  Session 2 ({session_id2}): 2 pre-init cards + 2 auto-init cards (100-101)"
        )
        print()

        print("Benefits:")
        print("  ✅ No need to pre-initialize hundreds of cards")
        print("  ✅ Can mix pre-initialized and blank cards")
        print("  ✅ Sequential numbering continues even if cards are lost/stolen")
        print("  ✅ Each session maintains independent counter")
        print()

        print("Configuration to enable:")
        print("  config.yaml:")
        print("    nfc:")
        print("      auto_init_cards: true")
        print("      auto_init_start_id: 1")
        print()

        db.close()

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    print("=" * 70)
    print("Demo complete!")
    print("See docs/AUTO_INIT_CARDS.md for full documentation")
    print("=" * 70)


if __name__ == "__main__":
    demo_auto_init()
