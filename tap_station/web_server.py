"""
Simple web server for health checks and participant status checking

Provides:
- /health endpoint for monitoring
- /check?token=XXX endpoint for participant status
- /api/status/<token> API endpoint
"""

import sys
import os
import logging
from flask import Flask, render_template, jsonify, request, send_from_directory
from datetime import datetime
import sqlite3

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

        @self.app.route('/health')
        def health_check():
            """
            Health check endpoint

            Returns:
                200 OK if service is running
            """
            try:
                # Check database is accessible
                count = self.db.get_event_count()

                return jsonify({
                    'status': 'ok',
                    'device_id': self.config.device_id,
                    'stage': self.config.stage,
                    'session': self.config.session_id,
                    'total_events': count,
                    'timestamp': datetime.now().isoformat()
                }), 200

            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return jsonify({
                    'status': 'error',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }), 500

        @self.app.route('/')
        def index():
            """Index page showing station info"""
            return render_template('index.html',
                                 device_id=self.config.device_id,
                                 stage=self.config.stage,
                                 session=self.config.session_id)

        @self.app.route('/check')
        def check_status():
            """
            Status check page for participants

            Query params:
                token: Token ID to check (e.g., "001")

            Returns:
                HTML page showing participant status
            """
            token_id = request.args.get('token')

            if not token_id:
                return render_template('error.html',
                                     error="No token ID provided"), 400

            # Get status from API
            try:
                status = self._get_token_status(token_id)
                return render_template('status.html',
                                     token_id=token_id,
                                     status=status,
                                     session=self.config.session_id)

            except Exception as e:
                logger.error(f"Status check failed for token {token_id}: {e}")
                return render_template('error.html',
                                     error=f"Error checking status: {e}"), 500

        @self.app.route('/api/status/<token_id>')
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
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/stats')
        def api_stats():
            """
            API endpoint for general statistics

            Returns:
                JSON with session statistics
            """
            try:
                stats = {
                    'device_id': self.config.device_id,
                    'stage': self.config.stage,
                    'session_id': self.config.session_id,
                    'total_events': self.db.get_event_count(self.config.session_id),
                    'recent_events': self.db.get_recent_events(10),
                    'timestamp': datetime.now().isoformat()
                }
                return jsonify(stats), 200

            except Exception as e:
                logger.error(f"API stats failed: {e}")
                return jsonify({'error': str(e)}), 500

    def _get_token_status(self, token_id: str) -> dict:
        """
        Get status for a token from database

        Args:
            token_id: Token ID

        Returns:
            Dictionary with token status
        """
        # Query database for all events for this token in this session
        cursor = self.db.conn.execute("""
            SELECT stage, timestamp, device_id
            FROM events
            WHERE token_id = ? AND session_id = ?
            ORDER BY timestamp
        """, (token_id, self.config.session_id))

        events = cursor.fetchall()

        # Parse events
        result = {
            'token_id': token_id,
            'session_id': self.config.session_id,
            'queue_join': None,
            'queue_join_time': None,
            'exit': None,
            'exit_time': None,
            'wait_time_minutes': None,
            'status': 'not_checked_in',
            'estimated_wait': self._estimate_wait_time()
        }

        for event in events:
            stage = event['stage']
            timestamp = event['timestamp']

            if stage == 'QUEUE_JOIN':
                result['queue_join'] = timestamp
                result['queue_join_time'] = self._format_time(timestamp)
                result['status'] = 'in_queue'

            elif stage == 'EXIT':
                result['exit'] = timestamp
                result['exit_time'] = self._format_time(timestamp)
                result['status'] = 'complete'

        # Calculate wait time if complete
        if result['queue_join'] and result['exit']:
            try:
                queue_time = datetime.fromisoformat(result['queue_join'])
                exit_time = datetime.fromisoformat(result['exit'])
                result['wait_time_minutes'] = int((exit_time - queue_time).total_seconds() / 60)
            except Exception as e:
                logger.warning(f"Failed to calculate wait time: {e}")

        return result

    def _format_time(self, timestamp: str) -> str:
        """Format timestamp for display"""
        try:
            dt = datetime.fromisoformat(timestamp)
            return dt.strftime('%I:%M %p')  # e.g., "02:15 PM"
        except:
            return timestamp

    def _estimate_wait_time(self) -> int:
        """
        Estimate current wait time based on recent completions

        Returns:
            Estimated wait time in minutes
        """
        try:
            # Get recent complete journeys (last 10)
            cursor = self.db.conn.execute("""
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
            """, (self.config.session_id,))

            journeys = cursor.fetchall()

            if not journeys:
                return 20  # Default estimate

            # Calculate average wait time
            total_wait = 0
            for journey in journeys:
                queue_dt = datetime.fromisoformat(journey['queue_time'])
                exit_dt = datetime.fromisoformat(journey['exit_time'])
                wait_minutes = (exit_dt - queue_dt).total_seconds() / 60
                total_wait += wait_minutes

            avg_wait = total_wait / len(journeys)
            return int(avg_wait)

        except Exception as e:
            logger.warning(f"Failed to estimate wait time: {e}")
            return 20  # Default fallback

    def run(self, host='0.0.0.0', port=8080):
        """
        Run the web server

        Args:
            host: Host to bind to
            port: Port to listen on
        """
        logger.info(f"Starting web server on {host}:{port}")
        self.app.run(host=host, port=port, debug=False)


def create_app(config_path='config.yaml'):
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
    db = Database(config.database_path, wal_mode=False)

    server = StatusWebServer(config, db)
    return server.app


# For running standalone
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Status Web Server')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        from tap_station.config import Config
        from tap_station.database import Database

        config = Config(args.config)
        db = Database(config.database_path, wal_mode=False)

        server = StatusWebServer(config, db)
        server.run(host=args.host, port=args.port)

    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
