"""SQLite database operations for event logging"""

import sqlite3
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


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

        # Ensure directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        # Create database and enable WAL mode
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        if wal_mode:
            self.conn.execute("PRAGMA journal_mode=WAL")
            logger.info("WAL mode enabled for crash resistance")

        self._create_tables()

    def _create_tables(self):
        """Create database tables if they don't exist"""
        self.conn.execute(
            """
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
        """
        )

        # Create index for fast lookups
        self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_token_stage_session
            ON events(token_id, stage, session_id)
        """
        )

        self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_session_timestamp
            ON events(session_id, timestamp)
        """
        )

        # Create table for auto-init token tracking
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auto_init_counter (
                session_id TEXT PRIMARY KEY,
                next_token_id INTEGER NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        self.conn.commit()
        logger.info("Database tables initialized")

    def log_event(
        self,
        token_id: str,
        uid: str,
        stage: str,
        device_id: str,
        session_id: str,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """
        Log an NFC tap event

        Args:
            token_id: Token ID from card (e.g., "001")
            uid: NFC card UID (hex string)
            stage: Stage name (e.g., "QUEUE_JOIN", "EXIT")
            device_id: Station device ID
            session_id: Session ID for this deployment
            timestamp: Event timestamp (defaults to now)

        Returns:
            True if logged successfully, False if duplicate detected
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Check for duplicate (same token, same stage, same session)
        if self._is_duplicate(token_id, stage, session_id):
            logger.warning(f"Duplicate tap detected: token={token_id}, stage={stage}")
            return False

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
            return True

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            self.conn.rollback()
            return False

    def _is_duplicate(self, token_id: str, stage: str, session_id: str) -> bool:
        """
        Check if this token has already been logged at this stage in this session

        Args:
            token_id: Token ID
            stage: Stage name
            session_id: Session ID

        Returns:
            True if duplicate, False otherwise
        """
        cursor = self.conn.execute(
            """
            SELECT COUNT(*) as count
            FROM events
            WHERE token_id = ? AND stage = ? AND session_id = ?
        """,
            (token_id, stage, session_id),
        )

        result = cursor.fetchone()
        return result["count"] > 0

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
            fallback_str = f"E{fallback_id:03d}"  # E prefix indicates error/fallback
            logger.warning(f"Using fallback token ID: {fallback_str}")
            return (fallback_id, fallback_str)

    def export_to_csv(self, output_path: str, session_id: Optional[str] = None) -> int:
        """
        Export events to CSV file

        Args:
            output_path: Path to output CSV file
            session_id: Optional session ID filter

        Returns:
            Number of rows exported
        """
        import csv

        # Build query
        if session_id:
            query = "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp"
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
