"""Shift summary extension - shift handoff reports."""

import logging
from datetime import datetime, timezone

from flask import jsonify, render_template

from tap_station.extension import Extension, resolve_stage

logger = logging.getLogger(__name__)


class ShiftSummaryExtension(Extension):
    """Shift handoff summary with queue/completion stats."""

    name = "shift_summary"
    order = 50

    def on_startup(self, ctx):
        self._config = ctx["config"]

    def on_api_routes(self, app, db, config):
        @app.route("/shift")
        def shift():
            """Shift handoff summary page."""
            return render_template(
                "shift.html",
                session=config.session_id,
                device_id=config.device_id,
            )

        @app.route("/api/shift-summary")
        def api_shift_summary():
            """API endpoint for shift handoff summary."""
            try:
                summary = _get_shift_summary(db, config)
                return jsonify(summary), 200
            except Exception as e:
                logger.error("API shift summary failed: %s", e)
                return jsonify({"error": str(e)}), 500

        def _get_shift_summary(db, config):
            session_id = config.session_id
            now = datetime.now(timezone.utc)

            # Resolve stage names from service integration
            stage_exit = resolve_stage("EXIT")
            stage_join = resolve_stage("QUEUE_JOIN")

            # Current queue state
            cursor = db.conn.execute(
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
                (stage_exit, stage_join, session_id),
            )
            current_queue = cursor.fetchone()["count"]

            # Completed this shift (last 4 hours)
            cursor = db.conn.execute(
                """
                SELECT COUNT(*) as count
                FROM events q
                JOIN events e
                    ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                WHERE q.stage = ?
                    AND e.stage = ?
                    AND q.session_id = ?
                    AND e.timestamp > datetime('now', '-4 hours')
                """,
                (stage_join, stage_exit, session_id),
            )
            completed_shift = cursor.fetchone()["count"]

            # Average wait this shift
            cursor = db.conn.execute(
                """
                SELECT
                    AVG((julianday(e.timestamp) - julianday(q.timestamp)) * 1440) as avg_wait
                FROM events q
                JOIN events e
                    ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                WHERE q.stage = ?
                    AND e.stage = ?
                    AND q.session_id = ?
                    AND e.timestamp > datetime('now', '-4 hours')
                """,
                (stage_join, stage_exit, session_id),
            )
            row = cursor.fetchone()
            avg_wait_shift = int(row["avg_wait"]) if row["avg_wait"] else 0

            # Busiest hour this shift
            cursor = db.conn.execute(
                """
                SELECT
                    strftime('%H:00', e.timestamp) as hour,
                    COUNT(*) as count
                FROM events q
                JOIN events e
                    ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                WHERE q.stage = ?
                    AND e.stage = ?
                    AND q.session_id = ?
                    AND e.timestamp > datetime('now', '-4 hours')
                GROUP BY hour
                ORDER BY count DESC
                LIMIT 1
                """,
                (stage_join, stage_exit, session_id),
            )
            busiest = cursor.fetchone()
            busiest_hour = busiest["hour"] if busiest else "N/A"
            busiest_count = busiest["count"] if busiest else 0

            # Service uptime today
            cursor = db.conn.execute(
                """
                SELECT MIN(timestamp) as first_event
                FROM events
                WHERE session_id = ?
                    AND date(timestamp) = date('now')
                """,
                (session_id,),
            )
            row = cursor.fetchone()
            service_hours = 0
            if row and row["first_event"]:
                first_dt = datetime.fromisoformat(row["first_event"])
                service_hours = round(
                    (now - first_dt).total_seconds() / 3600, 1
                )

            # Longest current wait
            cursor = db.conn.execute(
                """
                SELECT MIN(q.timestamp) as earliest
                FROM events q
                LEFT JOIN events e
                    ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                    AND e.stage = ?
                WHERE q.stage = ?
                    AND q.session_id = ?
                    AND e.id IS NULL
                """,
                (stage_exit, stage_join, session_id),
            )
            row = cursor.fetchone()
            longest_wait = 0
            if row and row["earliest"]:
                earliest_dt = datetime.fromisoformat(row["earliest"])
                longest_wait = int(
                    (now - earliest_dt).total_seconds() / 60
                )

            return {
                "current_queue": current_queue,
                "completed_this_shift": completed_shift,
                "avg_wait_minutes_shift": avg_wait_shift,
                "busiest_hour": busiest_hour,
                "busiest_hour_count": busiest_count,
                "service_hours_today": service_hours,
                "longest_current_wait_minutes": longest_wait,
                "timestamp": now.isoformat(),
                "session_id": session_id,
            }


extension = ShiftSummaryExtension()
