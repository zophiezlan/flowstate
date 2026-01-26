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
import sys
import logging
import subprocess
import os
import shutil
import time
import secrets
from collections import defaultdict
from io import StringIO
from threading import Lock
from functools import wraps
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, current_app
from datetime import datetime, timezone, timedelta

# Import utilities
from .datetime_utils import parse_timestamp, from_iso
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
                req_time for req_time in self.requests[key]
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
                req_time for req_time in self.requests[key]
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
        if not session.get('admin_authenticated'):
            return redirect(url_for('login', next=request.url))
        
        # Check session timeout
        last_activity = session.get('last_activity')
        if last_activity:
            try:
                last_activity_time = datetime.fromisoformat(last_activity)
                # Get timeout from Flask app config (set during init)
                timeout_minutes = current_app.config.get('ADMIN_SESSION_TIMEOUT_MINUTES', 60)
                if datetime.now(timezone.utc) - last_activity_time > timedelta(minutes=timeout_minutes):
                    # Session timed out
                    session.clear()
                    return redirect(url_for('login', next=request.url, error='Session timed out. Please login again.'))
            except (ValueError, TypeError):
                # Invalid timestamp, clear session
                session.clear()
                return redirect(url_for('login'))
        
        # Update last activity time
        session['last_activity'] = datetime.now(timezone.utc).isoformat()
        
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
            key = request.remote_addr or 'unknown'
            
            if not limiter.is_allowed(key):
                return jsonify({
                    "success": False,
                    "error": "Rate limit exceeded. Please try again later.",
                }), 429
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


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
        
        # Configure Flask session for admin authentication
        # Generate a secure random secret key for session encryption
        self.app.config['SECRET_KEY'] = secrets.token_hex(32)
        self.app.config['SESSION_COOKIE_HTTPONLY'] = True
        self.app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
        self.app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
        
        # Store admin password and timeout from config
        self.app.config['ADMIN_PASSWORD'] = config.admin_password
        self.app.config['ADMIN_SESSION_TIMEOUT_MINUTES'] = config.admin_session_timeout_minutes
        
        # Initialize rate limiters for different endpoint types
        # Control endpoints (manual-event, remove-event): 10 requests/minute
        self.control_limiter = RateLimiter(max_requests=10, window_seconds=60)
        # Anomaly endpoint: 30 requests/minute (higher since it's read-only)
        self.anomaly_limiter = RateLimiter(max_requests=30, window_seconds=60)

        # Load service configuration
        if SERVICE_CONFIG_AVAILABLE:
            self.svc = get_service_integration()
            logger.info(f"Service configuration loaded: {self.svc.get_service_name()}")
        else:
            self.svc = None
            logger.warning("Service configuration not available")

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
                            "timestamp": datetime.now(timezone.utc).isoformat(),
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
                            "timestamp": datetime.now(timezone.utc).isoformat(),
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

                        # Handle timestamp using centralized function
                        ts_val = event.get("timestamp_ms") or event.get("timestampMs")
                        timestamp = parse_timestamp(ts_val, default_to_now=False)

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
                                    {"id": "EXIT", "label": "Completed", "order": 3},
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
                    "ui_labels": self.svc._config.ui_labels if self.svc._config else {},
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
                if password == self.app.config.get('ADMIN_PASSWORD'):
                    # Set session as authenticated
                    session.permanent = True
                    session['admin_authenticated'] = True
                    session['last_activity'] = datetime.now(timezone.utc).isoformat()
                    session['login_time'] = datetime.now(timezone.utc).isoformat()
                    
                    # Redirect to original destination or control panel
                    next_url = request.args.get('next')
                    if next_url and next_url.startswith('/'):
                        return redirect(next_url)
                    return redirect(url_for('control'))
                else:
                    # Invalid password
                    return render_template(
                        "login.html",
                        session=self.config.session_id,
                        error="Invalid password. Please try again."
                    )
            
            # GET request - show login form
            error = request.args.get('error')
            return render_template(
                "login.html",
                session=self.config.session_id,
                error=error
            )

        @self.app.route("/logout")
        def logout():
            """Logout admin user"""
            session.clear()
            return redirect(url_for('login', error='You have been logged out.'))

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

        @self.app.route("/shift")
        def shift_summary():
            """Shift summary page for handoffs"""
            return render_template(
                "shift.html",
                device_id=self.config.device_id,
                stage=self.config.stage,
                session=self.config.session_id,
            )
        
        @self.app.route("/event-summary")
        @require_admin_auth
        def event_summary():
            """Event summary page with final statistics and goal tracking"""
            try:
                session_id = self.config.session_id
                summary_data = self._calculate_event_summary(session_id)
                
                return render_template(
                    "event_summary.html",
                    **summary_data
                )
            except Exception as e:
                logger.error(f"Event summary failed: {e}", exc_info=True)
                return render_template("error.html", error=str(e)), 500

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
                        jsonify({"success": False, "error": "No command specified"}),
                        400,
                    )

                result = self._execute_control_command(command)
                return jsonify(result), 200

            except Exception as e:
                logger.error(f"Command execution failed: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route("/api/control/force-exit", methods=["POST"])
        @require_admin_auth
        def api_force_exit():
            """Force exit for stuck cards"""
            try:
                data = request.get_json()
                token_ids = data.get("token_ids", [])

                if not token_ids:
                    return (
                        jsonify({"success": False, "error": "No token IDs provided"}),
                        400,
                    )

                result = self._force_exit_cards(token_ids)
                return jsonify(result), 200

            except Exception as e:
                logger.error(f"Force exit failed: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route("/api/control/stuck-cards")
        @require_admin_auth
        def api_stuck_cards():
            """Get list of stuck cards (in queue >2 hours)"""
            try:
                stuck_cards = self._get_stuck_cards()
                return jsonify(stuck_cards), 200
            except Exception as e:
                logger.error(f"Get stuck cards failed: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/control/anomalies")
        @require_admin_auth
        @rate_limit(self.anomaly_limiter)
        def api_anomalies():
            """Get real-time anomaly detection for human errors"""
            try:
                anomalies = self.db.get_anomalies(self.config.session_id)

                return (
                    jsonify(
                        {
                            "anomalies": anomalies,
                            "summary": anomalies.get("summary", {}),
                            "session_id": self.config.session_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    ),
                    200,
                )
            except Exception as e:
                logger.error(f"Get anomalies failed: {e}")
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/control/manual-event", methods=["POST"])
        @require_admin_auth
        @rate_limit(self.control_limiter)
        def api_manual_event():
            """Add a manual event for missed taps"""
            try:
                data = request.get_json()

                # Validate required fields
                required = ["token_id", "stage", "timestamp", "operator_id", "reason"]
                missing = [f for f in required if f not in data]
                if missing:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": f"Missing required fields: {', '.join(missing)}",
                            }
                        ),
                        400,
                    )

                # Parse timestamp with comprehensive error handling
                try:
                    timestamp_str = data["timestamp"]
                    
                    # Try ISO format first
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str)
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=timezone.utc)
                    except (ValueError, AttributeError):
                        # Try parsing as Unix timestamp (seconds or milliseconds)
                        try:
                            ts_value = float(timestamp_str)
                            # If value is very large, assume milliseconds
                            if ts_value > 1e10:
                                ts_value = ts_value / 1000
                            timestamp = datetime.fromtimestamp(ts_value, tz=timezone.utc)
                        except (ValueError, OSError) as e:
                            return (
                                jsonify(
                                    {
                                        "success": False,
                                        "error": f"Invalid timestamp format. Expected ISO 8601 string (YYYY-MM-DDTHH:MM:SS) or Unix timestamp. Got: {timestamp_str}",
                                    }
                                ),
                                400,
                            )
                    
                    # Validate timestamp is reasonable (not too far in past or future)
                    now = datetime.now(timezone.utc)
                    max_age_days = 30
                    max_future_hours = 1
                    
                    if timestamp < now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=max_age_days):
                        return (
                            jsonify(
                                {
                                    "success": False,
                                    "error": f"Timestamp is more than {max_age_days} days in the past",
                                }
                            ),
                            400,
                        )
                    
                    if timestamp > now + timedelta(hours=max_future_hours):
                        return (
                            jsonify(
                                {
                                    "success": False,
                                    "error": f"Timestamp is more than {max_future_hours} hours in the future",
                                }
                            ),
                            400,
                        )
                        
                except KeyError:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": "Missing required field: timestamp",
                            }
                        ),
                        400,
                    )

                # Add manual event
                result = self.db.add_manual_event(
                    token_id=data["token_id"],
                    stage=data["stage"],
                    timestamp=timestamp,
                    session_id=self.config.session_id,
                    operator_id=data["operator_id"],
                    reason=data["reason"],
                )

                if result["success"]:
                    return (
                        jsonify(
                            {
                                "success": True,
                                "message": "Manual event added successfully",
                                "warnings": result.get("warning"),
                            }
                        ),
                        200,
                    )
                else:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": result.get("warning", "Failed to add event"),
                            }
                        ),
                        400,
                    )

            except Exception as e:
                logger.error(f"Manual event addition failed: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route("/api/control/remove-event", methods=["POST"])
        @require_admin_auth
        @rate_limit(self.control_limiter)
        def api_remove_event():
            """Remove an incorrect event"""
            try:
                data = request.get_json()
                
                if not data:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": "Request body must be JSON",
                            }
                        ),
                        400,
                    )

                # Validate required fields
                required = ["event_id", "operator_id", "reason"]
                missing = [f for f in required if f not in data]
                if missing:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": f"Missing required fields: {', '.join(missing)}",
                            }
                        ),
                        400,
                    )
                
                # Validate event_id is an integer
                try:
                    event_id = int(data["event_id"])
                    if event_id <= 0:
                        raise ValueError("event_id must be positive")
                except (ValueError, TypeError) as e:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": f"Invalid event_id: must be a positive integer",
                            }
                        ),
                        400,
                    )
                
                # Validate operator_id is non-empty
                operator_id = str(data["operator_id"]).strip()
                if not operator_id:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": "operator_id cannot be empty",
                            }
                        ),
                        400,
                    )
                
                # Validate reason is non-empty
                reason = str(data["reason"]).strip()
                if not reason:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": "reason cannot be empty",
                            }
                        ),
                        400,
                    )

                # Remove event
                result = self.db.remove_event(
                    event_id=event_id,
                    operator_id=operator_id,
                    reason=reason,
                )

                if result["success"]:
                    return (
                        jsonify(
                            {
                                "success": True,
                                "message": "Event removed successfully",
                                "removed_event": result["removed_event"],
                            }
                        ),
                        200,
                    )
                else:
                    return jsonify(result), 400

            except Exception as e:
                logger.error(f"Event removal failed: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route("/api/export")
        def api_export():
            """Export data as CSV"""
            try:
                # Get filter parameters
                filter_type = request.args.get("filter", "all")
                session_id = self.config.session_id

                # Build query based on filter
                if filter_type == "hour":
                    where_clause = "WHERE session_id = ? AND timestamp > datetime('now', '-1 hour')"
                elif filter_type == "today":
                    where_clause = (
                        "WHERE session_id = ? AND date(timestamp) = date('now')"
                    )
                else:
                    where_clause = "WHERE session_id = ?"

                # Fetch data
                cursor = self.db.conn.execute(
                    f"""
                    SELECT id, token_id, uid, stage, timestamp, device_id, session_id
                    FROM events
                    {where_clause}
                    ORDER BY timestamp DESC
                """,
                    (session_id,),
                )

                # Generate CSV
                output = StringIO()
                writer = csv.writer(output)
                writer.writerow(
                    [
                        "ID",
                        "Token ID",
                        "UID",
                        "Stage",
                        "Timestamp",
                        "Device ID",
                        "Session ID",
                    ]
                )

                for row in cursor.fetchall():
                    writer.writerow(
                        [
                            row["id"],
                            row["token_id"],
                            row["uid"],
                            row["stage"],
                            row["timestamp"],
                            row["device_id"],
                            row["session_id"],
                        ]
                    )

                # Return as downloadable file
                from flask import make_response

                csv_data = output.getvalue()
                response = make_response(csv_data)
                response.headers["Content-Disposition"] = (
                    f"attachment; filename=nfc_data_{filter_type}_{session_id}.csv"
                )
                response.headers["Content-Type"] = "text/csv"

                return response

            except Exception as e:
                logger.error(f"Export failed: {e}")
                return jsonify({"error": str(e)}), 500

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
                from flask import send_file
                from datetime import datetime

                # Create backup filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                session_id = self.config.session_id
                backup_filename = f"tap_station_backup_{session_id}_{timestamp}.db"

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

        @self.app.route("/api/notes", methods=["GET", "POST"])
        def api_notes():
            """Add or retrieve event notes"""
            if request.method == "POST":
                try:
                    data = request.get_json()
                    note_text = data.get("note", "").strip()

                    if not note_text:
                        return jsonify({"error": "Note text required"}), 400

                    # Store note in database using events table with special stage
                    from datetime import datetime

                    now = datetime.now(timezone.utc)

                    self.db.log_event(
                        token_id="NOTE",
                        uid=note_text[:100],  # Store first 100 chars in uid
                        stage="NOTE",
                        device_id=data.get("author", "staff"),
                        session_id=self.config.session_id,
                        timestamp=now,
                    )

                    # Store full note text in a comment field if available
                    # For now, we'll retrieve from uid

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
                    logger.error(f"Add note failed: {e}")
                    return jsonify({"error": str(e)}), 500
            else:
                # GET - retrieve notes
                try:
                    session_id = self.config.session_id
                    cursor = self.db.conn.execute(
                        """
                        SELECT timestamp, device_id as author, uid as note_text
                        FROM events
                        WHERE session_id = ? AND stage = 'NOTE'
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
                    logger.error(f"Get notes failed: {e}")
                    return jsonify({"error": str(e)}), 500

        @self.app.route("/api/control/hardware-status")
        @require_admin_auth
        def api_hardware_status():
            """Get hardware component status"""
            try:
                status = self._get_hardware_status()
                return jsonify(status), 200
            except Exception as e:
                logger.error(f"Hardware status check failed: {e}")
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

        @self.app.route("/api/shift-summary")
        def api_shift_summary():
            """
            API endpoint for shift handoff summary

            Returns:
                JSON with shift summary information
            """
            try:
                summary = self._get_shift_summary()
                return jsonify(summary), 200

            except Exception as e:
                logger.error(f"API shift summary failed: {e}")
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

        @self.app.route("/insights")
        def insights():
            """Service insights and quality metrics page"""
            return render_template(
                "insights.html",
                session=self.config.session_id,
                device_id=self.config.device_id,
            )

        @self.app.route("/api/service-insights")
        def api_service_insights():
            """
            API endpoint for service quality insights

            Returns:
                JSON with SLIs, SLOs, and quality scores
            """
            try:
                insights_data = self._get_service_insights()
                return jsonify(insights_data), 200
            except Exception as e:
                logger.error(f"API service insights failed: {e}")
                return jsonify({"error": str(e)}), 500

    def _get_service_insights(self) -> dict:
        """
        Get service quality insights including SLIs and SLOs

        Returns:
            Dictionary with quality metrics
        """
        try:
            from .service_quality import ServiceQualityMetrics

            session_id = self.config.session_id
            quality = ServiceQualityMetrics(self.db.conn)

            # Configure based on service settings
            if self.svc:
                quality.configure(
                    target_wait_minutes=self.svc.get_wait_warning_minutes(),
                    target_throughput_per_hour=self.svc.get_people_per_hour()
                )

            # Calculate quality score
            quality_score = quality.calculate_quality_score(session_id)

            # Evaluate SLOs
            slos = quality.evaluate_slos(session_id)

            # Get SLIs
            slis = quality.calculate_slis(session_id)

            return {
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "quality_score": {
                    "overall": quality_score.overall,
                    "status": quality_score.status.value,
                    "components": quality_score.components,
                },
                "slos": slos,
                "slis": slis,
            }
        except ImportError:
            # Service quality module not available
            logger.warning("Service quality module not available")
            return {
                "session_id": self.config.session_id,
                "error": "Service quality metrics not available",
                "quality_score": {"overall": 0, "status": "unknown", "components": {}},
                "slos": {},
                "slis": {},
            }
        except Exception as e:
            logger.error(f"Error calculating service insights: {e}", exc_info=True)
            return {
                "session_id": self.config.session_id,
                "error": str(e),
                "quality_score": {"overall": 0, "status": "unknown", "components": {}},
                "slos": {},
                "slis": {},
            }

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

        # Get 3-stage metrics (if available)
        three_stage_metrics = self._calculate_3stage_metrics(limit=20)

        # Get operational metrics
        operational_metrics = self._get_operational_metrics()

        # Count people currently in service (if using 3-stage)
        in_service = self._get_current_in_service()

        # Recent completions with wait times
        recent_completions = self._get_recent_completions(limit=10)

        # Activity by hour (last 12 hours)
        hourly_activity = self._get_hourly_activity(hours=12)

        # Recent events feed
        recent_events = self._get_recent_events_feed(limit=15)

        # Queue details with time in service
        queue_details = self._get_queue_details()

        # Smart wait estimate
        smart_estimate = self._calculate_smart_wait_estimate()

        return {
            "device_id": self.config.device_id,
            "stage": self.config.stage,
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stats": {
                "today_events": today_events,
                "last_hour_events": last_hour_events,
                "in_queue": in_queue,
                "in_service": in_service,
                "completed_today": completed_today,
                "avg_wait_minutes": avg_wait,
                "throughput_per_hour": (
                    last_hour_events / 2 if last_hour_events > 0 else 0
                ),  # Rough estimate
                "longest_wait_current": operational_metrics["longest_wait_current"],
                "estimated_wait_new": operational_metrics["estimated_wait_new"],
                "smart_wait_estimate": smart_estimate,
                "service_uptime_minutes": operational_metrics["service_uptime_minutes"],
                "capacity_utilization": operational_metrics["capacity_utilization"],
                # 3-stage metrics
                "avg_queue_wait_minutes": three_stage_metrics["avg_queue_wait_minutes"],
                "avg_service_time_minutes": three_stage_metrics[
                    "avg_service_time_minutes"
                ],
                "avg_total_time_minutes": three_stage_metrics["avg_total_time_minutes"],
                "has_3stage_data": three_stage_metrics["has_3stage_data"],
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
        queue_mult = self.svc.get_queue_multiplier() if self.svc else 2
        default_wait = self.svc.get_default_wait_estimate() if self.svc else 20
        estimated_wait_new = (
            avg_wait + (in_queue * queue_mult) if avg_wait > 0 else default_wait
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
            WHERE q.stage = 'QUEUE_JOIN'
                AND e.stage = 'EXIT'
                AND q.session_id = ?
                AND e.timestamp > datetime('now', '-1 hour')
        """,
            (session_id,),
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
        queue_crit = self.svc.get_queue_critical_threshold() if self.svc else 20

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
                self.svc.get_alert_message("wait_warning", minutes=longest_wait)
                if self.svc
                else f"⏱️ Longest wait: {longest_wait} min"
            )
            alerts.append({"level": "warning", "message": message})
        if longest_wait > wait_crit:
            message = (
                self.svc.get_alert_message("wait_critical", minutes=longest_wait)
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
        capacity_crit = self.svc.get_capacity_critical_percent() if self.svc else 90
        if capacity_utilization > capacity_crit:
            alerts.append({"level": "info", "message": "⚡ Operating near capacity"})

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
            minutes_since_last = int((now - last_event_dt).total_seconds() / 60)

            inactivity_crit = (
                self.svc.get_service_inactivity_critical_minutes() if self.svc else 10
            )
            inactivity_warn = (
                self.svc.get_service_inactivity_warning_minutes() if self.svc else 5
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
            WHERE q.stage = 'QUEUE_JOIN'
                AND e.stage = 'EXIT'
                AND q.session_id = ?
                AND e.timestamp > datetime('now', '-1 hour')
        """,
            (session_id,),
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
        stuck_hours = self.svc.get_stuck_cards_threshold_hours() if self.svc else 2
        # Use SQLite concatenation to safely build time offset from parameter
        cursor = self.db.conn.execute(
            """
            SELECT COUNT(*) as count
            FROM events q
            LEFT JOIN events e
                ON q.token_id = e.token_id
                AND q.session_id = e.session_id
                AND e.stage = 'EXIT'
            WHERE q.stage = 'QUEUE_JOIN'
                AND q.session_id = ?
                AND e.id IS NULL
                AND q.timestamp < datetime('now', '-' || ? || ' hours')
        """,
            (session_id, str(stuck_hours)),
        )
        stuck_count = cursor.fetchone()["count"]
        if stuck_count > 0:
            alerts.append(
                {
                    "level": "warning",
                    "message": f"⚠️ {stuck_count} people in queue >{stuck_hours} hours - possible abandonments or missed exits",
                }
            )

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
                ensure_dir(backup_dir)
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
                AND e.stage = 'EXIT'
            WHERE q.stage = 'QUEUE_JOIN'
                AND q.session_id = ?
                AND e.id IS NULL
        """,
            (session_id,),
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
            WHERE q.stage = 'QUEUE_JOIN'
                AND e.stage = 'EXIT'
                AND q.session_id = ?
                AND date(e.timestamp) = date('now')
        """,
            (session_id,),
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

    def _get_shift_summary(self) -> dict:
        """
        Get shift handoff summary

        Returns:
            Dictionary with shift summary information
        """
        session_id = self.config.session_id
        now = datetime.now(timezone.utc)

        # Current queue state
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
        current_queue = cursor.fetchone()["count"]

        # Completed this shift (last 4 hours)
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
                AND e.timestamp > datetime('now', '-4 hours')
        """,
            (session_id,),
        )
        completed_shift = cursor.fetchone()["count"]

        # Average wait this shift
        cursor = self.db.conn.execute(
            """
            SELECT
                AVG((julianday(e.timestamp) - julianday(q.timestamp)) * 1440) as avg_wait
            FROM events q
            JOIN events e
                ON q.token_id = e.token_id
                AND q.session_id = e.session_id
            WHERE q.stage = 'QUEUE_JOIN'
                AND e.stage = 'EXIT'
                AND q.session_id = ?
                AND e.timestamp > datetime('now', '-4 hours')
        """,
            (session_id,),
        )
        row = cursor.fetchone()
        avg_wait_shift = int(row["avg_wait"]) if row["avg_wait"] else 0

        # Busiest hour this shift
        cursor = self.db.conn.execute(
            """
            SELECT
                strftime('%H:00', e.timestamp) as hour,
                COUNT(*) as count
            FROM events q
            JOIN events e
                ON q.token_id = e.token_id
                AND q.session_id = e.session_id
            WHERE q.stage = 'QUEUE_JOIN'
                AND e.stage = 'EXIT'
                AND q.session_id = ?
                AND e.timestamp > datetime('now', '-4 hours')
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 1
        """,
            (session_id,),
        )
        busiest = cursor.fetchone()
        busiest_hour = busiest["hour"] if busiest else "N/A"
        busiest_count = busiest["count"] if busiest else 0

        # Service uptime today
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
        first_event = None
        service_hours = 0
        if row and row["first_event"]:
            first_dt = datetime.fromisoformat(row["first_event"])
            service_hours = round((now - first_dt).total_seconds() / 3600, 1)

        # Longest current wait
        cursor = self.db.conn.execute(
            """
            SELECT MIN(q.timestamp) as earliest
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
        row = cursor.fetchone()
        longest_wait = 0
        if row and row["earliest"]:
            earliest_dt = datetime.fromisoformat(row["earliest"])
            longest_wait = int((now - earliest_dt).total_seconds() / 60)

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

    def _calculate_3stage_metrics(self, limit=20) -> dict:
        """
        Calculate separate metrics for 3-stage journey

        Stages:
        - QUEUE_JOIN: Person enters queue
        - SERVICE_START: Staff begins helping
        - EXIT: Service complete

        Returns:
            Dictionary with queue_wait_minutes, service_time_minutes, total_time_minutes
        """
        session_id = self.config.session_id

        try:
            # Get recent 3-stage completions
            cursor = self.db.conn.execute(
                """
                SELECT
                    q.token_id,
                    q.timestamp as queue_time,
                    s.timestamp as service_start_time,
                    e.timestamp as exit_time
                FROM events q
                LEFT JOIN events s
                    ON q.token_id = s.token_id
                    AND q.session_id = s.session_id
                    AND s.stage = 'SERVICE_START'
                LEFT JOIN events e
                    ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                    AND e.stage = 'EXIT'
                WHERE q.stage = 'QUEUE_JOIN'
                    AND q.session_id = ?
                    AND e.timestamp IS NOT NULL
                ORDER BY e.timestamp DESC
                LIMIT ?
            """,
                (session_id, limit),
            )

            journeys = cursor.fetchall()

            if not journeys:
                return {
                    "avg_queue_wait_minutes": 0,
                    "avg_service_time_minutes": 0,
                    "avg_total_time_minutes": 0,
                    "has_3stage_data": False,
                    "journeys_analyzed": 0,
                }

            queue_waits = []
            service_times = []
            total_times = []
            three_stage_count = 0

            for journey in journeys:
                queue_dt = datetime.fromisoformat(journey["queue_time"])
                exit_dt = datetime.fromisoformat(journey["exit_time"])

                # Calculate total time (always available)
                total_minutes = (exit_dt - queue_dt).total_seconds() / 60
                total_times.append(total_minutes)

                # If SERVICE_START exists, calculate separate metrics
                if journey["service_start_time"]:
                    service_start_dt = datetime.fromisoformat(
                        journey["service_start_time"]
                    )

                    queue_wait = (service_start_dt - queue_dt).total_seconds() / 60
                    service_time = (exit_dt - service_start_dt).total_seconds() / 60

                    # Only include if times are reasonable (positive and < 24 hours)
                    if 0 <= queue_wait < 1440 and 0 <= service_time < 1440:
                        queue_waits.append(queue_wait)
                        service_times.append(service_time)
                        three_stage_count += 1

            has_3stage = three_stage_count > 0

            return {
                "avg_queue_wait_minutes": (
                    int(sum(queue_waits) / len(queue_waits)) if queue_waits else 0
                ),
                "avg_service_time_minutes": (
                    int(sum(service_times) / len(service_times)) if service_times else 0
                ),
                "avg_total_time_minutes": (
                    int(sum(total_times) / len(total_times)) if total_times else 0
                ),
                "has_3stage_data": has_3stage,
                "journeys_analyzed": len(journeys),
                "three_stage_count": three_stage_count,
            }

        except Exception as e:
            logger.warning(f"Failed to calculate 3-stage metrics: {e}")
            return {
                "avg_queue_wait_minutes": 0,
                "avg_service_time_minutes": 0,
                "avg_total_time_minutes": 0,
                "has_3stage_data": False,
                "journeys_analyzed": 0,
            }

    def _get_current_in_service(self) -> int:
        """
        Get count of people currently being served (between SERVICE_START and EXIT)

        Returns:
            Number of people currently in service
        """
        session_id = self.config.session_id

        try:
            cursor = self.db.conn.execute(
                """
                SELECT COUNT(DISTINCT s.token_id) as count
                FROM events s
                LEFT JOIN events e
                    ON s.token_id = e.token_id
                    AND s.session_id = e.session_id
                    AND e.stage = 'EXIT'
                WHERE s.stage = 'SERVICE_START'
                    AND s.session_id = ?
                    AND e.id IS NULL
            """,
                (session_id,),
            )

            return cursor.fetchone()["count"]

        except Exception as e:
            logger.warning(f"Failed to get in-service count: {e}")
            return 0

    def _get_stuck_cards(self) -> dict:
        """
        Get list of cards stuck in queue (>2 hours without exit)

        Returns:
            Dictionary with stuck cards and metadata
        """
        session_id = self.config.session_id
        now = datetime.now(timezone.utc)

        try:
            cursor = self.db.conn.execute(
                """
                SELECT
                    q.token_id,
                    q.timestamp as queue_time,
                    q.device_id
                FROM events q
                LEFT JOIN events e
                    ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                    AND e.stage = 'EXIT'
                WHERE q.stage = 'QUEUE_JOIN'
                    AND q.session_id = ?
                    AND e.id IS NULL
                    AND q.timestamp < datetime('now', '-2 hours')
                ORDER BY q.timestamp ASC
            """,
                (session_id,),
            )

            stuck_cards = []
            for row in cursor.fetchall():
                queue_dt = datetime.fromisoformat(row["queue_time"])
                hours_stuck = (now - queue_dt).total_seconds() / 3600

                stuck_cards.append(
                    {
                        "token_id": row["token_id"],
                        "queue_time": queue_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "hours_stuck": round(hours_stuck, 1),
                        "device_id": row["device_id"],
                    }
                )

            return {
                "stuck_cards": stuck_cards,
                "count": len(stuck_cards),
                "session_id": session_id,
                "timestamp": now.isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get stuck cards: {e}")
            return {"stuck_cards": [], "count": 0, "error": str(e)}

    def _force_exit_cards(self, token_ids: list) -> dict:
        """
        Force exit for stuck cards by inserting EXIT events

        Args:
            token_ids: List of token IDs to force exit

        Returns:
            Dictionary with success status and details
        """
        session_id = self.config.session_id
        now = datetime.now(timezone.utc)

        try:
            success_count = 0
            failed = []

            for token_id in token_ids:
                try:
                    # Insert EXIT event with special device_id to mark as forced
                    self.db.log_event(
                        token_id=token_id,
                        uid=f"FORCED_{token_id}",
                        stage="EXIT",
                        device_id="manual_force_exit",
                        session_id=session_id,
                        timestamp=now,
                    )
                    success_count += 1
                    logger.info(f"Force exited card: {token_id}")

                except Exception as e:
                    logger.error(f"Failed to force exit {token_id}: {e}")
                    failed.append({"token_id": token_id, "error": str(e)})

            return {
                "success": True,
                "processed": len(token_ids),
                "success_count": success_count,
                "failed_count": len(failed),
                "failed": failed,
                "message": f"Successfully force-exited {success_count} of {len(token_ids)} cards",
            }

        except Exception as e:
            logger.error(f"Force exit operation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "processed": 0,
                "success_count": 0,
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
                logger.warning(f"Could not parse timestamp for card {token_id}: {e}")
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

            # Determine status message
            status_map = {
                "QUEUE_JOIN": "In Queue",
                "SERVICE_START": "Being Served",
                "EXIT": "Completed",
            }
            status = status_map.get(current_stage, current_stage)

            # Calculate total time if completed
            total_time = None
            if current_stage == "EXIT" and len(events) > 1:
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

    def _calculate_smart_wait_estimate(self) -> dict:
        """
        Calculate smart wait time estimate using recent completion rates

        Returns:
            Dictionary with estimate, confidence, and reasoning
        """
        session_id = self.config.session_id
        now = datetime.now(timezone.utc)

        try:
            # Get current queue length
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
            queue_length = cursor.fetchone()["count"]

            # Calculate recent completion rate (last 30 minutes)
            cursor = self.db.conn.execute(
                """
                SELECT COUNT(*) as completions,
                       MIN(e.timestamp) as first_completion
                FROM events q
                JOIN events e
                    ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                WHERE q.stage = 'QUEUE_JOIN'
                    AND e.stage = 'EXIT'
                    AND q.session_id = ?
                    AND e.timestamp > datetime('now', '-30 minutes')
            """,
                (session_id,),
            )

            recent_data = cursor.fetchone()
            recent_completions = recent_data["completions"]

            # Calculate average service time from recent completions
            cursor = self.db.conn.execute(
                """
                SELECT 
                    AVG((julianday(e.timestamp) - julianday(q.timestamp)) * 1440) as avg_time
                FROM events q
                JOIN events e
                    ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                WHERE q.stage = 'QUEUE_JOIN'
                    AND e.stage = 'EXIT'
                    AND q.session_id = ?
                    AND e.timestamp > datetime('now', '-30 minutes')
            """,
                (session_id,),
            )

            avg_service_time = cursor.fetchone()["avg_time"] or 0

            # Determine confidence based on sample size
            if recent_completions >= 5:
                confidence = "high"
                confidence_icon = "✓"
            elif recent_completions >= 2:
                confidence = "medium"
                confidence_icon = "~"
            else:
                confidence = "low"
                confidence_icon = "?"

            # Calculate smart estimate
            if recent_completions > 0 and avg_service_time > 0:
                # Use recent completion rate
                minutes_per_person = avg_service_time
                estimated_wait = int(queue_length * minutes_per_person)
                method = "recent_rate"
                reasoning = f"Based on {recent_completions} recent completions (~{int(avg_service_time)} min/person)"
            else:
                # Fall back to overall average
                wait_sample_size = (
                    self.svc.get_wait_time_sample_size() if self.svc else 20
                )
                overall_avg = self._calculate_avg_wait_time(limit=wait_sample_size)
                queue_mult = self.svc.get_queue_multiplier() if self.svc else 2
                default_wait = self.svc.get_default_wait_estimate() if self.svc else 20
                if overall_avg > 0:
                    estimated_wait = overall_avg + (queue_length * queue_mult)
                    method = "overall_avg"
                    reasoning = f"Using overall average ({queue_length} in queue)"
                else:
                    # No data, use default estimate
                    estimated_wait = default_wait if queue_length > 0 else 0
                    method = "default"
                    reasoning = "Insufficient data for accurate estimate"
                    confidence = "low"
                    confidence_icon = "?"

            # Cap estimate at reasonable maximum
            if estimated_wait > 120:
                estimated_wait = 120
                reasoning += " (capped at 2 hours)"

            return {
                "estimate_minutes": estimated_wait,
                "confidence": confidence,
                "confidence_icon": confidence_icon,
                "method": method,
                "reasoning": reasoning,
                "queue_length": queue_length,
                "recent_completions": recent_completions,
                "avg_service_time": (
                    round(avg_service_time, 1) if avg_service_time else 0
                ),
            }

        except Exception as e:
            logger.error(f"Smart wait estimate failed: {e}")
            # Return fallback
            return {
                "estimate_minutes": 20,
                "confidence": "low",
                "confidence_icon": "?",
                "method": "error",
                "reasoning": "Error calculating estimate",
                "queue_length": 0,
                "recent_completions": 0,
                "avg_service_time": 0,
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

    def _get_hardware_status(self) -> dict:
        """Get status of hardware components"""
        import os
        import subprocess

        status = {"timestamp": datetime.now(timezone.utc).isoformat(), "components": {}}

        # I2C Status
        try:
            i2c_exists = os.path.exists("/dev/i2c-1") or os.path.exists("/dev/i2c-0")
            status["components"]["i2c"] = {
                "status": "ok" if i2c_exists else "error",
                "message": "I2C bus available" if i2c_exists else "I2C not found",
                "critical": True,
            }
        except:
            status["components"]["i2c"] = {
                "status": "unknown",
                "message": "Cannot check",
                "critical": True,
            }

        # GPIO/LEDs/Buzzer Status
        try:
            import RPi.GPIO as GPIO

            status["components"]["gpio"] = {
                "status": "ok",
                "message": f"GPIO available",
                "details": {
                    "buzzer": (
                        f"GPIO {self.config.gpio_buzzer}"
                        if self.config.buzzer_enabled
                        else "Disabled"
                    ),
                    "green_led": (
                        f"GPIO {self.config.gpio_led_green}"
                        if self.config.led_enabled
                        else "Disabled"
                    ),
                    "red_led": (
                        f"GPIO {self.config.gpio_led_red}"
                        if self.config.led_enabled
                        else "Disabled"
                    ),
                },
                "critical": False,
            }
        except ImportError:
            status["components"]["gpio"] = {
                "status": "warning",
                "message": "Not on Raspberry Pi",
                "critical": False,
            }
        except Exception as e:
            status["components"]["gpio"] = {
                "status": "error",
                "message": str(e),
                "critical": False,
            }

        # RTC Status
        try:
            if os.path.exists("/dev/rtc0") or os.path.exists("/dev/rtc1"):
                result = subprocess.run(
                    ["sudo", "hwclock", "-r"], capture_output=True, text=True, timeout=2
                )
                if result.returncode == 0:
                    status["components"]["rtc"] = {
                        "status": "ok",
                        "message": "RTC available",
                        "time": result.stdout.strip(),
                        "critical": False,
                    }
                else:
                    status["components"]["rtc"] = {
                        "status": "warning",
                        "message": "RTC not readable",
                        "critical": False,
                    }
            else:
                status["components"]["rtc"] = {
                    "status": "info",
                    "message": "No RTC detected (using system time)",
                    "critical": False,
                }
        except Exception as e:
            status["components"]["rtc"] = {
                "status": "info",
                "message": "RTC check unavailable",
                "critical": False,
            }

        # Temperature
        try:
            result = subprocess.run(
                ["vcgencmd", "measure_temp"], capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                temp_str = result.stdout.strip().split("=")[1].replace("'C", "")
                temp = float(temp_str)
                temp_status = (
                    "ok" if temp < 70 else ("warning" if temp < 80 else "error")
                )
                status["components"]["temperature"] = {
                    "status": temp_status,
                    "message": f"{temp}°C",
                    "value": temp,
                    "critical": temp >= 80,
                }
            else:
                status["components"]["temperature"] = {
                    "status": "unknown",
                    "message": "Cannot read temperature",
                    "critical": False,
                }
        except Exception:
            status["components"]["temperature"] = {
                "status": "unknown",
                "message": "Temperature unavailable",
                "critical": False,
            }

        # Under-voltage check
        try:
            result = subprocess.run(
                ["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                throttled = result.stdout.strip().split("=")[1]
                is_throttled = throttled != "0x0"
                status["components"]["power"] = {
                    "status": "error" if is_throttled else "ok",
                    "message": (
                        "Under-voltage detected!" if is_throttled else "Power OK"
                    ),
                    "throttled_hex": throttled,
                    "critical": is_throttled,
                }
            else:
                status["components"]["power"] = {
                    "status": "unknown",
                    "message": "Cannot check power",
                    "critical": False,
                }
        except Exception:
            status["components"]["power"] = {
                "status": "unknown",
                "message": "Power check unavailable",
                "critical": False,
            }

        # Disk space
        try:
            stat = os.statvfs("/")
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
            total_gb = (stat.f_blocks * stat.f_frsize) / (1024**3)
            percent_used = ((total_gb - free_gb) / total_gb) * 100

            disk_status = (
                "ok"
                if percent_used < 80
                else ("warning" if percent_used < 90 else "error")
            )
            status["components"]["disk"] = {
                "status": disk_status,
                "message": f"{free_gb:.1f} GB free of {total_gb:.1f} GB",
                "percent_used": round(percent_used, 1),
                "free_gb": round(free_gb, 1),
                "critical": percent_used >= 90,
            }
        except Exception:
            status["components"]["disk"] = {
                "status": "unknown",
                "message": "Disk info unavailable",
                "critical": False,
            }

        return status
    
    def _calculate_event_summary(self, session_id: str) -> dict:
        """
        Calculate comprehensive event summary statistics
        
        Args:
            session_id: Session ID for the event
            
        Returns:
            Dictionary with event summary data
        """
        from datetime import datetime
        
        now = datetime.now(timezone.utc)
        
        # Get all completed journeys
        cursor = self.db.conn.execute(
            """
            SELECT 
                j.token_id,
                j.timestamp as queue_time,
                e.timestamp as exit_time,
                s.timestamp as service_start_time,
                CAST((julianday(e.timestamp) - julianday(j.timestamp)) * 1440 AS INTEGER) as total_minutes,
                CAST((julianday(e.timestamp) - julianday(COALESCE(s.timestamp, j.timestamp))) * 1440 AS INTEGER) as service_minutes
            FROM events j
            JOIN events e ON j.token_id = e.token_id 
                        AND j.session_id = e.session_id
                        AND e.stage = 'EXIT'
            LEFT JOIN events s ON j.token_id = s.token_id
                             AND j.session_id = s.session_id
                             AND s.stage = 'SERVICE_START'
            WHERE j.stage = 'QUEUE_JOIN'
                AND j.session_id = ?
                AND datetime(e.timestamp) > datetime(j.timestamp)
            ORDER BY j.timestamp ASC
        """,
            (session_id,)
        )
        
        journeys = cursor.fetchall()
        total_served = len(journeys)
        
        # Calculate wait time statistics
        wait_times = [j["total_minutes"] for j in journeys if j["total_minutes"] > 0]
        service_times = [j["service_minutes"] for j in journeys if j["service_minutes"] and j["service_minutes"] > 0]
        
        avg_wait_min = int(sum(wait_times) / len(wait_times)) if wait_times else 0
        median_wait_min = int(sorted(wait_times)[len(wait_times) // 2]) if wait_times else 0
        avg_service_min = int(sum(service_times) / len(service_times)) if service_times else 0
        p90_service_min = int(sorted(service_times)[int(len(service_times) * 0.9)]) if len(service_times) > 10 else avg_service_min
        
        # Calculate peak queue
        cursor = self.db.conn.execute(
            """
            SELECT 
                datetime(timestamp) as time,
                (SELECT COUNT(DISTINCT q.token_id)
                 FROM events q
                 LEFT JOIN events e ON q.token_id = e.token_id
                                    AND q.session_id = e.session_id
                                    AND e.stage = 'EXIT'
                                    AND datetime(e.timestamp) <= datetime(events.timestamp)
                 WHERE q.stage = 'QUEUE_JOIN'
                   AND q.session_id = ?
                   AND datetime(q.timestamp) <= datetime(events.timestamp)
                   AND (e.id IS NULL OR datetime(e.timestamp) > datetime(events.timestamp))
                ) as queue_length
            FROM events
            WHERE session_id = ?
            ORDER BY queue_length DESC
            LIMIT 1
        """,
            (session_id, session_id)
        )
        
        peak_row = cursor.fetchone()
        peak_queue = peak_row["queue_length"] if peak_row else 0
        peak_time = peak_row["time"].split()[1][:5] if peak_row and peak_row["time"] else "N/A"
        
        # Calculate service hours and throughput
        cursor = self.db.conn.execute(
            "SELECT MIN(timestamp) as first_event, MAX(timestamp) as last_event FROM events WHERE session_id = ?",
            (session_id,)
        )
        time_row = cursor.fetchone()
        service_hours = 0
        if time_row and time_row["first_event"] and time_row["last_event"]:
            first_dt = datetime.fromisoformat(time_row["first_event"])
            last_dt = datetime.fromisoformat(time_row["last_event"])
            service_hours = round((last_dt - first_dt).total_seconds() / 3600, 1)
        
        throughput = int(total_served / service_hours) if service_hours > 0 else 0
        
        # Calculate abandonment rate
        cursor = self.db.conn.execute(
            """
            SELECT COUNT(DISTINCT q.token_id) as abandoned
            FROM events q
            LEFT JOIN events e ON q.token_id = e.token_id
                               AND q.session_id = e.session_id
                               AND e.stage = 'EXIT'
            WHERE q.stage = 'QUEUE_JOIN'
                AND q.session_id = ?
                AND e.id IS NULL
        """,
            (session_id,)
        )
        abandoned_count = cursor.fetchone()["abandoned"]
        total_joined = total_served + abandoned_count
        abandonment_rate = int((abandoned_count / total_joined) * 100) if total_joined > 0 else 0
        
        # Get anomalies summary
        anomalies = self.db.get_anomalies(session_id)
        anomalies_summary = {
            "total_anomalies": anomalies.get("summary", {}).get("total_anomalies", 0),
            "forgotten_exits": len(anomalies.get("forgotten_exit_taps", [])),
            "stuck_in_service": len(anomalies.get("stuck_in_service", [])),
            "rapid_fire_taps": len(anomalies.get("rapid_fire_taps", [])),
        }
        
        # Calculate busiest period (hour with most completions)
        cursor = self.db.conn.execute(
            """
            SELECT 
                strftime('%H:00', timestamp) as hour,
                COUNT(*) as count
            FROM events
            WHERE session_id = ? AND stage = 'EXIT'
            GROUP BY hour
            ORDER BY count DESC
            LIMIT 1
        """,
            (session_id,)
        )
        busiest_row = cursor.fetchone()
        busiest_period = busiest_row["hour"] if busiest_row else "N/A"
        busiest_count = busiest_row["count"] if busiest_row else 0
        
        # Quality assessment
        if avg_wait_min < 10:
            quality_assessment = "Excellent - average wait under 10 minutes"
        elif avg_wait_min < 20:
            quality_assessment = "Good - average wait under 20 minutes"
        elif avg_wait_min < 30:
            quality_assessment = "Fair - average wait 20-30 minutes"
        else:
            quality_assessment = "Needs improvement - average wait exceeds 30 minutes"
        
        # Capacity assessment
        if peak_queue < 10:
            capacity_assessment = "Well-managed - peak queue stayed under 10 people"
        elif peak_queue < 20:
            capacity_assessment = "Adequate - peak queue reached 10-20 people"
        else:
            capacity_assessment = f"Strained - peak queue reached {peak_queue} people, consider adding capacity"
        
        # Sample goals (in production, these would come from config or database)
        goals = [
            {
                "name": "Serve 150+ Participants",
                "target": 150,
                "actual": total_served,
                "unit": "people",
                "progress_percent": min(100, int((total_served / 150) * 100)),
                "status_class": "goal-achieved" if total_served >= 150 else ("goal-partial" if total_served >= 100 else "goal-missed"),
                "status_text": "✓ Achieved" if total_served >= 150 else (f"{int((total_served / 150) * 100)}% Complete" if total_served >= 100 else "Not Met"),
                "progress_class": "" if total_served >= 150 else ("warning" if total_served >= 100 else "danger")
            },
            {
                "name": "Average Wait <15 Minutes",
                "target": 15,
                "actual": avg_wait_min,
                "unit": "min avg",
                "progress_percent": min(100, int((15 / max(avg_wait_min, 1)) * 100)),
                "status_class": "goal-achieved" if avg_wait_min <= 15 else ("goal-partial" if avg_wait_min <= 25 else "goal-missed"),
                "status_text": "✓ Achieved" if avg_wait_min <= 15 else (f"{avg_wait_min} min" if avg_wait_min <= 25 else "Not Met"),
                "progress_class": "" if avg_wait_min <= 15 else ("warning" if avg_wait_min <= 25 else "danger")
            },
            {
                "name": "Abandonment Rate <10%",
                "target": 10,
                "actual": abandonment_rate,
                "unit": "%",
                "progress_percent": min(100, int((10 / max(abandonment_rate, 1)) * 100)) if abandonment_rate > 0 else 100,
                "status_class": "goal-achieved" if abandonment_rate <= 10 else ("goal-partial" if abandonment_rate <= 20 else "goal-missed"),
                "status_text": "✓ Achieved" if abandonment_rate <= 10 else (f"{abandonment_rate}%" if abandonment_rate <= 20 else "Not Met"),
                "progress_class": "" if abandonment_rate <= 10 else ("warning" if abandonment_rate <= 20 else "danger")
            }
        ]
        
        return {
            "session_id": session_id,
            "event_date": datetime.now().strftime("%B %d, %Y"),
            "total_served": total_served,
            "avg_wait_min": avg_wait_min,
            "median_wait_min": median_wait_min,
            "peak_queue": peak_queue,
            "peak_time": peak_time,
            "throughput": throughput,
            "service_hours": service_hours,
            "abandonment_rate": abandonment_rate,
            "abandoned_count": abandoned_count,
            "avg_service_min": avg_service_min,
            "p90_service_min": p90_service_min,
            "anomalies_summary": anomalies_summary,
            "goals": goals,
            "busiest_period": busiest_period,
            "busiest_count": busiest_count,
            "quality_assessment": quality_assessment,
            "capacity_assessment": capacity_assessment,
            "session_timeout_minutes": self.app.config.get('ADMIN_SESSION_TIMEOUT_MINUTES', 60)
        }


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
