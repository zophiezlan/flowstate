"""SQLite database operations for event logging"""

import csv
import functools
import logging
import sqlite3
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .anomaly_detector import AnomalyDetector
from .constants import (
    DatabaseDefaults,
    WorkflowStages,
    get_workflow_transitions,
)
from .datetime_utils import from_iso, minutes_since, to_iso, utc_now
from .path_utils import ensure_parent_dir
from .validation import StageNameValidator, TokenValidator

logger = logging.getLogger(__name__)


def synchronized(method):
    """Decorator to synchronize database methods with threading lock."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


class Database:
    """Handle all SQLite database operations"""

    def __init__(self, db_path: str, wal_mode: bool = True):
        """
        Initialize database connection

        Args:
            db_path: Path to SQLite database file
            wal_mode: Enable WAL mode for crash resistance
        """
        self.db_path = db_path

        # Thread safety lock for concurrent access
        self._lock = threading.RLock()

        # Ensure directory exists (uses centralized path utility)
        ensure_parent_dir(db_path)

        # Create database and enable WAL mode
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        if wal_mode:
            self.conn.execute("PRAGMA journal_mode=WAL")
            logger.info("WAL mode enabled for crash resistance")

        self._create_tables()

        # Initialize anomaly detector
        self.anomaly_detector = AnomalyDetector()

    def _create_tables(self):
        """Create database tables if they don't exist"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_id TEXT NOT NULL,
                uid TEXT NOT NULL,
                stage TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                device_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index for fast lookups
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_token_stage_session
            ON events(token_id, stage, session_id)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_timestamp
            ON events(session_id, timestamp)
        """)

        # Create table for auto-init token tracking
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS auto_init_counter (
                session_id TEXT PRIMARY KEY,
                next_token_id INTEGER NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create table for UID to token ID mapping (prevents duplicates on write failure)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS uid_token_mapping (
                uid TEXT NOT NULL,
                session_id TEXT NOT NULL,
                token_id TEXT NOT NULL,
                assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                write_success INTEGER DEFAULT 0,
                PRIMARY KEY (uid, session_id)
            )
        """)

        # Create audit table for deleted events
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS deleted_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_event_id INTEGER NOT NULL,
                token_id TEXT NOT NULL,
                uid TEXT NOT NULL,
                stage TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                device_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                deleted_by TEXT NOT NULL,
                deletion_reason TEXT,
                original_created_at TEXT
            )
        """)

        # Create index for deleted events lookups
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_deleted_session_token
            ON deleted_events(session_id, token_id)
        """)

        self.conn.commit()
        logger.info("Database tables initialized")

    @synchronized
    def log_event(
        self,
        token_id: str,
        uid: str,
        stage: str,
        device_id: str,
        session_id: str,
        timestamp: Optional[datetime] = None,
        allow_out_of_order: bool = False,
        skip_duplicate_check: bool = False,
    ) -> dict:
        """
        Log an NFC tap event with sequence validation

        Args:
            token_id: Token ID from card (e.g., "001")
            uid: NFC card UID (hex string)
            stage: Stage name (e.g., "QUEUE_JOIN", "EXIT")
            device_id: Station device ID
            session_id: Session ID for this deployment
            timestamp: Event timestamp (defaults to now)
            allow_out_of_order: If True, allow out-of-sequence taps (for manual corrections)
            skip_duplicate_check: If True, skip duplicate checking (for manual corrections)

        Returns:
            Dict with status and details:
            - success: True if logged successfully
            - duplicate: True if duplicate detected
            - out_of_order: True if sequence violation detected
            - warning: Human-readable warning message if applicable
        """
        if timestamp is None:
            timestamp = utc_now()

        result = {
            "success": False,
            "duplicate": False,
            "out_of_order": False,
            "warning": None,
        }

        # Input validation
        try:
            # Validate token_id format
            if not TokenValidator.is_valid_token_id(token_id):
                logger.warning(f"Invalid token_id format: {token_id}")
                result["warning"] = f"Invalid token ID format: {token_id}"
                # Still allow it to proceed for backward compatibility

            # Validate and normalize stage
            try:
                stage = StageNameValidator.validate_stage_or_raise(stage)
            except ValueError as e:
                logger.error(f"Invalid stage: {e}")
                result["warning"] = str(e)
                return result

        except Exception as e:
            logger.error(f"Validation error: {e}")
            result["warning"] = f"Validation error: {str(e)}"
            return result

        # Check for duplicate (same token, same stage, same session)
        # Skip this check for manual corrections where staff intentionally add events
        if not skip_duplicate_check and self._is_duplicate(
            token_id, stage, session_id
        ):
            logger.warning(
                f"Duplicate tap detected: token={token_id}, stage={stage}"
            )
            result["duplicate"] = True
            result["warning"] = f"Card already tapped at {stage}"
            return result

        # Validate sequence unless explicitly allowed to bypass
        if not allow_out_of_order:
            sequence_check = self._validate_sequence(
                token_id, stage, session_id
            )
            if not sequence_check["valid"]:
                logger.warning(
                    f"Out-of-order tap detected: token={token_id}, "
                    f"stage={stage}, reason={sequence_check['reason']}"
                )
                result["out_of_order"] = True
                result["warning"] = sequence_check["reason"]
                result["suggestion"] = sequence_check.get("suggestion")
                # Still log the event but mark it with warning
                # This allows data collection while alerting staff

        # Insert event
        timestamp_str = timestamp.isoformat()

        try:
            self.conn.execute(
                """
                INSERT INTO events (token_id, uid, stage, timestamp, device_id, session_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (token_id, uid, stage, timestamp_str, device_id, session_id),
            )

            self.conn.commit()
            logger.info(
                f"Logged event: token={token_id}, stage={stage}, device={device_id}"
            )
            result["success"] = True
            return result

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            self.conn.rollback()
            result["warning"] = f"Database error: {str(e)}"
            return result

    def _is_duplicate(
        self,
        token_id: str,
        stage: str,
        session_id: str,
        grace_minutes: int = DatabaseDefaults.GRACE_PERIOD_MINUTES,
    ) -> bool:
        """
        Check if this token has already been logged at this stage in this session
        Provides a grace period to allow corrections

        Args:
            token_id: Token ID
            stage: Stage name
            session_id: Session ID
            grace_minutes: Minutes before considering it a true duplicate (allows corrections)

        Returns:
            True if duplicate (outside grace period), False otherwise
        """
        cursor = self.conn.execute(
            """
            SELECT timestamp
            FROM events
            WHERE token_id = ? AND stage = ? AND session_id = ?
            ORDER BY datetime(timestamp) DESC
            LIMIT 1
        """,
            (token_id, stage, session_id),
        )

        result = cursor.fetchone()

        if not result:
            return False  # No previous tap, not a duplicate

        # Check if within grace period using datetime utilities
        mins_elapsed = minutes_since(result["timestamp"])

        # If within grace period, allow it (not a duplicate)
        # This helps with accidental taps at wrong station
        if mins_elapsed <= grace_minutes:
            logger.info(
                f"Tap within {grace_minutes}min grace period: "
                f"token={token_id}, stage={stage}, "
                f"last_tap={mins_elapsed:.1f}min ago - allowing correction"
            )
            return False

        # Outside grace period - true duplicate
        return True

    def _validate_sequence(
        self, token_id: str, stage: str, session_id: str
    ) -> dict:
        """
        Validate that this tap makes sense given the card's journey so far
        Implements state machine logic to catch human errors

        Args:
            token_id: Token ID
            stage: Stage being tapped
            session_id: Session ID

        Returns:
            Dict with 'valid' (bool), 'reason' (str), and 'suggestion' (str)
        """
        # Get all existing stages for this token in this session
        cursor = self.conn.execute(
            """
            SELECT stage, timestamp
            FROM events
            WHERE token_id = ? AND session_id = ?
            ORDER BY datetime(timestamp) ASC
        """,
            (token_id, session_id),
        )

        existing_stages = [row["stage"] for row in cursor.fetchall()]

        # Use centralized workflow transitions for validation
        transitions = get_workflow_transitions()
        return transitions.validate_sequence(existing_stages, stage)

    @synchronized
    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent events for monitoring

        Args:
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM events
            ORDER BY datetime(timestamp) DESC, id DESC
            LIMIT ?
        """,
            (limit,),
        )

        return [dict(row) for row in cursor.fetchall()]

    @synchronized
    def get_anomalies(self, session_id: str) -> Dict[str, Any]:
        """
        Detect various human error patterns and anomalies in real-time.

        This method now delegates most detection logic to AnomalyDetector class.

        Args:
            session_id: Session ID to check

        Returns:
            Dict with various anomaly categories and counts
        """
        # Use the anomaly detector for most detection logic
        anomalies = self.anomaly_detector.get_anomalies(self.conn, session_id)

        # Add incomplete journeys detection (database-specific query)
        try:
            sql = """
                SELECT token_id, 
                       GROUP_CONCAT(stage, ' → ') as journey,
                       COUNT(*) as tap_count,
                       MAX(timestamp) as last_tap
                FROM events
                WHERE session_id = ?
                GROUP BY token_id
                HAVING MAX(CASE WHEN stage = ? THEN 1 ELSE 0 END) = 0
                ORDER BY datetime(last_tap) DESC
            """
            cursor = self.conn.execute(sql, (session_id, WorkflowStages.EXIT))

            for row in cursor.fetchall():
                anomalies["incomplete_journeys"].append(
                    {
                        "token_id": row["token_id"],
                        "journey": row["journey"],
                        "tap_count": row["tap_count"],
                        "last_tap": row["last_tap"],
                        "severity": "medium",
                        "suggestion": "Journey incomplete - missing EXIT tap",
                    }
                )
        except Exception as e:
            logger.error(
                f"Error detecting incomplete journeys: {e}", exc_info=True
            )

        try:
            # Detect out-of-order events
            sql = """
                SELECT e.token_id, e.stage, e.timestamp, e.device_id,
                       (SELECT GROUP_CONCAT(stage, ' → ')
                        FROM (SELECT stage FROM events 
                              WHERE token_id = e.token_id 
                                AND session_id = e.session_id
                                AND datetime(timestamp) <= datetime(e.timestamp)
                              ORDER BY datetime(timestamp), id)
                       ) as sequence_so_far
                FROM events e
                WHERE e.session_id = ?
                    AND e.timestamp > datetime('now', '-1 hour')
                ORDER BY e.timestamp DESC
            """
            cursor = self.conn.execute(sql, (session_id,))

            workflow = get_workflow_transitions()
            for row in cursor.fetchall():
                # Parse sequence and check validity
                stages = (
                    row["sequence_so_far"].split(" → ")
                    if row["sequence_so_far"]
                    else []
                )
                if len(stages) > 1:
                    # Check if the last transition was valid
                    prev_stage = stages[-2]
                    curr_stage = stages[-1]

                    if not workflow.is_valid_transition(
                        prev_stage, curr_stage
                    ):
                        anomalies["out_of_order_events"].append(
                            {
                                "token_id": row["token_id"],
                                "stage": row["stage"],
                                "timestamp": row["timestamp"],
                                "sequence": row["sequence_so_far"],
                                "severity": "medium",
                                "suggestion": f"Invalid transition: {prev_stage} → {curr_stage}",
                            }
                        )
        except Exception as e:
            logger.error(
                f"Error detecting out-of-order events: {e}", exc_info=True
            )

        # Calculate summary statistics
        summary = {
            "total_anomalies": sum(
                len(v) for v in anomalies.values() if isinstance(v, list)
            ),
            "high_severity": sum(
                1
                for category in anomalies.values()
                if isinstance(category, list)
                for item in category
                if isinstance(item, dict) and item.get("severity") == "high"
            ),
            "medium_severity": sum(
                1
                for category in anomalies.values()
                if isinstance(category, list)
                for item in category
                if isinstance(item, dict) and item.get("severity") == "medium"
            ),
            "low_severity": sum(
                1
                for category in anomalies.values()
                if isinstance(category, list)
                for item in category
                if isinstance(item, dict) and item.get("severity") == "low"
            ),
        }
        anomalies["summary"] = summary

        return anomalies

    @synchronized
    def get_event_count(self, session_id: Optional[str] = None) -> int:
        """
        Get total event count, optionally filtered by session

        Args:
            session_id: Optional session ID filter

        Returns:
            Event count
        """
        if session_id:
            cursor = self.conn.execute(
                "SELECT COUNT(*) as count FROM events WHERE session_id = ?",
                (session_id,),
            )
        else:
            cursor = self.conn.execute("SELECT COUNT(*) as count FROM events")

        return cursor.fetchone()["count"]

    @synchronized
    def get_participant_tap_count(self, token_id: str, session_id: str) -> int:
        """
        Get the number of taps for a specific participant in a session

        This is used for failover stage alternation to determine which stage
        should handle the next tap (odd taps vs even taps).

        Args:
            token_id: Token ID to count taps for
            session_id: Session ID to filter by

        Returns:
            Number of taps for this participant in this session
        """
        cursor = self.conn.execute(
            "SELECT COUNT(*) as count FROM events WHERE token_id = ? AND session_id = ?",
            (token_id, session_id),
        )
        row = cursor.fetchone()
        return row["count"] if row else 0

    @synchronized
    def add_manual_event(
        self,
        token_id: str,
        stage: str,
        timestamp: datetime,
        session_id: str,
        operator_id: str,
        reason: str,
    ) -> dict:
        """
        Manually add a missed event (for staff corrections)

        Args:
            token_id: Token ID
            stage: Stage name
            timestamp: When the event should have occurred
            session_id: Session ID
            operator_id: ID of staff member making correction
            reason: Why this manual event is being added

        Returns:
            Dict with success status and details
        """
        uid = f"MANUAL_{operator_id}"
        device_id = f"manual_correction"

        # Log the manual addition
        logger.info(
            f"Manual event addition: token={token_id}, stage={stage}, "
            f"operator={operator_id}, reason={reason}"
        )

        # Use allow_out_of_order=True to bypass sequence validation
        # Use skip_duplicate_check=True to allow staff to intentionally add duplicate corrections
        result = self.log_event(
            token_id=token_id,
            uid=uid,
            stage=stage,
            device_id=device_id,
            session_id=session_id,
            timestamp=timestamp,
            allow_out_of_order=True,
            skip_duplicate_check=True,
        )

        if result["success"]:
            # Log to audit trail (you could create a separate audit table)
            logger.info(
                f"✓ Manual event added successfully: {token_id} at {stage}, "
                f"backdated to {timestamp.isoformat()}"
            )

        return result

    @synchronized
    def remove_event(
        self,
        event_id: int,
        operator_id: str,
        reason: str,
    ) -> dict:
        """
        Remove an incorrect event with full audit trail

        Args:
            event_id: ID of event to remove
            operator_id: ID of staff member making correction
            reason: Why this event is being removed

        Returns:
            Dict with success status
        """
        try:
            # First, get the event details for audit log
            cursor = self.conn.execute(
                "SELECT * FROM events WHERE id = ?",
                (event_id,),
            )
            event = cursor.fetchone()

            if not event:
                return {
                    "success": False,
                    "error": f"Event {event_id} not found",
                }

            # Log the removal
            logger.warning(
                f"Manual event removal: id={event_id}, token={event['token_id']}, "
                f"stage={event['stage']}, operator={operator_id}, reason={reason}"
            )

            # Archive to deleted_events table before deletion
            self.conn.execute(
                """
                INSERT INTO deleted_events 
                (original_event_id, token_id, uid, stage, timestamp, device_id, 
                 session_id, deleted_by, deletion_reason, original_created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["id"],
                    event["token_id"],
                    event["uid"],
                    event["stage"],
                    event["timestamp"],
                    event["device_id"],
                    event["session_id"],
                    operator_id,
                    reason,
                    event["created_at"],
                ),
            )

            # Delete the event
            self.conn.execute(
                "DELETE FROM events WHERE id = ?",
                (event_id,),
            )
            self.conn.commit()

            logger.info(
                f"✓ Event {event_id} removed and archived to deleted_events table"
            )

            return {
                "success": True,
                "removed_event": dict(event),
            }

        except sqlite3.Error as e:
            logger.error(f"Failed to remove event {event_id}: {e}")
            self.conn.rollback()
            return {
                "success": False,
                "error": str(e),
            }

    @synchronized
    def get_next_auto_init_token_id(
        self, session_id: str, start_id: int = 1
    ) -> tuple[int, str]:
        """
        Get and increment the next available token ID for auto-initialization

        Args:
            session_id: Session ID
            start_id: Starting token ID if not yet initialized

        Returns:
            Tuple of (next_token_id as int, token_id as formatted string)
        """
        try:
            # Use a transaction to ensure atomicity and prevent race conditions
            # This ensures that even with concurrent access, each card gets a unique ID
            cursor = self.conn.cursor()

            # Try to get existing counter
            cursor.execute(
                "SELECT next_token_id FROM auto_init_counter WHERE session_id = ?",
                (session_id,),
            )
            row = cursor.fetchone()

            if row:
                # Use existing counter
                next_id = row["next_token_id"]

                # Increment counter atomically
                cursor.execute(
                    """
                    UPDATE auto_init_counter
                    SET next_token_id = next_token_id + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                """,
                    (session_id,),
                )
            else:
                # Initialize counter for this session
                next_id = start_id
                cursor.execute(
                    """
                    INSERT INTO auto_init_counter (session_id, next_token_id, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                    (session_id, next_id + 1),
                )

            self.conn.commit()

            # Format as 3-digit string
            token_id_str = f"{next_id:03d}"
            logger.info(
                f"Auto-assigned token ID {token_id_str} for session {session_id}"
            )

            return (next_id, token_id_str)

        except sqlite3.Error as e:
            logger.error(f"Failed to get next auto-init token ID: {e}")
            self.conn.rollback()

            # Return a fallback using UUID to ensure uniqueness
            fallback_id = abs(hash(str(uuid.uuid4()))) % 10000
            fallback_str = (
                f"E{fallback_id:03d}"  # E prefix indicates error/fallback
            )
            logger.warning(f"Using fallback token ID: {fallback_str}")
            return (fallback_id, fallback_str)

    @synchronized
    def get_token_for_uid(self, uid: str, session_id: str) -> Optional[str]:
        """
        Check if a UID already has a token ID assigned.

        Args:
            uid: Card UID
            session_id: Session ID

        Returns:
            Token ID if mapping exists, None otherwise
        """
        cursor = self.conn.execute(
            "SELECT token_id FROM uid_token_mapping WHERE uid = ? AND session_id = ?",
            (uid, session_id),
        )
        row = cursor.fetchone()
        return row["token_id"] if row else None

    @synchronized
    def save_uid_token_mapping(
        self, uid: str, token_id: str, session_id: str, write_success: bool = False
    ) -> bool:
        """
        Save a UID to token ID mapping.

        Args:
            uid: Card UID
            token_id: Assigned token ID
            session_id: Session ID
            write_success: Whether the token was successfully written to the card

        Returns:
            True if saved successfully
        """
        try:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO uid_token_mapping
                (uid, session_id, token_id, assigned_at, write_success)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
                """,
                (uid, session_id, token_id, 1 if write_success else 0),
            )
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Failed to save UID token mapping: {e}")
            return False

    @synchronized
    def update_uid_token_mapping_write_success(self, uid: str, session_id: str) -> bool:
        """
        Mark a UID token mapping as successfully written to card.

        Args:
            uid: Card UID
            session_id: Session ID

        Returns:
            True if updated successfully
        """
        try:
            self.conn.execute(
                "UPDATE uid_token_mapping SET write_success = 1 WHERE uid = ? AND session_id = ?",
                (uid, session_id),
            )
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Failed to update UID token mapping: {e}")
            return False

    def get_or_create_token_for_uid(
        self, uid: str, session_id: str, start_id: int = 1
    ) -> Tuple[str, bool]:
        """
        Get existing token for a UID, or create and assign a new one.

        This prevents duplicate token assignments when card writing fails.
        If the same UID is seen again, it reuses the previously assigned token.

        Args:
            uid: Card UID
            session_id: Session ID
            start_id: Starting token ID if creating new assignment

        Returns:
            Tuple of (token_id, is_new) where is_new indicates if a new token was assigned
        """
        # Check if this UID already has a token assigned
        existing = self.get_token_for_uid(uid, session_id)
        if existing:
            logger.info(f"Reusing existing token {existing} for UID {uid}")
            return (existing, False)

        # Assign new token ID
        _, token_id = self.get_next_auto_init_token_id(session_id, start_id)

        # Save mapping (write_success=False until card write is confirmed)
        self.save_uid_token_mapping(uid, token_id, session_id, write_success=False)

        logger.info(f"Assigned new token {token_id} to UID {uid}")
        return (token_id, True)

    @synchronized
    def export_to_csv(
        self, output_path: str, session_id: Optional[str] = None
    ) -> int:
        """
        Export events to CSV file

        Args:
            output_path: Path to output CSV file
            session_id: Optional session ID filter

        Returns:
            Number of rows exported
        """
        # Build query
        if session_id:
            query = (
                "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp"
            )
            params = (session_id,)
        else:
            query = "SELECT * FROM events ORDER BY timestamp"
            params = ()

        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()

        if not rows:
            logger.warning("No events to export")
            return 0

        # Write CSV
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(rows[0].keys())

            # Data
            for row in rows:
                writer.writerow(row)

        logger.info(f"Exported {len(rows)} events to {output_path}")
        return len(rows)

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
