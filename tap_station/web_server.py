"""
Simple web server for health checks and participant status checking

Provides:
- /health endpoint for monitoring
- /check?token=XXX endpoint for participant status
- /api/status/<token> API endpoint
- /control endpoint for system administration (requires authentication)
- /login endpoint for admin authentication
"""

import csv
import logging
import os
import secrets
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from functools import wraps
from io import StringIO
from threading import Lock

from flask import (
    Flask,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

# Import utilities
from .datetime_utils import from_iso, parse_timestamp
from .path_utils import ensure_dir

# Initialize logger at module level (before try block to avoid duplication)
logger = logging.getLogger(__name__)

# Import service configuration integration
try:
    from .service_integration import get_service_integration

    SERVICE_CONFIG_AVAILABLE = True
except ImportError:
    SERVICE_CONFIG_AVAILABLE = False
    logger.warning("Service configuration not available, using defaults")


# Simple rate limiting implementation
class RateLimiter:
    """Simple in-memory rate limiter for API endpoints"""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Initialize rate limiter

        Args:
            max_requests: Maximum requests allowed per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
        self.lock = Lock()

    def is_allowed(self, key: str) -> bool:
        """
        Check if request is allowed

        Args:
            key: Identifier (e.g., IP address)

        Returns:
            True if request is allowed
        """
        now = time.time()
        with self.lock:
            # Clean up old requests
            self.requests[key] = [
                req_time
                for req_time in self.requests[key]
                if now - req_time < self.window_seconds
            ]

            # Check if under limit
            if len(self.requests[key]) < self.max_requests:
                self.requests[key].append(now)
                return True

            return False

    def get_remaining(self, key: str) -> int:
        """Get number of remaining requests in current window"""
        now = time.time()
        with self.lock:
            # Clean up old requests
            self.requests[key] = [
                req_time
                for req_time in self.requests[key]
                if now - req_time < self.window_seconds
            ]
            return max(0, self.max_requests - len(self.requests[key]))


def require_admin_auth(f):
    """
    Decorator to require admin authentication for control panel routes

    Checks if user is logged in via session. If not, redirects to login page.
    Also checks session timeout and auto-logs out inactive sessions.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is authenticated
        if not session.get("admin_authenticated"):
            return redirect(url_for("login", next=request.url))

        # Check session timeout
        last_activity = session.get("last_activity")
        if last_activity:
            try:
                last_activity_time = datetime.fromisoformat(last_activity)
                # Get timeout from Flask app config (set during init)
                timeout_minutes = current_app.config.get(
                    "ADMIN_SESSION_TIMEOUT_MINUTES", 60
                )
                if datetime.now(timezone.utc) - last_activity_time > timedelta(
                    minutes=timeout_minutes
                ):
                    # Session timed out
                    session.clear()
                    return redirect(
                        url_for(
                            "login",
                            next=request.url,
                            error="Session timed out. Please login again.",
                        )
                    )
            except (ValueError, TypeError):
                # Invalid timestamp, clear session
                session.clear()
                return redirect(url_for("login"))

        # Update last activity time
        session["last_activity"] = datetime.now(timezone.utc).isoformat()

        return f(*args, **kwargs)

    return decorated_function


def rate_limit(limiter: RateLimiter):
    """
    Decorator to apply rate limiting to Flask routes

    Args:
        limiter: RateLimiter instance
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Use IP address as key
            key = request.remote_addr or "unknown"

            if not limiter.is_allowed(key):
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Rate limit exceeded. Please try again later.",
                        }
                    ),
                    429,
                )

            return f(*args, **kwargs)

        return decorated_function

    return decorator


class StatusWebServer:
    """Web server for health checks and status"""

    def __init__(self, config, database, registry=None):
        """
        Initialize web server

        Args:
            config: Config instance
            database: Database instance
            registry: ExtensionRegistry instance (optional)
        """
        self.config = config
        self.db = database

        # Extension registry (use a no-op registry if none provided)
        if registry is None:
            from .registry import ExtensionRegistry

            registry = ExtensionRegistry()
        self.registry = registry
        self.app = Flask(__name__)

        # Configure Flask session for admin authentication
        # Generate a secure random secret key for session encryption
        self.app.config["SECRET_KEY"] = secrets.token_hex(32)
        self.app.config["SESSION_COOKIE_HTTPONLY"] = True
        self.app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
        self.app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)

        # Store admin password and timeout from config
        self.app.config["ADMIN_PASSWORD"] = config.admin_password
        self.app.config["ADMIN_SESSION_TIMEOUT_MINUTES"] = (
            config.admin_session_timeout_minutes
        )

        # Load service configuration
        if SERVICE_CONFIG_AVAILABLE:
            self.svc = get_service_integration()
            logger.info(
                f"Service configuration loaded: {self.svc.get_service_name()}"
            )
        else:
            self.svc = None
            logger.warning("Service configuration not available")

        # Cache stage IDs from service configuration for SQL queries
        # This allows stage names to be configured rather than hardcoded
        self._init_stage_ids()

        # Setup routes
        self._setup_routes()

    def _init_stage_ids(self):
        """
        Initialize stage IDs from service configuration.

        Required stages (always present):
        - STAGE_QUEUE_JOIN: First stage in workflow (entry point)
        - STAGE_EXIT: Last stage in workflow (completion)

        Optional stages (may be None):
        - STAGE_SERVICE_START: When service begins (for 3+ stage workflows)
        - STAGE_SUBSTANCE_RETURNED: When substance is returned (for accountability)

        Services can use any stage names they want. The system adapts to
        whatever workflow is configured, from simple 2-stage queue tracking
        to complex multi-stage accountability workflows.
        """
        if self.svc:
            # Required stages - always exist
            self.STAGE_QUEUE_JOIN = self.svc.get_first_stage()
            self.STAGE_EXIT = self.svc.get_last_stage()
            # Optional stages - may be None if not in workflow
            self.STAGE_SERVICE_START = self.svc.get_service_start_stage()
            self.STAGE_SUBSTANCE_RETURNED = self.svc.get_substance_returned_stage()
            # Track workflow complexity
            self._has_service_start = self.svc.has_service_start_stage()
            self._has_substance_returned = self.svc.has_substance_returned_stage()
            self._is_multi_stage = self.svc.is_multi_stage_workflow()
        else:
            # Minimal fallback - only assume required stages exist
            self.STAGE_QUEUE_JOIN = "QUEUE_JOIN"
            self.STAGE_EXIT = "EXIT"
            # Don't assume optional stages exist
            self.STAGE_SERVICE_START = None
            self.STAGE_SUBSTANCE_RETURNED = None
            self._has_service_start = False
            self._has_substance_returned = False
            self._is_multi_stage = False

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
                            "timestamp": datetime.now(
                                timezone.utc
                            ).isoformat(),
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
                            "timestamp": datetime.now(
                                timezone.utc
                            ).isoformat(),
                        }
                    ),
                    500,
                )

        @self.app.route("/healthz")
        def healthz():
            """
            Kubernetes-style liveness probe.

            Returns:
                200 OK if service is alive (can respond to requests)
                503 if service is not functioning
            """
            try:
                # Simple liveness check - just verify app is responding
                return jsonify({"status": "ok"}), 200
            except Exception as e:
                logger.error(f"Liveness check failed: {e}")
                return jsonify({"status": "error", "error": str(e)}), 503

        @self.app.route("/readyz")
        def readyz():
            """
            Kubernetes-style readiness probe.

            Returns:
                200 OK if service is ready to accept traffic
                503 if service is not ready (e.g., database not accessible)
            """
            errors = []

            # Check database connectivity
            try:
                count = self.db.get_event_count()
            except Exception as e:
                errors.append(f"database: {e}")

            # Check disk space (warn if > 90% full)
            try:
                usage = shutil.disk_usage("/")
                percent_used = (usage.used / usage.total) * 100
                if percent_used > 90:
                    errors.append(f"disk: {percent_used:.1f}% full (critical)")
            except Exception:
                pass  # Don't fail on disk check errors

            if errors:
                return (
                    jsonify(
                        {
                            "status": "not_ready",
                            "errors": errors,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    ),
                    503,
                )

            return (
                jsonify(
                    {
                        "status": "ready",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                200,
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
                        jsonify(
                            {"error": "Too many events (max 1000 per request)"}
                        ),
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
                            logger.warning(
                                f"Invalid event type: {type(event)}"
                            )
                            errors += 1
                            continue

                        # Normalize fields
                        token_id = str(
                            event.get("token_id")
                            or event.get("tokenId")
                            or "UNKNOWN"
                        )
                        uid = str(
                            event.get("uid")
                            or event.get("serial")
                            or token_id
                            or "UNKNOWN"
                        )
                        stage = (
                            str(event.get("stage") or "").strip().upper()
                            or "UNKNOWN"
                        )

                        # Validate stage against service configuration
                        if self.svc and not self.svc.is_valid_stage(stage):
                            logger.warning(
                                f"Invalid stage '{stage}' in event for token "
                                f"'{event.get('token_id')}'. Valid stages: "
                                f"{self.svc.get_all_stage_ids()}"
                            )
                            # Continue processing - log event but flag it
                            # This allows review of misconfigured stages later

                        session_id = str(
                            event.get("session_id")
                            or event.get("sessionId")
                            or "UNKNOWN"
                        )
                        device_id = str(
                            event.get("device_id")
                            or event.get("deviceId")
                            or "mobile"
                        )

                        # Validate field lengths (prevent database bloat)
                        if (
                            len(token_id) > 100
                            or len(uid) > 100
                            or len(stage) > 50
                        ):
                            logger.warning(f"Field too long in event: {event}")
                            errors += 1
                            continue

                        # Handle timestamp using centralized function
                        ts_val = event.get("timestamp_ms") or event.get(
                            "timestampMs"
                        )
                        timestamp = parse_timestamp(
                            ts_val, default_to_now=False
                        )

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
                return (
                    render_template(
                        "error.html", error="No token ID provided"
                    ),
                    400,
                )

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
                    render_template(
                        "error.html", error=f"Error checking status: {e}"
                    ),
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
                logger.error(
                    f"API status check failed for token {token_id}: {e}"
                )
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
                    "total_events": self.db.get_event_count(
                        self.config.session_id
                    ),
                    "recent_events": self.db.get_recent_events(10),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                return jsonify(stats), 200

            except Exception as e:
                logger.error(f"API stats failed: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/service-config")
        def api_service_config():
            """
            API endpoint for service configuration

            Returns:
                JSON with service configuration for frontend use
            """
            try:
                if not self.svc:
                    # Return default configuration
                    return (
                        jsonify(
                            {
                                "service_name": "Drug Checking Service",
                                "workflow_stages": [
                                    {
                                        "id": "QUEUE_JOIN",
                                        "label": "In Queue",
                                        "order": 1,
                                    },
                                    {
                                        "id": "SERVICE_START",
                                        "label": "Being Served",
                                        "order": 2,
                                    },
                                    {
                                        "id": "SUBSTANCE_RETURNED",
                                        "label": "Substance Returned",
                                        "order": 3,
                                    },
                                    {
                                        "id": "EXIT",
                                        "label": "Completed",
                                        "order": 4,
                                    },
                                ],
                                "ui_labels": {
                                    "queue_count": "people in queue",
                                    "wait_time": "estimated wait",
                                    "served_today": "served today",
                                    "avg_service_time": "avg service time",
                                    "service_status": "service status",
                                },
                                "display_settings": {
                                    "refresh_interval": 5,
                                    "show_queue_positions": True,
                                    "show_wait_estimates": True,
                                    "show_served_count": True,
                                    "show_avg_time": True,
                                },
                            }
                        ),
                        200,
                    )

                # Return actual configuration
                config = {
                    "service_name": self.svc.get_service_name(),
                    "workflow_stages": (
                        [
                            {
                                "id": stage.id,
                                "label": stage.label,
                                "description": stage.description,
                                "order": stage.order,
                                "visible_to_public": stage.visible_to_public,
                            }
                            for stage in self.svc._config.workflow_stages
                        ]
                        if self.svc._config
                        else []
                    ),
                    "ui_labels": (
                        self.svc._config.ui_labels if self.svc._config else {}
                    ),
                    "display_settings": {
                        "refresh_interval": self.svc.get_public_refresh_interval(),
                        "show_queue_positions": self.svc.show_queue_positions(),
                        "show_wait_estimates": self.svc.show_wait_estimates(),
                        "show_served_count": self.svc.show_served_count(),
                        "show_avg_time": self.svc.show_avg_time(),
                    },
                    "capacity": {
                        "people_per_hour": self.svc.get_people_per_hour(),
                        "avg_service_minutes": self.svc.get_avg_service_minutes(),
                    },
                }
                return jsonify(config), 200

            except Exception as e:
                logger.error(f"API service config failed: {e}")
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

        @self.app.route("/login", methods=["GET", "POST"])
        def login():
            """Admin login page and authentication"""
            if request.method == "POST":
                password = request.form.get("password", "").strip()

                # Verify password
                if password == self.app.config.get("ADMIN_PASSWORD"):
                    # Set session as authenticated
                    session.permanent = True
                    session["admin_authenticated"] = True
                    session["last_activity"] = datetime.now(
                        timezone.utc
                    ).isoformat()
                    session["login_time"] = datetime.now(
                        timezone.utc
                    ).isoformat()

                    # Redirect to original destination or control panel
                    next_url = request.args.get("next")
                    if next_url and next_url.startswith("/"):
                        return redirect(next_url)
                    return redirect(url_for("control"))
                else:
                    # Invalid password
                    return render_template(
                        "login.html",
                        session=self.config.session_id,
                        error="Invalid password. Please try again.",
                    )

            # GET request - show login form
            error = request.args.get("error")
            return render_template(
                "login.html", session=self.config.session_id, error=error
            )

        @self.app.route("/logout")
        def logout():
            """Logout admin user"""
            session.clear()
            return redirect(
                url_for("login", error="You have been logged out.")
            )

        @self.app.route("/control")
        @require_admin_auth
        def control():
            """Control panel for system administration"""
            return render_template(
                "control.html",
                device_id=self.config.device_id,
                stage=self.config.stage,
                session=self.config.session_id,
            )

        @self.app.route("/api/control/status")
        @require_admin_auth
        def api_control_status():
            """Get system status for control panel"""
            try:
                status = self._get_system_status()
                return jsonify(status), 200
            except Exception as e:
                logger.error(f"Control status failed: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/control/execute", methods=["POST"])
        @require_admin_auth
        def api_control_execute():
            """Execute a control command"""
            try:
                data = request.get_json()
                command = data.get("command")

                if not command:
                    return (
                        jsonify(
                            {"success": False, "error": "No command specified"}
                        ),
                        400,
                    )

                result = self._execute_control_command(command)
                return jsonify(result), 200

            except Exception as e:
                logger.error(f"Command execution failed: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route("/api/card-lookup")
        def api_card_lookup():
            """Look up current status and journey for a card"""
            try:
                token_id = request.args.get("token_id", "").strip()
                if not token_id:
                    return jsonify({"error": "Token ID required"}), 400

                card_info = self._get_card_status(token_id)
                return jsonify(card_info), 200

            except Exception as e:
                logger.error(f"Card lookup failed: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/control/backup-database")
        @require_admin_auth
        def api_backup_database():
            """Download full database backup"""
            try:
                from datetime import datetime

                from flask import send_file

                # Create backup filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                session_id = self.config.session_id
                backup_filename = (
                    f"tap_station_backup_{session_id}_{timestamp}.db"
                )

                # Get database path
                db_path = self.db.db_path

                # Send file directly (Flask handles the streaming)
                return send_file(
                    db_path,
                    mimetype="application/x-sqlite3",
                    as_attachment=True,
                    download_name=backup_filename,
                )

            except Exception as e:
                logger.error(f"Database backup failed: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/public")
        def public_display():
            """Public-facing queue status display"""
            return render_template("public.html")

        @self.app.route("/api/public")
        def api_public():
            """
            API endpoint for public queue display

            Returns:
                JSON with public-safe queue statistics
            """
            try:
                stats = self._get_public_stats()
                return jsonify(stats), 200

            except Exception as e:
                logger.error(f"API public failed: {e}")
                return jsonify({"error": str(e)}), 500

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

        # Let extensions register their API routes
        self.registry.run_on_api_routes(self.app, self.db, self.config)

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
                AND e.stage = ?
            WHERE q.stage = ?
                AND q.session_id = ?
                AND e.id IS NULL
        """,
            (self.STAGE_EXIT, self.STAGE_QUEUE_JOIN, session_id),
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
            WHERE q.stage = ?
                AND e.stage = ?
                AND q.session_id = ?
                AND date(e.timestamp) = date('now')
        """,
            (self.STAGE_QUEUE_JOIN, self.STAGE_EXIT, session_id),
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

        stats = {
            "device_id": self.config.device_id,
            "stage": self.config.stage,
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stats": {
                "today_events": today_events,
                "last_hour_events": last_hour_events,
                "in_queue": in_queue,
                "in_service": 0,  # Set by three_stage extension
                "completed_today": completed_today,
                "avg_wait_minutes": avg_wait,
                "throughput_per_hour": (
                    last_hour_events / 2 if last_hour_events > 0 else 0
                ),  # Rough estimate
                "longest_wait_current": operational_metrics[
                    "longest_wait_current"
                ],
                "estimated_wait_new": operational_metrics[
                    "estimated_wait_new"
                ],
                "smart_wait_estimate": {},  # Set by smart_estimates extension
                "service_uptime_minutes": operational_metrics[
                    "service_uptime_minutes"
                ],
                "capacity_utilization": operational_metrics[
                    "capacity_utilization"
                ],
                # 3-stage metrics (set by three_stage extension)
                "avg_queue_wait_minutes": 0,
                "avg_service_time_minutes": 0,
                "avg_total_time_minutes": 0,
                "has_3stage_data": False,
            },
            "operational": {
                "alerts": operational_metrics["alerts"],
                "queue_health": operational_metrics["queue_health"],
            },
            # Set by substance_tracking extension
            "substance_return": {
                "enabled": False,
                "pending_returns": 0,
                "completed_returns": 0,
                "return_rate_percent": 0,
            },
            "queue_details": queue_details,
            "recent_completions": recent_completions,
            "hourly_activity": hourly_activity,
            "recent_events": recent_events,
        }

        # Let extensions add their own dashboard stats
        self.registry.run_on_dashboard_stats(stats)

        return stats

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
                AND e.stage = ?
            WHERE q.stage = ?
                AND q.session_id = ?
                AND e.id IS NULL
            ORDER BY datetime(q.timestamp) ASC
            LIMIT 1
        """,
            (self.STAGE_EXIT, self.STAGE_QUEUE_JOIN, session_id),
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
                AND e.stage = ?
            WHERE q.stage = ?
                AND q.session_id = ?
                AND e.id IS NULL
        """,
            (self.STAGE_EXIT, self.STAGE_QUEUE_JOIN, session_id),
        )
        in_queue = cursor.fetchone()["count"]
        queue_mult = self.svc.get_queue_multiplier() if self.svc else 2
        default_wait = self.svc.get_default_wait_estimate() if self.svc else 20
        estimated_wait_new = (
            avg_wait + (in_queue * queue_mult)
            if avg_wait > 0
            else default_wait
        )

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
            WHERE q.stage = ?
                AND e.stage = ?
                AND q.session_id = ?
                AND e.timestamp > datetime('now', '-1 hour')
        """,
            (self.STAGE_QUEUE_JOIN, self.STAGE_EXIT, session_id),
        )
        completed_last_hour = cursor.fetchone()["completed"]
        # Get service capacity from configuration
        people_per_hour = self.svc.get_people_per_hour() if self.svc else 12
        capacity_utilization = min(
            100, int((completed_last_hour / people_per_hour) * 100)
        )

        # Generate alerts
        alerts = []

        # Get alert thresholds from configuration
        queue_warn = self.svc.get_queue_warning_threshold() if self.svc else 10
        queue_crit = (
            self.svc.get_queue_critical_threshold() if self.svc else 20
        )

        # Queue length alerts
        if in_queue > queue_warn:
            message = (
                self.svc.get_alert_message("queue_warning", count=in_queue)
                if self.svc
                else f"Queue is long ({in_queue} people)"
            )
            alerts.append({"level": "warning", "message": message})
        if in_queue > queue_crit:
            message = (
                self.svc.get_alert_message("queue_critical", count=in_queue)
                if self.svc
                else f"🚨 Queue critical ({in_queue} people) - consider additional resources"
            )
            alerts.append(
                {
                    "level": "critical",
                    "message": message,
                }
            )

        # Wait time alerts
        wait_warn = self.svc.get_wait_warning_minutes() if self.svc else 45
        wait_crit = self.svc.get_wait_critical_minutes() if self.svc else 90

        if longest_wait > wait_warn:
            message = (
                self.svc.get_alert_message(
                    "wait_warning", minutes=longest_wait
                )
                if self.svc
                else f"⏱️ Longest wait: {longest_wait} min"
            )
            alerts.append({"level": "warning", "message": message})
        if longest_wait > wait_crit:
            message = (
                self.svc.get_alert_message(
                    "wait_critical", minutes=longest_wait
                )
                if self.svc
                else f"🚨 Critical wait time: {longest_wait} min"
            )
            alerts.append(
                {
                    "level": "critical",
                    "message": message,
                }
            )

        # Capacity alerts
        capacity_crit = (
            self.svc.get_capacity_critical_percent() if self.svc else 90
        )
        if capacity_utilization > capacity_crit:
            alerts.append(
                {"level": "info", "message": "⚡ Operating near capacity"}
            )

        # Check for station inactivity (no events in last 10 minutes)
        cursor = self.db.conn.execute(
            """
            SELECT MAX(timestamp) as last_event
            FROM events
            WHERE session_id = ?
        """,
            (session_id,),
        )
        row = cursor.fetchone()
        if row and row["last_event"]:
            last_event_dt = datetime.fromisoformat(row["last_event"])
            minutes_since_last = int(
                (now - last_event_dt).total_seconds() / 60
            )

            inactivity_crit = (
                self.svc.get_service_inactivity_critical_minutes()
                if self.svc
                else 10
            )
            inactivity_warn = (
                self.svc.get_service_inactivity_warning_minutes()
                if self.svc
                else 5
            )

            if minutes_since_last > inactivity_crit and in_queue > 0:
                message = (
                    self.svc.get_alert_message(
                        "inactivity_critical", minutes=minutes_since_last
                    )
                    if self.svc
                    else f"⚠️ No activity in {minutes_since_last} min - station may be down!"
                )
                alerts.append(
                    {
                        "level": "critical",
                        "message": message,
                    }
                )
            elif minutes_since_last > inactivity_warn and in_queue > 0:
                message = (
                    self.svc.get_alert_message(
                        "inactivity_warning", minutes=minutes_since_last
                    )
                    if self.svc
                    else f"No taps in {minutes_since_last} min - check stations"
                )
                alerts.append(
                    {
                        "level": "warning",
                        "message": message,
                    }
                )

        # Check for unusual service time variance
        cursor = self.db.conn.execute(
            """
            SELECT
                AVG((julianday(e.timestamp) - julianday(q.timestamp)) * 1440) as avg_time,
                MAX((julianday(e.timestamp) - julianday(q.timestamp)) * 1440) as max_time
            FROM events q
            JOIN events e
                ON q.token_id = e.token_id
                AND q.session_id = e.session_id
            WHERE q.stage = ?
                AND e.stage = ?
                AND q.session_id = ?
                AND e.timestamp > datetime('now', '-1 hour')
        """,
            (self.STAGE_QUEUE_JOIN, self.STAGE_EXIT, session_id),
        )
        row = cursor.fetchone()
        if row and row["avg_time"] and row["max_time"]:
            avg_time = float(row["avg_time"])
            max_time = float(row["max_time"])

            # Alert if someone took more than the configured multiplier of average time
            variance_multiplier = (
                self.svc.get_service_variance_multiplier() if self.svc else 3
            )
            if max_time > avg_time * variance_multiplier and avg_time > 5:
                alerts.append(
                    {
                        "level": "info",
                        "message": f"📊 Service time variance detected - longest service: {int(max_time)} min",
                    }
                )

        # Check for potential abandonments (people in queue > threshold hours)
        stuck_hours = (
            self.svc.get_stuck_cards_threshold_hours() if self.svc else 2
        )
        # Use SQLite concatenation to safely build time offset from parameter
        cursor = self.db.conn.execute(
            """
            SELECT COUNT(*) as count
            FROM events q
            LEFT JOIN events e
                ON q.token_id = e.token_id
                AND q.session_id = e.session_id
                AND e.stage = ?
            WHERE q.stage = ?
                AND q.session_id = ?
                AND e.id IS NULL
                AND q.timestamp < datetime('now', '-' || ? || ' hours')
        """,
            (self.STAGE_EXIT, self.STAGE_QUEUE_JOIN, session_id, str(stuck_hours)),
        )
        stuck_count = cursor.fetchone()["count"]
        if stuck_count > 0:
            alerts.append(
                {
                    "level": "warning",
                    "message": f"⚠️ {stuck_count} people in queue >{stuck_hours} hours - possible abandonments or missed exits",
                }
            )

        # Check for unreturned substances (SUBSTANCE_RETURNED stage tracking)
        if self.svc and self.svc.has_substance_returned_stage():
            unreturned_warn = self.svc.get_unreturned_substance_warning_minutes()
            unreturned_crit = self.svc.get_unreturned_substance_critical_minutes()

            # Find people who have SERVICE_START but no SUBSTANCE_RETURNED
            cursor = self.db.conn.execute(
                """
                SELECT
                    s.token_id,
                    s.timestamp as service_start_time,
                    (julianday('now') - julianday(s.timestamp)) * 1440 as minutes_waiting
                FROM events s
                LEFT JOIN events r
                    ON s.token_id = r.token_id
                    AND s.session_id = r.session_id
                    AND r.stage = ?
                LEFT JOIN events e
                    ON s.token_id = e.token_id
                    AND s.session_id = e.session_id
                    AND e.stage = ?
                WHERE s.stage = ?
                    AND s.session_id = ?
                    AND r.id IS NULL
                    AND e.id IS NULL
                ORDER BY s.timestamp ASC
                """,
                (
                    self.STAGE_SUBSTANCE_RETURNED,
                    self.STAGE_EXIT,
                    self.STAGE_SERVICE_START,
                    session_id,
                ),
            )

            unreturned = cursor.fetchall()
            unreturned_warning_count = 0
            unreturned_critical_count = 0
            oldest_unreturned_minutes = 0

            for row in unreturned:
                minutes = int(row["minutes_waiting"]) if row["minutes_waiting"] else 0
                if minutes > unreturned_crit:
                    unreturned_critical_count += 1
                    if minutes > oldest_unreturned_minutes:
                        oldest_unreturned_minutes = minutes
                elif minutes > unreturned_warn:
                    unreturned_warning_count += 1

            if unreturned_critical_count > 0:
                message = (
                    self.svc.get_alert_message(
                        "unreturned_substance_critical",
                        count=unreturned_critical_count,
                        minutes=oldest_unreturned_minutes,
                        token=unreturned[0]["token_id"] if unreturned else "unknown",
                    )
                    if self.svc
                    else f"🚨 URGENT: {unreturned_critical_count} substances not returned for >{unreturned_crit} min"
                )
                alerts.append({"level": "critical", "message": message})
            elif unreturned_warning_count > 0:
                message = (
                    self.svc.get_alert_message(
                        "unreturned_substance_warning",
                        count=unreturned_warning_count,
                        minutes=unreturned_warn,
                        token=unreturned[0]["token_id"] if unreturned else "unknown",
                    )
                    if self.svc
                    else f"⚠️ {unreturned_warning_count} substances not returned for >{unreturned_warn} min"
                )
                alerts.append({"level": "warning", "message": message})

        # Queue health assessment (use same thresholds as alerts)
        if in_queue > queue_crit or longest_wait > wait_crit:
            queue_health = "critical"
        elif in_queue > queue_warn or longest_wait > wait_warn:
            queue_health = "warning"
        elif in_queue > (queue_warn // 2) or longest_wait > (wait_warn // 1.5):
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
                AND e.stage = ?
            WHERE q.stage = ?
                AND q.session_id = ?
                AND e.id IS NULL
            ORDER BY datetime(q.timestamp) ASC
        """,
            (self.STAGE_EXIT, self.STAGE_QUEUE_JOIN, session_id),
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
                WHERE q.stage = ?
                    AND e.stage = ?
                    AND q.session_id = ?
                ORDER BY e.timestamp DESC
                LIMIT ?
            """,
                (
                    self.STAGE_QUEUE_JOIN,
                    self.STAGE_EXIT,
                    self.config.session_id,
                    limit,
                ),
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
                WHERE q.stage = ?
                    AND e.stage = ?
                    AND q.session_id = ?
                ORDER BY e.timestamp DESC
                LIMIT ?
            """,
                (
                    self.STAGE_QUEUE_JOIN,
                    self.STAGE_EXIT,
                    self.config.session_id,
                    limit,
                ),
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

            if stage == self.STAGE_QUEUE_JOIN:
                result["queue_join"] = timestamp
                result["queue_join_time"] = self._format_time(timestamp)
                result["status"] = "in_queue"

            elif stage == self.STAGE_EXIT:
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
                WHERE q.stage = ?
                    AND e.stage = ?
                    AND q.session_id = ?
                ORDER BY e.timestamp DESC
                LIMIT 10
            """,
                (self.STAGE_QUEUE_JOIN, self.STAGE_EXIT, self.config.session_id),
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
                "total_events": self.db.get_event_count(
                    self.config.session_id
                ),
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
                return {
                    "success": True,
                    "output": result.stdout + result.stderr,
                }

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
                return {
                    "success": True,
                    "output": result.stdout + result.stderr,
                }

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
                return {
                    "success": True,
                    "output": result.stdout + result.stderr,
                }

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
                return {
                    "success": True,
                    "output": result.stdout + result.stderr,
                }

            elif command == "backup-database":
                # Create backup
                backup_dir = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "backups"
                )
                ensure_dir(backup_dir)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(
                    backup_dir, f"events_{timestamp}.db"
                )
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
                output += (
                    f"Session ID:                  {self.config.session_id}\n"
                )
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
                return {
                    "success": True,
                    "output": result.stdout + result.stderr,
                }

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
                return {
                    "success": True,
                    "output": result.stdout + result.stderr,
                }

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
                return {
                    "success": False,
                    "error": f"Unknown command: {command}",
                }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            logger.error(f"Command execution failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _get_public_stats(self) -> dict:
        """
        Get public-facing statistics (safe for participant display)

        Returns:
            Dictionary with public statistics
        """
        session_id = self.config.session_id
        now = datetime.now(timezone.utc)

        # Get current queue length
        cursor = self.db.conn.execute(
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
            (self.STAGE_EXIT, self.STAGE_QUEUE_JOIN, session_id),
        )
        queue_length = cursor.fetchone()["count"]

        # Calculate estimated wait time
        avg_wait = self._calculate_avg_wait_time(limit=10)
        # Add buffer based on queue length (using configured multiplier)
        queue_mult = self.svc.get_queue_multiplier() if self.svc else 2
        default_wait = self.svc.get_default_wait_estimate() if self.svc else 20
        estimated_wait = (
            avg_wait + (queue_length * queue_mult)
            if avg_wait > 0
            else (default_wait // 4)
        )

        # Get completed today
        cursor = self.db.conn.execute(
            """
            SELECT COUNT(*) as count
            FROM events q
            JOIN events e
                ON q.token_id = e.token_id
                AND q.session_id = e.session_id
            WHERE q.stage = ?
                AND e.stage = ?
                AND q.session_id = ?
                AND date(e.timestamp) = date('now')
        """,
            (self.STAGE_QUEUE_JOIN, self.STAGE_EXIT, session_id),
        )
        completed_today = cursor.fetchone()["count"]

        # Check if service is active (any activity in last 10 minutes)
        cursor = self.db.conn.execute(
            """
            SELECT COUNT(*) as count
            FROM events
            WHERE session_id = ?
                AND timestamp > datetime('now', '-10 minutes')
        """,
            (session_id,),
        )
        service_active = cursor.fetchone()["count"] > 0

        return {
            "queue_length": queue_length,
            "estimated_wait_minutes": estimated_wait,
            "completed_today": completed_today,
            "avg_service_minutes": avg_wait,
            "service_active": service_active,
            "session_id": session_id,
            "timestamp": now.isoformat(),
        }

    def _get_card_status(self, token_id: str) -> dict:
        """
        Get current status and full journey for a card

        Args:
            token_id: Token ID to lookup

        Returns:
            Dictionary with card status and journey information
        """
        session_id = self.config.session_id
        now = datetime.now(timezone.utc)

        try:
            # Get all events for this card in current session
            cursor = self.db.conn.execute(
                """
                SELECT stage, timestamp, device_id
                FROM events
                WHERE session_id = ? AND token_id = ?
                ORDER BY timestamp ASC
            """,
                (session_id, token_id),
            )

            events = cursor.fetchall()

            if not events:
                return {
                    "found": False,
                    "token_id": token_id,
                    "message": "Card not found in current session",
                }

            # Determine current stage (last event)
            last_event = events[-1]
            current_stage = last_event["stage"]
            current_stage_time = last_event["timestamp"]

            # Calculate time in current stage
            try:
                if current_stage_time.endswith("Z"):
                    stage_dt = datetime.fromisoformat(
                        current_stage_time.replace("Z", "+00:00")
                    )
                else:
                    stage_dt = datetime.fromisoformat(current_stage_time)
                    if stage_dt.tzinfo is None:
                        stage_dt = stage_dt.replace(tzinfo=timezone.utc)

                time_in_stage = int((now - stage_dt).total_seconds() / 60)
            except Exception as e:
                logger.warning(
                    f"Could not parse timestamp for card {token_id}: {e}"
                )
                time_in_stage = 0

            # Build journey timeline
            journey = []
            for event in events:
                journey.append(
                    {
                        "stage": event["stage"],
                        "timestamp": event["timestamp"],
                        "device": event["device_id"],
                    }
                )

            # Determine status message - build dynamically from config
            status_map = {
                self.STAGE_QUEUE_JOIN: "In Queue",
                self.STAGE_EXIT: "Completed",
            }
            # Add SERVICE_START if this workflow uses it
            if self._has_service_start and self.STAGE_SERVICE_START:
                status_map[self.STAGE_SERVICE_START] = "Being Served"
            # Add SUBSTANCE_RETURNED if this workflow uses it
            if self._has_substance_returned and self.STAGE_SUBSTANCE_RETURNED:
                status_map[self.STAGE_SUBSTANCE_RETURNED] = "Substance Returned"
            # Override with display names from service config if available
            if self.svc and self.svc._config:
                for stage in self.svc._config.workflow_stages:
                    if stage.id in status_map and stage.display_name:
                        status_map[stage.id] = stage.display_name
            status = status_map.get(current_stage, current_stage)

            # Calculate total time if completed
            total_time = None
            if current_stage == self.STAGE_EXIT and len(events) > 1:
                try:
                    first_time = events[0]["timestamp"]
                    if first_time.endswith("Z"):
                        first_dt = datetime.fromisoformat(
                            first_time.replace("Z", "+00:00")
                        )
                    else:
                        first_dt = datetime.fromisoformat(first_time)
                        if first_dt.tzinfo is None:
                            first_dt = first_dt.replace(tzinfo=timezone.utc)

                    if current_stage_time.endswith("Z"):
                        last_dt = datetime.fromisoformat(
                            current_stage_time.replace("Z", "+00:00")
                        )
                    else:
                        last_dt = datetime.fromisoformat(current_stage_time)
                        if last_dt.tzinfo is None:
                            last_dt = last_dt.replace(tzinfo=timezone.utc)

                    total_time = int((last_dt - first_dt).total_seconds() / 60)
                except Exception as e:
                    logger.warning(f"Could not calculate total time: {e}")

            return {
                "found": True,
                "token_id": token_id,
                "status": status,
                "current_stage": current_stage,
                "time_in_stage_minutes": time_in_stage,
                "current_stage_timestamp": current_stage_time,
                "journey": journey,
                "total_events": len(events),
                "total_time_minutes": total_time,
            }

        except Exception as e:
            logger.error(f"Failed to get card status for {token_id}: {e}")
            return {
                "found": False,
                "token_id": token_id,
                "error": str(e),
                "message": "Error retrieving card status",
            }

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
    parser.add_argument(
        "--config", default="config.yaml", help="Config file path"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument(
        "--port", type=int, default=8080, help="Port to listen on"
    )

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
