"""
Service Configuration Loader for flowstate

This module loads and validates service-specific configuration from service_config.yaml,
allowing different festival drug checking services to customize their deployment.

The service configuration extends the base config.yaml with service-specific settings
like workflow stages, alert thresholds, UI labels, staffing models, etc.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class WorkflowStage:
    """Represents a single workflow stage"""

    id: str
    label: str
    description: str
    order: int
    required: bool = True
    visible_to_public: bool = True
    duration_estimate: int = 0
    icon: str = ""


@dataclass
class ServiceConfig:
    """Service configuration data structure"""

    # Service identity
    service_name: str = "Drug Checking Service"
    service_description: str = "Festival Community Drug Checking"
    service_type: str = "festival"
    organization: str = ""

    # Workflow
    workflow_stages: List[WorkflowStage] = field(default_factory=list)
    allow_skip_stages: bool = False
    allow_repeat_stages: bool = False
    enforce_stage_order: bool = True

    # Capacity
    people_per_hour: int = 12
    avg_service_minutes: int = 5
    default_wait_estimate: int = 20
    queue_multiplier: int = 2

    # Alert thresholds
    queue_warning_threshold: int = 10
    queue_critical_threshold: int = 20
    wait_warning_minutes: int = 45
    wait_critical_minutes: int = 90
    service_inactivity_warning_minutes: int = 5
    service_inactivity_critical_minutes: int = 10
    stuck_cards_threshold_hours: int = 2
    service_variance_multiplier: int = 3
    capacity_critical_percent: int = 90
    temperature_critical_celsius: int = 80
    disk_warning_percent: int = 80
    disk_critical_percent: int = 90
    unreturned_substance_warning_minutes: int = 15
    unreturned_substance_critical_minutes: int = 30

    # Alert messages
    alert_messages: Dict[str, str] = field(default_factory=dict)

    # UI labels
    ui_labels: Dict[str, str] = field(default_factory=dict)

    # Display settings
    public_refresh_interval: int = 5
    show_queue_positions: bool = True
    show_wait_estimates: bool = True
    show_served_count: bool = True
    show_avg_time: bool = True
    max_recent_events: int = 15
    max_recent_completions: int = 10
    analytics_history_hours: int = 12

    # Staffing
    roles: List[Dict[str, Any]] = field(default_factory=list)
    require_staff_id: bool = False

    # Locations
    multi_location: bool = False
    sites: List[Dict[str, Any]] = field(default_factory=list)
    shared_queue: bool = False

    # Metrics
    wait_time_sample_size: int = 20
    shift_summary_hours: int = 4

    # Raw config for accessing other fields
    _raw_config: Dict[str, Any] = field(default_factory=dict)

    def get_stage_by_id(self, stage_id: str) -> Optional[WorkflowStage]:
        """Get a workflow stage by its ID"""
        for stage in self.workflow_stages:
            if stage.id == stage_id:
                return stage
        return None

    def get_stage_label(self, stage_id: str) -> str:
        """Get the display label for a stage"""
        stage = self.get_stage_by_id(stage_id)
        return stage.label if stage else stage_id

    def get_stage_order(self, stage_id: str) -> int:
        """Get the order number for a stage"""
        stage = self.get_stage_by_id(stage_id)
        return stage.order if stage else 999

    def get_all_stage_ids(self) -> List[str]:
        """Get list of all stage IDs in order"""
        return [
            stage.id
            for stage in sorted(self.workflow_stages, key=lambda s: s.order)
        ]

    def get_public_stages(self) -> List[WorkflowStage]:
        """Get only stages that should be visible to the public"""
        return [s for s in self.workflow_stages if s.visible_to_public]

    def get_ui_label(self, key: str, default: str = None) -> str:
        """Get a UI label by key"""
        return self.ui_labels.get(key, default or key)

    def get_alert_message(self, key: str, **kwargs) -> str:
        """Get an alert message template and format it with kwargs"""
        template = self.alert_messages.get(key, "")
        try:
            return template.format(**kwargs)
        except KeyError:
            return template

    def get_raw(self, path: str, default: Any = None) -> Any:
        """
        Get a value from the raw config using dot notation
        Example: get_raw('integrations.webhooks.enabled')
        """
        keys = path.split(".")
        value = self._raw_config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value


class ServiceConfigLoader:
    """Loads and validates service configuration"""

    DEFAULT_CONFIG_PATH = Path(__file__).parent / "service_config.yaml"

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the config loader

        Args:
            config_path: Path to service_config.yaml (defaults to ./service_config.yaml)
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config: Optional[ServiceConfig] = None

    def load(self) -> ServiceConfig:
        """
        Load and parse the service configuration file

        Returns:
            ServiceConfig object with all configuration
        """
        if not self.config_path.exists():
            logger.warning(
                f"Service config not found at {self.config_path}, using defaults"
            )
            return self._create_default_config()

        try:
            with open(self.config_path, "r") as f:
                raw_config = yaml.safe_load(f)

            if not raw_config:
                logger.warning("Service config is empty, using defaults")
                return self._create_default_config()

            config = self._parse_config(raw_config)
            self.config = config

            logger.info(
                f"Loaded service configuration for: {config.service_name}"
            )
            logger.info(f"  Workflow stages: {len(config.workflow_stages)}")
            logger.info(f"  Stage IDs: {config.get_all_stage_ids()}")

            return config

        except yaml.YAMLError as e:
            logger.error(f"Error parsing service config: {e}")
            return self._create_default_config()
        except Exception as e:
            logger.error(f"Unexpected error loading service config: {e}")
            return self._create_default_config()

    def _parse_config(self, raw: Dict[str, Any]) -> ServiceConfig:
        """Parse raw YAML into ServiceConfig object"""

        config = ServiceConfig()
        config._raw_config = raw

        # Parse service identity
        if "service" in raw:
            service = raw["service"]
            config.service_name = service.get("name", config.service_name)
            config.service_description = service.get(
                "description", config.service_description
            )
            config.service_type = service.get("type", config.service_type)
            config.organization = service.get(
                "organization", config.organization
            )

        # Parse workflow stages
        if "workflow" in raw:
            workflow = raw["workflow"]

            # Load standard stages
            if "stages" in workflow:
                config.workflow_stages = [
                    WorkflowStage(**stage) for stage in workflow["stages"]
                ]

            # Add custom stages if defined
            if "custom_stages" in workflow:
                custom_stages = [
                    WorkflowStage(**stage)
                    for stage in workflow["custom_stages"]
                ]
                config.workflow_stages.extend(custom_stages)

            # Sort stages by order
            config.workflow_stages.sort(key=lambda s: s.order)

            # Workflow behavior
            config.allow_skip_stages = workflow.get(
                "allow_skip_stages", config.allow_skip_stages
            )
            config.allow_repeat_stages = workflow.get(
                "allow_repeat_stages", config.allow_repeat_stages
            )
            config.enforce_stage_order = workflow.get(
                "enforce_stage_order", config.enforce_stage_order
            )

        # Parse capacity settings
        if "capacity" in raw:
            capacity = raw["capacity"]
            config.people_per_hour = capacity.get(
                "people_per_hour", config.people_per_hour
            )
            config.avg_service_minutes = capacity.get(
                "avg_service_minutes", config.avg_service_minutes
            )
            config.default_wait_estimate = capacity.get(
                "default_wait_estimate", config.default_wait_estimate
            )
            config.queue_multiplier = capacity.get(
                "queue_multiplier", config.queue_multiplier
            )

        # Parse alert thresholds
        if "alerts" in raw:
            alerts = raw["alerts"]

            if "queue" in alerts:
                config.queue_warning_threshold = alerts["queue"].get(
                    "warning_threshold", config.queue_warning_threshold
                )
                config.queue_critical_threshold = alerts["queue"].get(
                    "critical_threshold", config.queue_critical_threshold
                )

            if "wait_time" in alerts:
                config.wait_warning_minutes = alerts["wait_time"].get(
                    "warning_minutes", config.wait_warning_minutes
                )
                config.wait_critical_minutes = alerts["wait_time"].get(
                    "critical_minutes", config.wait_critical_minutes
                )

            if "service_inactivity" in alerts:
                config.service_inactivity_warning_minutes = alerts[
                    "service_inactivity"
                ].get(
                    "warning_minutes",
                    config.service_inactivity_warning_minutes,
                )
                config.service_inactivity_critical_minutes = alerts[
                    "service_inactivity"
                ].get(
                    "critical_minutes",
                    config.service_inactivity_critical_minutes,
                )

            if "stuck_cards" in alerts:
                config.stuck_cards_threshold_hours = alerts["stuck_cards"].get(
                    "threshold_hours", config.stuck_cards_threshold_hours
                )

            if "service_time_variance" in alerts:
                config.service_variance_multiplier = alerts[
                    "service_time_variance"
                ].get("multiplier", config.service_variance_multiplier)

            if "capacity_utilization" in alerts:
                config.capacity_critical_percent = alerts[
                    "capacity_utilization"
                ].get("critical_percent", config.capacity_critical_percent)

            if "system" in alerts:
                config.temperature_critical_celsius = alerts["system"].get(
                    "temperature_critical_celsius",
                    config.temperature_critical_celsius,
                )
                config.disk_warning_percent = alerts["system"].get(
                    "disk_usage_warning_percent", config.disk_warning_percent
                )
                config.disk_critical_percent = alerts["system"].get(
                    "disk_usage_critical_percent", config.disk_critical_percent
                )

            if "unreturned_substances" in alerts:
                config.unreturned_substance_warning_minutes = alerts[
                    "unreturned_substances"
                ].get(
                    "warning_minutes",
                    config.unreturned_substance_warning_minutes,
                )
                config.unreturned_substance_critical_minutes = alerts[
                    "unreturned_substances"
                ].get(
                    "critical_minutes",
                    config.unreturned_substance_critical_minutes,
                )

            # Alert messages
            if "messages" in alerts:
                config.alert_messages = alerts["messages"]

        # Parse UI labels
        if "ui" in raw:
            ui = raw["ui"]

            if "labels" in ui:
                config.ui_labels = ui["labels"]

            if "public_display" in ui:
                pd = ui["public_display"]
                config.show_queue_positions = pd.get(
                    "show_queue_positions", config.show_queue_positions
                )
                config.show_wait_estimates = pd.get(
                    "show_wait_estimates", config.show_wait_estimates
                )
                config.show_served_count = pd.get(
                    "show_served_count", config.show_served_count
                )
                config.show_avg_time = pd.get(
                    "show_avg_time", config.show_avg_time
                )
                config.public_refresh_interval = pd.get(
                    "refresh_interval_seconds", config.public_refresh_interval
                )

            if "dashboard" in ui:
                dash = ui["dashboard"]
                config.max_recent_events = dash.get(
                    "max_recent_events", config.max_recent_events
                )
                config.max_recent_completions = dash.get(
                    "max_recent_completions", config.max_recent_completions
                )
                config.analytics_history_hours = dash.get(
                    "analytics_history_hours", config.analytics_history_hours
                )

        # Parse staffing
        if "staffing" in raw:
            staffing = raw["staffing"]
            config.roles = staffing.get("roles", [])
            config.require_staff_id = staffing.get(
                "require_staff_id", config.require_staff_id
            )

        # Parse locations
        if "locations" in raw:
            locations = raw["locations"]
            config.multi_location = locations.get(
                "multi_location", config.multi_location
            )
            config.sites = locations.get("sites", [])
            config.shared_queue = locations.get(
                "shared_queue", config.shared_queue
            )

        # Parse metrics
        if "metrics" in raw:
            metrics = raw["metrics"]
            if "windows" in metrics:
                windows = metrics["windows"]
                config.wait_time_sample_size = windows.get(
                    "wait_time_sample_size", config.wait_time_sample_size
                )
                config.shift_summary_hours = windows.get(
                    "shift_summary_hours", config.shift_summary_hours
                )

        return config

    def _create_default_config(self) -> ServiceConfig:
        """Create a default configuration with standard workflow"""
        config = ServiceConfig()

        # Default workflow: QUEUE_JOIN -> SERVICE_START -> EXIT
        config.workflow_stages = [
            WorkflowStage(
                id="QUEUE_JOIN",
                label="Joined Queue",
                description="Participant joins the queue",
                order=1,
                required=True,
                visible_to_public=True,
                duration_estimate=0,
            ),
            WorkflowStage(
                id="SERVICE_START",
                label="Service Started",
                description="Service interaction begins",
                order=2,
                required=False,
                visible_to_public=True,
                duration_estimate=5,
            ),
            WorkflowStage(
                id="EXIT",
                label="Service Complete",
                description="Participant completes service",
                order=3,
                required=True,
                visible_to_public=True,
                duration_estimate=0,
            ),
        ]

        # Default UI labels
        config.ui_labels = {
            "queue_count": "people in queue",
            "wait_time": "estimated wait",
            "served_today": "served today",
            "avg_service_time": "avg service time",
            "service_status": "service status",
            "status_active": "ACTIVE",
            "status_idle": "IDLE",
            "status_stopped": "STOPPED",
        }

        # Default alert messages
        config.alert_messages = {
            "queue_warning": "Queue is getting long ({count} people)",
            "queue_critical": "Queue is very long ({count} people) - consider adding staff",
            "wait_warning": "Estimated wait time is high ({minutes} min)",
            "wait_critical": "Estimated wait time is very high ({minutes} min)",
            "inactivity_warning": "No service activity for {minutes} minutes",
            "inactivity_critical": "Service appears stopped - no activity for {minutes} minutes",
        }

        logger.info("Using default service configuration")

        return config


# Global service config instance
_service_config: Optional[ServiceConfig] = None


def load_service_config(config_path: Optional[Path] = None) -> ServiceConfig:
    """
    Load the service configuration (singleton pattern)

    Args:
        config_path: Optional path to service_config.yaml

    Returns:
        ServiceConfig object
    """
    global _service_config

    if _service_config is None:
        loader = ServiceConfigLoader(config_path)
        _service_config = loader.load()

    return _service_config


def get_service_config() -> ServiceConfig:
    """
    Get the current service configuration

    Returns:
        ServiceConfig object (loads if not already loaded)
    """
    global _service_config

    if _service_config is None:
        _service_config = load_service_config()

    return _service_config


def reload_service_config(config_path: Optional[Path] = None) -> ServiceConfig:
    """
    Force reload the service configuration

    Args:
        config_path: Optional path to service_config.yaml

    Returns:
        Newly loaded ServiceConfig object
    """
    global _service_config
    _service_config = None
    return load_service_config(config_path)


# Convenience functions for common operations
def get_stage_label(stage_id: str) -> str:
    """Get the display label for a stage ID"""
    return get_service_config().get_stage_label(stage_id)


def get_all_stage_ids() -> List[str]:
    """Get all stage IDs in order"""
    return get_service_config().get_all_stage_ids()


def get_ui_label(key: str, default: str = None) -> str:
    """Get a UI label by key"""
    return get_service_config().get_ui_label(key, default)


def get_alert_message(key: str, **kwargs) -> str:
    """Get a formatted alert message"""
    return get_service_config().get_alert_message(key, **kwargs)


if __name__ == "__main__":
    # Test the configuration loader
    logging.basicConfig(level=logging.INFO)

    config = load_service_config()

    print(f"\nService: {config.service_name}")
    print(f"Type: {config.service_type}")
    print(f"\nWorkflow stages ({len(config.workflow_stages)}):")
    for stage in config.workflow_stages:
        print(f"  {stage.order}. {stage.id} - {stage.label}")
        print(
            f"     Required: {stage.required}, Public: {stage.visible_to_public}, Duration: {stage.duration_estimate}min"
        )

    print(f"\nCapacity: {config.people_per_hour} people/hour")
    print(f"Avg service time: {config.avg_service_minutes} minutes")

    print(f"\nAlert thresholds:")
    print(f"  Queue warning: {config.queue_warning_threshold} people")
    print(f"  Queue critical: {config.queue_critical_threshold} people")
    print(f"  Wait warning: {config.wait_warning_minutes} minutes")
    print(f"  Wait critical: {config.wait_critical_minutes} minutes")

    print(f"\nUI Labels:")
    for key, value in config.ui_labels.items():
        print(f"  {key}: {value}")
