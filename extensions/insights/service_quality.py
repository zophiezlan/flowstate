"""
Service Quality Metrics and SLI Tracking

This module provides comprehensive service quality monitoring, including:
- Service Level Indicators (SLIs) tracking
- Service Level Objectives (SLOs) monitoring
- Quality metrics collection and aggregation
- Real-time service health scoring

The module is designed around service design principles, focusing on
measurable outcomes that matter for service delivery and improvement.
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from tap_station.datetime_utils import utc_now

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of quality metrics"""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class HealthStatus(Enum):
    """Service health status levels"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


@dataclass
class SLODefinition:
    """Defines a Service Level Objective"""

    name: str
    description: str
    target: float  # Target percentage (0-100)
    warning_threshold: float  # Warning if below this
    metric_query: str  # SQL query or metric name
    window_hours: int = 24  # Time window for calculation
    unit: str = "percent"


@dataclass
class MetricValue:
    """A single metric observation"""

    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE


@dataclass
class QualityScore:
    """Overall service quality score"""

    overall: float
    components: Dict[str, float]
    status: HealthStatus
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)


class ServiceQualityMetrics:
    """
    Tracks and reports service quality metrics.

    This class provides:
    - Real-time SLI calculation
    - SLO compliance monitoring
    - Service health scoring
    - Quality trend analysis
    """

    # Default SLO definitions for harm reduction services
    DEFAULT_SLOS = [
        SLODefinition(
            name="wait_time_slo",
            description="Percentage of participants waiting less than target time",
            target=80.0,
            warning_threshold=70.0,
            metric_query="wait_time_under_target",
            window_hours=4,
            unit="percent",
        ),
        SLODefinition(
            name="completion_rate_slo",
            description="Percentage of journeys completed (joined and exited)",
            target=95.0,
            warning_threshold=90.0,
            metric_query="completion_rate",
            window_hours=24,
            unit="percent",
        ),
        SLODefinition(
            name="throughput_slo",
            description="Service capacity utilization vs target",
            target=70.0,
            warning_threshold=50.0,
            metric_query="throughput_rate",
            window_hours=4,
            unit="percent",
        ),
        SLODefinition(
            name="error_rate_slo",
            description="Percentage of error-free operations",
            target=99.0,
            warning_threshold=95.0,
            metric_query="error_free_rate",
            window_hours=24,
            unit="percent",
        ),
    ]

    def __init__(
        self,
        conn: sqlite3.Connection,
        slos: Optional[List[SLODefinition]] = None,
        target_wait_minutes: int = 30,
        target_throughput_per_hour: int = 12,
    ):
        """
        Initialize service quality metrics.

        Args:
            conn: Database connection
            slos: Custom SLO definitions (uses defaults if not provided)
            target_wait_minutes: Target wait time in minutes
            target_throughput_per_hour: Target throughput capacity
        """
        self._conn = conn
        self._slos = slos or self.DEFAULT_SLOS.copy()
        self._target_wait = target_wait_minutes
        self._target_throughput = target_throughput_per_hour
        self._metric_history: List[MetricValue] = []
        self._max_history_size = 10000

    def configure(
        self,
        target_wait_minutes: Optional[int] = None,
        target_throughput_per_hour: Optional[int] = None,
        custom_slos: Optional[List[SLODefinition]] = None,
    ) -> None:
        """
        Update configuration.

        Args:
            target_wait_minutes: New target wait time
            target_throughput_per_hour: New target throughput
            custom_slos: Custom SLO definitions to add
        """
        if target_wait_minutes is not None:
            self._target_wait = target_wait_minutes
        if target_throughput_per_hour is not None:
            self._target_throughput = target_throughput_per_hour
        if custom_slos:
            self._slos.extend(custom_slos)

    def calculate_slis(self, session_id: str) -> Dict[str, float]:
        """
        Calculate all Service Level Indicators.

        Args:
            session_id: Session to calculate metrics for

        Returns:
            Dictionary of SLI names to values
        """
        slis = {}

        # Wait time SLI
        slis["avg_wait_time"] = self._calc_avg_wait_time(session_id)
        slis["median_wait_time"] = self._calc_median_wait_time(session_id)
        slis["p95_wait_time"] = self._calc_percentile_wait_time(session_id, 95)
        slis["wait_time_under_target"] = self._calc_wait_time_under_target(
            session_id
        )

        # Throughput SLI
        slis["current_throughput"] = self._calc_current_throughput(session_id)
        slis["throughput_rate"] = self._calc_throughput_rate(session_id)

        # Completion SLI
        slis["completion_rate"] = self._calc_completion_rate(session_id)
        slis["active_journeys"] = self._calc_active_journeys(session_id)

        # Quality SLIs
        slis["error_free_rate"] = self._calc_error_free_rate(session_id)
        slis["sequence_compliance"] = self._calc_sequence_compliance(
            session_id
        )

        # Service SLIs
        slis["avg_service_time"] = self._calc_avg_service_time(session_id)
        slis["service_efficiency"] = self._calc_service_efficiency(session_id)

        return slis

    def evaluate_slos(self, session_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Evaluate all SLOs and return compliance status.

        Args:
            session_id: Session to evaluate

        Returns:
            Dictionary of SLO results with status and details
        """
        slis = self.calculate_slis(session_id)
        results = {}

        for slo in self._slos:
            metric_value = slis.get(slo.metric_query, 0.0)

            status = "met"
            if metric_value < slo.warning_threshold:
                status = "warning"
            if metric_value < slo.target * 0.8:  # 20% below target
                status = "critical"

            results[slo.name] = {
                "name": slo.name,
                "description": slo.description,
                "target": slo.target,
                "current": metric_value,
                "status": status,
                "warning_threshold": slo.warning_threshold,
                "compliance": (
                    (metric_value / slo.target * 100)
                    if slo.target > 0
                    else 100
                ),
                "window_hours": slo.window_hours,
                "unit": slo.unit,
            }

        return results

    def calculate_quality_score(self, session_id: str) -> QualityScore:
        """
        Calculate overall service quality score.

        Args:
            session_id: Session to score

        Returns:
            QualityScore with overall rating and breakdown
        """
        slos = self.evaluate_slos(session_id)
        slis = self.calculate_slis(session_id)

        # Calculate component scores (0-100)
        components = {
            "timeliness": self._score_timeliness(slis),
            "throughput": self._score_throughput(slis),
            "completion": self._score_completion(slis),
            "reliability": self._score_reliability(slis),
        }

        # Weighted overall score
        weights = {
            "timeliness": 0.30,
            "throughput": 0.25,
            "completion": 0.25,
            "reliability": 0.20,
        }

        overall = sum(components[k] * weights.get(k, 0.25) for k in components)

        # Determine health status
        if overall >= 90:
            status = HealthStatus.HEALTHY
        elif overall >= 70:
            status = HealthStatus.DEGRADED
        elif overall >= 50:
            status = HealthStatus.UNHEALTHY
        else:
            status = HealthStatus.CRITICAL

        return QualityScore(
            overall=overall,
            components=components,
            status=status,
            timestamp=utc_now(),
            details={
                "slos": slos,
                "slis": slis,
                "target_wait_minutes": self._target_wait,
                "target_throughput": self._target_throughput,
            },
        )

    def get_quality_trend(
        self, session_id: str, hours: int = 4, interval_minutes: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get quality score trend over time.

        Args:
            session_id: Session to analyze
            hours: Number of hours to look back
            interval_minutes: Interval between data points

        Returns:
            List of quality snapshots over time
        """
        trend = []
        now = utc_now()

        # This is a simplified implementation - in production,
        # you would want to store historical metrics
        for i in range(0, hours * 60, interval_minutes):
            point_time = now - timedelta(minutes=i)
            # For now, just return current score with timestamp
            # A full implementation would query historical data
            if i == 0:
                score = self.calculate_quality_score(session_id)
                trend.append(
                    {
                        "timestamp": point_time.isoformat(),
                        "overall": score.overall,
                        "status": score.status.value,
                        "components": score.components,
                    }
                )

        return trend

    def record_metric(self, metric: MetricValue) -> None:
        """
        Record a metric observation.

        Args:
            metric: The metric value to record
        """
        self._metric_history.append(metric)

        # Trim history if too large
        if len(self._metric_history) > self._max_history_size:
            self._metric_history = self._metric_history[
                -self._max_history_size // 2 :
            ]

    # =========================================================================
    # Private SLI Calculation Methods
    # =========================================================================

    def _calc_avg_wait_time(self, session_id: str) -> float:
        """Calculate average wait time (QUEUE_JOIN to SERVICE_START or EXIT)"""
        try:
            cursor = self._conn.execute(
                """
                SELECT AVG(
                    CAST((julianday(e.timestamp) - julianday(q.timestamp)) * 1440 AS REAL)
                ) as avg_wait
                FROM events q
                JOIN events e ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                    AND e.stage IN ('SERVICE_START', 'EXIT')
                    AND datetime(e.timestamp) > datetime(q.timestamp)
                WHERE q.stage = 'QUEUE_JOIN'
                    AND q.session_id = ?
                    AND datetime(q.timestamp) > datetime('now', '-4 hours')
            """,
                (session_id,),
            )
            row = cursor.fetchone()
            return row["avg_wait"] if row and row["avg_wait"] else 0.0
        except Exception as e:
            logger.error("Error calculating avg wait time: %s", e)
            return 0.0

    def _calc_median_wait_time(self, session_id: str) -> float:
        """Calculate median wait time"""
        try:
            cursor = self._conn.execute(
                """
                WITH wait_times AS (
                    SELECT CAST((julianday(e.timestamp) - julianday(q.timestamp)) * 1440 AS REAL) as wait
                    FROM events q
                    JOIN events e ON q.token_id = e.token_id
                        AND q.session_id = e.session_id
                        AND e.stage IN ('SERVICE_START', 'EXIT')
                        AND datetime(e.timestamp) > datetime(q.timestamp)
                    WHERE q.stage = 'QUEUE_JOIN'
                        AND q.session_id = ?
                        AND datetime(q.timestamp) > datetime('now', '-4 hours')
                )
                SELECT AVG(wait) as median
                FROM (
                    SELECT wait FROM wait_times ORDER BY wait
                    LIMIT 2 - (SELECT COUNT(*) FROM wait_times) % 2
                    OFFSET (SELECT (COUNT(*) - 1) / 2 FROM wait_times)
                )
            """,
                (session_id,),
            )
            row = cursor.fetchone()
            return row["median"] if row and row["median"] else 0.0
        except Exception as e:
            logger.error("Error calculating median wait time: %s", e)
            return 0.0

    def _calc_percentile_wait_time(
        self, session_id: str, percentile: int
    ) -> float:
        """Calculate wait time at given percentile"""
        try:
            cursor = self._conn.execute(
                """
                WITH wait_times AS (
                    SELECT CAST((julianday(e.timestamp) - julianday(q.timestamp)) * 1440 AS REAL) as wait,
                           ROW_NUMBER() OVER (ORDER BY (julianday(e.timestamp) - julianday(q.timestamp))) as rn,
                           COUNT(*) OVER () as total
                    FROM events q
                    JOIN events e ON q.token_id = e.token_id
                        AND q.session_id = e.session_id
                        AND e.stage IN ('SERVICE_START', 'EXIT')
                        AND datetime(e.timestamp) > datetime(q.timestamp)
                    WHERE q.stage = 'QUEUE_JOIN'
                        AND q.session_id = ?
                        AND datetime(q.timestamp) > datetime('now', '-4 hours')
                )
                SELECT wait FROM wait_times
                WHERE rn >= CAST(total * ? / 100.0 AS INTEGER)
                LIMIT 1
            """,
                (session_id, percentile),
            )
            row = cursor.fetchone()
            return row["wait"] if row and row["wait"] else 0.0
        except Exception as e:
            logger.error("Error calculating p%s wait time: %s", percentile, e)
            return 0.0

    def _calc_wait_time_under_target(self, session_id: str) -> float:
        """Calculate percentage of wait times under target"""
        try:
            cursor = self._conn.execute(
                """
                WITH wait_times AS (
                    SELECT CAST((julianday(e.timestamp) - julianday(q.timestamp)) * 1440 AS REAL) as wait
                    FROM events q
                    JOIN events e ON q.token_id = e.token_id
                        AND q.session_id = e.session_id
                        AND e.stage IN ('SERVICE_START', 'EXIT')
                        AND datetime(e.timestamp) > datetime(q.timestamp)
                    WHERE q.stage = 'QUEUE_JOIN'
                        AND q.session_id = ?
                        AND datetime(q.timestamp) > datetime('now', '-4 hours')
                )
                SELECT
                    CAST(SUM(CASE WHEN wait <= ? THEN 1 ELSE 0 END) AS REAL) * 100.0 /
                    NULLIF(COUNT(*), 0) as pct_under_target
                FROM wait_times
            """,
                (session_id, self._target_wait),
            )
            row = cursor.fetchone()
            return (
                row["pct_under_target"]
                if row and row["pct_under_target"]
                else 100.0
            )
        except Exception as e:
            logger.error("Error calculating wait time under target: %s", e)
            return 100.0

    def _calc_current_throughput(self, session_id: str) -> float:
        """Calculate current throughput (completions per hour)"""
        try:
            cursor = self._conn.execute(
                """
                SELECT COUNT(*) * 1.0 / NULLIF(
                    (julianday('now') - julianday(MIN(timestamp))) * 24, 0
                ) as throughput
                FROM events
                WHERE stage = 'EXIT'
                    AND session_id = ?
                    AND datetime(timestamp) > datetime('now', '-4 hours')
            """,
                (session_id,),
            )
            row = cursor.fetchone()
            return row["throughput"] if row and row["throughput"] else 0.0
        except Exception as e:
            logger.error("Error calculating throughput: %s", e)
            return 0.0

    def _calc_throughput_rate(self, session_id: str) -> float:
        """Calculate throughput as percentage of target"""
        throughput = self._calc_current_throughput(session_id)
        if self._target_throughput <= 0:
            return 100.0
        return min(100.0, (throughput / self._target_throughput) * 100)

    def _calc_completion_rate(self, session_id: str) -> float:
        """Calculate journey completion rate"""
        try:
            cursor = self._conn.execute(
                """
                WITH journeys AS (
                    SELECT token_id,
                           MAX(CASE WHEN stage = 'QUEUE_JOIN' THEN 1 ELSE 0 END) as joined,
                           MAX(CASE WHEN stage = 'EXIT' THEN 1 ELSE 0 END) as exited
                    FROM events
                    WHERE session_id = ?
                        AND datetime(timestamp) > datetime('now', '-24 hours')
                    GROUP BY token_id
                )
                SELECT CAST(SUM(exited) AS REAL) * 100.0 / NULLIF(SUM(joined), 0) as completion
                FROM journeys
            """,
                (session_id,),
            )
            row = cursor.fetchone()
            return row["completion"] if row and row["completion"] else 100.0
        except Exception as e:
            logger.error("Error calculating completion rate: %s", e)
            return 100.0

    def _calc_active_journeys(self, session_id: str) -> int:
        """Calculate number of active (incomplete) journeys"""
        try:
            cursor = self._conn.execute(
                """
                SELECT COUNT(DISTINCT q.token_id) as active
                FROM events q
                LEFT JOIN events e ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                    AND e.stage = 'EXIT'
                WHERE q.stage = 'QUEUE_JOIN'
                    AND q.session_id = ?
                    AND e.id IS NULL
            """,
                (session_id,),
            )
            row = cursor.fetchone()
            return row["active"] if row else 0
        except Exception as e:
            logger.error("Error calculating active journeys: %s", e)
            return 0

    def _calc_error_free_rate(self, session_id: str) -> float:
        """Calculate percentage of error-free operations"""
        # In a real implementation, this would track validation errors
        # For now, return based on sequence compliance
        return self._calc_sequence_compliance(session_id)

    def _calc_sequence_compliance(self, session_id: str) -> float:
        """Calculate percentage of journeys with valid sequences"""
        try:
            cursor = self._conn.execute(
                """
                WITH journey_sequences AS (
                    SELECT token_id,
                           GROUP_CONCAT(stage, '→') as sequence
                    FROM (
                        SELECT token_id, stage, timestamp
                        FROM events
                        WHERE session_id = ?
                        ORDER BY token_id, timestamp
                    )
                    GROUP BY token_id
                )
                SELECT
                    CAST(SUM(CASE
                        WHEN sequence LIKE 'QUEUE_JOIN%EXIT' THEN 1
                        WHEN sequence = 'EXIT' THEN 1
                        ELSE 0
                    END) AS REAL) * 100.0 / NULLIF(COUNT(*), 0) as compliance
                FROM journey_sequences
            """,
                (session_id,),
            )
            row = cursor.fetchone()
            return row["compliance"] if row and row["compliance"] else 100.0
        except Exception as e:
            logger.error("Error calculating sequence compliance: %s", e)
            return 100.0

    def _calc_avg_service_time(self, session_id: str) -> float:
        """Calculate average service time (SERVICE_START to EXIT)"""
        try:
            cursor = self._conn.execute(
                """
                SELECT AVG(
                    CAST((julianday(e.timestamp) - julianday(s.timestamp)) * 1440 AS REAL)
                ) as avg_service
                FROM events s
                JOIN events e ON s.token_id = e.token_id
                    AND s.session_id = e.session_id
                    AND e.stage = 'EXIT'
                    AND datetime(e.timestamp) > datetime(s.timestamp)
                WHERE s.stage = 'SERVICE_START'
                    AND s.session_id = ?
                    AND datetime(s.timestamp) > datetime('now', '-4 hours')
            """,
                (session_id,),
            )
            row = cursor.fetchone()
            return row["avg_service"] if row and row["avg_service"] else 0.0
        except Exception as e:
            logger.error("Error calculating avg service time: %s", e)
            return 0.0

    def _calc_service_efficiency(self, session_id: str) -> float:
        """Calculate service efficiency (consistent service times)"""
        try:
            # Low variance = high efficiency
            cursor = self._conn.execute(
                """
                WITH service_times AS (
                    SELECT CAST((julianday(e.timestamp) - julianday(s.timestamp)) * 1440 AS REAL) as svc_time
                    FROM events s
                    JOIN events e ON s.token_id = e.token_id
                        AND s.session_id = e.session_id
                        AND e.stage = 'EXIT'
                        AND datetime(e.timestamp) > datetime(s.timestamp)
                    WHERE s.stage = 'SERVICE_START'
                        AND s.session_id = ?
                        AND datetime(s.timestamp) > datetime('now', '-4 hours')
                )
                SELECT
                    AVG(svc_time) as avg_time,
                    (SUM(svc_time * svc_time) - SUM(svc_time) * SUM(svc_time) / COUNT(*)) /
                    NULLIF(COUNT(*) - 1, 0) as variance
                FROM service_times
            """,
                (session_id,),
            )
            row = cursor.fetchone()
            if row and row["avg_time"] and row["variance"]:
                # Coefficient of variation (lower = more efficient)
                cv = (row["variance"] ** 0.5) / row["avg_time"]
                # Convert to efficiency score (100 = perfectly consistent)
                return max(0, 100 - (cv * 100))
            return 100.0
        except Exception as e:
            logger.error("Error calculating service efficiency: %s", e)
            return 100.0

    # =========================================================================
    # Scoring Methods
    # =========================================================================

    def _score_timeliness(self, slis: Dict[str, float]) -> float:
        """Score timeliness component"""
        wait_under = slis.get("wait_time_under_target", 100)
        avg_wait = slis.get("avg_wait_time", 0)

        # Combine wait time under target with average wait penalty
        score = wait_under
        if avg_wait > self._target_wait:
            penalty = min(
                30, (avg_wait - self._target_wait) / self._target_wait * 30
            )
            score = max(0, score - penalty)

        return score

    def _score_throughput(self, slis: Dict[str, float]) -> float:
        """Score throughput component"""
        return slis.get("throughput_rate", 0)

    def _score_completion(self, slis: Dict[str, float]) -> float:
        """Score completion component"""
        completion = slis.get("completion_rate", 100)
        active = slis.get("active_journeys", 0)

        # Penalty for too many active journeys
        if active > 20:
            completion = max(0, completion - (active - 20))

        return completion

    def _score_reliability(self, slis: Dict[str, float]) -> float:
        """Score reliability component"""
        error_free = slis.get("error_free_rate", 100)
        sequence = slis.get("sequence_compliance", 100)
        efficiency = slis.get("service_efficiency", 100)

        return error_free * 0.4 + sequence * 0.4 + efficiency * 0.2


# =============================================================================
# Global Instance
# =============================================================================

_service_quality: Optional[ServiceQualityMetrics] = None


def get_service_quality(conn: sqlite3.Connection) -> ServiceQualityMetrics:
    """Get or create the service quality metrics instance"""
    global _service_quality
    if _service_quality is None:
        _service_quality = ServiceQualityMetrics(conn)
    return _service_quality
