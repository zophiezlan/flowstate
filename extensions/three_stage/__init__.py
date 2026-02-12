"""Three-stage metrics extension - queue wait vs service time breakdown."""

import logging
from datetime import datetime, timezone

from tap_station.extension import Extension, resolve_stage

logger = logging.getLogger(__name__)


class ThreeStageExtension(Extension):
    """Separate queue wait and service time metrics for 3-stage workflows."""

    name = "three_stage"
    order = 40  # Before general dashboard extensions

    def on_startup(self, ctx):
        self._config = ctx["config"]
        self._db = ctx["db"]
        self._stage_exit = resolve_stage("EXIT")
        self._stage_join = resolve_stage("QUEUE_JOIN")
        self._stage_service_start = resolve_stage("SERVICE_START")

    def on_dashboard_stats(self, stats):
        """Add 3-stage metrics and in-service count to dashboard."""
        three_stage = self._calculate_3stage_metrics(limit=20)
        in_service = self._get_current_in_service()

        # Inject into stats.stats
        s = stats.get("stats", {})
        s["avg_queue_wait_minutes"] = three_stage["avg_queue_wait_minutes"]
        s["avg_service_time_minutes"] = three_stage["avg_service_time_minutes"]
        s["avg_total_time_minutes"] = three_stage["avg_total_time_minutes"]
        s["has_3stage_data"] = three_stage["has_3stage_data"]
        s["in_service"] = in_service

    def _calculate_3stage_metrics(self, limit=20):
        """Calculate separate metrics for 3-stage journey."""
        if not self._stage_service_start:
            return {
                "avg_queue_wait_minutes": 0,
                "avg_service_time_minutes": 0,
                "avg_total_time_minutes": 0,
                "has_3stage_data": False,
                "journeys_analyzed": 0,
                "three_stage_count": 0,
            }

        session_id = self._config.session_id

        try:
            cursor = self._db.conn.execute(
                """
                SELECT
                    q.token_id,
                    q.timestamp as queue_time,
                    s.timestamp as service_start_time,
                    e.timestamp as exit_time
                FROM events q
                LEFT JOIN events s
                    ON q.token_id = s.token_id
                    AND q.session_id = s.session_id
                    AND s.stage = ?
                LEFT JOIN events e
                    ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                    AND e.stage = ?
                WHERE q.stage = ?
                    AND q.session_id = ?
                    AND e.timestamp IS NOT NULL
                ORDER BY e.timestamp DESC
                LIMIT ?
            """,
                (
                    self._stage_service_start,
                    self._stage_exit,
                    self._stage_join,
                    session_id,
                    limit,
                ),
            )

            journeys = cursor.fetchall()

            if not journeys:
                return {
                    "avg_queue_wait_minutes": 0,
                    "avg_service_time_minutes": 0,
                    "avg_total_time_minutes": 0,
                    "has_3stage_data": False,
                    "journeys_analyzed": 0,
                }

            queue_waits = []
            service_times = []
            total_times = []
            three_stage_count = 0

            for journey in journeys:
                queue_dt = datetime.fromisoformat(journey["queue_time"])
                exit_dt = datetime.fromisoformat(journey["exit_time"])

                total_minutes = (exit_dt - queue_dt).total_seconds() / 60
                total_times.append(total_minutes)

                if journey["service_start_time"]:
                    service_start_dt = datetime.fromisoformat(
                        journey["service_start_time"],
                    )
                    queue_wait = (
                        service_start_dt - queue_dt
                    ).total_seconds() / 60
                    service_time = (
                        exit_dt - service_start_dt
                    ).total_seconds() / 60

                    if 0 <= queue_wait < 1440 and 0 <= service_time < 1440:
                        queue_waits.append(queue_wait)
                        service_times.append(service_time)
                        three_stage_count += 1

            has_3stage = three_stage_count > 0

            return {
                "avg_queue_wait_minutes": (
                    int(sum(queue_waits) / len(queue_waits))
                    if queue_waits else 0
                ),
                "avg_service_time_minutes": (
                    int(sum(service_times) / len(service_times))
                    if service_times else 0
                ),
                "avg_total_time_minutes": (
                    int(sum(total_times) / len(total_times))
                    if total_times else 0
                ),
                "has_3stage_data": has_3stage,
                "journeys_analyzed": len(journeys),
                "three_stage_count": three_stage_count,
            }

        except Exception as e:
            logger.warning("Failed to calculate 3-stage metrics: %s", e)
            return {
                "avg_queue_wait_minutes": 0,
                "avg_service_time_minutes": 0,
                "avg_total_time_minutes": 0,
                "has_3stage_data": False,
                "journeys_analyzed": 0,
            }

    def _get_current_in_service(self):
        """Get count of people currently being served."""
        if not self._stage_service_start:
            return 0

        session_id = self._config.session_id

        try:
            cursor = self._db.conn.execute(
                """
                SELECT COUNT(DISTINCT s.token_id) as count
                FROM events s
                LEFT JOIN events e
                    ON s.token_id = e.token_id
                    AND s.session_id = e.session_id
                    AND e.stage = ?
                WHERE s.stage = ?
                    AND s.session_id = ?
                    AND e.id IS NULL
            """,
                (self._stage_exit, self._stage_service_start, session_id),
            )

            return cursor.fetchone()["count"]

        except Exception as e:
            logger.warning("Failed to get in-service count: %s", e)
            return 0


extension = ThreeStageExtension()
