"""Notes extension - operational notes for the session."""

import logging
from datetime import datetime, timezone

from flask import jsonify, request

from tap_station.extension import Extension

logger = logging.getLogger(__name__)


class NotesExtension(Extension):
    """Allows staff to add and retrieve operational notes."""

    name = "notes"
    order = 50

    def on_startup(self, ctx):
        self.db = ctx["db"]
        self.config = ctx["config"]

    def on_api_routes(self, app, db, config):
        @app.route("/api/notes", methods=["GET", "POST"])
        def api_notes():
            """Add or retrieve event notes."""
            if request.method == "POST":
                try:
                    data = request.get_json()
                    note_text = data.get("note", "").strip()

                    if not note_text:
                        return (
                            jsonify({"error": "Note text required"}),
                            400,
                        )

                    now = datetime.now(timezone.utc)

                    db.log_event(
                        token_id="NOTE",
                        uid=note_text[:100],
                        stage="NOTE",
                        device_id=data.get("author", "staff"),
                        session_id=config.session_id,
                        timestamp=now,
                    )

                    return (
                        jsonify(
                            {
                                "success": True,
                                "message": "Note added",
                                "timestamp": now.isoformat(),
                            }
                        ),
                        201,
                    )

                except Exception as e:
                    logger.error("Add note failed: %s", e)
                    return jsonify({"error": str(e)}), 500

            else:
                # GET - retrieve notes
                try:
                    session_id = config.session_id
                    cursor = db.conn.execute(
                        """
                        SELECT timestamp,
                               device_id as author,
                               uid as note_text
                        FROM events
                        WHERE session_id = ?
                          AND stage = 'NOTE'
                        ORDER BY timestamp DESC
                        LIMIT 50
                        """,
                        (session_id,),
                    )

                    notes = []
                    for row in cursor.fetchall():
                        notes.append(
                            {
                                "timestamp": row["timestamp"],
                                "author": row["author"],
                                "note": row["note_text"],
                            }
                        )

                    return jsonify({"notes": notes}), 200

                except Exception as e:
                    logger.error("Get notes failed: %s", e)
                    return jsonify({"error": str(e)}), 500


extension = NotesExtension()
