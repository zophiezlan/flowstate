"""
Service Configuration Integration

This module provides a simplified integration layer for the service configuration
system. It wraps the service_config_loader and provides convenient access methods.

The integration layer ensures that:
1. Configuration is loaded once (singleton pattern)
2. Default values are always available
3. The interface is consistent and easy to use
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from .service_config_loader import (
        ServiceConfig,
        WorkflowStage,
        get_service_config,
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
    _DEFAULT_STAGES = ["QUEUE_JOIN", "SERVICE_START", "SUBSTANCE_RETURNED", "EXIT"]
    _DEFAULT_LABELS = {
        "QUEUE_JOIN": "In Queue",
        "SERVICE_START": "Being Served",
        "SUBSTANCE_RETURNED": "Substance Returned",
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
                logger.info(
                    "Service configuration loaded: %s", self._config.service_name
                )
            except Exception as e:
                logger.error("Failed to load service config: %s", e)
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
        """
        Get the ID of the service start stage, if it exists.

        Returns None if:
        - No config is loaded
        - The workflow doesn't include a SERVICE_START stage

        Note: This specifically looks for a stage named "SERVICE_START".
        Services with custom stage names should use get_intermediate_stages()
        or check their workflow configuration directly.
        """
        if self._config:
            for stage in self._config.workflow_stages:
                if stage.id == "SERVICE_START":
                    return stage.id
        return None  # Don't assume - return None if not found

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
            return {
                stage.id: stage.label for stage in self._config.workflow_stages
            }
        return self._DEFAULT_LABELS.copy()

    def has_service_start_stage(self) -> bool:
        """
        Check if the workflow includes a SERVICE_START stage.

        Returns False if no config is loaded - we don't assume any stages exist.
        """
        if self._config:
            return any(
                stage.id == "SERVICE_START" for stage in self._config.workflow_stages
            )
        return False  # Don't assume - no config means we don't know

    def has_substance_returned_stage(self) -> bool:
        """Check if the workflow includes a SUBSTANCE_RETURNED stage"""
        if self._config:
            return any(
                stage.id == "SUBSTANCE_RETURNED"
                for stage in self._config.workflow_stages
            )
        return False  # Not in default 3-stage workflow

    def get_substance_returned_stage(self) -> Optional[str]:
        """Get the ID of the substance returned stage, if it exists"""
        if self._config:
            for stage in self._config.workflow_stages:
                if stage.id == "SUBSTANCE_RETURNED":
                    return stage.id
        return None

    def has_stage(self, stage_id: str) -> bool:
        """Check if a specific stage exists in the workflow"""
        if self._config:
            return any(
                stage.id == stage_id for stage in self._config.workflow_stages
            )
        return stage_id in self._DEFAULT_STAGES

    def is_valid_stage(self, stage_id: str) -> bool:
        """Check if a stage ID is valid for this service configuration"""
        return self.has_stage(stage_id)

    def get_intermediate_stages(self) -> List[str]:
        """
        Get all stages between first and last (exclusive).

        For a workflow like: QUEUE_JOIN → SERVICE_START → SUBSTANCE_RETURNED → EXIT
        This returns: ["SERVICE_START", "SUBSTANCE_RETURNED"]

        For a 2-stage workflow: QUEUE_JOIN → EXIT
        This returns: []

        Useful for services with custom stage names that don't use
        standard names like SERVICE_START or SUBSTANCE_RETURNED.
        """
        if self._config and len(self._config.workflow_stages) > 2:
            return [
                stage.id for stage in self._config.workflow_stages[1:-1]
            ]
        return []

    def get_stage_count(self) -> int:
        """Get the number of stages in the workflow"""
        if self._config:
            return len(self._config.workflow_stages)
        return len(self._DEFAULT_STAGES)

    def is_multi_stage_workflow(self) -> bool:
        """
        Check if this workflow has more than entry and exit stages.

        Returns True for 3+ stage workflows (e.g., QUEUE_JOIN → SERVICE_START → EXIT)
        Returns False for 2-stage workflows (e.g., QUEUE_JOIN → EXIT)
        """
        return self.get_stage_count() > 2

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

    def get_unreturned_substance_warning_minutes(self) -> int:
        return self._get("unreturned_substance_warning_minutes", 15)

    def get_unreturned_substance_critical_minutes(self) -> int:
        return self._get("unreturned_substance_critical_minutes", 30)

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
