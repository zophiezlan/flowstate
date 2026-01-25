"""
Data Integrity Verification

This module provides data integrity features including:
- Event checksums for tamper detection
- Database integrity verification
- Audit trail integrity
- Data consistency checks

These features ensure data quality and enable trust in collected data
for harm reduction reporting and analysis.
"""

import hashlib
import hmac
import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .datetime_utils import utc_now, to_iso

logger = logging.getLogger(__name__)


class IntegrityStatus(Enum):
    """Status of integrity verification"""
    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN = "unknown"
    ERROR = "error"


@dataclass
class IntegrityCheckResult:
    """Result of an integrity check"""
    status: IntegrityStatus
    checked_at: datetime
    details: str = ""
    issues: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return self.status == IntegrityStatus.VALID

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "checked_at": to_iso(self.checked_at),
            "details": self.details,
            "issues": self.issues,
            "is_valid": self.is_valid,
            "metadata": self.metadata
        }


class ChecksumCalculator:
    """
    Calculates checksums for data integrity verification.

    Supports multiple algorithms and can generate both simple checksums
    and HMACs with secret keys for tamper detection.
    """

    ALGORITHMS = {
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512,
        "md5": hashlib.md5,
        "blake2b": hashlib.blake2b,
    }

    def __init__(
        self,
        algorithm: str = "sha256",
        secret_key: Optional[str] = None
    ):
        """
        Initialize checksum calculator.

        Args:
            algorithm: Hash algorithm to use
            secret_key: Optional secret for HMAC calculation
        """
        if algorithm not in self.ALGORITHMS:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        self._algorithm = algorithm
        self._hash_func = self.ALGORITHMS[algorithm]
        self._secret_key = secret_key.encode() if secret_key else None

    def calculate(self, data: Any) -> str:
        """
        Calculate checksum for data.

        Args:
            data: Data to checksum (will be JSON serialized)

        Returns:
            Hex-encoded checksum string
        """
        # Normalize data to JSON for consistent hashing
        normalized = self._normalize(data)
        data_bytes = normalized.encode('utf-8')

        if self._secret_key:
            # Use HMAC for keyed checksum
            return hmac.new(
                self._secret_key,
                data_bytes,
                self._hash_func
            ).hexdigest()
        else:
            # Use simple hash
            return self._hash_func(data_bytes).hexdigest()

    def verify(self, data: Any, expected_checksum: str) -> bool:
        """
        Verify data against expected checksum.

        Args:
            data: Data to verify
            expected_checksum: Expected checksum value

        Returns:
            True if checksum matches
        """
        actual = self.calculate(data)
        return hmac.compare_digest(actual, expected_checksum)

    def _normalize(self, data: Any) -> str:
        """Normalize data to a consistent string representation"""
        if isinstance(data, str):
            return data
        elif isinstance(data, (dict, list)):
            return json.dumps(data, sort_keys=True, default=str)
        else:
            return str(data)


@dataclass
class EventChecksum:
    """Checksum record for an event"""
    event_id: int
    checksum: str
    algorithm: str
    created_at: datetime
    fields_included: List[str]


class IntegrityManager:
    """
    Manages data integrity verification for the tap station.

    Features:
    - Event checksums for tamper detection
    - Chain verification for audit trails
    - Database integrity checks
    - Consistency validation
    """

    # Fields included in event checksums
    EVENT_CHECKSUM_FIELDS = [
        "token_id", "uid", "stage", "timestamp",
        "device_id", "session_id"
    ]

    def __init__(
        self,
        conn: sqlite3.Connection,
        secret_key: Optional[str] = None,
        algorithm: str = "sha256"
    ):
        """
        Initialize integrity manager.

        Args:
            conn: Database connection
            secret_key: Secret key for HMAC checksums
            algorithm: Hash algorithm to use
        """
        self._conn = conn
        self._calculator = ChecksumCalculator(algorithm, secret_key)
        self._algorithm = algorithm
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create integrity-related tables if needed"""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS event_checksums (
                event_id INTEGER PRIMARY KEY,
                checksum TEXT NOT NULL,
                algorithm TEXT NOT NULL,
                created_at TEXT NOT NULL,
                previous_checksum TEXT
            )
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS integrity_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_type TEXT NOT NULL,
                status TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                details TEXT,
                issues_json TEXT
            )
        """)

        self._conn.commit()

    def calculate_event_checksum(self, event: Dict[str, Any]) -> str:
        """
        Calculate checksum for an event.

        Args:
            event: Event data dictionary

        Returns:
            Checksum string
        """
        # Extract only the fields we want to checksum
        checksum_data = {
            k: event.get(k) for k in self.EVENT_CHECKSUM_FIELDS
        }
        return self._calculator.calculate(checksum_data)

    def store_event_checksum(
        self,
        event_id: int,
        event_data: Dict[str, Any],
        chain: bool = True
    ) -> str:
        """
        Calculate and store checksum for an event.

        Args:
            event_id: Database ID of the event
            event_data: Event data dictionary
            chain: Include previous checksum in chain

        Returns:
            The calculated checksum
        """
        checksum = self.calculate_event_checksum(event_data)

        # Get previous checksum for chaining
        previous = None
        if chain:
            cursor = self._conn.execute("""
                SELECT checksum FROM event_checksums
                ORDER BY event_id DESC LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                previous = row[0]
                # Include previous in current checksum for chain
                chain_data = {"event": event_data, "previous": previous}
                checksum = self._calculator.calculate(chain_data)

        self._conn.execute("""
            INSERT OR REPLACE INTO event_checksums
            (event_id, checksum, algorithm, created_at, previous_checksum)
            VALUES (?, ?, ?, ?, ?)
        """, (event_id, checksum, self._algorithm, to_iso(utc_now()), previous))

        self._conn.commit()
        return checksum

    def verify_event(self, event_id: int) -> IntegrityCheckResult:
        """
        Verify integrity of a single event.

        Args:
            event_id: ID of the event to verify

        Returns:
            Integrity check result
        """
        issues = []

        try:
            # Get event data
            cursor = self._conn.execute(
                "SELECT * FROM events WHERE id = ?",
                (event_id,)
            )
            event_row = cursor.fetchone()
            if not event_row:
                return IntegrityCheckResult(
                    status=IntegrityStatus.ERROR,
                    checked_at=utc_now(),
                    details=f"Event {event_id} not found"
                )

            event = dict(event_row)

            # Get stored checksum
            cursor = self._conn.execute(
                "SELECT * FROM event_checksums WHERE event_id = ?",
                (event_id,)
            )
            checksum_row = cursor.fetchone()
            if not checksum_row:
                return IntegrityCheckResult(
                    status=IntegrityStatus.UNKNOWN,
                    checked_at=utc_now(),
                    details="No checksum stored for event",
                    issues=["Missing checksum record"]
                )

            # Verify checksum
            stored_checksum = checksum_row["checksum"]
            previous_checksum = checksum_row["previous_checksum"]

            if previous_checksum:
                # Verify chained checksum
                chain_data = {"event": event, "previous": previous_checksum}
                calculated = self._calculator.calculate(chain_data)
            else:
                calculated = self.calculate_event_checksum(event)

            if calculated != stored_checksum:
                issues.append("Checksum mismatch - data may have been modified")
                return IntegrityCheckResult(
                    status=IntegrityStatus.INVALID,
                    checked_at=utc_now(),
                    details="Event data integrity check failed",
                    issues=issues,
                    metadata={
                        "event_id": event_id,
                        "stored": stored_checksum,
                        "calculated": calculated
                    }
                )

            return IntegrityCheckResult(
                status=IntegrityStatus.VALID,
                checked_at=utc_now(),
                details="Event integrity verified",
                metadata={"event_id": event_id}
            )

        except Exception as e:
            logger.error(f"Error verifying event {event_id}: {e}")
            return IntegrityCheckResult(
                status=IntegrityStatus.ERROR,
                checked_at=utc_now(),
                details=str(e)
            )

    def verify_chain(
        self,
        session_id: Optional[str] = None,
        limit: int = 1000
    ) -> IntegrityCheckResult:
        """
        Verify integrity chain for events.

        Args:
            session_id: Optional session to verify
            limit: Maximum events to check

        Returns:
            Integrity check result
        """
        issues = []
        verified_count = 0

        try:
            query = """
                SELECT e.*, c.checksum, c.previous_checksum
                FROM events e
                LEFT JOIN event_checksums c ON e.id = c.event_id
            """
            params = []

            if session_id:
                query += " WHERE e.session_id = ?"
                params.append(session_id)

            query += " ORDER BY e.id ASC LIMIT ?"
            params.append(limit)

            cursor = self._conn.execute(query, params)
            rows = cursor.fetchall()

            previous_checksum = None
            for row in rows:
                event = dict(row)
                stored_checksum = event.pop("checksum", None)
                expected_previous = event.pop("previous_checksum", None)

                if stored_checksum is None:
                    issues.append(f"Missing checksum for event {event['id']}")
                    continue

                # Verify chain link
                if expected_previous and expected_previous != previous_checksum:
                    issues.append(
                        f"Chain break at event {event['id']}: "
                        f"expected previous {expected_previous}, got {previous_checksum}"
                    )

                # Verify checksum
                if expected_previous:
                    chain_data = {"event": event, "previous": expected_previous}
                    calculated = self._calculator.calculate(chain_data)
                else:
                    calculated = self.calculate_event_checksum(event)

                if calculated != stored_checksum:
                    issues.append(f"Checksum mismatch for event {event['id']}")

                previous_checksum = stored_checksum
                verified_count += 1

            if issues:
                return IntegrityCheckResult(
                    status=IntegrityStatus.INVALID,
                    checked_at=utc_now(),
                    details=f"Chain verification failed ({len(issues)} issues)",
                    issues=issues,
                    metadata={"verified_count": verified_count}
                )

            return IntegrityCheckResult(
                status=IntegrityStatus.VALID,
                checked_at=utc_now(),
                details=f"Chain verification passed ({verified_count} events)",
                metadata={"verified_count": verified_count}
            )

        except Exception as e:
            logger.error(f"Error verifying chain: {e}")
            return IntegrityCheckResult(
                status=IntegrityStatus.ERROR,
                checked_at=utc_now(),
                details=str(e)
            )

    def verify_database(self) -> IntegrityCheckResult:
        """
        Verify overall database integrity.

        Returns:
            Integrity check result
        """
        issues = []

        try:
            # SQLite integrity check
            cursor = self._conn.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            if result != "ok":
                issues.append(f"SQLite integrity check failed: {result}")

            # Check for orphaned checksums
            cursor = self._conn.execute("""
                SELECT COUNT(*) FROM event_checksums
                WHERE event_id NOT IN (SELECT id FROM events)
            """)
            orphaned = cursor.fetchone()[0]
            if orphaned > 0:
                issues.append(f"Found {orphaned} orphaned checksum records")

            # Check for missing checksums
            cursor = self._conn.execute("""
                SELECT COUNT(*) FROM events
                WHERE id NOT IN (SELECT event_id FROM event_checksums)
            """)
            missing = cursor.fetchone()[0]
            if missing > 0:
                issues.append(f"Found {missing} events without checksums")

            # Check for duplicate tokens in same stage/session
            cursor = self._conn.execute("""
                SELECT token_id, stage, session_id, COUNT(*) as cnt
                FROM events
                GROUP BY token_id, stage, session_id
                HAVING cnt > 1
            """)
            duplicates = cursor.fetchall()
            if duplicates:
                for dup in duplicates[:5]:  # Limit to first 5
                    issues.append(
                        f"Duplicate: token={dup[0]}, stage={dup[1]}, count={dup[3]}"
                    )

            status = IntegrityStatus.VALID if not issues else IntegrityStatus.INVALID
            return IntegrityCheckResult(
                status=status,
                checked_at=utc_now(),
                details=f"Database integrity check complete ({len(issues)} issues)",
                issues=issues
            )

        except Exception as e:
            logger.error(f"Error checking database integrity: {e}")
            return IntegrityCheckResult(
                status=IntegrityStatus.ERROR,
                checked_at=utc_now(),
                details=str(e)
            )

    def log_check_result(self, check_type: str, result: IntegrityCheckResult) -> None:
        """
        Log an integrity check result to the database.

        Args:
            check_type: Type of check performed
            result: The check result
        """
        self._conn.execute("""
            INSERT INTO integrity_checks
            (check_type, status, checked_at, details, issues_json)
            VALUES (?, ?, ?, ?, ?)
        """, (
            check_type,
            result.status.value,
            to_iso(result.checked_at),
            result.details,
            json.dumps(result.issues)
        ))
        self._conn.commit()

    def get_check_history(
        self,
        check_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get history of integrity checks.

        Args:
            check_type: Optional filter by check type
            limit: Maximum records to return

        Returns:
            List of check records
        """
        query = "SELECT * FROM integrity_checks"
        params = []

        if check_type:
            query += " WHERE check_type = ?"
            params.append(check_type)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        cursor = self._conn.execute(query, params)
        results = []

        for row in cursor.fetchall():
            record = dict(row)
            record["issues"] = json.loads(record.pop("issues_json", "[]"))
            results.append(record)

        return results


# =============================================================================
# Convenience Functions
# =============================================================================

_integrity_manager: Optional[IntegrityManager] = None


def get_integrity_manager(
    conn: sqlite3.Connection,
    secret_key: Optional[str] = None
) -> IntegrityManager:
    """Get or create the integrity manager"""
    global _integrity_manager
    if _integrity_manager is None:
        _integrity_manager = IntegrityManager(conn, secret_key)
    return _integrity_manager


def calculate_checksum(data: Any, algorithm: str = "sha256") -> str:
    """Calculate a simple checksum for data"""
    calculator = ChecksumCalculator(algorithm)
    return calculator.calculate(data)
