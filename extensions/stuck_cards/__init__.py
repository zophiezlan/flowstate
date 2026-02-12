"""Stuck cards extension - detect and force-exit stuck cards."""

import logging
from datetime import datetime, timezone

from flask import jsonify, request

from tap_station.extension import Extension, resolve_stage

logger = logging.getLogger(__name__)


class StuckCardsExtension(Extension):
    """Detect cards stuck in queue >2 hours and allow force-exit."""

    name = "stuck_cards"
    order = 50

    def on_startup(self, ctx):
        self._config = ctx["config"]

    def on_api_routes(self, app, db, config):
        from tap_station.web_server import require_admin_auth

        stage_exit = resolve_stage("EXIT")
        stage_join = resolve_stage("QUEUE_JOIN")

        @app.route("/api/control/stuck-cards")
        @require_admin_auth
        def api_stuck_cards():
            """Get list of stuck cards (in queue >2 hours)."""
            try:
                result = _get_stuck_cards(db, config, stage_exit, stage_join)
                return jsonify(result), 200
            except Exception as e:
                logger.error("Get stuck cards failed: %s", e)
                return jsonify({"error": str(e)}), 500

        @app.route("/api/control/force-exit", methods=["POST"])
        @require_admin_auth
        def api_force_exit():
            """Force exit for stuck cards."""
            try:
                data = request.get_json()
                if not data or "token_ids" not in data:
                    return jsonify({
                        "success": False,
                        "error": "token_ids list required",
                    }), 400

                result = _force_exit_cards(
                    db, config, data["token_ids"], stage_exit,
                )
                return jsonify(result), 200
            except Exception as e:
                logger.error("Force exit failed: %s", e)
                return jsonify({"success": False, "error": str(e)}), 500

        def _get_stuck_cards(db, config, stage_exit, stage_join):
            session_id = config.session_id
            now = datetime.now(timezone.utc)

            try:
                cursor = db.conn.execute(
                    """
                    SELECT
                        q.token_id,
                        q.timestamp as queue_time,
                        q.device_id
                    FROM events q
                    LEFT JOIN events e
                        ON q.token_id = e.token_id
                        AND q.session_id = e.session_id
                        AND e.stage = ?
                    WHERE q.stage = ?
                        AND q.session_id = ?
                        AND e.id IS NULL
                        AND q.timestamp < datetime('now', '-2 hours')
                    ORDER BY q.timestamp ASC
                    """,
                    (stage_exit, stage_join, session_id),
                )

                stuck_cards = []
                for row in cursor.fetchall():
                    queue_dt = datetime.fromisoformat(row["queue_time"])
                    hours_stuck = (now - queue_dt).total_seconds() / 3600
                    stuck_cards.append({
                        "token_id": row["token_id"],
                        "queue_time": queue_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "hours_stuck": round(hours_stuck, 1),
                        "device_id": row["device_id"],
                    })

                return {
                    "stuck_cards": stuck_cards,
                    "count": len(stuck_cards),
                    "session_id": session_id,
                    "timestamp": now.isoformat(),
                }

            except Exception as e:
                logger.error("Failed to get stuck cards: %s", e)
                return {"stuck_cards": [], "count": 0, "error": str(e)}

        def _force_exit_cards(db, config, token_ids, stage_exit):
            session_id = config.session_id
            now = datetime.now(timezone.utc)

            try:
                success_count = 0
                failed = []

                for token_id in token_ids:
                    try:
                        db.log_event(
                            token_id=token_id,
                            uid=f"FORCED_{token_id}",
                            stage=stage_exit,
                            device_id="manual_force_exit",
                            session_id=session_id,
                            timestamp=now,
                        )
                        success_count += 1
                        logger.info("Force exited card: %s", token_id)
                    except Exception as e:
                        logger.error(
                            "Failed to force exit %s: %s", token_id, e,
                        )
                        failed.append({
                            "token_id": token_id, "error": str(e),
                        })

                return {
                    "success": True,
                    "processed": len(token_ids),
                    "success_count": success_count,
                    "failed_count": len(failed),
                    "failed": failed,
                    "message": (
                        f"Successfully force-exited {success_count}"
                        f" of {len(token_ids)} cards"
                    ),
                }

            except Exception as e:
                logger.error("Force exit operation failed: %s", e)
                return {
                    "success": False,
                    "error": str(e),
                    "processed": 0,
                    "success_count": 0,
                }


extension = StuckCardsExtension()
