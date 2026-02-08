"""Export extension - CSV data export."""

import csv
import logging
from io import StringIO

from flask import jsonify, make_response, request

from tap_station.extension import Extension

logger = logging.getLogger(__name__)


class ExportExtension(Extension):
    """CSV data export for events."""

    name = "export"
    order = 50

    def on_api_routes(self, app, db, config):
        @app.route("/api/export")
        def api_export():
            """Export data as CSV."""
            try:
                filter_type = request.args.get("filter", "all")
                session_id = config.session_id

                if filter_type == "hour":
                    where = "WHERE session_id = ? AND timestamp > datetime('now', '-1 hour')"
                elif filter_type == "today":
                    where = "WHERE session_id = ? AND date(timestamp) = date('now')"
                else:
                    where = "WHERE session_id = ?"

                cursor = db.conn.execute(
                    f"""
                    SELECT id, token_id, uid, stage, timestamp,
                           device_id, session_id
                    FROM events
                    {where}
                    ORDER BY timestamp DESC
                    """,
                    (session_id,),
                )

                output = StringIO()
                writer = csv.writer(output)
                writer.writerow(
                    ["ID", "Token ID", "UID", "Stage", "Timestamp",
                     "Device ID", "Session ID"]
                )

                for row in cursor.fetchall():
                    writer.writerow(
                        [row["id"], row["token_id"], row["uid"],
                         row["stage"], row["timestamp"],
                         row["device_id"], row["session_id"]]
                    )

                csv_data = output.getvalue()
                response = make_response(csv_data)
                response.headers["Content-Disposition"] = (
                    f"attachment; filename=nfc_data_{filter_type}_{session_id}.csv"
                )
                response.headers["Content-Type"] = "text/csv"
                return response

            except Exception as e:
                logger.error("Export failed: %s", e)
                return jsonify({"error": str(e)}), 500


extension = ExportExtension()
