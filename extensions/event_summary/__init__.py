"""Event summary extension - end-of-day summary report."""

import logging
from datetime import datetime, timezone

from flask import jsonify, render_template

from tap_station.extension import Extension

logger = logging.getLogger(__name__)


class EventSummaryExtension(Extension):
    """End-of-day event summary with goals and assessments."""

    name = "event_summary"
    order = 50

    def on_api_routes(self, app, db, config):
        stage_exit = _get_stage(config, "EXIT")
        stage_join = _get_stage(config, "QUEUE_JOIN")
        stage_service_start = _get_stage(config, "SERVICE_START")

        @app.route("/event-summary")
        def event_summary():
            """Event summary page."""
            return render_template(
                "event_summary.html",
                session=config.session_id,
                device_id=config.device_id,
            )

        @app.route("/api/event-summary")
        def api_event_summary():
            """API endpoint for event summary data."""
            try:
                summary = _calculate_event_summary(
                    db, config, stage_exit, stage_join, stage_service_start,
                )
                return jsonify(summary), 200
            except Exception as e:
                logger.error("Event summary failed: %s", e)
                return jsonify({"error": str(e)}), 500

        def _calculate_event_summary(
            db, config, stage_exit, stage_join, stage_service_start,
        ):
            session_id = config.session_id
            now = datetime.now(timezone.utc)

            # Get all completed journeys
            cursor = db.conn.execute(
                """
                SELECT
                    j.token_id,
                    j.timestamp as queue_time,
                    e.timestamp as exit_time,
                    s.timestamp as service_start_time,
                    CAST((julianday(e.timestamp) - julianday(j.timestamp)) * 1440 AS INTEGER) as total_minutes,
                    CAST((julianday(e.timestamp) - julianday(COALESCE(s.timestamp, j.timestamp))) * 1440 AS INTEGER) as service_minutes
                FROM events j
                JOIN events e ON j.token_id = e.token_id
                            AND j.session_id = e.session_id
                            AND e.stage = ?
                LEFT JOIN events s ON j.token_id = s.token_id
                                 AND j.session_id = s.session_id
                                 AND s.stage = ?
                WHERE j.stage = ?
                    AND j.session_id = ?
                    AND datetime(e.timestamp) > datetime(j.timestamp)
                ORDER BY j.timestamp ASC
                """,
                (stage_exit, stage_service_start, stage_join, session_id),
            )

            journeys = cursor.fetchall()
            total_served = len(journeys)

            wait_times = [
                j["total_minutes"] for j in journeys if j["total_minutes"] > 0
            ]
            service_times = [
                j["service_minutes"]
                for j in journeys
                if j["service_minutes"] and j["service_minutes"] > 0
            ]

            avg_wait_min = (
                int(sum(wait_times) / len(wait_times)) if wait_times else 0
            )
            median_wait_min = (
                int(sorted(wait_times)[len(wait_times) // 2])
                if wait_times else 0
            )
            avg_service_min = (
                int(sum(service_times) / len(service_times))
                if service_times else 0
            )
            p90_service_min = (
                int(sorted(service_times)[int(len(service_times) * 0.9)])
                if len(service_times) > 10
                else avg_service_min
            )

            # Peak queue
            cursor = db.conn.execute(
                """
                SELECT
                    datetime(timestamp) as time,
                    (SELECT COUNT(DISTINCT q.token_id)
                     FROM events q
                     LEFT JOIN events e ON q.token_id = e.token_id
                                        AND q.session_id = e.session_id
                                        AND e.stage = ?
                                        AND datetime(e.timestamp) <= datetime(events.timestamp)
                     WHERE q.stage = ?
                       AND q.session_id = ?
                       AND datetime(q.timestamp) <= datetime(events.timestamp)
                       AND (e.id IS NULL OR datetime(e.timestamp) > datetime(events.timestamp))
                    ) as queue_length
                FROM events
                WHERE session_id = ?
                ORDER BY queue_length DESC
                LIMIT 1
                """,
                (stage_exit, stage_join, session_id, session_id),
            )

            peak_row = cursor.fetchone()
            peak_queue = peak_row["queue_length"] if peak_row else 0
            peak_time = (
                peak_row["time"].split()[1][:5]
                if peak_row and peak_row["time"]
                else "N/A"
            )

            # Service hours and throughput
            cursor = db.conn.execute(
                "SELECT MIN(timestamp) as first_event, MAX(timestamp) as last_event FROM events WHERE session_id = ?",
                (session_id,),
            )
            time_row = cursor.fetchone()
            service_hours = 0
            if time_row and time_row["first_event"] and time_row["last_event"]:
                first_dt = datetime.fromisoformat(time_row["first_event"])
                last_dt = datetime.fromisoformat(time_row["last_event"])
                service_hours = round(
                    (last_dt - first_dt).total_seconds() / 3600, 1,
                )

            throughput = (
                int(total_served / service_hours)
                if service_hours > 0 else 0
            )

            # Abandonment
            cursor = db.conn.execute(
                """
                SELECT COUNT(DISTINCT q.token_id) as abandoned
                FROM events q
                LEFT JOIN events e ON q.token_id = e.token_id
                                   AND q.session_id = e.session_id
                                   AND e.stage = ?
                WHERE q.stage = ?
                    AND q.session_id = ?
                    AND e.id IS NULL
                """,
                (stage_exit, stage_join, session_id),
            )
            abandoned_count = cursor.fetchone()["abandoned"]
            total_joined = total_served + abandoned_count
            abandonment_rate = (
                int((abandoned_count / total_joined) * 100)
                if total_joined > 0 else 0
            )

            # Anomalies summary
            anomalies = db.get_anomalies(session_id)
            anomalies_summary = {
                "total_anomalies": anomalies.get("summary", {}).get(
                    "total_anomalies", 0,
                ),
                "forgotten_exits": len(
                    anomalies.get("forgotten_exit_taps", []),
                ),
                "stuck_in_service": len(
                    anomalies.get("stuck_in_service", []),
                ),
                "rapid_fire_taps": len(
                    anomalies.get("rapid_fire_taps", []),
                ),
            }

            # Busiest period
            cursor = db.conn.execute(
                """
                SELECT
                    strftime('%H:00', timestamp) as hour,
                    COUNT(*) as count
                FROM events
                WHERE session_id = ? AND stage = ?
                GROUP BY hour
                ORDER BY count DESC
                LIMIT 1
                """,
                (session_id, stage_exit),
            )
            busiest_row = cursor.fetchone()
            busiest_period = busiest_row["hour"] if busiest_row else "N/A"
            busiest_count = busiest_row["count"] if busiest_row else 0

            # Quality assessment
            if avg_wait_min < 10:
                quality_assessment = "Excellent - average wait under 10 minutes"
            elif avg_wait_min < 20:
                quality_assessment = "Good - average wait under 20 minutes"
            elif avg_wait_min < 30:
                quality_assessment = "Fair - average wait 20-30 minutes"
            else:
                quality_assessment = (
                    "Needs improvement - average wait exceeds 30 minutes"
                )

            # Capacity assessment
            if peak_queue < 10:
                capacity_assessment = (
                    "Well-managed - peak queue stayed under 10 people"
                )
            elif peak_queue < 20:
                capacity_assessment = (
                    "Adequate - peak queue reached 10-20 people"
                )
            else:
                capacity_assessment = (
                    f"Strained - peak queue reached {peak_queue} people,"
                    " consider adding capacity"
                )

            # Goals
            goals = [
                {
                    "name": "Serve 150+ Participants",
                    "target": 150,
                    "actual": total_served,
                    "unit": "people",
                    "progress_percent": min(
                        100, int((total_served / 150) * 100),
                    ),
                    "status_class": (
                        "goal-achieved" if total_served >= 150
                        else ("goal-partial" if total_served >= 100
                              else "goal-missed")
                    ),
                    "status_text": (
                        "\u2713 Achieved" if total_served >= 150
                        else (f"{int((total_served / 150) * 100)}% Complete"
                              if total_served >= 100 else "Not Met")
                    ),
                    "progress_class": (
                        "" if total_served >= 150
                        else ("warning" if total_served >= 100 else "danger")
                    ),
                },
                {
                    "name": "Average Wait <15 Minutes",
                    "target": 15,
                    "actual": avg_wait_min,
                    "unit": "min avg",
                    "progress_percent": min(
                        100, int((15 / max(avg_wait_min, 1)) * 100),
                    ),
                    "status_class": (
                        "goal-achieved" if avg_wait_min <= 15
                        else ("goal-partial" if avg_wait_min <= 25
                              else "goal-missed")
                    ),
                    "status_text": (
                        "\u2713 Achieved" if avg_wait_min <= 15
                        else (f"{avg_wait_min} min" if avg_wait_min <= 25
                              else "Not Met")
                    ),
                    "progress_class": (
                        "" if avg_wait_min <= 15
                        else ("warning" if avg_wait_min <= 25 else "danger")
                    ),
                },
                {
                    "name": "Abandonment Rate <10%",
                    "target": 10,
                    "actual": abandonment_rate,
                    "unit": "%",
                    "progress_percent": (
                        min(
                            100,
                            int((10 / max(abandonment_rate, 1)) * 100),
                        )
                        if abandonment_rate > 0 else 100
                    ),
                    "status_class": (
                        "goal-achieved" if abandonment_rate <= 10
                        else ("goal-partial" if abandonment_rate <= 20
                              else "goal-missed")
                    ),
                    "status_text": (
                        "\u2713 Achieved" if abandonment_rate <= 10
                        else (f"{abandonment_rate}%"
                              if abandonment_rate <= 20 else "Not Met")
                    ),
                    "progress_class": (
                        "" if abandonment_rate <= 10
                        else ("warning" if abandonment_rate <= 20
                              else "danger")
                    ),
                },
            ]

            return {
                "session_id": session_id,
                "event_date": datetime.now().strftime("%B %d, %Y"),
                "total_served": total_served,
                "avg_wait_min": avg_wait_min,
                "median_wait_min": median_wait_min,
                "peak_queue": peak_queue,
                "peak_time": peak_time,
                "throughput": throughput,
                "service_hours": service_hours,
                "abandonment_rate": abandonment_rate,
                "abandoned_count": abandoned_count,
                "avg_service_min": avg_service_min,
                "p90_service_min": p90_service_min,
                "anomalies_summary": anomalies_summary,
                "goals": goals,
                "busiest_period": busiest_period,
                "busiest_count": busiest_count,
                "quality_assessment": quality_assessment,
                "capacity_assessment": capacity_assessment,
                "session_timeout_minutes": app.config.get(
                    "ADMIN_SESSION_TIMEOUT_MINUTES", 60,
                ),
            }


def _get_stage(config, fallback):
    """Resolve stage name from service integration or use fallback."""
    try:
        from tap_station.service_integration import get_service_integration

        svc = get_service_integration()
        if svc:
            if fallback == "EXIT":
                return svc.get_last_stage()
            elif fallback == "QUEUE_JOIN":
                return svc.get_first_stage()
            elif fallback == "SERVICE_START":
                return svc.get_service_start_stage()
    except ImportError:
        pass
    if fallback == "SERVICE_START":
        return None
    return fallback


extension = EventSummaryExtension()
