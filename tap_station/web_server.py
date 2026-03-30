"""Minimal v1 web server for FlowState consolidation."""

import csv
import logging
import secrets
from collections import defaultdict
from datetime import datetime, timezone
from functools import wraps
from io import StringIO

from flask import Flask, jsonify, render_template, request, session

from .constants import WorkflowStages
from .datetime_utils import parse_timestamp

logger = logging.getLogger(__name__)


class StatusWebServer:
    """Minimal Flask server for checkpoint ingest, dashboard data, export, and correction."""

    def __init__(self, config, database, registry=None):
        self.config = config
        self.db = database
        self.app = Flask(__name__)
        self.app.config["SECRET_KEY"] = secrets.token_hex(32)
        self.app.config["ADMIN_PASSWORD"] = config.admin_password
        self._setup_routes()

    def _require_admin_auth(self, f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("admin_authenticated"):
                return jsonify({"error": "admin authentication required"}), 401
            return f(*args, **kwargs)

        return decorated

    def _setup_routes(self):
        @self.app.route("/health")
        def health_check():
            return (
                jsonify(
                    {
                        "status": "ok",
                        "device_id": self.config.device_id,
                        "session_id": self.config.session_id,
                        "events": self.db.get_event_count(self.config.session_id),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                200,
            )

        @self.app.route("/healthz")
        def healthz():
            return jsonify({"status": "ok"}), 200

        @self.app.route("/readyz")
        def readyz():
            try:
                self.db.get_event_count(self.config.session_id)
                return jsonify({"status": "ready"}), 200
            except Exception as exc:
                return jsonify({"status": "not_ready", "error": str(exc)}), 503

        @self.app.route("/api/stages")
        def stages():
            return jsonify({"stages": WorkflowStages.ALL_STAGES}), 200

        @self.app.route("/api/service-config")
        def service_config():
            return (
                jsonify(
                    {
                        "service_name": "FlowState v1",
                        "workflow_stages": [
                            {"id": stage, "label": stage, "order": idx + 1}
                            for idx, stage in enumerate(WorkflowStages.ALL_STAGES)
                        ],
                    }
                ),
                200,
            )

        @self.app.route("/api/ingest", methods=["POST"])
        def ingest_events():
            payload = request.get_json(silent=True)
            events = payload if isinstance(payload, list) else [payload]
            if not events or events == [None]:
                return jsonify({"error": "Expected event object or list"}), 400

            inserted = 0
            duplicates = 0
            errors = 0

            for event in events:
                if not isinstance(event, dict):
                    errors += 1
                    continue

                token_id = str(event.get("token_id") or event.get("tokenId") or "").strip()
                uid = str(event.get("uid") or event.get("serial") or token_id or "UNKNOWN")
                stage = str(event.get("stage") or "").strip()
                session_id = str(event.get("session_id") or event.get("sessionId") or self.config.session_id)
                device_id = str(event.get("device_id") or event.get("deviceId") or "checkpoint-client")

                if not token_id or not stage:
                    errors += 1
                    continue

                ts_val = event.get("timestamp_ms") or event.get("timestampMs")
                timestamp = parse_timestamp(ts_val, default_to_now=True)

                result = self.db.log_event(
                    token_id=token_id,
                    uid=uid,
                    stage=stage,
                    device_id=device_id,
                    session_id=session_id,
                    timestamp=timestamp,
                )
                if result.get("success"):
                    inserted += 1
                elif result.get("duplicate"):
                    duplicates += 1
                else:
                    errors += 1

            return (
                jsonify(
                    {
                        "status": "ok",
                        "summary": {
                            "received": len(events),
                            "inserted": inserted,
                            "duplicates": duplicates,
                            "errors": errors,
                        },
                    }
                ),
                200,
            )

        @self.app.route("/api/episodes/active")
        def active_episodes():
            rows = self.db.conn.execute(
                """
                WITH latest AS (
                    SELECT token_id, MAX(id) AS max_id
                    FROM events
                    WHERE session_id = ?
                    GROUP BY token_id
                )
                SELECT e.token_id, e.stage AS current_stage, e.timestamp AS last_seen,
                       (SELECT MIN(timestamp) FROM events se WHERE se.token_id = e.token_id AND se.session_id = e.session_id) AS entered_at
                FROM events e
                INNER JOIN latest l ON l.max_id = e.id
                WHERE e.stage != ?
                ORDER BY datetime(e.timestamp) DESC
                """,
                (self.config.session_id, WorkflowStages.COMPLETED),
            ).fetchall()
            return jsonify({"episodes": [dict(r) for r in rows]}), 200

        @self.app.route("/api/dashboard")
        def dashboard_data():
            events = self.db.conn.execute(
                """
                WITH latest AS (
                    SELECT token_id, MAX(id) AS max_id
                    FROM events
                    WHERE session_id = ?
                    GROUP BY token_id
                )
                SELECT e.token_id, e.stage
                FROM events e
                INNER JOIN latest l ON l.max_id = e.id
                """,
                (self.config.session_id,),
            ).fetchall()

            stage_counts = defaultdict(int)
            active = 0
            for row in events:
                stage = row["stage"]
                stage_counts[stage] += 1
                if stage != WorkflowStages.COMPLETED:
                    active += 1

            return (
                jsonify(
                    {
                        "active_count": active,
                        "counts_per_stage": {s: stage_counts.get(s, 0) for s in WorkflowStages.ALL_STAGES},
                        "recent_events": self.db.get_recent_events(20),
                    }
                ),
                200,
            )

        @self.app.route("/api/stats")
        def stats():
            payload, _ = dashboard_data()
            return payload

        @self.app.route("/api/export.csv")
        def export_csv():
            rows = self.db.conn.execute(
                """
                SELECT token_id, stage, timestamp, device_id, session_id
                FROM events
                WHERE session_id = ?
                ORDER BY datetime(timestamp) ASC, id ASC
                """,
                (self.config.session_id,),
            ).fetchall()

            buf = StringIO()
            writer = csv.writer(buf)
            writer.writerow(["token_id", "stage", "timestamp", "device_id", "session_id"])
            for r in rows:
                writer.writerow([r["token_id"], r["stage"], r["timestamp"], r["device_id"], r["session_id"]])

            return (
                buf.getvalue(),
                200,
                {
                    "Content-Type": "text/csv",
                    "Content-Disposition": f"attachment; filename=flowstate-{self.config.session_id}.csv",
                },
            )

        @self.app.route("/api/export")
        def export_csv_compat():
            return export_csv()

        @self.app.route("/api/admin/login", methods=["POST"])
        def admin_login():
            payload = request.get_json(silent=True) or {}
            password = payload.get("password", "")
            if password != self.app.config["ADMIN_PASSWORD"]:
                return jsonify({"success": False, "error": "Invalid password"}), 401
            session["admin_authenticated"] = True
            return jsonify({"success": True}), 200

        @self.app.route("/api/admin/correct-stage", methods=["POST"])
        @self._require_admin_auth
        def correct_stage():
            payload = request.get_json(silent=True) or {}
            token_id = str(payload.get("token_id", "")).strip()
            target_stage = str(payload.get("target_stage", "")).strip()
            corrected_by = str(payload.get("corrected_by") or "admin")

            if not token_id or not target_stage:
                return jsonify({"success": False, "error": "token_id and target_stage are required"}), 400

            result = self.db.set_episode_stage(
                token_id=token_id,
                target_stage=target_stage,
                session_id=self.config.session_id,
                corrected_by=corrected_by,
            )
            status = 200 if result.get("success") else 400
            return jsonify(result), status

        @self.app.route("/")
        @self.app.route("/dashboard")
        def dashboard():
            return render_template(
                "dashboard_v1.html",
                device_id=self.config.device_id,
                stage=self.config.stage,
                session=self.config.session_id,
            )

    def run(self, host: str = "0.0.0.0", port: int = 8080):
        logger.info("Starting minimal web server on %s:%s", host, port)
        self.app.run(host=host, port=port, debug=False, use_reloader=False)
