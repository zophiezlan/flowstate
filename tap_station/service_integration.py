"""
Service Configuration Integration

This module provides a simplified integration layer for the service configuration
system. It wraps the service_config_loader and provides convenient access methods.

The integration layer ensures that:
1. Configuration is loaded once (singleton pattern)
2. Default values are always available
3. The interface is consistent and easy to use
"""

import sys
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Add parent directory to path to import service_config_loader
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

try:
    from service_config_loader import (
        get_service_config,
        ServiceConfig,
        WorkflowStage,
    )
    SERVICE_CONFIG_AVAILABLE = True
except ImportError:
    logger.warning("service_config_loader not available, using defaults")
    SERVICE_CONFIG_AVAILABLE = False
    ServiceConfig = None
    WorkflowStage = None


class ServiceIntegration:
    """
    Integration layer for service configuration.

    This class provides a clean interface to access service-specific settings
    while ensuring defaults are always available.
    """

    # Default values (used as fallbacks)
    _DEFAULT_STAGES = ["QUEUE_JOIN", "SERVICE_START", "EXIT"]
    _DEFAULT_LABELS = {
        "QUEUE_JOIN": "In Queue",
        "SERVICE_START": "Being Served",
        "EXIT": "Completed",
    }
    _DEFAULT_UI_LABELS = {
        "queue_count": "people in queue",
        "wait_time": "estimated wait",
        "served_today": "served today",
        "avg_service_time": "avg service time",
        "service_status": "service status",
        "status_active": "ACTIVE",
        "status_idle": "IDLE",
        "status_stopped": "STOPPED",
    }
    _DEFAULT_ALERT_MESSAGES = {
        "queue_warning": "Queue is getting long ({count} people)",
        "queue_critical": "Queue is very long ({count} people) - consider adding staff",
        "wait_warning": "Estimated wait time is high ({minutes} min)",
        "wait_critical": "Estimated wait time is very high ({minutes} min)",
        "inactivity_warning": "No service activity for {minutes} minutes",
        "inactivity_critical": "Service appears stopped - no activity for {minutes} minutes",
    }

    def __init__(self):
        """Initialize service integration"""
        self._config: Optional[ServiceConfig] = None
        self._load_config()

    def _load_config(self):
        """Load service configuration"""
        if SERVICE_CONFIG_AVAILABLE:
            try:
                self._config = get_service_config()
                logger.info(f"Service configuration loaded: {self._config.service_name}")
            except Exception as e:
                logger.error(f"Failed to load service config: {e}")
                self._config = None
        else:
            self._config = None

    @property
    def config(self) -> Optional[ServiceConfig]:
        """Access the underlying ServiceConfig object"""
        return self._config

    def has_config(self) -> bool:
        """Check if service configuration is loaded"""
        return self._config is not None

    # =========================================================================
    # Helper method for safe config access
    # =========================================================================

    def _get(self, attr: str, default: Any) -> Any:
        """
        Safely get an attribute from config with fallback.

        Args:
            attr: Attribute name on ServiceConfig
            default: Default value if config unavailable

        Returns:
            Config value or default
        """
        if self._config is not None:
            return getattr(self._config, attr, default)
        return default

    # =========================================================================
    # Stage Management
    # =========================================================================

    def get_first_stage(self) -> str:
        """Get the ID of the first stage in the workflow"""
        if self._config and self._config.workflow_stages:
            return self._config.workflow_stages[0].id
        return "QUEUE_JOIN"

    def get_last_stage(self) -> str:
        """Get the ID of the last stage in the workflow"""
        if self._config and self._config.workflow_stages:
            return self._config.workflow_stages[-1].id
        return "EXIT"

    def get_service_start_stage(self) -> Optional[str]:
        """Get the ID of the service start stage, if it exists"""
        if self._config:
            for stage in self._config.workflow_stages:
                if stage.id == "SERVICE_START":
                    return stage.id
            if len(self._config.workflow_stages) > 2:
                return self._config.workflow_stages[1].id
        return "SERVICE_START"

    def get_all_stage_ids(self) -> List[str]:
        """Get all stage IDs in workflow order"""
        if self._config:
            return self._config.get_all_stage_ids()
        return self._DEFAULT_STAGES.copy()

    def get_stage_label(self, stage_id: str) -> str:
        """Get human-readable label for a stage"""
        if self._config:
            return self._config.get_stage_label(stage_id)
        return self._DEFAULT_LABELS.get(stage_id, stage_id)

    def get_stage_labels_map(self) -> Dict[str, str]:
        """Get a mapping of stage IDs to display labels"""
        if self._config:
            return {stage.id: stage.label for stage in self._config.workflow_stages}
        return self._DEFAULT_LABELS.copy()

    def has_service_start_stage(self) -> bool:
        """Check if the workflow includes a service start stage"""
        if self._config:
            return len(self._config.workflow_stages) > 2
        return True

    # =========================================================================
    # Capacity & Throughput (using _get helper)
    # =========================================================================

    def get_people_per_hour(self) -> int:
        return self._get("people_per_hour", 12)

    def get_avg_service_minutes(self) -> int:
        return self._get("avg_service_minutes", 5)

    def get_default_wait_estimate(self) -> int:
        return self._get("default_wait_estimate", 20)

    def get_queue_multiplier(self) -> int:
        return self._get("queue_multiplier", 2)

    # =========================================================================
    # Alert Thresholds (using _get helper)
    # =========================================================================

    def get_queue_warning_threshold(self) -> int:
        return self._get("queue_warning_threshold", 10)

    def get_queue_critical_threshold(self) -> int:
        return self._get("queue_critical_threshold", 20)

    def get_wait_warning_minutes(self) -> int:
        return self._get("wait_warning_minutes", 45)

    def get_wait_critical_minutes(self) -> int:
        return self._get("wait_critical_minutes", 90)

    def get_service_inactivity_warning_minutes(self) -> int:
        return self._get("service_inactivity_warning_minutes", 5)

    def get_service_inactivity_critical_minutes(self) -> int:
        return self._get("service_inactivity_critical_minutes", 10)

    def get_stuck_cards_threshold_hours(self) -> int:
        return self._get("stuck_cards_threshold_hours", 2)

    def get_service_variance_multiplier(self) -> int:
        return self._get("service_variance_multiplier", 3)

    def get_capacity_critical_percent(self) -> int:
        return self._get("capacity_critical_percent", 90)

    def get_temperature_critical_celsius(self) -> int:
        return self._get("temperature_critical_celsius", 80)

    def get_disk_warning_percent(self) -> int:
        return self._get("disk_warning_percent", 80)

    def get_disk_critical_percent(self) -> int:
        return self._get("disk_critical_percent", 90)

    # =========================================================================
    # UI Labels & Messages
    # =========================================================================

    def get_service_name(self) -> str:
        return self._get("service_name", "Drug Checking Service")

    def get_ui_label(self, key: str, default: str = None) -> str:
        """Get a UI label by key"""
        if self._config:
            return self._config.get_ui_label(key, default)
        return self._DEFAULT_UI_LABELS.get(key, default or key)

    def get_alert_message(self, key: str, **kwargs) -> str:
        """Get a formatted alert message"""
        if self._config:
            return self._config.get_alert_message(key, **kwargs)

        template = self._DEFAULT_ALERT_MESSAGES.get(key, "")
        try:
            return template.format(**kwargs)
        except KeyError:
            return template

    # =========================================================================
    # Display Settings (using _get helper)
    # =========================================================================

    def get_public_refresh_interval(self) -> int:
        return self._get("public_refresh_interval", 5)

    def show_queue_positions(self) -> bool:
        return self._get("show_queue_positions", True)

    def show_wait_estimates(self) -> bool:
        return self._get("show_wait_estimates", True)

    def show_served_count(self) -> bool:
        return self._get("show_served_count", True)

    def show_avg_time(self) -> bool:
        return self._get("show_avg_time", True)

    def get_max_recent_events(self) -> int:
        return self._get("max_recent_events", 15)

    def get_max_recent_completions(self) -> int:
        return self._get("max_recent_completions", 10)

    def get_analytics_history_hours(self) -> int:
        return self._get("analytics_history_hours", 12)

    def get_wait_time_sample_size(self) -> int:
        return self._get("wait_time_sample_size", 20)

    def get_shift_summary_hours(self) -> int:
        return self._get("shift_summary_hours", 4)

    # =========================================================================
    # Raw Configuration Access
    # =========================================================================

    def get_raw_config(self, path: str, default: Any = None) -> Any:
        """Get a value from raw configuration using dot notation"""
        if self._config:
            return self._config.get_raw(path, default)
        return default


# =============================================================================
# Global Instance (Singleton)
# =============================================================================

_service_integration: Optional[ServiceIntegration] = None


def get_service_integration() -> ServiceIntegration:
    """Get the global service integration instance (singleton)"""
    global _service_integration
    if _service_integration is None:
        _service_integration = ServiceIntegration()
    return _service_integration


# =============================================================================
# Convenience Functions
# =============================================================================

def get_first_stage() -> str:
    """Get the first stage ID (typically QUEUE_JOIN)"""
    return get_service_integration().get_first_stage()


def get_last_stage() -> str:
    """Get the last stage ID (typically EXIT)"""
    return get_service_integration().get_last_stage()


def get_service_start_stage() -> Optional[str]:
    """Get the service start stage ID (if it exists)"""
    return get_service_integration().get_service_start_stage()


def get_stage_label(stage_id: str) -> str:
    """Get the display label for a stage"""
    return get_service_integration().get_stage_label(stage_id)


def get_ui_label(key: str, default: str = None) -> str:
    """Get a UI label by key"""
    return get_service_integration().get_ui_label(key, default)


if __name__ == "__main__":
    # Test the service integration
    logging.basicConfig(level=logging.INFO)

    integration = get_service_integration()

    print(f"\nService: {integration.get_service_name()}")
    print(f"\nWorkflow Stages:")
    print(f"  First: {integration.get_first_stage()} ({integration.get_stage_label(integration.get_first_stage())})")
    if integration.has_service_start_stage():
        svc_stage = integration.get_service_start_stage()
        print(f"  Service: {svc_stage} ({integration.get_stage_label(svc_stage)})")
    print(f"  Last: {integration.get_last_stage()} ({integration.get_stage_label(integration.get_last_stage())})")

    print(f"\nCapacity:")
    print(f"  {integration.get_people_per_hour()} people/hour")
    print(f"  {integration.get_avg_service_minutes()} min average")

    print(f"\nAlert Thresholds:")
    print(f"  Queue: {integration.get_queue_warning_threshold()} warn, {integration.get_queue_critical_threshold()} critical")
    print(f"  Wait: {integration.get_wait_warning_minutes()} warn, {integration.get_wait_critical_minutes()} critical min")
