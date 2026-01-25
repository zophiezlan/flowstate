"""
Custom SLO (Service Level Objective) Definition System

This module allows services to define their own SLOs beyond the defaults,
enabling measurement of what matters most for their specific context.

Key Features:
- YAML-based SLO definitions
- Custom metric expressions
- Composite SLOs (combining multiple metrics)
- SLO budgets and burn rate tracking
- Historical compliance analysis

Service Design Principles:
- Services define their own success metrics
- Focus on outcomes that matter to participants
- Continuous measurement for improvement
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .datetime_utils import utc_now

logger = logging.getLogger(__name__)


class SLOMetricType(Enum):
    """Types of SLO metrics"""
    PERCENTAGE = "percentage"  # Value between 0-100
    COUNT = "count"            # Integer count
    DURATION = "duration"      # Time in minutes
    RATE = "rate"              # Per-hour rate
    RATIO = "ratio"            # Ratio (0-1)


class SLOStatus(Enum):
    """SLO compliance status"""
    MET = "met"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    UNKNOWN = "unknown"


class SLOAggregation(Enum):
    """Aggregation methods for SLO calculations"""
    AVERAGE = "average"
    PERCENTILE = "percentile"
    SUM = "sum"
    COUNT = "count"
    MIN = "min"
    MAX = "max"


@dataclass
class SLOTarget:
    """Defines an SLO target"""
    operator: str  # ">=", "<=", ">", "<", "=="
    value: float
    warning_threshold: Optional[float] = None  # Warning when approaching target

    def evaluate(self, current_value: float) -> Tuple[bool, SLOStatus]:
        """Evaluate if current value meets the target"""
        met = False

        if self.operator == ">=":
            met = current_value >= self.value
        elif self.operator == "<=":
            met = current_value <= self.value
        elif self.operator == ">":
            met = current_value > self.value
        elif self.operator == "<":
            met = current_value < self.value
        elif self.operator == "==":
            met = abs(current_value - self.value) < 0.001

        if met:
            return True, SLOStatus.MET

        # Check if at risk (within warning threshold)
        if self.warning_threshold is not None:
            if self.operator in (">=", ">"):
                if current_value >= self.warning_threshold:
                    return False, SLOStatus.AT_RISK
            elif self.operator in ("<=", "<"):
                if current_value <= self.warning_threshold:
                    return False, SLOStatus.AT_RISK

        return False, SLOStatus.BREACHED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "operator": self.operator,
            "value": self.value,
            "warning_threshold": self.warning_threshold
        }


@dataclass
class CustomSLODefinition:
    """
    A custom SLO definition.

    SLOs can be defined using:
    1. Built-in metrics (wait_time, completion_rate, etc.)
    2. SQL queries for custom calculations
    3. Composite metrics combining multiple values
    """
    id: str
    name: str
    description: str
    metric_type: SLOMetricType
    target: SLOTarget
    window_hours: int = 24
    query: Optional[str] = None  # SQL query (optional)
    metric_id: Optional[str] = None  # Built-in metric to use
    aggregation: SLOAggregation = SLOAggregation.AVERAGE
    percentile: int = 95  # Used when aggregation is PERCENTILE
    unit: str = ""
    tags: List[str] = field(default_factory=list)
    enabled: bool = True
    weight: float = 1.0  # For composite SLOs

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "metric_type": self.metric_type.value,
            "target": self.target.to_dict(),
            "window_hours": self.window_hours,
            "query": self.query,
            "metric_id": self.metric_id,
            "aggregation": self.aggregation.value,
            "percentile": self.percentile,
            "unit": self.unit,
            "tags": self.tags,
            "enabled": self.enabled,
            "weight": self.weight
        }


@dataclass
class SLOResult:
    """Result of an SLO evaluation"""
    slo_id: str
    slo_name: str
    target_value: float
    current_value: float
    status: SLOStatus
    compliance_percentage: float
    window_hours: int
    evaluated_at: datetime
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "slo_id": self.slo_id,
            "slo_name": self.slo_name,
            "target_value": self.target_value,
            "current_value": self.current_value,
            "status": self.status.value,
            "compliance_percentage": self.compliance_percentage,
            "window_hours": self.window_hours,
            "evaluated_at": self.evaluated_at.isoformat(),
            "details": self.details
        }


@dataclass
class SLOBudget:
    """Tracks SLO error budget"""
    slo_id: str
    total_budget_minutes: float
    remaining_budget_minutes: float
    burn_rate: float  # Minutes consumed per hour
    estimated_exhaustion: Optional[datetime]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "slo_id": self.slo_id,
            "total_budget_minutes": self.total_budget_minutes,
            "remaining_budget_minutes": self.remaining_budget_minutes,
            "remaining_percentage": (self.remaining_budget_minutes / self.total_budget_minutes * 100)
                if self.total_budget_minutes > 0 else 100,
            "burn_rate": self.burn_rate,
            "estimated_exhaustion": self.estimated_exhaustion.isoformat()
                if self.estimated_exhaustion else None
        }


class CustomSLOManager:
    """
    Manages custom SLO definitions and evaluations.

    This manager allows services to:
    - Define custom SLOs
    - Evaluate SLO compliance
    - Track error budgets
    - Generate compliance reports
    """

    # Built-in metric calculators
    BUILTIN_METRICS = {
        "wait_time_avg": "Average wait time in minutes",
        "wait_time_p50": "Median wait time in minutes",
        "wait_time_p90": "90th percentile wait time",
        "wait_time_p95": "95th percentile wait time",
        "wait_under_target": "Percentage of waits under target",
        "completion_rate": "Percentage of completed journeys",
        "abandonment_rate": "Percentage of abandoned journeys",
        "throughput_hourly": "Completions per hour",
        "service_time_avg": "Average service time in minutes",
        "queue_size_avg": "Average queue size",
        "error_rate": "Percentage of sequence errors",
        "substance_return_rate": "Percentage of substances returned",
    }

    def __init__(
        self,
        conn: sqlite3.Connection,
        target_wait_minutes: int = 30
    ):
        """
        Initialize the custom SLO manager.

        Args:
            conn: Database connection
            target_wait_minutes: Default target wait time
        """
        self._conn = conn
        self._target_wait = target_wait_minutes
        self._slos: Dict[str, CustomSLODefinition] = {}
        self._load_default_slos()

    def _load_default_slos(self) -> None:
        """Load default SLO definitions"""
        defaults = [
            CustomSLODefinition(
                id="wait_time_slo",
                name="Wait Time SLO",
                description="Percentage of participants waiting less than target",
                metric_type=SLOMetricType.PERCENTAGE,
                target=SLOTarget(">=", 80.0, warning_threshold=70.0),
                window_hours=4,
                metric_id="wait_under_target",
                unit="%",
                tags=["participant_experience", "core"]
            ),
            CustomSLODefinition(
                id="completion_rate_slo",
                name="Completion Rate SLO",
                description="Percentage of journeys that complete (join to exit)",
                metric_type=SLOMetricType.PERCENTAGE,
                target=SLOTarget(">=", 95.0, warning_threshold=90.0),
                window_hours=24,
                metric_id="completion_rate",
                unit="%",
                tags=["participant_experience", "core"]
            ),
            CustomSLODefinition(
                id="throughput_slo",
                name="Throughput SLO",
                description="Service capacity utilization",
                metric_type=SLOMetricType.PERCENTAGE,
                target=SLOTarget(">=", 70.0, warning_threshold=50.0),
                window_hours=4,
                metric_id="throughput_hourly",
                unit="%",
                tags=["operational", "core"]
            ),
            CustomSLODefinition(
                id="p90_wait_slo",
                name="P90 Wait Time SLO",
                description="90th percentile wait time should be under target",
                metric_type=SLOMetricType.DURATION,
                target=SLOTarget("<=", 45.0, warning_threshold=60.0),
                window_hours=4,
                metric_id="wait_time_p90",
                unit="minutes",
                tags=["participant_experience"]
            ),
        ]

        for slo in defaults:
            self._slos[slo.id] = slo

    def define_slo(self, slo: CustomSLODefinition) -> None:
        """
        Define a new custom SLO.

        Args:
            slo: The SLO definition
        """
        self._slos[slo.id] = slo
        logger.info(f"Defined SLO: {slo.id} ({slo.name})")

    def define_slo_from_dict(self, config: Dict[str, Any]) -> CustomSLODefinition:
        """
        Define an SLO from a configuration dictionary.

        Args:
            config: Dictionary with SLO configuration

        Returns:
            The created SLO definition
        """
        target = SLOTarget(
            operator=config.get("target_operator", ">="),
            value=config.get("target_value", 95.0),
            warning_threshold=config.get("warning_threshold")
        )

        slo = CustomSLODefinition(
            id=config["id"],
            name=config.get("name", config["id"]),
            description=config.get("description", ""),
            metric_type=SLOMetricType(config.get("metric_type", "percentage")),
            target=target,
            window_hours=config.get("window_hours", 24),
            query=config.get("query"),
            metric_id=config.get("metric_id"),
            aggregation=SLOAggregation(config.get("aggregation", "average")),
            percentile=config.get("percentile", 95),
            unit=config.get("unit", ""),
            tags=config.get("tags", []),
            enabled=config.get("enabled", True),
            weight=config.get("weight", 1.0)
        )

        self.define_slo(slo)
        return slo

    def remove_slo(self, slo_id: str) -> bool:
        """Remove an SLO definition"""
        if slo_id in self._slos:
            del self._slos[slo_id]
            logger.info(f"Removed SLO: {slo_id}")
            return True
        return False

    def get_slo(self, slo_id: str) -> Optional[CustomSLODefinition]:
        """Get an SLO definition by ID"""
        return self._slos.get(slo_id)

    def list_slos(
        self,
        tags: Optional[List[str]] = None,
        enabled_only: bool = True
    ) -> List[CustomSLODefinition]:
        """
        List SLO definitions.

        Args:
            tags: Filter by tags (any match)
            enabled_only: Only return enabled SLOs

        Returns:
            List of matching SLO definitions
        """
        slos = list(self._slos.values())

        if enabled_only:
            slos = [s for s in slos if s.enabled]

        if tags:
            slos = [s for s in slos if any(t in s.tags for t in tags)]

        return slos

    def evaluate_slo(
        self,
        slo_id: str,
        session_id: str
    ) -> Optional[SLOResult]:
        """
        Evaluate a single SLO.

        Args:
            slo_id: SLO to evaluate
            session_id: Session to evaluate against

        Returns:
            SLO result or None if SLO not found
        """
        slo = self._slos.get(slo_id)
        if not slo or not slo.enabled:
            return None

        current_value = self._calculate_metric(slo, session_id)
        if current_value is None:
            return SLOResult(
                slo_id=slo_id,
                slo_name=slo.name,
                target_value=slo.target.value,
                current_value=0,
                status=SLOStatus.UNKNOWN,
                compliance_percentage=0,
                window_hours=slo.window_hours,
                evaluated_at=utc_now(),
                details={"error": "Could not calculate metric"}
            )

        is_met, status = slo.target.evaluate(current_value)

        # Calculate compliance percentage
        if slo.target.operator in (">=", ">"):
            compliance = min(100, (current_value / slo.target.value) * 100) if slo.target.value > 0 else 100
        else:
            compliance = min(100, (slo.target.value / current_value) * 100) if current_value > 0 else 100

        return SLOResult(
            slo_id=slo_id,
            slo_name=slo.name,
            target_value=slo.target.value,
            current_value=current_value,
            status=status,
            compliance_percentage=compliance,
            window_hours=slo.window_hours,
            evaluated_at=utc_now(),
            details={
                "unit": slo.unit,
                "description": slo.description,
                "target_operator": slo.target.operator
            }
        )

    def evaluate_all_slos(
        self,
        session_id: str,
        tags: Optional[List[str]] = None
    ) -> Dict[str, SLOResult]:
        """
        Evaluate all matching SLOs.

        Args:
            session_id: Session to evaluate
            tags: Optional tag filter

        Returns:
            Dictionary of SLO ID to result
        """
        slos = self.list_slos(tags=tags)
        results = {}

        for slo in slos:
            result = self.evaluate_slo(slo.id, session_id)
            if result:
                results[slo.id] = result

        return results

    def get_slo_summary(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Get a summary of all SLO status.

        Args:
            session_id: Session to evaluate

        Returns:
            Summary with counts and overall status
        """
        results = self.evaluate_all_slos(session_id)

        status_counts = {
            SLOStatus.MET: 0,
            SLOStatus.AT_RISK: 0,
            SLOStatus.BREACHED: 0,
            SLOStatus.UNKNOWN: 0
        }

        for result in results.values():
            status_counts[result.status] += 1

        total = len(results)
        if total == 0:
            overall_status = SLOStatus.UNKNOWN
        elif status_counts[SLOStatus.BREACHED] > 0:
            overall_status = SLOStatus.BREACHED
        elif status_counts[SLOStatus.AT_RISK] > 0:
            overall_status = SLOStatus.AT_RISK
        else:
            overall_status = SLOStatus.MET

        return {
            "timestamp": utc_now().isoformat(),
            "session_id": session_id,
            "overall_status": overall_status.value,
            "total_slos": total,
            "met": status_counts[SLOStatus.MET],
            "at_risk": status_counts[SLOStatus.AT_RISK],
            "breached": status_counts[SLOStatus.BREACHED],
            "unknown": status_counts[SLOStatus.UNKNOWN],
            "compliance_rate": (status_counts[SLOStatus.MET] / total * 100) if total > 0 else 100,
            "results": {k: v.to_dict() for k, v in results.items()}
        }

    def calculate_error_budget(
        self,
        slo_id: str,
        session_id: str,
        budget_period_hours: int = 168  # 1 week
    ) -> Optional[SLOBudget]:
        """
        Calculate the error budget for an SLO.

        Error budget represents how much "failure" is acceptable
        before breaching the SLO target.

        Args:
            slo_id: SLO to calculate budget for
            session_id: Session to analyze
            budget_period_hours: Budget period (default 1 week)

        Returns:
            SLO budget information
        """
        slo = self._slos.get(slo_id)
        if not slo:
            return None

        # For a 95% SLO over 168 hours, error budget is 5% = 8.4 hours
        # This is simplified - real implementation would track actual violations
        error_budget_fraction = 1 - (slo.target.value / 100) if slo.metric_type == SLOMetricType.PERCENTAGE else 0.05
        total_budget = budget_period_hours * 60 * error_budget_fraction  # In minutes

        # Estimate consumed budget from recent violations
        result = self.evaluate_slo(slo_id, session_id)
        if not result:
            return None

        # Simple estimation: if at X% compliance, consumed (100-X)% of budget
        compliance = result.compliance_percentage
        consumed_fraction = max(0, (100 - compliance) / 100)
        consumed_budget = total_budget * consumed_fraction
        remaining_budget = total_budget - consumed_budget

        # Calculate burn rate (minutes per hour)
        hours_elapsed = min(budget_period_hours, slo.window_hours)
        burn_rate = consumed_budget / hours_elapsed if hours_elapsed > 0 else 0

        # Estimate exhaustion time
        estimated_exhaustion = None
        if burn_rate > 0 and remaining_budget > 0:
            hours_until_exhaustion = remaining_budget / burn_rate / 60
            estimated_exhaustion = utc_now() + timedelta(hours=hours_until_exhaustion)

        return SLOBudget(
            slo_id=slo_id,
            total_budget_minutes=total_budget,
            remaining_budget_minutes=remaining_budget,
            burn_rate=burn_rate,
            estimated_exhaustion=estimated_exhaustion
        )

    def _calculate_metric(
        self,
        slo: CustomSLODefinition,
        session_id: str
    ) -> Optional[float]:
        """Calculate the metric value for an SLO"""
        # If custom SQL query is provided, use it
        if slo.query:
            return self._execute_custom_query(slo.query, session_id, slo.window_hours)

        # Otherwise use built-in metric
        if slo.metric_id:
            return self._calculate_builtin_metric(slo.metric_id, session_id, slo.window_hours)

        return None

    def _execute_custom_query(
        self,
        query: str,
        session_id: str,
        window_hours: int
    ) -> Optional[float]:
        """Execute a custom SQL query for metric calculation"""
        try:
            # Replace placeholders
            query = query.replace("{session_id}", "?")
            query = query.replace("{window_hours}", str(window_hours))

            cursor = self._conn.execute(query, (session_id,))
            row = cursor.fetchone()

            if row:
                # Return first numeric column
                for value in row:
                    if isinstance(value, (int, float)):
                        return float(value)
            return None

        except Exception as e:
            logger.error(f"Error executing custom SLO query: {e}")
            return None

    def _calculate_builtin_metric(
        self,
        metric_id: str,
        session_id: str,
        window_hours: int
    ) -> Optional[float]:
        """Calculate a built-in metric"""
        try:
            if metric_id == "wait_time_avg":
                return self._calc_wait_time_avg(session_id, window_hours)
            elif metric_id == "wait_time_p50":
                return self._calc_wait_time_percentile(session_id, window_hours, 50)
            elif metric_id == "wait_time_p90":
                return self._calc_wait_time_percentile(session_id, window_hours, 90)
            elif metric_id == "wait_time_p95":
                return self._calc_wait_time_percentile(session_id, window_hours, 95)
            elif metric_id == "wait_under_target":
                return self._calc_wait_under_target(session_id, window_hours)
            elif metric_id == "completion_rate":
                return self._calc_completion_rate(session_id, window_hours)
            elif metric_id == "abandonment_rate":
                completion = self._calc_completion_rate(session_id, window_hours)
                return 100 - completion if completion is not None else None
            elif metric_id == "throughput_hourly":
                return self._calc_throughput(session_id, window_hours)
            elif metric_id == "service_time_avg":
                return self._calc_service_time_avg(session_id, window_hours)
            elif metric_id == "substance_return_rate":
                return self._calc_substance_return_rate(session_id, window_hours)
            else:
                logger.warning(f"Unknown built-in metric: {metric_id}")
                return None

        except Exception as e:
            logger.error(f"Error calculating metric {metric_id}: {e}")
            return None

    def _calc_wait_time_avg(self, session_id: str, window_hours: int) -> Optional[float]:
        """Calculate average wait time"""
        cursor = self._conn.execute("""
            SELECT AVG(CAST((julianday(e.timestamp) - julianday(q.timestamp)) * 1440 AS REAL)) as avg_wait
            FROM events q
            JOIN events e ON q.token_id = e.token_id AND q.session_id = e.session_id
                AND e.stage IN ('SERVICE_START', 'EXIT')
                AND datetime(e.timestamp) > datetime(q.timestamp)
            WHERE q.stage = 'QUEUE_JOIN' AND q.session_id = ?
                AND datetime(q.timestamp) > datetime('now', '-' || ? || ' hours')
        """, (session_id, window_hours))
        row = cursor.fetchone()
        return row["avg_wait"] if row and row["avg_wait"] else 0

    def _calc_wait_time_percentile(
        self,
        session_id: str,
        window_hours: int,
        percentile: int
    ) -> Optional[float]:
        """Calculate percentile wait time"""
        cursor = self._conn.execute("""
            WITH wait_times AS (
                SELECT CAST((julianday(e.timestamp) - julianday(q.timestamp)) * 1440 AS REAL) as wait,
                       ROW_NUMBER() OVER (ORDER BY (julianday(e.timestamp) - julianday(q.timestamp))) as rn,
                       COUNT(*) OVER () as total
                FROM events q
                JOIN events e ON q.token_id = e.token_id AND q.session_id = e.session_id
                    AND e.stage IN ('SERVICE_START', 'EXIT')
                    AND datetime(e.timestamp) > datetime(q.timestamp)
                WHERE q.stage = 'QUEUE_JOIN' AND q.session_id = ?
                    AND datetime(q.timestamp) > datetime('now', '-' || ? || ' hours')
            )
            SELECT wait FROM wait_times WHERE rn >= CAST(total * ? / 100.0 AS INTEGER) LIMIT 1
        """, (session_id, window_hours, percentile))
        row = cursor.fetchone()
        return row["wait"] if row and row["wait"] else 0

    def _calc_wait_under_target(self, session_id: str, window_hours: int) -> Optional[float]:
        """Calculate percentage of waits under target"""
        cursor = self._conn.execute("""
            WITH wait_times AS (
                SELECT CAST((julianday(e.timestamp) - julianday(q.timestamp)) * 1440 AS REAL) as wait
                FROM events q
                JOIN events e ON q.token_id = e.token_id AND q.session_id = e.session_id
                    AND e.stage IN ('SERVICE_START', 'EXIT')
                    AND datetime(e.timestamp) > datetime(q.timestamp)
                WHERE q.stage = 'QUEUE_JOIN' AND q.session_id = ?
                    AND datetime(q.timestamp) > datetime('now', '-' || ? || ' hours')
            )
            SELECT CAST(SUM(CASE WHEN wait <= ? THEN 1 ELSE 0 END) AS REAL) * 100.0 /
                   NULLIF(COUNT(*), 0) as pct_under
            FROM wait_times
        """, (session_id, window_hours, self._target_wait))
        row = cursor.fetchone()
        return row["pct_under"] if row and row["pct_under"] else 100

    def _calc_completion_rate(self, session_id: str, window_hours: int) -> Optional[float]:
        """Calculate journey completion rate"""
        cursor = self._conn.execute("""
            WITH journeys AS (
                SELECT token_id,
                       MAX(CASE WHEN stage = 'QUEUE_JOIN' THEN 1 ELSE 0 END) as joined,
                       MAX(CASE WHEN stage = 'EXIT' THEN 1 ELSE 0 END) as exited
                FROM events WHERE session_id = ?
                    AND datetime(timestamp) > datetime('now', '-' || ? || ' hours')
                GROUP BY token_id
            )
            SELECT CAST(SUM(exited) AS REAL) * 100.0 / NULLIF(SUM(joined), 0) as completion
            FROM journeys
        """, (session_id, window_hours))
        row = cursor.fetchone()
        return row["completion"] if row and row["completion"] else 100

    def _calc_throughput(self, session_id: str, window_hours: int) -> Optional[float]:
        """Calculate hourly throughput"""
        cursor = self._conn.execute("""
            SELECT COUNT(*) * 1.0 / ? as hourly_throughput
            FROM events
            WHERE stage = 'EXIT' AND session_id = ?
                AND datetime(timestamp) > datetime('now', '-' || ? || ' hours')
        """, (window_hours, session_id, window_hours))
        row = cursor.fetchone()
        return row["hourly_throughput"] if row and row["hourly_throughput"] else 0

    def _calc_service_time_avg(self, session_id: str, window_hours: int) -> Optional[float]:
        """Calculate average service time"""
        cursor = self._conn.execute("""
            SELECT AVG(CAST((julianday(e.timestamp) - julianday(s.timestamp)) * 1440 AS REAL)) as avg_svc
            FROM events s
            JOIN events e ON s.token_id = e.token_id AND s.session_id = e.session_id
                AND e.stage = 'EXIT' AND datetime(e.timestamp) > datetime(s.timestamp)
            WHERE s.stage = 'SERVICE_START' AND s.session_id = ?
                AND datetime(s.timestamp) > datetime('now', '-' || ? || ' hours')
        """, (session_id, window_hours))
        row = cursor.fetchone()
        return row["avg_svc"] if row and row["avg_svc"] else 0

    def _calc_substance_return_rate(self, session_id: str, window_hours: int) -> Optional[float]:
        """Calculate substance return rate"""
        cursor = self._conn.execute("""
            WITH services AS (
                SELECT token_id,
                       MAX(CASE WHEN stage = 'SERVICE_START' THEN 1 ELSE 0 END) as started,
                       MAX(CASE WHEN stage = 'SUBSTANCE_RETURNED' THEN 1 ELSE 0 END) as returned
                FROM events WHERE session_id = ?
                    AND datetime(timestamp) > datetime('now', '-' || ? || ' hours')
                GROUP BY token_id
            )
            SELECT CAST(SUM(returned) AS REAL) * 100.0 / NULLIF(SUM(started), 0) as return_rate
            FROM services WHERE started = 1
        """, (session_id, window_hours))
        row = cursor.fetchone()
        return row["return_rate"] if row and row["return_rate"] else 100


# =============================================================================
# Configuration Loading Helpers
# =============================================================================

def load_slos_from_config(
    config: Dict[str, Any],
    manager: CustomSLOManager
) -> int:
    """
    Load SLO definitions from a configuration dictionary.

    Args:
        config: Configuration with 'slos' key
        manager: SLO manager to load into

    Returns:
        Number of SLOs loaded
    """
    slo_configs = config.get("slos", config.get("service_level_objectives", []))
    loaded = 0

    for slo_config in slo_configs:
        try:
            manager.define_slo_from_dict(slo_config)
            loaded += 1
        except Exception as e:
            logger.error(f"Error loading SLO {slo_config.get('id', 'unknown')}: {e}")

    return loaded


# =============================================================================
# Global Instance
# =============================================================================

_slo_manager: Optional[CustomSLOManager] = None


def get_slo_manager(conn: sqlite3.Connection) -> CustomSLOManager:
    """Get or create the global SLO manager"""
    global _slo_manager
    if _slo_manager is None:
        _slo_manager = CustomSLOManager(conn)
    return _slo_manager
