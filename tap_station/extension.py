"""Extension protocol for FlowState modules."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TapEvent:
    """Mutable event passed through on_tap hooks.

    Extensions may modify token_id, stage, or add to extra.
    Core reads back the (possibly modified) values before logging.
    """

    uid: str
    token_id: str
    stage: str
    device_id: str
    session_id: str
    extra: Dict[str, Any] = field(default_factory=dict)


class Extension:
    """Base class for FlowState extensions.

    Override only the hooks you need. All have safe no-op defaults.
    """

    name: str = "unnamed"
    order: int = 50  # Lower runs first. auto_init=10, failover=20.

    def on_startup(self, ctx: dict) -> None:
        """Called once at startup. ctx has 'db', 'config', 'nfc', 'app'."""
        pass

    def on_shutdown(self) -> None:
        """Called on graceful shutdown."""
        pass

    def on_tap(self, event: TapEvent) -> None:
        """Called after NFC read, before log_event(). May mutate event."""
        pass

    def on_dashboard_stats(self, stats: dict) -> None:
        """Called after core assembles base stats. May add keys."""
        pass

    def on_api_routes(self, app, db, config) -> None:
        """Called once at startup. Register additional Flask routes."""
        pass


def resolve_stage(fallback: str) -> Optional[str]:
    """Resolve a stage name from service integration, or return fallback.

    Used by extensions to get the configured stage ID for EXIT,
    QUEUE_JOIN, SERVICE_START, etc. Returns None for SERVICE_START
    if not configured.

    Args:
        fallback: Stage name to resolve (e.g. "EXIT", "QUEUE_JOIN",
                  "SERVICE_START")

    Returns:
        Resolved stage ID string, or None for optional stages
    """
    try:
        from tap_station.service_integration import get_service_integration

        svc = get_service_integration()
        if svc:
            if fallback == "EXIT":
                return svc.get_last_stage()
            elif fallback == "QUEUE_JOIN":
                return svc.get_first_stage()
            elif fallback == "SERVICE_START":
                return svc.get_service_start_stage()
    except ImportError:
        pass
    if fallback == "SERVICE_START":
        return None
    return fallback
