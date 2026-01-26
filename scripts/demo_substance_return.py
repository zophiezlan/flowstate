#!/usr/bin/env python3
"""
Demo script showing substance return confirmation workflow

This demonstrates how the system tracks substance custody and return.
"""

import sys
import os
import tempfile
from datetime import datetime, timezone, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tap_station.database import Database


def demo_substance_return_workflow():
    """Demonstrate a complete substance return workflow"""

    print("=" * 70)
    print("SUBSTANCE RETURN CONFIRMATION SYSTEM - DEMO")
    print("=" * 70)
    print()

    # Create temporary database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        db = Database(db_path, wal_mode=True)
        session_id = "demo-festival-2026"
        now = datetime.now(timezone.utc)

        print("Scenario: Participant brings substance for testing")
        print("-" * 70)
        print()

        # Participant 1: Complete workflow
        print("👤 Participant #042 arrives")
        print()

        # Stage 1: Join queue
        print("1️⃣  QUEUE_JOIN (12:00 PM)")
        print("   → Participant taps card at entry")
        print("   → Substance: In participant's possession")
        db.log_event(
            token_id="042",
            uid="ABCD1234",
            stage="QUEUE_JOIN",
            device_id="station1",
            session_id=session_id,
            timestamp=now,
        )
        print("   ✓ Logged\n")

        # Stage 2: Service starts
        print("2️⃣  SERVICE_START (12:10 PM - waited 10 minutes)")
        print("   → Staff receives substance from participant")
        print("   → Substance: In staff custody")
        print("   → Staff taps participant's card")
        print("   → Testing begins...")
        db.log_event(
            token_id="042",
            uid="ABCD1234",
            stage="SERVICE_START",
            device_id="station2",
            session_id=session_id,
            timestamp=now + timedelta(minutes=10),
        )
        print("   ✓ Logged\n")

        # Stage 3: Substance returned
        print("3️⃣  SUBSTANCE_RETURNED (12:18 PM - service took 8 minutes)")
        print("   → Testing complete, results discussed")
        print("   → Staff physically hands substance back to participant")
        print("   → Substance: Returned to participant ✓")
        print("   → Staff taps card to confirm return")
        db.log_event(
            token_id="042",
            uid="ABCD1234",
            stage="SUBSTANCE_RETURNED",
            device_id="station3",
            session_id=session_id,
            timestamp=now + timedelta(minutes=18),
        )
        print("   ✓ Logged (ACCOUNTABILITY CONFIRMED)\n")

        # Stage 4: Exit
        print("4️⃣  EXIT (12:19 PM)")
        print("   → Participant taps at exit")
        print("   → Substance: Participant leaves with substance")
        db.log_event(
            token_id="042",
            uid="ABCD1234",
            stage="EXIT",
            device_id="station4",
            session_id=session_id,
            timestamp=now + timedelta(minutes=19),
        )
        print("   ✓ Logged\n")

        print("=" * 70)
        print("JOURNEY COMPLETE")
        print("=" * 70)
        print()

        # Calculate metrics
        events = db.get_recent_events(limit=10)

        print("📊 Metrics:")
        print(f"   • Total time: 19 minutes")
        print(f"   • Queue wait: 10 minutes")
        print(f"   • Service time: 8 minutes")
        print(f"   • Return confirmation: 1 minute")
        print()

        print("✅ Benefits Demonstrated:")
        print("   • Complete audit trail of substance custody")
        print("   • Timestamped proof of return")
        print("   • No risk of substance being forgotten")
        print("   • Staff accountability")
        print("   • Participant trust")
        print()

        # Now demonstrate alert scenario
        print("=" * 70)
        print("SCENARIO 2: Unreturned Substance Alert")
        print("=" * 70)
        print()

        print("👤 Participant #067 arrives")
        print()

        # Queue join
        print("1️⃣  QUEUE_JOIN (12:30 PM)")
        db.log_event(
            token_id="067",
            uid="EFGH5678",
            stage="QUEUE_JOIN",
            device_id="station1",
            session_id=session_id,
            timestamp=now + timedelta(minutes=30),
        )
        print("   ✓ Logged\n")

        # Service starts
        print("2️⃣  SERVICE_START (12:40 PM)")
        print("   → Staff receives substance")
        print("   → Substance: In staff custody")
        db.log_event(
            token_id="067",
            uid="EFGH5678",
            stage="SERVICE_START",
            device_id="station2",
            session_id=session_id,
            timestamp=now + timedelta(minutes=40),
        )
        print("   ✓ Logged\n")

        print("   ⏱️  Time passes... (35 minutes)")
        print()

        # Check for unreturned substances
        print("🔍 Checking for unreturned substances...")
        print()

        # Use LEFT JOIN for better performance than NOT IN
        cursor = db.conn.execute(
            """
            SELECT 
                e.token_id,
                e.timestamp,
                (julianday('now') - julianday(e.timestamp)) * 24 * 60 as minutes_ago
            FROM events e
            LEFT JOIN events r ON e.token_id = r.token_id 
                              AND r.session_id = ?
                              AND r.stage = 'SUBSTANCE_RETURNED'
            WHERE e.session_id = ?
              AND e.stage = 'SERVICE_START'
              AND r.token_id IS NULL
            """,
            (session_id, session_id),
        )

        unreturned = cursor.fetchall()

        if unreturned:
            print("⚠️  ALERT: Unreturned Substances Detected!")
            print()
            for row in unreturned:
                print(f"   🚨 Token #{row['token_id']}")
                print(f"      Service started: {row['timestamp'][:19]}")
                print(f"      Status: AWAITING RETURN")
                print(f"      Action: Staff should return substance immediately")
            print()

        print("💡 This alert would appear on the dashboard, allowing")
        print("   coordinators to follow up and ensure no substances")
        print("   are left behind.")
        print()

        # Now return the substance
        print("3️⃣  SUBSTANCE_RETURNED (12:42 PM)")
        print("   → Coordinator follows up")
        print("   → Substance returned to participant")
        db.log_event(
            token_id="067",
            uid="EFGH5678",
            stage="SUBSTANCE_RETURNED",
            device_id="station3",
            session_id=session_id,
            timestamp=now + timedelta(minutes=42),
        )
        print("   ✓ Alert resolved!\n")

        print("=" * 70)
        print("DEMO COMPLETE")
        print("=" * 70)
        print()

        print("Key Takeaways:")
        print("1. SUBSTANCE_RETURNED stage creates accountability")
        print("2. System tracks custody chain automatically")
        print("3. Alerts prevent substances from being forgotten")
        print("4. Builds trust between participants and service")
        print("5. No additional hardware needed - works with existing system")
        print()

        # Cleanup
        db.close()

    finally:
        # Clean up database files
        if os.path.exists(db_path):
            os.unlink(db_path)
        for ext in ["-wal", "-shm"]:
            wal_path = db_path + ext
            if os.path.exists(wal_path):
                os.unlink(wal_path)


if __name__ == "__main__":
    demo_substance_return_workflow()
