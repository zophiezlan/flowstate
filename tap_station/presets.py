"""
Service Delivery Configuration Presets

This module provides pre-configured service profiles for common deployment
scenarios. Presets enable quick setup while allowing full customization.

Available presets:
- Festival Drug Checking Service
- Pop-up Harm Reduction
- Fixed-Site Service
- Mobile/Outreach Service
- Training/Demo Mode

Presets configure:
- Workflow stages
- Capacity settings
- Alert thresholds
- UI labels
- Operational parameters
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy

logger = logging.getLogger(__name__)


class ServiceType(Enum):
    """Types of service deployments"""
    FESTIVAL = "festival"
    POPUP = "popup"
    FIXED_SITE = "fixed_site"
    MOBILE = "mobile"
    TRAINING = "training"
    CUSTOM = "custom"


@dataclass
class WorkflowStagePreset:
    """Preset configuration for a workflow stage"""
    id: str
    label: str
    description: str
    order: int
    required: bool = True
    visible_to_public: bool = True
    duration_estimate: int = 0
    icon: str = ""


@dataclass
class CapacityPreset:
    """Preset configuration for service capacity"""
    people_per_hour: int
    avg_service_minutes: int
    default_wait_estimate: int
    queue_multiplier: int
    peak_multiplier: float = 0.8
    off_peak_multiplier: float = 1.2


@dataclass
class AlertThresholdsPreset:
    """Preset configuration for alert thresholds"""
    queue_warning: int
    queue_critical: int
    wait_warning_minutes: int
    wait_critical_minutes: int
    inactivity_warning_minutes: int
    inactivity_critical_minutes: int
    stuck_cards_hours: int


@dataclass
class UILabelsPreset:
    """Preset configuration for UI labels"""
    service_name: str
    organization: str
    queue_count_label: str = "people in queue"
    wait_time_label: str = "estimated wait"
    served_today_label: str = "served today"
    service_status_active: str = "ACTIVE"
    service_status_idle: str = "IDLE"
    custom_labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class ServicePreset:
    """Complete service configuration preset"""
    id: str
    name: str
    description: str
    service_type: ServiceType
    workflow_stages: List[WorkflowStagePreset]
    capacity: CapacityPreset
    alerts: AlertThresholdsPreset
    ui_labels: UILabelsPreset
    features: Dict[str, bool] = field(default_factory=dict)
    custom_config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert preset to configuration dictionary"""
        return {
            "preset_id": self.id,
            "preset_name": self.name,
            "service": {
                "name": self.ui_labels.service_name,
                "type": self.service_type.value,
                "organization": self.ui_labels.organization,
            },
            "workflow": {
                "stages": [
                    {
                        "id": s.id,
                        "label": s.label,
                        "description": s.description,
                        "order": s.order,
                        "required": s.required,
                        "visible_to_public": s.visible_to_public,
                        "duration_estimate": s.duration_estimate,
                        "icon": s.icon,
                    }
                    for s in self.workflow_stages
                ]
            },
            "capacity": {
                "people_per_hour": self.capacity.people_per_hour,
                "avg_service_minutes": self.capacity.avg_service_minutes,
                "default_wait_estimate": self.capacity.default_wait_estimate,
                "queue_multiplier": self.capacity.queue_multiplier,
            },
            "alerts": {
                "queue": {
                    "warning_threshold": self.alerts.queue_warning,
                    "critical_threshold": self.alerts.queue_critical,
                },
                "wait_time": {
                    "warning_minutes": self.alerts.wait_warning_minutes,
                    "critical_minutes": self.alerts.wait_critical_minutes,
                },
                "service_inactivity": {
                    "warning_minutes": self.alerts.inactivity_warning_minutes,
                    "critical_minutes": self.alerts.inactivity_critical_minutes,
                },
                "stuck_cards": {
                    "threshold_hours": self.alerts.stuck_cards_hours,
                },
            },
            "ui": {
                "labels": {
                    "queue_count": self.ui_labels.queue_count_label,
                    "wait_time": self.ui_labels.wait_time_label,
                    "served_today": self.ui_labels.served_today_label,
                    "status_active": self.ui_labels.service_status_active,
                    "status_idle": self.ui_labels.service_status_idle,
                    **self.ui_labels.custom_labels,
                }
            },
            "features": self.features,
            **self.custom_config,
        }


# =============================================================================
# Built-in Presets
# =============================================================================

class Presets:
    """Collection of built-in service presets"""

    @staticmethod
    def festival_drug_checking() -> ServicePreset:
        """
        Festival Drug Checking Service preset.

        Full workflow with substance return tracking.
        High throughput, suitable for large festivals.
        """
        return ServicePreset(
            id="festival_drug_checking",
            name="Festival Drug Checking Service",
            description="Full-featured drug checking service for festivals with substance return tracking",
            service_type=ServiceType.FESTIVAL,
            workflow_stages=[
                WorkflowStagePreset(
                    id="QUEUE_JOIN",
                    label="Joined Queue",
                    description="Participant joins the queue",
                    order=1,
                    required=True,
                    visible_to_public=True,
                    icon="⏰"
                ),
                WorkflowStagePreset(
                    id="SERVICE_START",
                    label="Service Started",
                    description="Service interaction begins",
                    order=2,
                    required=False,
                    visible_to_public=True,
                    duration_estimate=5,
                    icon="🔬"
                ),
                WorkflowStagePreset(
                    id="SUBSTANCE_RETURNED",
                    label="Substance Returned",
                    description="Substance handed back to participant",
                    order=3,
                    required=False,
                    visible_to_public=True,
                    duration_estimate=1,
                    icon="🤝"
                ),
                WorkflowStagePreset(
                    id="EXIT",
                    label="Service Complete",
                    description="Participant completes service",
                    order=4,
                    required=True,
                    visible_to_public=True,
                    icon="✅"
                ),
            ],
            capacity=CapacityPreset(
                people_per_hour=12,
                avg_service_minutes=5,
                default_wait_estimate=20,
                queue_multiplier=2
            ),
            alerts=AlertThresholdsPreset(
                queue_warning=10,
                queue_critical=20,
                wait_warning_minutes=45,
                wait_critical_minutes=90,
                inactivity_warning_minutes=5,
                inactivity_critical_minutes=10,
                stuck_cards_hours=2
            ),
            ui_labels=UILabelsPreset(
                service_name="Drug Checking Service",
                organization="Harm Reduction Services",
                queue_count_label="people waiting",
                wait_time_label="estimated wait time"
            ),
            features={
                "show_queue_positions": True,
                "show_wait_estimates": True,
                "show_served_count": True,
                "substance_return_tracking": True,
                "auto_init_cards": True,
            }
        )

    @staticmethod
    def simple_queue() -> ServicePreset:
        """
        Simple Queue preset.

        Minimal two-stage workflow (join → exit).
        Best for quick deployments or simple services.
        """
        return ServicePreset(
            id="simple_queue",
            name="Simple Queue",
            description="Minimal queue tracking with join and exit only",
            service_type=ServiceType.POPUP,
            workflow_stages=[
                WorkflowStagePreset(
                    id="QUEUE_JOIN",
                    label="Joined",
                    description="Joined the queue",
                    order=1,
                    required=True,
                    visible_to_public=True,
                    icon="📝"
                ),
                WorkflowStagePreset(
                    id="EXIT",
                    label="Done",
                    description="Service complete",
                    order=2,
                    required=True,
                    visible_to_public=True,
                    icon="✅"
                ),
            ],
            capacity=CapacityPreset(
                people_per_hour=20,
                avg_service_minutes=3,
                default_wait_estimate=10,
                queue_multiplier=2
            ),
            alerts=AlertThresholdsPreset(
                queue_warning=15,
                queue_critical=30,
                wait_warning_minutes=30,
                wait_critical_minutes=60,
                inactivity_warning_minutes=10,
                inactivity_critical_minutes=20,
                stuck_cards_hours=1
            ),
            ui_labels=UILabelsPreset(
                service_name="Queue Service",
                organization="",
            ),
            features={
                "show_queue_positions": True,
                "show_wait_estimates": True,
                "show_served_count": True,
                "substance_return_tracking": False,
                "auto_init_cards": True,
            }
        )

    @staticmethod
    def standard_service() -> ServicePreset:
        """
        Standard Service preset.

        Three-stage workflow (join → service start → exit).
        Good balance of tracking detail and simplicity.
        """
        return ServicePreset(
            id="standard_service",
            name="Standard Service",
            description="Standard three-stage tracking for most services",
            service_type=ServiceType.FIXED_SITE,
            workflow_stages=[
                WorkflowStagePreset(
                    id="QUEUE_JOIN",
                    label="In Queue",
                    description="Waiting for service",
                    order=1,
                    required=True,
                    visible_to_public=True,
                    icon="⏳"
                ),
                WorkflowStagePreset(
                    id="SERVICE_START",
                    label="Being Served",
                    description="Service in progress",
                    order=2,
                    required=False,
                    visible_to_public=True,
                    duration_estimate=10,
                    icon="🔧"
                ),
                WorkflowStagePreset(
                    id="EXIT",
                    label="Completed",
                    description="Service finished",
                    order=3,
                    required=True,
                    visible_to_public=True,
                    icon="✅"
                ),
            ],
            capacity=CapacityPreset(
                people_per_hour=10,
                avg_service_minutes=6,
                default_wait_estimate=15,
                queue_multiplier=2
            ),
            alerts=AlertThresholdsPreset(
                queue_warning=8,
                queue_critical=15,
                wait_warning_minutes=30,
                wait_critical_minutes=60,
                inactivity_warning_minutes=10,
                inactivity_critical_minutes=15,
                stuck_cards_hours=2
            ),
            ui_labels=UILabelsPreset(
                service_name="Service Point",
                organization="",
            ),
            features={
                "show_queue_positions": True,
                "show_wait_estimates": True,
                "show_served_count": True,
                "substance_return_tracking": False,
                "auto_init_cards": True,
            }
        )

    @staticmethod
    def mobile_outreach() -> ServicePreset:
        """
        Mobile/Outreach Service preset.

        Simplified workflow for mobile operations.
        Lower capacity, higher flexibility.
        """
        return ServicePreset(
            id="mobile_outreach",
            name="Mobile Outreach",
            description="Simplified service for mobile and outreach operations",
            service_type=ServiceType.MOBILE,
            workflow_stages=[
                WorkflowStagePreset(
                    id="QUEUE_JOIN",
                    label="Engaged",
                    description="Started interaction",
                    order=1,
                    required=True,
                    visible_to_public=False,
                    icon="👋"
                ),
                WorkflowStagePreset(
                    id="EXIT",
                    label="Completed",
                    description="Interaction finished",
                    order=2,
                    required=True,
                    visible_to_public=False,
                    icon="✅"
                ),
            ],
            capacity=CapacityPreset(
                people_per_hour=6,
                avg_service_minutes=10,
                default_wait_estimate=5,
                queue_multiplier=3
            ),
            alerts=AlertThresholdsPreset(
                queue_warning=5,
                queue_critical=10,
                wait_warning_minutes=20,
                wait_critical_minutes=45,
                inactivity_warning_minutes=15,
                inactivity_critical_minutes=30,
                stuck_cards_hours=1
            ),
            ui_labels=UILabelsPreset(
                service_name="Outreach Service",
                organization="",
                queue_count_label="active engagements",
                served_today_label="completed today"
            ),
            features={
                "show_queue_positions": False,
                "show_wait_estimates": False,
                "show_served_count": True,
                "substance_return_tracking": False,
                "auto_init_cards": True,
            }
        )

    @staticmethod
    def training_demo() -> ServicePreset:
        """
        Training/Demo Mode preset.

        Full workflow with relaxed thresholds for training.
        """
        return ServicePreset(
            id="training_demo",
            name="Training / Demo Mode",
            description="Training and demonstration mode with relaxed thresholds",
            service_type=ServiceType.TRAINING,
            workflow_stages=[
                WorkflowStagePreset(
                    id="QUEUE_JOIN",
                    label="Join",
                    description="Demo: Join queue",
                    order=1,
                    required=True,
                    visible_to_public=True,
                    icon="1️⃣"
                ),
                WorkflowStagePreset(
                    id="SERVICE_START",
                    label="Start",
                    description="Demo: Start service",
                    order=2,
                    required=False,
                    visible_to_public=True,
                    duration_estimate=2,
                    icon="2️⃣"
                ),
                WorkflowStagePreset(
                    id="SUBSTANCE_RETURNED",
                    label="Return",
                    description="Demo: Substance returned",
                    order=3,
                    required=False,
                    visible_to_public=True,
                    icon="3️⃣"
                ),
                WorkflowStagePreset(
                    id="EXIT",
                    label="Exit",
                    description="Demo: Exit",
                    order=4,
                    required=True,
                    visible_to_public=True,
                    icon="4️⃣"
                ),
            ],
            capacity=CapacityPreset(
                people_per_hour=60,
                avg_service_minutes=1,
                default_wait_estimate=1,
                queue_multiplier=1
            ),
            alerts=AlertThresholdsPreset(
                queue_warning=100,
                queue_critical=200,
                wait_warning_minutes=60,
                wait_critical_minutes=120,
                inactivity_warning_minutes=60,
                inactivity_critical_minutes=120,
                stuck_cards_hours=24
            ),
            ui_labels=UILabelsPreset(
                service_name="Training Mode",
                organization="DEMO",
            ),
            features={
                "show_queue_positions": True,
                "show_wait_estimates": True,
                "show_served_count": True,
                "substance_return_tracking": True,
                "auto_init_cards": True,
                "training_mode": True,
            },
            custom_config={
                "demo_mode": True,
                "allow_duplicate_taps": True,
            }
        )

    @staticmethod
    def high_volume() -> ServicePreset:
        """
        High Volume Service preset.

        Optimized for high-throughput operations.
        """
        return ServicePreset(
            id="high_volume",
            name="High Volume Service",
            description="Optimized for high-throughput service delivery",
            service_type=ServiceType.FESTIVAL,
            workflow_stages=[
                WorkflowStagePreset(
                    id="QUEUE_JOIN",
                    label="Queued",
                    description="In queue",
                    order=1,
                    required=True,
                    visible_to_public=True,
                    icon="📋"
                ),
                WorkflowStagePreset(
                    id="SERVICE_START",
                    label="Serving",
                    description="Being served",
                    order=2,
                    required=False,
                    visible_to_public=True,
                    duration_estimate=3,
                    icon="⚡"
                ),
                WorkflowStagePreset(
                    id="EXIT",
                    label="Done",
                    description="Complete",
                    order=3,
                    required=True,
                    visible_to_public=True,
                    icon="✅"
                ),
            ],
            capacity=CapacityPreset(
                people_per_hour=30,
                avg_service_minutes=2,
                default_wait_estimate=10,
                queue_multiplier=1
            ),
            alerts=AlertThresholdsPreset(
                queue_warning=25,
                queue_critical=50,
                wait_warning_minutes=30,
                wait_critical_minutes=60,
                inactivity_warning_minutes=3,
                inactivity_critical_minutes=5,
                stuck_cards_hours=1
            ),
            ui_labels=UILabelsPreset(
                service_name="High Volume Service",
                organization="",
            ),
            features={
                "show_queue_positions": True,
                "show_wait_estimates": True,
                "show_served_count": True,
                "substance_return_tracking": False,
                "auto_init_cards": True,
            }
        )


class PresetManager:
    """
    Manages service configuration presets.

    Features:
    - Load built-in presets
    - Custom preset registration
    - Preset modification and inheritance
    - Export/import presets
    """

    def __init__(self):
        self._presets: Dict[str, ServicePreset] = {}
        self._load_builtins()

    def _load_builtins(self) -> None:
        """Load all built-in presets"""
        builtins = [
            Presets.festival_drug_checking(),
            Presets.simple_queue(),
            Presets.standard_service(),
            Presets.mobile_outreach(),
            Presets.training_demo(),
            Presets.high_volume(),
        ]

        for preset in builtins:
            self._presets[preset.id] = preset

        logger.info(f"Loaded {len(builtins)} built-in presets")

    def get_preset(self, preset_id: str) -> Optional[ServicePreset]:
        """Get a preset by ID"""
        return self._presets.get(preset_id)

    def list_presets(self) -> List[Dict[str, Any]]:
        """List all available presets"""
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "service_type": p.service_type.value,
                "stage_count": len(p.workflow_stages),
            }
            for p in self._presets.values()
        ]

    def register_preset(self, preset: ServicePreset) -> None:
        """Register a custom preset"""
        self._presets[preset.id] = preset
        logger.info(f"Registered preset: {preset.id}")

    def create_from_base(
        self,
        base_preset_id: str,
        new_id: str,
        name: str,
        modifications: Dict[str, Any]
    ) -> Optional[ServicePreset]:
        """
        Create a new preset by modifying an existing one.

        Args:
            base_preset_id: ID of preset to base on
            new_id: ID for the new preset
            name: Name for the new preset
            modifications: Dictionary of modifications to apply

        Returns:
            New preset or None if base not found
        """
        base = self._presets.get(base_preset_id)
        if not base:
            return None

        # Deep copy base preset
        new_preset = deepcopy(base)
        new_preset.id = new_id
        new_preset.name = name

        # Apply modifications
        if "capacity" in modifications:
            for key, value in modifications["capacity"].items():
                if hasattr(new_preset.capacity, key):
                    setattr(new_preset.capacity, key, value)

        if "alerts" in modifications:
            for key, value in modifications["alerts"].items():
                if hasattr(new_preset.alerts, key):
                    setattr(new_preset.alerts, key, value)

        if "ui_labels" in modifications:
            for key, value in modifications["ui_labels"].items():
                if hasattr(new_preset.ui_labels, key):
                    setattr(new_preset.ui_labels, key, value)

        if "features" in modifications:
            new_preset.features.update(modifications["features"])

        self._presets[new_id] = new_preset
        return new_preset

    def get_preset_config(self, preset_id: str) -> Optional[Dict[str, Any]]:
        """Get preset as configuration dictionary"""
        preset = self._presets.get(preset_id)
        if preset:
            return preset.to_dict()
        return None

    def recommend_preset(
        self,
        expected_daily_visitors: int,
        has_substance_return: bool,
        is_mobile: bool
    ) -> str:
        """
        Recommend a preset based on service characteristics.

        Args:
            expected_daily_visitors: Expected visitors per day
            has_substance_return: Whether to track substance returns
            is_mobile: Whether this is a mobile service

        Returns:
            Recommended preset ID
        """
        if is_mobile:
            return "mobile_outreach"

        if has_substance_return:
            return "festival_drug_checking"

        if expected_daily_visitors > 200:
            return "high_volume"

        if expected_daily_visitors < 50:
            return "simple_queue"

        return "standard_service"


# =============================================================================
# Global Instance
# =============================================================================

_preset_manager: Optional[PresetManager] = None


def get_preset_manager() -> PresetManager:
    """Get the global preset manager"""
    global _preset_manager
    if _preset_manager is None:
        _preset_manager = PresetManager()
    return _preset_manager


def get_preset(preset_id: str) -> Optional[ServicePreset]:
    """Convenience function to get a preset"""
    return get_preset_manager().get_preset(preset_id)


def list_presets() -> List[Dict[str, Any]]:
    """Convenience function to list presets"""
    return get_preset_manager().list_presets()
