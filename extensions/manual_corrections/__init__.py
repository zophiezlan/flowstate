"""Manual corrections extension - add/remove events manually."""

import logging
from datetime import datetime, timedelta, timezone

from flask import jsonify, request

from tap_station.extension import Extension

logger = logging.getLogger(__name__)


class ManualCorrectionsExtension(Extension):
    """Manual event addition and removal for staff corrections."""

    name = "manual_corrections"
    order = 50

    def on_api_routes(self, app, db, config):
        from tap_station.web_server import RateLimiter, rate_limit, require_admin_auth

        control_limiter = RateLimiter(max_requests=10, window_seconds=60)

        @app.route("/api/control/manual-event", methods=["POST"])
        @require_admin_auth
        @rate_limit(control_limiter)
        def api_manual_event():
            """Add a manual event for missed taps."""
            try:
                data = request.get_json()

                required = [
                    "token_id", "stage", "timestamp",
                    "operator_id", "reason",
                ]
                missing = [f for f in required if f not in data]
                if missing:
                    return jsonify({
                        "success": False,
                        "error": f"Missing required fields: {', '.join(missing)}",
                    }), 400

                # Parse timestamp
                try:
                    timestamp_str = data["timestamp"]
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=timezone.utc)
                    except (ValueError, AttributeError):
                        try:
                            ts_value = float(timestamp_str)
                            if ts_value > 1e10:
                                ts_value = ts_value / 1000
                            timestamp = datetime.fromtimestamp(
                                ts_value, tz=timezone.utc,
                            )
                        except (ValueError, OSError):
                            return jsonify({
                                "success": False,
                                "error": (
                                    "Invalid timestamp format. Expected ISO 8601"
                                    " or Unix timestamp."
                                    f" Got: {timestamp_str}"
                                ),
                            }), 400

                    # Validate timestamp range
                    now = datetime.now(timezone.utc)
                    max_age_days = 30
                    max_future_hours = 1

                    if timestamp < now.replace(
                        hour=0, minute=0, second=0, microsecond=0,
                    ) - timedelta(days=max_age_days):
                        return jsonify({
                            "success": False,
                            "error": f"Timestamp is more than {max_age_days} days in the past",
                        }), 400

                    if timestamp > now + timedelta(hours=max_future_hours):
                        return jsonify({
                            "success": False,
                            "error": f"Timestamp is more than {max_future_hours} hours in the future",
                        }), 400

                except KeyError:
                    return jsonify({
                        "success": False,
                        "error": "Missing required field: timestamp",
                    }), 400

                result = db.add_manual_event(
                    token_id=data["token_id"],
                    stage=data["stage"],
                    timestamp=timestamp,
                    session_id=config.session_id,
                    operator_id=data["operator_id"],
                    reason=data["reason"],
                )

                if result["success"]:
                    return jsonify({
                        "success": True,
                        "message": "Manual event added successfully",
                        "warnings": result.get("warning"),
                    }), 200
                else:
                    return jsonify({
                        "success": False,
                        "error": result.get("warning", "Failed to add event"),
                    }), 400

            except Exception as e:
                logger.error("Manual event addition failed: %s", e)
                return jsonify({"success": False, "error": str(e)}), 500

        @app.route("/api/control/remove-event", methods=["POST"])
        @require_admin_auth
        @rate_limit(control_limiter)
        def api_remove_event():
            """Remove an incorrect event."""
            try:
                data = request.get_json()

                if not data:
                    return jsonify({
                        "success": False,
                        "error": "Request body must be JSON",
                    }), 400

                required = ["event_id", "operator_id", "reason"]
                missing = [f for f in required if f not in data]
                if missing:
                    return jsonify({
                        "success": False,
                        "error": f"Missing required fields: {', '.join(missing)}",
                    }), 400

                # Validate event_id
                try:
                    event_id = int(data["event_id"])
                    if event_id <= 0:
                        raise ValueError("event_id must be positive")
                except (ValueError, TypeError):
                    return jsonify({
                        "success": False,
                        "error": "Invalid event_id: must be a positive integer",
                    }), 400

                operator_id = str(data["operator_id"]).strip()
                if not operator_id:
                    return jsonify({
                        "success": False,
                        "error": "operator_id cannot be empty",
                    }), 400

                reason = str(data["reason"]).strip()
                if not reason:
                    return jsonify({
                        "success": False,
                        "error": "reason cannot be empty",
                    }), 400

                result = db.remove_event(
                    event_id=event_id,
                    operator_id=operator_id,
                    reason=reason,
                )

                if result["success"]:
                    return jsonify({
                        "success": True,
                        "message": "Event removed successfully",
                        "removed_event": result["removed_event"],
                    }), 200
                else:
                    return jsonify(result), 400

            except Exception as e:
                logger.error("Event removal failed: %s", e)
                return jsonify({"success": False, "error": str(e)}), 500


extension = ManualCorrectionsExtension()
