"""
Service Delivery Improvement Engine

This module provides continuous improvement recommendations based on service
performance data. It analyzes patterns, identifies improvement opportunities,
and suggests actionable interventions.

Key Features:
- Pattern analysis for bottleneck detection
- Data-driven improvement recommendations
- Service design optimization suggestions
- Performance trend analysis
- Actionable insights with priority scoring

Service Design Principles Applied:
1. Understanding user needs through wait time and completion analysis
2. Designing for outcomes by focusing on what participants experience
3. Continuous improvement through data-driven recommendations
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import sqlite3

from .datetime_utils import utc_now

logger = logging.getLogger(__name__)


class ImprovementCategory(Enum):
    """Categories of service improvement recommendations"""

    CAPACITY = "capacity"
    WORKFLOW = "workflow"
    STAFFING = "staffing"
    QUEUE_MANAGEMENT = "queue_management"
    PARTICIPANT_EXPERIENCE = "participant_experience"
    OPERATIONAL = "operational"
    DATA_QUALITY = "data_quality"


class ImprovementPriority(Enum):
    """Priority levels for recommendations"""

    CRITICAL = "critical"  # Immediate action required
    HIGH = "high"  # Address within shift
    MEDIUM = "medium"  # Address within day
    LOW = "low"  # Consider for future
    INFORMATIONAL = "informational"  # For awareness


class ImprovementStatus(Enum):
    """Status of improvement recommendations"""

    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    DISMISSED = "dismissed"


@dataclass
class ImprovementRecommendation:
    """A service improvement recommendation"""

    id: str
    category: ImprovementCategory
    priority: ImprovementPriority
    title: str
    description: str
    rationale: str
    suggested_actions: List[str]
    expected_impact: str
    metrics_affected: List[str]
    evidence: Dict[str, Any] = field(default_factory=dict)
    status: ImprovementStatus = ImprovementStatus.NEW
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "id": self.id,
            "category": self.category.value,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "rationale": self.rationale,
            "suggested_actions": self.suggested_actions,
            "expected_impact": self.expected_impact,
            "metrics_affected": self.metrics_affected,
            "evidence": self.evidence,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ServicePattern:
    """An identified pattern in service data"""

    pattern_type: str
    description: str
    frequency: float  # How often this pattern occurs (0-1)
    impact_score: float  # Impact on service quality (0-100)
    trend: str  # "improving", "stable", "degrading"
    data_points: int
    first_seen: datetime
    last_seen: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "pattern_type": self.pattern_type,
            "description": self.description,
            "frequency": self.frequency,
            "impact_score": self.impact_score,
            "trend": self.trend,
            "data_points": self.data_points,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
        }


class ServiceImprovementEngine:
    """
    Analyzes service data and generates improvement recommendations.

    This engine focuses on service design principles:
    - Participant-centric analysis
    - Data-driven insights
    - Actionable recommendations
    - Continuous improvement cycle
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        target_wait_minutes: int = 30,
        target_throughput_per_hour: int = 12,
        analysis_window_hours: int = 24,
    ):
        """
        Initialize the improvement engine.

        Args:
            conn: Database connection
            target_wait_minutes: Target maximum wait time
            target_throughput_per_hour: Target service capacity
            analysis_window_hours: Hours of data to analyze
        """
        self._conn = conn
        self._target_wait = target_wait_minutes
        self._target_throughput = target_throughput_per_hour
        self._analysis_window = analysis_window_hours
        self._recommendations: Dict[str, ImprovementRecommendation] = {}
        self._patterns: List[ServicePattern] = []
        self._recommendation_counter = 0

    def configure(
        self,
        target_wait_minutes: Optional[int] = None,
        target_throughput_per_hour: Optional[int] = None,
        analysis_window_hours: Optional[int] = None,
    ) -> None:
        """Update configuration parameters"""
        if target_wait_minutes is not None:
            self._target_wait = target_wait_minutes
        if target_throughput_per_hour is not None:
            self._target_throughput = target_throughput_per_hour
        if analysis_window_hours is not None:
            self._analysis_window = analysis_window_hours

    def analyze_and_recommend(self, session_id: str) -> List[ImprovementRecommendation]:
        """
        Run full analysis and generate recommendations.

        Args:
            session_id: Session to analyze

        Returns:
            List of improvement recommendations sorted by priority
        """
        recommendations = []

        # Run all analysis methods
        recommendations.extend(self._analyze_wait_times(session_id))
        recommendations.extend(self._analyze_throughput(session_id))
        recommendations.extend(self._analyze_completion_rates(session_id))
        recommendations.extend(self._analyze_service_variability(session_id))
        recommendations.extend(self._analyze_queue_patterns(session_id))
        recommendations.extend(self._analyze_peak_periods(session_id))
        recommendations.extend(self._analyze_data_quality(session_id))

        # Store recommendations
        for rec in recommendations:
            self._recommendations[rec.id] = rec

        # Sort by priority
        priority_order = {
            ImprovementPriority.CRITICAL: 0,
            ImprovementPriority.HIGH: 1,
            ImprovementPriority.MEDIUM: 2,
            ImprovementPriority.LOW: 3,
            ImprovementPriority.INFORMATIONAL: 4,
        }

        recommendations.sort(key=lambda r: priority_order[r.priority])
        return recommendations

    def get_quick_wins(
        self, session_id: str, max_results: int = 5
    ) -> List[ImprovementRecommendation]:
        """
        Get quick-win improvements that can be implemented immediately.

        Args:
            session_id: Session to analyze
            max_results: Maximum recommendations to return

        Returns:
            List of quick-win recommendations
        """
        all_recs = self.analyze_and_recommend(session_id)

        # Filter for actionable, high-impact items
        quick_wins = [
            r
            for r in all_recs
            if r.priority in (ImprovementPriority.CRITICAL, ImprovementPriority.HIGH)
            and len(r.suggested_actions) <= 3
        ]

        return quick_wins[:max_results]

    def get_service_health_report(self, session_id: str) -> Dict[str, Any]:
        """
        Generate a comprehensive service health report.

        Args:
            session_id: Session to analyze

        Returns:
            Health report with metrics, patterns, and recommendations
        """
        recommendations = self.analyze_and_recommend(session_id)
        patterns = self._detect_patterns(session_id)
        metrics = self._calculate_key_metrics(session_id)

        # Calculate overall health score
        health_score = self._calculate_health_score(metrics, recommendations)

        return {
            "timestamp": utc_now().isoformat(),
            "session_id": session_id,
            "health_score": health_score,
            "health_status": self._health_status_from_score(health_score),
            "metrics": metrics,
            "patterns": [p.to_dict() for p in patterns],
            "recommendations": {
                "critical": [
                    r.to_dict()
                    for r in recommendations
                    if r.priority == ImprovementPriority.CRITICAL
                ],
                "high": [
                    r.to_dict()
                    for r in recommendations
                    if r.priority == ImprovementPriority.HIGH
                ],
                "medium": [
                    r.to_dict()
                    for r in recommendations
                    if r.priority == ImprovementPriority.MEDIUM
                ],
                "low": [
                    r.to_dict()
                    for r in recommendations
                    if r.priority == ImprovementPriority.LOW
                ],
            },
            "summary": self._generate_summary(metrics, patterns, recommendations),
        }

    def acknowledge_recommendation(self, recommendation_id: str) -> bool:
        """Mark a recommendation as acknowledged"""
        if recommendation_id in self._recommendations:
            self._recommendations[recommendation_id].status = (
                ImprovementStatus.ACKNOWLEDGED
            )
            return True
        return False

    def dismiss_recommendation(self, recommendation_id: str, reason: str = "") -> bool:
        """Dismiss a recommendation with optional reason"""
        if recommendation_id in self._recommendations:
            self._recommendations[recommendation_id].status = (
                ImprovementStatus.DISMISSED
            )
            self._recommendations[recommendation_id].evidence[
                "dismissed_reason"
            ] = reason
            return True
        return False

    # =========================================================================
    # Analysis Methods
    # =========================================================================

    def _analyze_wait_times(self, session_id: str) -> List[ImprovementRecommendation]:
        """Analyze wait time patterns and generate recommendations"""
        recommendations = []

        try:
            # Get wait time statistics
            cursor = self._conn.execute(
                """
                WITH wait_times AS (
                    SELECT
                        CAST((julianday(e.timestamp) - julianday(q.timestamp)) * 1440 AS REAL) as wait,
                        strftime('%H', q.timestamp) as hour
                    FROM events q
                    JOIN events e ON q.token_id = e.token_id
                        AND q.session_id = e.session_id
                        AND e.stage IN ('SERVICE_START', 'EXIT')
                        AND datetime(e.timestamp) > datetime(q.timestamp)
                    WHERE q.stage = 'QUEUE_JOIN'
                        AND q.session_id = ?
                        AND datetime(q.timestamp) > datetime('now', '-' || ? || ' hours')
                )
                SELECT
                    AVG(wait) as avg_wait,
                    MAX(wait) as max_wait,
                    MIN(wait) as min_wait,
                    COUNT(*) as sample_size,
                    SUM(CASE WHEN wait > ? THEN 1 ELSE 0 END) as over_target
                FROM wait_times
            """,
                (session_id, self._analysis_window, self._target_wait),
            )

            row = cursor.fetchone()
            if row and row["sample_size"] and row["sample_size"] > 0:
                avg_wait = row["avg_wait"] or 0
                max_wait = row["max_wait"] or 0
                over_target_pct = (row["over_target"] / row["sample_size"]) * 100

                # High average wait time
                if avg_wait > self._target_wait:
                    priority = (
                        ImprovementPriority.CRITICAL
                        if avg_wait > self._target_wait * 2
                        else ImprovementPriority.HIGH
                    )
                    recommendations.append(
                        self._create_recommendation(
                            category=ImprovementCategory.QUEUE_MANAGEMENT,
                            priority=priority,
                            title="Average Wait Time Exceeds Target",
                            description=f"Average wait time is {avg_wait:.1f} minutes, exceeding the {self._target_wait} minute target.",
                            rationale="Long wait times negatively impact participant experience and may cause people to leave before being served.",
                            suggested_actions=[
                                "Consider adding additional service stations",
                                "Review service workflow for bottlenecks",
                                "Implement queue triage for quick consultations",
                            ],
                            expected_impact=f"Reducing wait time to target could improve {over_target_pct:.0f}% of participant experiences",
                            metrics_affected=[
                                "avg_wait_time",
                                "completion_rate",
                                "participant_satisfaction",
                            ],
                            evidence={
                                "avg_wait_minutes": avg_wait,
                                "target_minutes": self._target_wait,
                                "max_wait_minutes": max_wait,
                                "sample_size": row["sample_size"],
                            },
                        )
                    )

                # High variability in wait times
                if max_wait > avg_wait * 3 and row["sample_size"] > 5:
                    recommendations.append(
                        self._create_recommendation(
                            category=ImprovementCategory.QUEUE_MANAGEMENT,
                            priority=ImprovementPriority.MEDIUM,
                            title="High Wait Time Variability",
                            description=f"Maximum wait ({max_wait:.0f}min) is significantly higher than average ({avg_wait:.1f}min).",
                            rationale="Inconsistent wait times make it difficult for participants to plan and may indicate operational issues.",
                            suggested_actions=[
                                "Investigate causes of longest waits",
                                "Implement consistent service timing",
                                "Consider priority lanes for complex cases",
                            ],
                            expected_impact="More predictable service delivery and better participant planning",
                            metrics_affected=[
                                "wait_time_variance",
                                "service_predictability",
                            ],
                            evidence={
                                "avg_wait": avg_wait,
                                "max_wait": max_wait,
                                "variance_ratio": (
                                    max_wait / avg_wait if avg_wait > 0 else 0
                                ),
                            },
                        )
                    )

        except Exception as e:
            logger.error(f"Error analyzing wait times: {e}")

        return recommendations

    def _analyze_throughput(self, session_id: str) -> List[ImprovementRecommendation]:
        """Analyze throughput patterns"""
        recommendations = []

        try:
            cursor = self._conn.execute(
                """
                WITH hourly AS (
                    SELECT
                        strftime('%H', timestamp) as hour,
                        COUNT(*) as completions
                    FROM events
                    WHERE stage = 'EXIT'
                        AND session_id = ?
                        AND datetime(timestamp) > datetime('now', '-' || ? || ' hours')
                    GROUP BY strftime('%H', timestamp)
                )
                SELECT
                    AVG(completions) as avg_hourly,
                    MAX(completions) as max_hourly,
                    MIN(completions) as min_hourly,
                    COUNT(*) as hours_active
                FROM hourly
            """,
                (session_id, self._analysis_window),
            )

            row = cursor.fetchone()
            if row and row["hours_active"] and row["hours_active"] > 0:
                avg_hourly = row["avg_hourly"] or 0
                throughput_rate = (
                    (avg_hourly / self._target_throughput) * 100
                    if self._target_throughput > 0
                    else 0
                )

                # Low throughput
                if throughput_rate < 70:
                    priority = (
                        ImprovementPriority.HIGH
                        if throughput_rate < 50
                        else ImprovementPriority.MEDIUM
                    )
                    recommendations.append(
                        self._create_recommendation(
                            category=ImprovementCategory.CAPACITY,
                            priority=priority,
                            title="Throughput Below Target",
                            description=f"Current throughput ({avg_hourly:.1f}/hour) is {throughput_rate:.0f}% of target ({self._target_throughput}/hour).",
                            rationale="Low throughput means longer queues and wait times for participants.",
                            suggested_actions=[
                                "Review staffing levels during active hours",
                                "Identify and address service bottlenecks",
                                "Consider process improvements to reduce service time",
                            ],
                            expected_impact="Increased throughput would reduce queue times and serve more participants",
                            metrics_affected=[
                                "throughput_rate",
                                "queue_length",
                                "wait_time",
                            ],
                            evidence={
                                "avg_hourly_throughput": avg_hourly,
                                "target_throughput": self._target_throughput,
                                "throughput_percentage": throughput_rate,
                            },
                        )
                    )

                # High variability in throughput
                if row["max_hourly"] and row["min_hourly"]:
                    variability = row["max_hourly"] - row["min_hourly"]
                    if variability > avg_hourly * 0.5 and row["hours_active"] >= 3:
                        recommendations.append(
                            self._create_recommendation(
                                category=ImprovementCategory.STAFFING,
                                priority=ImprovementPriority.LOW,
                                title="Inconsistent Hourly Throughput",
                                description=f"Throughput varies significantly ({row['min_hourly']}-{row['max_hourly']}/hour).",
                                rationale="Variable throughput may indicate staffing gaps or inconsistent demand management.",
                                suggested_actions=[
                                    "Review staffing schedules against demand patterns",
                                    "Consider flexible staffing for peak periods",
                                    "Track and anticipate demand patterns",
                                ],
                                expected_impact="More consistent service delivery throughout operating hours",
                                metrics_affected=[
                                    "throughput_consistency",
                                    "staffing_efficiency",
                                ],
                                evidence={
                                    "min_hourly": row["min_hourly"],
                                    "max_hourly": row["max_hourly"],
                                    "variability": variability,
                                },
                            )
                        )

        except Exception as e:
            logger.error(f"Error analyzing throughput: {e}")

        return recommendations

    def _analyze_completion_rates(
        self, session_id: str
    ) -> List[ImprovementRecommendation]:
        """Analyze journey completion rates"""
        recommendations = []

        try:
            cursor = self._conn.execute(
                """
                WITH journeys AS (
                    SELECT
                        token_id,
                        MAX(CASE WHEN stage = 'QUEUE_JOIN' THEN 1 ELSE 0 END) as joined,
                        MAX(CASE WHEN stage = 'SERVICE_START' THEN 1 ELSE 0 END) as started,
                        MAX(CASE WHEN stage = 'EXIT' THEN 1 ELSE 0 END) as completed
                    FROM events
                    WHERE session_id = ?
                        AND datetime(timestamp) > datetime('now', '-' || ? || ' hours')
                    GROUP BY token_id
                )
                SELECT
                    SUM(joined) as total_joined,
                    SUM(started) as total_started,
                    SUM(completed) as total_completed,
                    SUM(CASE WHEN joined = 1 AND completed = 0 THEN 1 ELSE 0 END) as abandoned
                FROM journeys
            """,
                (session_id, self._analysis_window),
            )

            row = cursor.fetchone()
            if row and row["total_joined"] and row["total_joined"] > 5:
                total = row["total_joined"]
                completed = row["total_completed"] or 0
                abandoned = row["abandoned"] or 0
                completion_rate = (completed / total) * 100
                abandonment_rate = (abandoned / total) * 100

                # Low completion rate
                if completion_rate < 90:
                    priority = (
                        ImprovementPriority.HIGH
                        if completion_rate < 80
                        else ImprovementPriority.MEDIUM
                    )
                    recommendations.append(
                        self._create_recommendation(
                            category=ImprovementCategory.PARTICIPANT_EXPERIENCE,
                            priority=priority,
                            title="Journey Completion Rate Below Target",
                            description=f"Only {completion_rate:.1f}% of participants complete their journey.",
                            rationale="Incomplete journeys may indicate participants leaving due to long waits or poor experience.",
                            suggested_actions=[
                                "Investigate why participants are leaving early",
                                "Provide better wait time estimates",
                                "Consider queue holding or callback systems",
                            ],
                            expected_impact="Improving completion rate ensures more participants receive full service",
                            metrics_affected=[
                                "completion_rate",
                                "participant_satisfaction",
                                "service_effectiveness",
                            ],
                            evidence={
                                "total_joined": total,
                                "total_completed": completed,
                                "completion_rate": completion_rate,
                                "abandonment_count": abandoned,
                            },
                        )
                    )

                # High abandonment
                if abandonment_rate > 10:
                    recommendations.append(
                        self._create_recommendation(
                            category=ImprovementCategory.QUEUE_MANAGEMENT,
                            priority=ImprovementPriority.HIGH,
                            title="High Queue Abandonment Rate",
                            description=f"{abandonment_rate:.1f}% of participants ({abandoned} people) joined but didn't complete service.",
                            rationale="High abandonment suggests wait times are too long or participants aren't informed about expected waits.",
                            suggested_actions=[
                                "Display accurate wait time estimates",
                                "Implement text/notification when turn is near",
                                "Provide comfortable waiting area",
                                "Communicate wait expectations at queue join",
                            ],
                            expected_impact="Reducing abandonment ensures participants who want service receive it",
                            metrics_affected=["abandonment_rate", "completion_rate"],
                            evidence={
                                "abandoned_count": abandoned,
                                "abandonment_rate": abandonment_rate,
                                "total_joined": total,
                            },
                        )
                    )

        except Exception as e:
            logger.error(f"Error analyzing completion rates: {e}")

        return recommendations

    def _analyze_service_variability(
        self, session_id: str
    ) -> List[ImprovementRecommendation]:
        """Analyze service time consistency"""
        recommendations = []

        try:
            cursor = self._conn.execute(
                """
                WITH service_times AS (
                    SELECT
                        CAST((julianday(e.timestamp) - julianday(s.timestamp)) * 1440 AS REAL) as svc_time
                    FROM events s
                    JOIN events e ON s.token_id = e.token_id
                        AND s.session_id = e.session_id
                        AND e.stage = 'EXIT'
                        AND datetime(e.timestamp) > datetime(s.timestamp)
                    WHERE s.stage = 'SERVICE_START'
                        AND s.session_id = ?
                        AND datetime(s.timestamp) > datetime('now', '-' || ? || ' hours')
                )
                SELECT
                    AVG(svc_time) as avg_time,
                    MAX(svc_time) as max_time,
                    MIN(svc_time) as min_time,
                    COUNT(*) as count
                FROM service_times
                WHERE svc_time > 0
            """,
                (session_id, self._analysis_window),
            )

            row = cursor.fetchone()
            if row and row["count"] and row["count"] > 5 and row["avg_time"]:
                avg_time = row["avg_time"]
                max_time = row["max_time"]
                min_time = row["min_time"]

                # Calculate coefficient of variation estimate
                range_ratio = (max_time - min_time) / avg_time if avg_time > 0 else 0

                # High service time variability
                if range_ratio > 2:
                    recommendations.append(
                        self._create_recommendation(
                            category=ImprovementCategory.WORKFLOW,
                            priority=ImprovementPriority.MEDIUM,
                            title="High Service Time Variability",
                            description=f"Service times vary widely ({min_time:.1f}-{max_time:.1f} min, avg {avg_time:.1f} min).",
                            rationale="Inconsistent service times make queue predictions difficult and may indicate process issues.",
                            suggested_actions=[
                                "Standardize service protocols where possible",
                                "Implement separate queues for complex cases",
                                "Review longest service interactions for patterns",
                            ],
                            expected_impact="More consistent service times improve predictability and efficiency",
                            metrics_affected=[
                                "service_time_variance",
                                "wait_time_prediction_accuracy",
                            ],
                            evidence={
                                "avg_service_time": avg_time,
                                "min_service_time": min_time,
                                "max_service_time": max_time,
                                "range_ratio": range_ratio,
                            },
                        )
                    )

        except Exception as e:
            logger.error(f"Error analyzing service variability: {e}")

        return recommendations

    def _analyze_queue_patterns(
        self, session_id: str
    ) -> List[ImprovementRecommendation]:
        """Analyze queue buildup patterns"""
        recommendations = []

        try:
            # Check current queue size
            cursor = self._conn.execute(
                """
                SELECT COUNT(DISTINCT q.token_id) as queue_size
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
            if row:
                queue_size = row["queue_size"] or 0

                # Large queue
                if queue_size > 15:
                    priority = (
                        ImprovementPriority.CRITICAL
                        if queue_size > 25
                        else ImprovementPriority.HIGH
                    )
                    recommendations.append(
                        self._create_recommendation(
                            category=ImprovementCategory.OPERATIONAL,
                            priority=priority,
                            title="Large Queue Buildup",
                            description=f"Current queue has {queue_size} people waiting.",
                            rationale="Large queues indicate demand exceeds capacity and participants face long waits.",
                            suggested_actions=[
                                "Add additional service capacity immediately",
                                "Communicate wait times to new arrivals",
                                "Consider queue cutoff for very long waits",
                            ],
                            expected_impact="Managing queue size improves participant experience and staff workload",
                            metrics_affected=[
                                "queue_length",
                                "wait_time",
                                "abandonment_rate",
                            ],
                            evidence={"current_queue_size": queue_size},
                        )
                    )

        except Exception as e:
            logger.error(f"Error analyzing queue patterns: {e}")

        return recommendations

    def _analyze_peak_periods(self, session_id: str) -> List[ImprovementRecommendation]:
        """Analyze demand patterns by hour"""
        recommendations = []

        try:
            cursor = self._conn.execute(
                """
                SELECT
                    strftime('%H', timestamp) as hour,
                    COUNT(*) as joins
                FROM events
                WHERE stage = 'QUEUE_JOIN'
                    AND session_id = ?
                    AND datetime(timestamp) > datetime('now', '-' || ? || ' hours')
                GROUP BY strftime('%H', timestamp)
                HAVING COUNT(*) > 3
                ORDER BY joins DESC
            """,
                (session_id, self._analysis_window),
            )

            rows = cursor.fetchall()
            if len(rows) >= 3:
                # Find peak hours
                peak_hours = [r["hour"] for r in rows[:3]]
                peak_demand = rows[0]["joins"] if rows else 0
                avg_demand = sum(r["joins"] for r in rows) / len(rows)

                if peak_demand > avg_demand * 1.5:
                    recommendations.append(
                        self._create_recommendation(
                            category=ImprovementCategory.STAFFING,
                            priority=ImprovementPriority.INFORMATIONAL,
                            title="Peak Demand Periods Identified",
                            description=f"Highest demand occurs at hours: {', '.join(peak_hours)} (up to {peak_demand} joins/hour).",
                            rationale="Understanding demand patterns allows proactive staffing adjustments.",
                            suggested_actions=[
                                f"Ensure maximum staffing during peak hours ({', '.join(peak_hours)})",
                                "Consider break schedules around peak times",
                                "Plan queue management strategies for peak periods",
                            ],
                            expected_impact="Proactive staffing for peaks reduces wait times during high demand",
                            metrics_affected=["staffing_efficiency", "peak_wait_times"],
                            evidence={
                                "peak_hours": peak_hours,
                                "peak_demand": peak_demand,
                                "average_demand": avg_demand,
                            },
                        )
                    )

        except Exception as e:
            logger.error(f"Error analyzing peak periods: {e}")

        return recommendations

    def _analyze_data_quality(self, session_id: str) -> List[ImprovementRecommendation]:
        """Analyze data quality issues"""
        recommendations = []

        try:
            # Check for sequence issues
            cursor = self._conn.execute(
                """
                WITH sequences AS (
                    SELECT
                        token_id,
                        GROUP_CONCAT(stage, '->') as seq,
                        COUNT(*) as stage_count
                    FROM (
                        SELECT token_id, stage, timestamp
                        FROM events
                        WHERE session_id = ?
                            AND datetime(timestamp) > datetime('now', '-' || ? || ' hours')
                        ORDER BY token_id, timestamp
                    )
                    GROUP BY token_id
                )
                SELECT
                    COUNT(*) as total_journeys,
                    SUM(CASE WHEN seq NOT LIKE 'QUEUE_JOIN%' THEN 1 ELSE 0 END) as missing_join,
                    SUM(CASE WHEN seq NOT LIKE '%EXIT' AND stage_count > 1 THEN 1 ELSE 0 END) as missing_exit
                FROM sequences
            """,
                (session_id, self._analysis_window),
            )

            row = cursor.fetchone()
            if row and row["total_journeys"] and row["total_journeys"] > 5:
                total = row["total_journeys"]
                missing_join = row["missing_join"] or 0
                missing_exit = row["missing_exit"] or 0

                data_quality_issues = missing_join + missing_exit
                issue_rate = (data_quality_issues / total) * 100

                if issue_rate > 10:
                    recommendations.append(
                        self._create_recommendation(
                            category=ImprovementCategory.DATA_QUALITY,
                            priority=ImprovementPriority.MEDIUM,
                            title="Data Quality Issues Detected",
                            description=f"{issue_rate:.1f}% of journeys have sequence issues ({missing_join} missing joins, {missing_exit} missing exits).",
                            rationale="Data quality affects reporting accuracy and operational insights.",
                            suggested_actions=[
                                "Review tap station procedures with staff",
                                "Check hardware reliability at all stations",
                                "Consider staff refresher training on workflow",
                            ],
                            expected_impact="Better data quality improves all metrics and insights",
                            metrics_affected=[
                                "data_completeness",
                                "reporting_accuracy",
                            ],
                            evidence={
                                "total_journeys": total,
                                "missing_joins": missing_join,
                                "missing_exits": missing_exit,
                                "issue_rate": issue_rate,
                            },
                        )
                    )

        except Exception as e:
            logger.error(f"Error analyzing data quality: {e}")

        return recommendations

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _create_recommendation(
        self,
        category: ImprovementCategory,
        priority: ImprovementPriority,
        title: str,
        description: str,
        rationale: str,
        suggested_actions: List[str],
        expected_impact: str,
        metrics_affected: List[str],
        evidence: Dict[str, Any],
    ) -> ImprovementRecommendation:
        """Create a new recommendation with unique ID"""
        self._recommendation_counter += 1
        return ImprovementRecommendation(
            id=f"REC-{self._recommendation_counter:04d}",
            category=category,
            priority=priority,
            title=title,
            description=description,
            rationale=rationale,
            suggested_actions=suggested_actions,
            expected_impact=expected_impact,
            metrics_affected=metrics_affected,
            evidence=evidence,
        )

    def _detect_patterns(self, session_id: str) -> List[ServicePattern]:
        """Detect recurring patterns in service data"""
        patterns = []
        now = utc_now()

        # This is a simplified pattern detection - can be expanded
        try:
            # Check for queue buildup pattern
            cursor = self._conn.execute(
                """
                SELECT COUNT(*) as hours_with_high_queue
                FROM (
                    SELECT strftime('%H', timestamp) as hour, COUNT(*) as queue_joins
                    FROM events
                    WHERE stage = 'QUEUE_JOIN'
                        AND session_id = ?
                        AND datetime(timestamp) > datetime('now', '-' || ? || ' hours')
                    GROUP BY strftime('%H', timestamp)
                    HAVING COUNT(*) > 10
                )
            """,
                (session_id, self._analysis_window),
            )

            row = cursor.fetchone()
            if (
                row
                and row["hours_with_high_queue"]
                and row["hours_with_high_queue"] >= 2
            ):
                patterns.append(
                    ServicePattern(
                        pattern_type="recurring_high_demand",
                        description="Multiple hours with high queue joins detected",
                        frequency=row["hours_with_high_queue"] / self._analysis_window,
                        impact_score=75.0,
                        trend="stable",
                        data_points=row["hours_with_high_queue"],
                        first_seen=now - timedelta(hours=self._analysis_window),
                        last_seen=now,
                    )
                )

        except Exception as e:
            logger.error(f"Error detecting patterns: {e}")

        self._patterns = patterns
        return patterns

    def _calculate_key_metrics(self, session_id: str) -> Dict[str, Any]:
        """Calculate key service metrics"""
        metrics = {
            "avg_wait_time": 0,
            "throughput_rate": 0,
            "completion_rate": 100,
            "queue_size": 0,
            "served_today": 0,
        }

        try:
            # Average wait time
            cursor = self._conn.execute(
                """
                SELECT AVG(CAST((julianday(e.timestamp) - julianday(q.timestamp)) * 1440 AS REAL)) as avg_wait
                FROM events q
                JOIN events e ON q.token_id = e.token_id AND q.session_id = e.session_id
                WHERE q.stage = 'QUEUE_JOIN' AND e.stage IN ('SERVICE_START', 'EXIT')
                    AND q.session_id = ? AND datetime(q.timestamp) > datetime('now', '-4 hours')
            """,
                (session_id,),
            )
            row = cursor.fetchone()
            if row and row["avg_wait"]:
                metrics["avg_wait_time"] = round(row["avg_wait"], 1)

            # Current queue size
            cursor = self._conn.execute(
                """
                SELECT COUNT(DISTINCT q.token_id) as queue_size
                FROM events q
                LEFT JOIN events e ON q.token_id = e.token_id AND q.session_id = e.session_id AND e.stage = 'EXIT'
                WHERE q.stage = 'QUEUE_JOIN' AND q.session_id = ? AND e.id IS NULL
            """,
                (session_id,),
            )
            row = cursor.fetchone()
            if row:
                metrics["queue_size"] = row["queue_size"] or 0

            # Served today
            cursor = self._conn.execute(
                """
                SELECT COUNT(*) as served FROM events
                WHERE stage = 'EXIT' AND session_id = ? AND date(timestamp) = date('now')
            """,
                (session_id,),
            )
            row = cursor.fetchone()
            if row:
                metrics["served_today"] = row["served"] or 0

        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")

        return metrics

    def _calculate_health_score(
        self, metrics: Dict[str, Any], recommendations: List[ImprovementRecommendation]
    ) -> float:
        """Calculate overall health score (0-100)"""
        score = 100.0

        # Deduct for critical/high recommendations
        critical_count = sum(
            1 for r in recommendations if r.priority == ImprovementPriority.CRITICAL
        )
        high_count = sum(
            1 for r in recommendations if r.priority == ImprovementPriority.HIGH
        )

        score -= critical_count * 15
        score -= high_count * 8

        # Deduct for poor metrics
        if metrics["avg_wait_time"] > self._target_wait:
            score -= min(
                20,
                (metrics["avg_wait_time"] - self._target_wait) / self._target_wait * 20,
            )

        if metrics["queue_size"] > 15:
            score -= min(15, (metrics["queue_size"] - 15) * 1.5)

        return max(0, min(100, score))

    def _health_status_from_score(self, score: float) -> str:
        """Convert health score to status label"""
        if score >= 90:
            return "excellent"
        elif score >= 75:
            return "good"
        elif score >= 60:
            return "fair"
        elif score >= 40:
            return "needs_attention"
        else:
            return "critical"

    def _generate_summary(
        self,
        metrics: Dict[str, Any],
        patterns: List[ServicePattern],
        recommendations: List[ImprovementRecommendation],
    ) -> str:
        """Generate a human-readable summary"""
        critical_count = sum(
            1 for r in recommendations if r.priority == ImprovementPriority.CRITICAL
        )
        high_count = sum(
            1 for r in recommendations if r.priority == ImprovementPriority.HIGH
        )

        parts = []

        if critical_count > 0:
            parts.append(
                f"{critical_count} critical issue(s) require immediate attention"
            )
        if high_count > 0:
            parts.append(f"{high_count} high-priority improvement(s) recommended")

        if metrics["queue_size"] > 10:
            parts.append(f"Queue currently has {metrics['queue_size']} people")

        if metrics["avg_wait_time"] > self._target_wait:
            parts.append(
                f"Average wait time ({metrics['avg_wait_time']}min) exceeds target ({self._target_wait}min)"
            )

        if not parts:
            return "Service is operating well with no critical issues identified."

        return ". ".join(parts) + "."


# =============================================================================
# Global Instance
# =============================================================================

_improvement_engine: Optional[ServiceImprovementEngine] = None


def get_improvement_engine(conn: sqlite3.Connection) -> ServiceImprovementEngine:
    """Get or create the service improvement engine"""
    global _improvement_engine
    if _improvement_engine is None:
        _improvement_engine = ServiceImprovementEngine(conn)
    return _improvement_engine


def analyze_service(conn: sqlite3.Connection, session_id: str) -> Dict[str, Any]:
    """Convenience function to run analysis and get health report"""
    engine = get_improvement_engine(conn)
    return engine.get_service_health_report(session_id)
