"""
Simple web server for health checks and participant status checking

Provides:
- /health endpoint for monitoring
- /check?token=XXX endpoint for participant status
- /api/status/<token> API endpoint
"""

import sys
import logging
from flask import Flask, render_template, jsonify, request
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class StatusWebServer:
    """Web server for health checks and status"""

    def __init__(self, config, database):
        """
        Initialize web server

        Args:
            config: Config instance
            database: Database instance
        """
        self.config = config
        self.db = database
        self.app = Flask(__name__)

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup Flask routes"""

        @self.app.route("/health")
        def health_check():
            """
            Health check endpoint

            Returns:
                200 OK if service is running
            """
            try:
                # Check database is accessible
                count = self.db.get_event_count()

                return (
                    jsonify(
                        {
                            "status": "ok",
                            "device_id": self.config.device_id,
                            "stage": self.config.stage,
                            "session": self.config.session_id,
                            "total_events": count,
                            "timestamp": datetime.now().isoformat(),
                        }
                    ),
                    200,
                )

            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return (
                    jsonify(
                        {
                            "status": "error",
                            "error": str(e),
                            "timestamp": datetime.now().isoformat(),
                        }
                    ),
                    500,
                )

        @self.app.route("/api/ingest", methods=["POST"])
        def ingest_events():
            """
            Ingest events from mobile devices

            Expected JSON body:
            [
                {
                    "token_id": "001",
                    "uid": "...",
                    "stage": "...",
                    "session_id": "...",
                    "device_id": "...",
                    "timestamp_ms": 1712...
                },
                ...
            ]
            """
            try:
                events = request.get_json()
                if not isinstance(events, list):
                    return jsonify({"error": "Expected list of events"}), 400

                # Payload size limit (max 1000 events per request)
                if len(events) > 1000:
                    logger.warning(f"Payload too large: {len(events)} events")
                    return (
                        jsonify({"error": "Too many events (max 1000 per request)"}),
                        413,
                    )

                # Reject empty payloads
                if len(events) == 0:
                    return jsonify({"error": "Empty event list"}), 400

                inserted = 0
                duplicates = 0
                errors = 0

                for event in events:
                    try:
                        # Basic type validation
                        if not isinstance(event, dict):
                            logger.warning(f"Invalid event type: {type(event)}")
                            errors += 1
                            continue

                        # Normalize fields
                        token_id = str(
                            event.get("token_id") or event.get("tokenId") or "UNKNOWN"
                        )
                        uid = str(
                            event.get("uid")
                            or event.get("serial")
                            or token_id
                            or "UNKNOWN"
                        )
                        stage = (
                            str(event.get("stage") or "").strip().upper() or "UNKNOWN"
                        )
                        session_id = str(
                            event.get("session_id")
                            or event.get("sessionId")
                            or "UNKNOWN"
                        )
                        device_id = str(
                            event.get("device_id") or event.get("deviceId") or "mobile"
                        )

                        # Validate field lengths (prevent database bloat)
                        if len(token_id) > 100 or len(uid) > 100 or len(stage) > 50:
                            logger.warning(f"Field too long in event: {event}")
                            errors += 1
                            continue

                        # Handle timestamp
                        ts_val = event.get("timestamp_ms") or event.get("timestampMs")
                        timestamp = None
                        if ts_val:
                            try:
                                timestamp = datetime.fromtimestamp(
                                    int(ts_val) / 1000, tz=timezone.utc
                                )
                            except (ValueError, TypeError, OSError):
                                pass

                        # Log event
                        success = self.db.log_event(
                            token_id=token_id,
                            uid=uid,
                            stage=stage,
                            device_id=device_id,
                            session_id=session_id,
                            timestamp=timestamp,
                        )

                        if success:
                            inserted += 1
                        else:
                            duplicates += 1

                    except Exception as e:
                        logger.warning(f"Failed to ingest event: {e}")
                        errors += 1

                logger.info(
                    f"Ingested {len(events)} events from mobile: "
                    f"+{inserted}, ={duplicates}, !{errors}"
                )
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

            except Exception as e:
                logger.error(f"Ingest failed: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/")
        def index():
            """Index page showing station info"""
            return render_template(
                "index.html",
                device_id=self.config.device_id,
                stage=self.config.stage,
                session=self.config.session_id,
            )

        @self.app.route("/check")
        def check_status():
            """
            Status check page for participants

            Query params:
                token: Token ID to check (e.g., "001")

            Returns:
                HTML page showing participant status
            """
            token_id = request.args.get("token")

            if not token_id:
                return render_template("error.html", error="No token ID provided"), 400

            # Get status from API
            try:
                status = self._get_token_status(token_id)
                return render_template(
                    "status.html",
                    token_id=token_id,
                    status=status,
                    session=self.config.session_id,
                )

            except Exception as e:
                logger.error(f"Status check failed for token {token_id}: {e}")
                return (
                    render_template("error.html", error=f"Error checking status: {e}"),
                    500,
                )

        @self.app.route("/api/status/<token_id>")
        def api_status(token_id):
            """
            API endpoint for token status

            Args:
                token_id: Token ID to check

            Returns:
                JSON with token status
            """
            try:
                status = self._get_token_status(token_id)
                return jsonify(status), 200

            except Exception as e:
                logger.error(f"API status check failed for token {token_id}: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/stats")
        def api_stats():
            """
            API endpoint for general statistics

            Returns:
                JSON with session statistics
            """
            try:
                stats = {
                    "device_id": self.config.device_id,
                    "stage": self.config.stage,
                    "session_id": self.config.session_id,
                    "total_events": self.db.get_event_count(self.config.session_id),
                    "recent_events": self.db.get_recent_events(10),
                    "timestamp": datetime.now().isoformat(),
                }
                return jsonify(stats), 200

            except Exception as e:
                logger.error(f"API stats failed: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/dashboard")
        def dashboard():
            """Live monitoring dashboard for events"""
            return render_template(
                "dashboard.html",
                device_id=self.config.device_id,
                stage=self.config.stage,
                session=self.config.session_id,
            )

        @self.app.route("/api/dashboard")
        def api_dashboard():
            """
            API endpoint for dashboard data

            Returns:
                JSON with comprehensive dashboard statistics
            """
            try:
                stats = self._get_dashboard_stats()
                return jsonify(stats), 200

            except Exception as e:
                logger.error(f"API dashboard failed: {e}")
                return jsonify({"error": str(e)}), 500

    def _get_dashboard_stats(self) -> dict:
        """
        Get comprehensive dashboard statistics

        Returns:
            Dictionary with all dashboard data
        """
        session_id = self.config.session_id

        # Today's events
        cursor = self.db.conn.execute(
            """
            SELECT COUNT(*) as count
            FROM events
            WHERE session_id = ? AND date(timestamp) = date('now')
        """,
            (session_id,),
        )
        today_events = cursor.fetchone()["count"]

        # Last hour events
        cursor = self.db.conn.execute(
            """
            SELECT COUNT(*) as count
            FROM events
            WHERE session_id = ? AND timestamp > datetime('now', '-1 hour')
        """,
            (session_id,),
        )
        last_hour_events = cursor.fetchone()["count"]

        # People currently in queue (joined but not exited)
        cursor = self.db.conn.execute(
            """
            SELECT COUNT(DISTINCT q.token_id) as count
            FROM events q
            LEFT JOIN events e
                ON q.token_id = e.token_id
                AND q.session_id = e.session_id
                AND e.stage = 'EXIT'
            WHERE q.stage = 'QUEUE_JOIN'
                AND q.session_id = ?
                AND e.id IS NULL
        """,
            (session_id,),
        )
        in_queue = cursor.fetchone()["count"]

        # Completed journeys today
        cursor = self.db.conn.execute(
            """
            SELECT COUNT(*) as count
            FROM events q
            JOIN events e
                ON q.token_id = e.token_id
                AND q.session_id = e.session_id
            WHERE q.stage = 'QUEUE_JOIN'
                AND e.stage = 'EXIT'
                AND q.session_id = ?
                AND date(e.timestamp) = date('now')
        """,
            (session_id,),
        )
        completed_today = cursor.fetchone()["count"]

        # Average wait time (last 20 completed)
        avg_wait = self._calculate_avg_wait_time(limit=20)

        # Recent completions with wait times
        recent_completions = self._get_recent_completions(limit=10)

        # Activity by hour (last 12 hours)
        hourly_activity = self._get_hourly_activity(hours=12)

        # Recent events feed
        recent_events = self._get_recent_events_feed(limit=15)

        return {
            "device_id": self.config.device_id,
            "stage": self.config.stage,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "stats": {
                "today_events": today_events,
                "last_hour_events": last_hour_events,
                "in_queue": in_queue,
                "completed_today": completed_today,
                "avg_wait_minutes": avg_wait,
                "throughput_per_hour": (
                    last_hour_events / 2 if last_hour_events > 0 else 0
                ),  # Rough estimate
            },
            "recent_completions": recent_completions,
            "hourly_activity": hourly_activity,
            "recent_events": recent_events,
        }

    def _calculate_avg_wait_time(self, limit=20) -> int:
        """Calculate average wait time from recent completions"""

        try:
            cursor = self.db.conn.execute(
                """
                SELECT
                    q.timestamp as queue_time,
                    e.timestamp as exit_time
                FROM events q
                JOIN events e
                    ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                WHERE q.stage = 'QUEUE_JOIN'
                    AND e.stage = 'EXIT'
                    AND q.session_id = ?
                ORDER BY e.timestamp DESC
                LIMIT ?
            """,
                (self.config.session_id, limit),
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
            logger.warning(f"Failed to calculate avg wait time: {e}")
            return 0

    def _get_recent_completions(self, limit=10) -> list:
        """Get recent completed journeys with wait times"""
        try:
            cursor = self.db.conn.execute(
                """
                SELECT
                    q.token_id,
                    q.timestamp as queue_time,
                    e.timestamp as exit_time
                FROM events q
                JOIN events e
                    ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                WHERE q.stage = 'QUEUE_JOIN'
                    AND e.stage = 'EXIT'
                    AND q.session_id = ?
                ORDER BY e.timestamp DESC
                LIMIT ?
            """,
                (self.config.session_id, limit),
            )

            completions = []
            for row in cursor.fetchall():
                queue_dt = datetime.fromisoformat(row["queue_time"])
                exit_dt = datetime.fromisoformat(row["exit_time"])
                wait_minutes = int((exit_dt - queue_dt).total_seconds() / 60)

                completions.append(
                    {
                        "token_id": row["token_id"],
                        "exit_time": exit_dt.strftime("%H:%M"),
                        "wait_minutes": wait_minutes,
                    }
                )

            return completions

        except Exception as e:
            logger.warning(f"Failed to get recent completions: {e}")
            return []

    def _get_hourly_activity(self, hours=12) -> list:
        """Get activity counts by hour"""
        try:
            cursor = self.db.conn.execute(
                """
                SELECT
                    strftime('%H:00', timestamp) as hour,
                    COUNT(*) as count
                FROM events
                WHERE session_id = ?
                    AND timestamp > datetime('now', ? || ' hours')
                GROUP BY hour
                ORDER BY hour
            """,
                (self.config.session_id, -hours),
            )

            return [
                {"hour": row["hour"], "count": row["count"]}
                for row in cursor.fetchall()
            ]

        except Exception as e:
            logger.warning(f"Failed to get hourly activity: {e}")
            return []

    def _get_recent_events_feed(self, limit=15) -> list:
        """Get recent events for activity feed"""
        try:
            cursor = self.db.conn.execute(
                """
                SELECT
                    token_id,
                    stage,
                    timestamp,
                    device_id
                FROM events
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (self.config.session_id, limit),
            )

            events = []
            for row in cursor.fetchall():
                dt = datetime.fromisoformat(row["timestamp"])
                events.append(
                    {
                        "token_id": row["token_id"],
                        "stage": row["stage"],
                        "time": dt.strftime("%H:%M:%S"),
                        "device_id": row["device_id"],
                    }
                )

            return events

        except Exception as e:
            logger.warning(f"Failed to get recent events: {e}")
            return []

    def _get_token_status(self, token_id: str) -> dict:
        """
        Get status for a token from database

        Args:
            token_id: Token ID

        Returns:
            Dictionary with token status
        """
        # Query database for all events for this token in this session
        cursor = self.db.conn.execute(
            """
            SELECT stage, timestamp, device_id
            FROM events
            WHERE token_id = ? AND session_id = ?
            ORDER BY timestamp
        """,
            (token_id, self.config.session_id),
        )

        events = cursor.fetchall()

        # Parse events
        result = {
            "token_id": token_id,
            "session_id": self.config.session_id,
            "queue_join": None,
            "queue_join_time": None,
            "exit": None,
            "exit_time": None,
            "wait_time_minutes": None,
            "status": "not_checked_in",
            "estimated_wait": self._estimate_wait_time(),
        }

        for event in events:
            stage = event["stage"]
            timestamp = event["timestamp"]

            if stage == "QUEUE_JOIN":
                result["queue_join"] = timestamp
                result["queue_join_time"] = self._format_time(timestamp)
                result["status"] = "in_queue"

            elif stage == "EXIT":
                result["exit"] = timestamp
                result["exit_time"] = self._format_time(timestamp)
                result["status"] = "complete"

        # Calculate wait time if complete
        if result["queue_join"] and result["exit"]:
            try:
                queue_time = datetime.fromisoformat(result["queue_join"])
                exit_time = datetime.fromisoformat(result["exit"])
                result["wait_time_minutes"] = int(
                    (exit_time - queue_time).total_seconds() / 60
                )
            except Exception as e:
                logger.warning(f"Failed to calculate wait time: {e}")

        return result

    def _format_time(self, timestamp: str) -> str:
        """Format timestamp for display"""
        try:
            dt = datetime.fromisoformat(timestamp)
            return dt.strftime("%I:%M %p")  # e.g., "02:15 PM"
        except (ValueError, TypeError):
            return timestamp

    def _estimate_wait_time(self) -> int:
        """
        Estimate current wait time based on recent completions

        Returns:
            Estimated wait time in minutes
        """
        try:
            # Get recent complete journeys (last 10)
            cursor = self.db.conn.execute(
                """
                SELECT
                    q.timestamp as queue_time,
                    e.timestamp as exit_time
                FROM events q
                JOIN events e
                    ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                WHERE q.stage = 'QUEUE_JOIN'
                    AND e.stage = 'EXIT'
                    AND q.session_id = ?
                ORDER BY e.timestamp DESC
                LIMIT 10
            """,
                (self.config.session_id,),
            )

            journeys = cursor.fetchall()

            if not journeys:
                return 20  # Default estimate

            # Calculate average wait time
            total_wait = 0
            for journey in journeys:
                queue_dt = datetime.fromisoformat(journey["queue_time"])
                exit_dt = datetime.fromisoformat(journey["exit_time"])
                wait_minutes = (exit_dt - queue_dt).total_seconds() / 60
                total_wait += wait_minutes

            avg_wait = total_wait / len(journeys)
            return int(avg_wait)

        except Exception as e:
            logger.warning(f"Failed to estimate wait time: {e}")
            return 20  # Default fallback

    def run(self, host="0.0.0.0", port=8080):
        """
        Run the web server

        Args:
            host: Host to bind to
            port: Port to listen on
        """
        logger.info(f"Starting web server on {host}:{port}")
        self.app.run(host=host, port=port, debug=False)


def create_app(config_path="config.yaml"):
    """
    Factory function to create Flask app

    Args:
        config_path: Path to config file

    Returns:
        Flask app instance
    """
    from tap_station.config import Config
    from tap_station.database import Database

    config = Config(config_path)
    db = Database(config.database_path, wal_mode=config.wal_mode)

    server = StatusWebServer(config, db)
    return server.app


# For running standalone
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Status Web Server")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        from tap_station.config import Config
        from tap_station.database import Database

        config = Config(args.config)
        db = Database(config.database_path, wal_mode=config.wal_mode)

        server = StatusWebServer(config, db)
        server.run(host=args.host, port=args.port)

    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)
