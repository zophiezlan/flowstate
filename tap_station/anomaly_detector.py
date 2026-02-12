"""
Anomaly Detection

This module provides anomaly detection for the tap station system,
identifying human errors and operational issues in real-time.

Extracted from database.py to improve separation of concerns.
"""

import logging
import sqlite3
from typing import Any, Dict, List

from .constants import DatabaseDefaults, WorkflowStages

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Detects anomalies and human error patterns in event data.

    This class handles detection of:
    - Forgotten exit taps
    - Stuck in service (unusually long service times)
    - Long service times (>2× median)
    - Rapid-fire duplicate taps
    - Out of order events
    """

    def __init__(
        self,
        stuck_threshold_minutes: int = DatabaseDefaults.STUCK_THRESHOLD_MINUTES,
        high_severity_threshold_minutes: int = DatabaseDefaults.ANOMALY_HIGH_THRESHOLD_MINUTES,
        service_stuck_threshold_minutes: int = 45,
        rapid_tap_threshold_minutes: int = 2,
    ):
        """
        Initialize the anomaly detector.

        Args:
            stuck_threshold_minutes: Minutes before considering a card "stuck"
            high_severity_threshold_minutes: Minutes before marking as high severity
            service_stuck_threshold_minutes: Minutes before considering stuck in service
            rapid_tap_threshold_minutes: Maximum minutes between taps to detect duplicates
        """
        self.stuck_threshold = stuck_threshold_minutes
        self.high_severity_threshold = high_severity_threshold_minutes
        self.service_stuck_threshold = service_stuck_threshold_minutes
        self.rapid_tap_threshold = rapid_tap_threshold_minutes

    def get_anomalies(
        self, conn: sqlite3.Connection, session_id: str
    ) -> Dict[str, Any]:
        """
        Detect various human error patterns and anomalies in real-time.

        Args:
            conn: SQLite database connection
            session_id: Session ID to check

        Returns:
            Dict with various anomaly categories and counts
        """
        anomalies = {
            "incomplete_journeys": [],
            "long_service_times": [],
            "stuck_in_service": [],
            "out_of_order_events": [],
            "rapid_fire_taps": [],
            "forgotten_exit_taps": [],
        }

        # Detect each type of anomaly
        self._detect_forgotten_exit_taps(conn, session_id, anomalies)
        self._detect_stuck_in_service(conn, session_id, anomalies)
        self._detect_long_service_times(conn, session_id, anomalies)
        self._detect_rapid_fire_taps(conn, session_id, anomalies)

        return anomalies

    def _detect_forgotten_exit_taps(
        self,
        conn: sqlite3.Connection,
        session_id: str,
        anomalies: Dict[str, List],
    ) -> None:
        """
        Detect cards that joined queue but never exited.

        Args:
            conn: SQLite database connection
            session_id: Session ID to check
            anomalies: Anomalies dict to update
        """
        try:
            # Use SQLite concatenation to safely build time offset from parameter
            sql = """
                SELECT q.token_id, q.timestamp,
                       CAST((julianday('now') - julianday(q.timestamp)) * 1440 AS INTEGER) as minutes_stuck
                FROM events q
                LEFT JOIN events e ON q.token_id = e.token_id
                                   AND q.session_id = e.session_id
                                   AND e.stage = ?
                WHERE q.stage = ?
                    AND q.session_id = ?
                    AND e.id IS NULL
                    AND q.timestamp < datetime('now', '-' || ? || ' minutes')
                ORDER BY q.timestamp ASC
            """
            cursor = conn.execute(
                sql,
                (
                    WorkflowStages.EXIT,
                    WorkflowStages.QUEUE_JOIN,
                    session_id,
                    str(self.stuck_threshold),
                ),
            )

            for row in cursor.fetchall():
                anomalies["forgotten_exit_taps"].append(
                    {
                        "token_id": row["token_id"],
                        "queue_join_time": row["timestamp"],
                        "minutes_stuck": row["minutes_stuck"],
                        "severity": (
                            "high"
                            if row["minutes_stuck"]
                            > self.high_severity_threshold
                            else "medium"
                        ),
                        "suggestion": "Participant may have left without tapping exit, or lost card",
                    }
                )
        except Exception as e:
            logger.error(
                "Error detecting forgotten exit taps: %s", e, exc_info=True
            )

    def _detect_stuck_in_service(
        self,
        conn: sqlite3.Connection,
        session_id: str,
        anomalies: Dict[str, List],
    ) -> None:
        """
        Detect cards stuck at SERVICE_START without completion.

        Args:
            conn: SQLite database connection
            session_id: Session ID to check
            anomalies: Anomalies dict to update
        """
        try:
            sql = """
                SELECT s.token_id, s.timestamp,
                       CAST((julianday('now') - julianday(s.timestamp)) * 1440 AS INTEGER) as minutes_stuck
                FROM events s
                LEFT JOIN events e ON s.token_id = e.token_id
                                   AND s.session_id = e.session_id
                                   AND e.stage IN (?, ?)
                                   AND datetime(e.timestamp) > datetime(s.timestamp)
                WHERE s.stage = ?
                    AND s.session_id = ?
                    AND e.id IS NULL
                    AND s.timestamp < datetime('now', '-' || ? || ' minutes')
                ORDER BY s.timestamp ASC
            """
            cursor = conn.execute(
                sql,
                (
                    WorkflowStages.EXIT,
                    WorkflowStages.SUBSTANCE_RETURNED,
                    WorkflowStages.SERVICE_START,
                    session_id,
                    str(self.service_stuck_threshold),
                ),
            )

            for row in cursor.fetchall():
                anomalies["stuck_in_service"].append(
                    {
                        "token_id": row["token_id"],
                        "service_start_time": row["timestamp"],
                        "minutes_stuck": row["minutes_stuck"],
                        "severity": (
                            "high" if row["minutes_stuck"] > 90 else "medium"
                        ),
                        "suggestion": "Service may be taking unusually long, or participant forgot to tap exit",
                    }
                )
        except Exception as e:
            logger.error(
                "Error detecting stuck in service: %s", e, exc_info=True
            )

    def _detect_long_service_times(
        self,
        conn: sqlite3.Connection,
        session_id: str,
        anomalies: Dict[str, List],
    ) -> None:
        """
        Detect service times >2× median service time.

        Args:
            conn: SQLite database connection
            session_id: Session ID to check
            anomalies: Anomalies dict to update
        """
        try:
            sql = """
                WITH service_times AS (
                    SELECT 
                        j.token_id,
                        j.timestamp as join_time,
                        e.timestamp as exit_time,
                        CAST((julianday(e.timestamp) - julianday(j.timestamp)) * 1440 AS INTEGER) as service_minutes
                    FROM events j
                    JOIN events e ON j.token_id = e.token_id
                                  AND j.session_id = e.session_id
                                  AND e.stage = ?
                    WHERE j.stage = ?
                        AND j.session_id = ?
                        AND datetime(e.timestamp) > datetime(j.timestamp)
                ),
                median_calc AS (
                    SELECT AVG(service_minutes) as median_service
                    FROM (
                        SELECT service_minutes
                        FROM service_times
                        ORDER BY service_minutes
                        LIMIT 2 - (SELECT COUNT(*) FROM service_times) % 2
                        OFFSET (SELECT (COUNT(*) - 1) / 2 FROM service_times)
                    )
                )
                SELECT st.token_id, st.join_time, st.exit_time, st.service_minutes, mc.median_service
                FROM service_times st, median_calc mc
                WHERE st.service_minutes > (mc.median_service * 2)
                    AND mc.median_service > 0
                ORDER BY st.service_minutes DESC
            """
            cursor = conn.execute(
                sql,
                (WorkflowStages.EXIT, WorkflowStages.QUEUE_JOIN, session_id),
            )

            for row in cursor.fetchall():
                anomalies["long_service_times"].append(
                    {
                        "token_id": row["token_id"],
                        "join_time": row["join_time"],
                        "exit_time": row["exit_time"],
                        "service_minutes": row["service_minutes"],
                        "median_service": row["median_service"],
                        "severity": "low",
                        "suggestion": f"Service time ({row['service_minutes']}min) is >2× median ({row['median_service']:.1f}min)",
                    }
                )
        except Exception as e:
            logger.error(
                "Error detecting long service times: %s", e, exc_info=True
            )

    def _detect_rapid_fire_taps(
        self,
        conn: sqlite3.Connection,
        session_id: str,
        anomalies: Dict[str, List],
    ) -> None:
        """
        Detect rapid duplicate taps (<2 min apart, same stage).

        Args:
            conn: SQLite database connection
            session_id: Session ID to check
            anomalies: Anomalies dict to update
        """
        try:
            sql = """
                SELECT e1.token_id, e1.stage, e1.timestamp as first_tap,
                       e2.timestamp as second_tap,
                       CAST((julianday(e2.timestamp) - julianday(e1.timestamp)) * 1440 AS REAL) as minutes_between
                FROM events e1
                JOIN events e2 ON e1.token_id = e2.token_id
                                AND e1.session_id = e2.session_id
                                AND e1.stage = e2.stage
                                AND e2.id > e1.id
                WHERE e1.session_id = ?
                    AND datetime(e2.timestamp) BETWEEN datetime(e1.timestamp) 
                        AND datetime(e1.timestamp, '+' || ? || ' minutes')
                ORDER BY e1.timestamp DESC
            """
            cursor = conn.execute(
                sql, (session_id, str(self.rapid_tap_threshold))
            )

            for row in cursor.fetchall():
                anomalies["rapid_fire_taps"].append(
                    {
                        "token_id": row["token_id"],
                        "stage": row["stage"],
                        "first_tap": row["first_tap"],
                        "second_tap": row["second_tap"],
                        "seconds_between": round(
                            row["minutes_between"] * 60, 1
                        ),
                        "severity": "low",
                        "suggestion": "Participant may have tapped multiple times accidentally",
                    }
                )
        except Exception as e:
            logger.error(
                "Error detecting rapid-fire taps: %s", e, exc_info=True
            )
