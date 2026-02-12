"""Smart estimates extension - intelligent wait time predictions."""

import logging
from datetime import datetime, timezone

from tap_station.extension import Extension, resolve_stage

logger = logging.getLogger(__name__)


class SmartEstimatesExtension(Extension):
    """Calculate smart wait estimates using recent completion rates."""

    name = "smart_estimates"
    order = 45

    def on_startup(self, ctx):
        self._config = ctx["config"]
        self._db = ctx["db"]
        self._svc = None
        self._stage_exit = resolve_stage("EXIT")
        self._stage_join = resolve_stage("QUEUE_JOIN")

        try:
            from tap_station.service_integration import get_service_integration

            self._svc = get_service_integration()
        except ImportError:
            pass

    def on_dashboard_stats(self, stats):
        """Add smart wait estimate to dashboard stats."""
        smart_estimate = self._calculate_smart_wait_estimate()
        s = stats.get("stats", {})
        s["smart_wait_estimate"] = smart_estimate

    def _calculate_avg_wait_time(self, limit=20):
        """Calculate average wait time from recent completions."""
        try:
            cursor = self._db.conn.execute(
                """
                SELECT
                    q.timestamp as queue_time,
                    e.timestamp as exit_time
                FROM events q
                JOIN events e
                    ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                WHERE q.stage = ?
                    AND e.stage = ?
                    AND q.session_id = ?
                ORDER BY e.timestamp DESC
                LIMIT ?
            """,
                (
                    self._stage_join,
                    self._stage_exit,
                    self._config.session_id,
                    limit,
                ),
            )

            journeys = cursor.fetchall()

            if not journeys:
                return 0

            total_wait = 0
            for journey in journeys:
                queue_dt = datetime.fromisoformat(journey["queue_time"])
                exit_dt = datetime.fromisoformat(journey["exit_time"])
                wait_minutes = (exit_dt - queue_dt).total_seconds() / 60
                total_wait += wait_minutes

            return int(total_wait / len(journeys))

        except Exception as e:
            logger.warning("Failed to calculate avg wait time: %s", e)
            return 0

    def _calculate_smart_wait_estimate(self):
        """Calculate smart wait time estimate using recent completion rates."""
        session_id = self._config.session_id

        try:
            # Current queue length
            cursor = self._db.conn.execute(
                """
                SELECT COUNT(DISTINCT q.token_id) as count
                FROM events q
                LEFT JOIN events e
                    ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                    AND e.stage = ?
                WHERE q.stage = ?
                    AND q.session_id = ?
                    AND e.id IS NULL
            """,
                (self._stage_exit, self._stage_join, session_id),
            )
            queue_length = cursor.fetchone()["count"]

            # Recent completion rate (last 30 minutes)
            cursor = self._db.conn.execute(
                """
                SELECT COUNT(*) as completions,
                       MIN(e.timestamp) as first_completion
                FROM events q
                JOIN events e
                    ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                WHERE q.stage = ?
                    AND e.stage = ?
                    AND q.session_id = ?
                    AND e.timestamp > datetime('now', '-30 minutes')
            """,
                (self._stage_join, self._stage_exit, session_id),
            )

            recent_data = cursor.fetchone()
            recent_completions = recent_data["completions"]

            # Average service time from recent completions
            cursor = self._db.conn.execute(
                """
                SELECT
                    AVG(
                        (julianday(e.timestamp) - julianday(q.timestamp)) * 1440
                    ) as avg_time
                FROM events q
                JOIN events e
                    ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                WHERE q.stage = ?
                    AND e.stage = ?
                    AND q.session_id = ?
                    AND e.timestamp > datetime('now', '-30 minutes')
            """,
                (self._stage_join, self._stage_exit, session_id),
            )

            avg_service_time = cursor.fetchone()["avg_time"] or 0

            # Confidence based on sample size
            if recent_completions >= 5:
                confidence = "high"
                confidence_icon = "\u2713"
            elif recent_completions >= 2:
                confidence = "medium"
                confidence_icon = "~"
            else:
                confidence = "low"
                confidence_icon = "?"

            # Calculate estimate
            if recent_completions > 0 and avg_service_time > 0:
                minutes_per_person = avg_service_time
                estimated_wait = int(queue_length * minutes_per_person)
                method = "recent_rate"
                reasoning = (
                    f"Based on {recent_completions} recent completions"
                    f" (~{int(avg_service_time)} min/person)"
                )
            else:
                # Fall back to overall average
                wait_sample_size = (
                    self._svc.get_wait_time_sample_size()
                    if self._svc else 20
                )
                overall_avg = self._calculate_avg_wait_time(
                    limit=wait_sample_size,
                )
                queue_mult = (
                    self._svc.get_queue_multiplier() if self._svc else 2
                )
                default_wait = (
                    self._svc.get_default_wait_estimate() if self._svc else 20
                )
                if overall_avg > 0:
                    estimated_wait = overall_avg + (queue_length * queue_mult)
                    method = "overall_avg"
                    reasoning = (
                        f"Using overall average ({queue_length} in queue)"
                    )
                else:
                    estimated_wait = default_wait if queue_length > 0 else 0
                    method = "default"
                    reasoning = "Insufficient data for accurate estimate"
                    confidence = "low"
                    confidence_icon = "?"

            # Cap at 2 hours
            if estimated_wait > 120:
                estimated_wait = 120
                reasoning += " (capped at 2 hours)"

            return {
                "estimate_minutes": estimated_wait,
                "confidence": confidence,
                "confidence_icon": confidence_icon,
                "method": method,
                "reasoning": reasoning,
                "queue_length": queue_length,
                "recent_completions": recent_completions,
                "avg_service_time": (
                    round(avg_service_time, 1) if avg_service_time else 0
                ),
            }

        except Exception as e:
            logger.error("Smart wait estimate failed: %s", e)
            return {
                "estimate_minutes": 20,
                "confidence": "low",
                "confidence_icon": "?",
                "method": "error",
                "reasoning": "Error calculating estimate",
                "queue_length": 0,
                "recent_completions": 0,
                "avg_service_time": 0,
            }


extension = SmartEstimatesExtension()
