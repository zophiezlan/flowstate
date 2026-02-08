"""Anomalies extension - real-time anomaly detection."""

import logging
from datetime import datetime, timezone

from flask import jsonify

from tap_station.extension import Extension

logger = logging.getLogger(__name__)


class AnomaliesExtension(Extension):
    """Real-time anomaly detection for human errors."""

    name = "anomalies"
    order = 50

    def on_api_routes(self, app, db, config):
        from tap_station.web_server import RateLimiter, rate_limit, require_admin_auth

        anomaly_limiter = RateLimiter(max_requests=30, window_seconds=60)

        @app.route("/api/control/anomalies")
        @require_admin_auth
        @rate_limit(anomaly_limiter)
        def api_anomalies():
            """Get real-time anomaly detection for human errors."""
            try:
                anomalies = db.get_anomalies(config.session_id)

                return jsonify({
                    "anomalies": anomalies,
                    "summary": anomalies.get("summary", {}),
                    "session_id": config.session_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }), 200
            except Exception as e:
                logger.error("Get anomalies failed: %s", e)
                return jsonify({"error": str(e)}), 500


extension = AnomaliesExtension()
