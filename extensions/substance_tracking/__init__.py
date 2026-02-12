"""Substance tracking extension - monitors substance return rates."""

import logging

from tap_station.extension import Extension, resolve_stage

logger = logging.getLogger(__name__)


class SubstanceTrackingExtension(Extension):
    """Track substance return rates for services that loan materials."""

    name = "substance_tracking"
    order = 45

    def on_startup(self, ctx):
        self._config = ctx["config"]
        self._db = ctx["db"]
        self._svc = None
        self._stage_exit = resolve_stage("EXIT")
        self._stage_service_start = resolve_stage("SERVICE_START")
        self._stage_substance_returned = None

        try:
            from tap_station.service_integration import get_service_integration

            self._svc = get_service_integration()
            if self._svc and self._svc.has_substance_returned_stage():
                self._stage_substance_returned = (
                    self._svc.get_substance_returned_stage()
                )
        except ImportError:
            pass

    def on_dashboard_stats(self, stats):
        """Add substance return tracking stats to dashboard."""
        substance_stats = self._get_substance_return_stats()
        stats["substance_return"] = substance_stats

    def _get_substance_return_stats(self):
        """Get substance return tracking statistics."""
        session_id = self._config.session_id

        if not self._svc or not self._stage_substance_returned:
            return {
                "enabled": False,
                "pending_returns": 0,
                "completed_returns": 0,
                "return_rate_percent": 0,
            }

        try:
            # People with SERVICE_START but no SUBSTANCE_RETURNED or EXIT
            cursor = self._db.conn.execute(
                """
                SELECT COUNT(DISTINCT s.token_id) as pending
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
                """,
                (
                    self._stage_substance_returned,
                    self._stage_exit,
                    self._stage_service_start,
                    session_id,
                ),
            )
            pending = cursor.fetchone()["pending"]

            # Completed substance returns
            cursor = self._db.conn.execute(
                """
                SELECT COUNT(DISTINCT token_id) as completed
                FROM events
                WHERE stage = ?
                    AND session_id = ?
                """,
                (self._stage_substance_returned, session_id),
            )
            completed = cursor.fetchone()["completed"]

            # Total service starts
            cursor = self._db.conn.execute(
                """
                SELECT COUNT(DISTINCT token_id) as total
                FROM events
                WHERE stage = ?
                    AND session_id = ?
                """,
                (self._stage_service_start, session_id),
            )
            total = cursor.fetchone()["total"]

            return_rate = int((completed / total * 100)) if total > 0 else 0

            return {
                "enabled": True,
                "pending_returns": pending,
                "completed_returns": completed,
                "total_served": total,
                "return_rate_percent": return_rate,
            }

        except Exception as e:
            logger.warning("Failed to get substance return stats: %s", e)
            return {
                "enabled": True,
                "pending_returns": 0,
                "completed_returns": 0,
                "return_rate_percent": 0,
            }


extension = SubstanceTrackingExtension()
