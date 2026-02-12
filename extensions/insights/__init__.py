"""Insights extension - service quality metrics and SLOs."""

import logging
from datetime import datetime, timezone

from flask import jsonify, render_template

from tap_station.extension import Extension

logger = logging.getLogger(__name__)


class InsightsExtension(Extension):
    """Service quality insights with SLIs and SLOs."""

    name = "insights"
    order = 50

    def on_api_routes(self, app, db, config):
        @app.route("/insights")
        def insights():
            """Service insights and quality metrics page."""
            return render_template(
                "insights.html",
                session=config.session_id,
                device_id=config.device_id,
            )

        @app.route("/api/service-insights")
        def api_service_insights():
            """API endpoint for service quality insights."""
            try:
                data = _get_service_insights(db, config)
                return jsonify(data), 200
            except Exception as e:
                logger.error("API service insights failed: %s", e)
                return jsonify({"error": str(e)}), 500

        def _get_service_insights(db, config):
            try:
                from extensions.insights.service_quality import ServiceQualityMetrics

                session_id = config.session_id
                quality = ServiceQualityMetrics(db.conn)

                # Configure from service integration
                try:
                    from tap_station.service_integration import (
                        get_service_integration,
                    )

                    svc = get_service_integration()
                    if svc:
                        quality.configure(
                            target_wait_minutes=svc.get_wait_warning_minutes(),
                            target_throughput_per_hour=svc.get_people_per_hour(),
                        )
                except ImportError:
                    pass

                quality_score = quality.calculate_quality_score(session_id)
                slos = quality.evaluate_slos(session_id)
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
                logger.warning("Service quality module not available")
                return {
                    "session_id": config.session_id,
                    "error": "Service quality metrics not available",
                    "quality_score": {
                        "overall": 0,
                        "status": "unknown",
                        "components": {},
                    },
                    "slos": {},
                    "slis": {},
                }
            except Exception as e:
                logger.error(
                    "Error calculating service insights: %s", e,
                    exc_info=True,
                )
                return {
                    "session_id": config.session_id,
                    "error": str(e),
                    "quality_score": {
                        "overall": 0,
                        "status": "unknown",
                        "components": {},
                    },
                    "slos": {},
                    "slis": {},
                }


extension = InsightsExtension()
