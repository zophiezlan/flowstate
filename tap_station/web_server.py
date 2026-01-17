"""
Simple web server for health checks and participant status checking

Provides:
- /health endpoint for monitoring
- /check?token=XXX endpoint for participant status
- /api/status/<token> API endpoint
- /control endpoint for system administration
"""

import sys
import logging
import subprocess
import os
import shutil
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

        @self.app.route("/monitor")
        def monitor():
            """Simplified monitor view for peer workers"""
            return render_template(
                "monitor.html",
                device_id=self.config.device_id,
                stage=self.config.stage,
                session=self.config.session_id,
            )

        @self.app.route("/control")
        def control():
            """Control panel for system administration"""
            return render_template(
                "control.html",
                device_id=self.config.device_id,
                stage=self.config.stage,
                session=self.config.session_id,
            )

        @self.app.route("/api/control/status")
        def api_control_status():
            """Get system status for control panel"""
            try:
                status = self._get_system_status()
                return jsonify(status), 200
            except Exception as e:
                logger.error(f"Control status failed: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/control/execute", methods=["POST"])
        def api_control_execute():
            """Execute a control command"""
            try:
                data = request.get_json()
                command = data.get("command")

                if not command:
                    return (
                        jsonify({"success": False, "error": "No command specified"}),
                        400,
                    )

                result = self._execute_control_command(command)
                return jsonify(result), 200

            except Exception as e:
                logger.error(f"Command execution failed: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

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

        # Get operational metrics
        operational_metrics = self._get_operational_metrics()

        # Recent completions with wait times
        recent_completions = self._get_recent_completions(limit=10)

        # Activity by hour (last 12 hours)
        hourly_activity = self._get_hourly_activity(hours=12)

        # Recent events feed
        recent_events = self._get_recent_events_feed(limit=15)

        # Queue details with time in service
        queue_details = self._get_queue_details()

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
                "longest_wait_current": operational_metrics["longest_wait_current"],
                "estimated_wait_new": operational_metrics["estimated_wait_new"],
                "service_uptime_minutes": operational_metrics["service_uptime_minutes"],
                "capacity_utilization": operational_metrics["capacity_utilization"],
            },
            "operational": {
                "alerts": operational_metrics["alerts"],
                "queue_health": operational_metrics["queue_health"],
            },
            "queue_details": queue_details,
            "recent_completions": recent_completions,
            "hourly_activity": hourly_activity,
            "recent_events": recent_events,
        }

    def _get_operational_metrics(self) -> dict:
        """
        Get operational metrics for live monitoring

        Returns:
            Dictionary with operational metrics and alerts
        """
        session_id = self.config.session_id
        now = datetime.now(timezone.utc)

        # Find longest current wait (person who has been in queue longest)
        cursor = self.db.conn.execute(
            """
            SELECT
                q.token_id,
                q.timestamp as queue_time
            FROM events q
            LEFT JOIN events e
                ON q.token_id = e.token_id
                AND q.session_id = e.session_id
                AND e.stage = 'EXIT'
            WHERE q.stage = 'QUEUE_JOIN'
                AND q.session_id = ?
                AND e.id IS NULL
            ORDER BY datetime(q.timestamp) ASC
            LIMIT 1
        """,
            (session_id,),
        )

        longest_wait = 0
        row = cursor.fetchone()
        if row:
            queue_dt = datetime.fromisoformat(row["queue_time"])
            longest_wait = int((now - queue_dt).total_seconds() / 60)

        # Calculate estimated wait for new arrivals
        avg_wait = self._calculate_avg_wait_time(limit=10)
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
        estimated_wait_new = avg_wait + (in_queue * 2) if avg_wait > 0 else 20

        # Calculate service uptime (time since first event today)
        cursor = self.db.conn.execute(
            """
            SELECT MIN(timestamp) as first_event
            FROM events
            WHERE session_id = ?
                AND date(timestamp) = date('now')
        """,
            (session_id,),
        )
        row = cursor.fetchone()
        service_uptime = 0
        if row and row["first_event"]:
            first_dt = datetime.fromisoformat(row["first_event"])
            service_uptime = int((now - first_dt).total_seconds() / 60)

        # Calculate capacity utilization (completions per hour vs theoretical max)
        cursor = self.db.conn.execute(
            """
            SELECT COUNT(*) as completed
            FROM events q
            JOIN events e
                ON q.token_id = e.token_id
                AND q.session_id = e.session_id
            WHERE q.stage = 'QUEUE_JOIN'
                AND e.stage = 'EXIT'
                AND q.session_id = ?
                AND e.timestamp > datetime('now', '-1 hour')
        """,
            (session_id,),
        )
        completed_last_hour = cursor.fetchone()["completed"]
        # Assume theoretical max of 12 people per hour (5 min per person)
        capacity_utilization = min(100, int((completed_last_hour / 12) * 100))

        # Generate alerts
        alerts = []
        if in_queue > 10:
            alerts.append(
                {"level": "warning", "message": f"Queue is long ({in_queue} people)"}
            )
        if in_queue > 20:
            alerts.append(
                {
                    "level": "critical",
                    "message": f"Queue critical ({in_queue} people) - consider additional resources",
                }
            )
        if longest_wait > 45:
            alerts.append(
                {"level": "warning", "message": f"Longest wait: {longest_wait} min"}
            )
        if longest_wait > 90:
            alerts.append(
                {
                    "level": "critical",
                    "message": f"Critical wait time: {longest_wait} min",
                }
            )
        if capacity_utilization > 90:
            alerts.append({"level": "info", "message": "Operating near capacity"})

        # Queue health assessment
        if in_queue > 20 or longest_wait > 90:
            queue_health = "critical"
        elif in_queue > 10 or longest_wait > 45:
            queue_health = "warning"
        elif in_queue > 5 or longest_wait > 30:
            queue_health = "moderate"
        else:
            queue_health = "good"

        return {
            "longest_wait_current": longest_wait,
            "estimated_wait_new": estimated_wait_new,
            "service_uptime_minutes": service_uptime,
            "capacity_utilization": capacity_utilization,
            "alerts": alerts,
            "queue_health": queue_health,
        }

    def _get_queue_details(self) -> list:
        """
        Get detailed information about people currently in queue

        Returns:
            List of people in queue with time-in-service
        """
        session_id = self.config.session_id
        now = datetime.now(timezone.utc)

        cursor = self.db.conn.execute(
            """
            SELECT
                q.token_id,
                q.timestamp as queue_time
            FROM events q
            LEFT JOIN events e
                ON q.token_id = e.token_id
                AND q.session_id = e.session_id
                AND e.stage = 'EXIT'
            WHERE q.stage = 'QUEUE_JOIN'
                AND q.session_id = ?
                AND e.id IS NULL
            ORDER BY datetime(q.timestamp) ASC
        """,
            (session_id,),
        )

        queue_details = []
        for idx, row in enumerate(cursor.fetchall(), 1):
            queue_dt = datetime.fromisoformat(row["queue_time"])
            time_in_service = int((now - queue_dt).total_seconds() / 60)

            queue_details.append(
                {
                    "position": idx,
                    "token_id": row["token_id"],
                    "queue_time": queue_dt.strftime("%H:%M"),
                    "time_in_service_minutes": time_in_service,
                }
            )

        return queue_details

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

    def _get_system_status(self) -> dict:
        """
        Get system status for control panel

        Returns:
            Dictionary with system status
        """
        try:
            # Check if service is running
            result = subprocess.run(
                ["systemctl", "is-active", "tap-station"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            service_running = result.returncode == 0

            # Get database size
            db_size = "Unknown"
            if os.path.exists(self.config.database_path):
                size_bytes = os.path.getsize(self.config.database_path)
                if size_bytes < 1024:
                    db_size = f"{size_bytes}B"
                elif size_bytes < 1024 * 1024:
                    db_size = f"{size_bytes / 1024:.1f}KB"
                else:
                    db_size = f"{size_bytes / (1024 * 1024):.1f}MB"

            # Get uptime
            uptime = "Unknown"
            try:
                with open("/proc/uptime", "r") as f:
                    uptime_seconds = float(f.read().split()[0])
                    uptime_hours = int(uptime_seconds / 3600)
                    uptime_minutes = int((uptime_seconds % 3600) / 60)
                    uptime = f"{uptime_hours}h {uptime_minutes}m"
            except Exception:
                pass

            return {
                "service_running": service_running,
                "total_events": self.db.get_event_count(self.config.session_id),
                "db_size": db_size,
                "uptime": uptime,
            }

        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return {
                "service_running": False,
                "total_events": 0,
                "db_size": "Unknown",
                "uptime": "Unknown",
            }

    def _execute_control_command(self, command: str) -> dict:
        """
        Execute a control command

        Args:
            command: Command identifier

        Returns:
            Dictionary with success status and output
        """
        logger.info(f"Executing control command: {command}")

        try:
            # Service management commands
            if command == "service-start":
                result = subprocess.run(
                    ["sudo", "systemctl", "start", "tap-station"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout + result.stderr,
                }

            elif command == "service-stop":
                result = subprocess.run(
                    ["sudo", "systemctl", "stop", "tap-station"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout + result.stderr,
                }

            elif command == "service-restart":
                result = subprocess.run(
                    ["sudo", "systemctl", "restart", "tap-station"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout + result.stderr,
                }

            elif command == "service-status":
                result = subprocess.run(
                    ["systemctl", "status", "tap-station"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return {"success": True, "output": result.stdout}

            # Diagnostic commands
            elif command == "verify-hardware":
                script_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "scripts",
                    "verify_hardware.py",
                )
                result = subprocess.run(
                    ["python3", script_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return {"success": True, "output": result.stdout + result.stderr}

            elif command == "verify-deployment":
                script_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "scripts",
                    "verify_deployment.sh",
                )
                result = subprocess.run(
                    ["bash", script_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return {"success": True, "output": result.stdout + result.stderr}

            elif command == "health-check":
                script_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "scripts",
                    "health_check.py",
                )
                result = subprocess.run(
                    ["python3", script_path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return {"success": True, "output": result.stdout + result.stderr}

            elif command == "i2c-detect":
                result = subprocess.run(
                    ["sudo", "i2cdetect", "-y", "1"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return {"success": True, "output": result.stdout}

            # Data operations
            elif command == "export-data":
                script_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "scripts",
                    "export_data.py",
                )
                result = subprocess.run(
                    ["python3", script_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return {"success": True, "output": result.stdout + result.stderr}

            elif command == "backup-database":
                # Create backup
                backup_dir = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "backups"
                )
                os.makedirs(backup_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(backup_dir, f"events_{timestamp}.db")
                shutil.copy2(self.config.database_path, backup_path)
                return {
                    "success": True,
                    "output": f"Database backed up to: {backup_path}",
                }

            elif command == "view-recent-events":
                events = self.db.get_recent_events(20)
                output = "Recent Events:\n" + "=" * 80 + "\n"
                for event in events:
                    output += f"{event['timestamp']} | {event['stage']:12} | Token {event['token_id']} | {event['device_id']}\n"
                return {"success": True, "output": output}

            elif command == "database-stats":
                total = self.db.get_event_count()
                session_total = self.db.get_event_count(self.config.session_id)
                output = f"Database Statistics:\n"
                output += f"=" * 80 + "\n"
                output += f"Total events (all sessions): {total}\n"
                output += f"Events in current session:   {session_total}\n"
                output += f"Session ID:                  {self.config.session_id}\n"
                return {"success": True, "output": output}

            # System control
            elif command == "system-reboot":
                subprocess.Popen(["sudo", "reboot"])
                return {"success": True, "output": "System rebooting..."}

            elif command == "system-shutdown":
                subprocess.Popen(["sudo", "shutdown", "-h", "now"])
                return {"success": True, "output": "System shutting down..."}

            elif command == "view-logs":
                log_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "logs",
                    "tap-station.log",
                )
                if os.path.exists(log_path):
                    result = subprocess.run(
                        ["tail", "-n", "50", log_path],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    return {"success": True, "output": result.stdout}
                else:
                    return {"success": False, "error": "Log file not found"}

            elif command == "disk-usage":
                result = subprocess.run(
                    ["df", "-h", "/"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return {"success": True, "output": result.stdout}

            # Development commands
            elif command == "dev-reset":
                script_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "scripts",
                    "dev_reset.py",
                )
                result = subprocess.run(
                    ["python3", script_path],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return {"success": True, "output": result.stdout + result.stderr}

            elif command == "test-read-card":
                # Test reading an NFC card
                try:
                    # Import NFC reader
                    from tap_station.nfc_reader import NFCReader

                    output = "Testing NFC card read...\n"
                    output += "Please place a card on the reader now...\n\n"

                    # Create temporary NFC reader
                    reader = NFCReader(
                        i2c_bus=self.config.i2c_bus,
                        address=self.config.i2c_address,
                        timeout=5,
                        retries=2,
                        debounce_seconds=0,
                    )

                    # Try to read a card
                    token_id, uid = reader.read_card()

                    if token_id and uid:
                        output += f"✓ Card read successful!\n"
                        output += f"  Token ID: {token_id}\n"
                        output += f"  UID: {uid}\n"
                        return {"success": True, "output": output}
                    else:
                        output += "✗ No card detected\n"
                        output += "  Make sure card is placed on reader\n"
                        output += "  Try again or check hardware connection\n"
                        return {"success": False, "error": output}

                except Exception as e:
                    output += f"✗ Error: {str(e)}\n"
                    output += "  Check NFC reader connection\n"
                    output += "  Run 'Verify Hardware' for diagnostics\n"
                    return {"success": False, "error": output}

            elif command == "run-tests":
                # Run pytest
                result = subprocess.run(
                    ["pytest", "tests/", "-v"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=os.path.dirname(os.path.dirname(__file__)),
                )
                return {"success": True, "output": result.stdout + result.stderr}

            elif command == "git-status":
                result = subprocess.run(
                    ["git", "status"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    cwd=os.path.dirname(os.path.dirname(__file__)),
                )
                return {"success": True, "output": result.stdout}

            else:
                return {"success": False, "error": f"Unknown command: {command}"}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            logger.error(f"Command execution failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

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
