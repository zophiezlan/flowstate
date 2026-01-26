"""
Constants and Workflow Stage Definitions

This module provides a single source of truth for workflow stages and other
constants used throughout the application. By centralizing these definitions,
we eliminate hardcoded values and make it easier to modify workflows.
"""

from typing import Dict, List, Set, Optional
from dataclasses import dataclass
from enum import Enum


# =============================================================================
# Delivery Status (used by webhooks and integrations)
# =============================================================================

class DeliveryStatus(Enum):
    """Status of event delivery to external systems"""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    DROPPED = "dropped"


# =============================================================================
# Workflow Stage Constants
# =============================================================================

class WorkflowStages:
    """Standard workflow stage identifiers"""

    # Core stages (always present)
    QUEUE_JOIN = "QUEUE_JOIN"
    EXIT = "EXIT"

    # Optional intermediate stages
    SERVICE_START = "SERVICE_START"
    SUBSTANCE_RETURNED = "SUBSTANCE_RETURNED"

    # All standard stages in typical order
    ALL_STAGES = [QUEUE_JOIN, SERVICE_START, SUBSTANCE_RETURNED, EXIT]

    # Minimum required stages
    REQUIRED_STAGES = [QUEUE_JOIN, EXIT]

    # Terminal stages (no transitions allowed after these)
    TERMINAL_STAGES = {EXIT}

    @classmethod
    def is_terminal(cls, stage: str) -> bool:
        """Check if a stage is terminal (no further transitions allowed)"""
        return stage in cls.TERMINAL_STAGES

    @classmethod
    def normalize(cls, stage: str) -> str:
        """
        Normalize a stage name to standard format.

        Args:
            stage: Stage name (various formats)

        Returns:
            Normalized stage name (uppercase with underscores)
        """
        if not isinstance(stage, str):
            return "UNKNOWN"

        normalized = stage.strip()
        if not normalized:
            return "UNKNOWN"

        lowered = normalized.lower()

        # Handle common variations
        if lowered in {"join", "queue_join", "queue-join", "queue join"}:
            return cls.QUEUE_JOIN
        if lowered in {"exit", "queue_exit", "queue-exit", "queue exit"}:
            return cls.EXIT
        if lowered in {"service_start", "service-start", "service start", "start"}:
            return cls.SERVICE_START
        if lowered in {"substance_returned", "substance-returned", "returned"}:
            return cls.SUBSTANCE_RETURNED

        return normalized.upper()


# =============================================================================
# Workflow Transition Rules
# =============================================================================

@dataclass
class TransitionRule:
    """Defines a valid workflow transition"""
    from_stage: str
    to_stages: List[str]
    requires_previous: bool = True


class WorkflowTransitions:
    """
    Defines valid stage transitions in the workflow.

    This class provides a data-driven approach to sequence validation,
    replacing hardcoded transition logic in the database module.
    """

    # Default transition rules
    # Each stage maps to a list of valid next stages
    DEFAULT_TRANSITIONS: Dict[str, List[str]] = {
        WorkflowStages.QUEUE_JOIN: [
            WorkflowStages.SERVICE_START,
            WorkflowStages.SUBSTANCE_RETURNED,
            WorkflowStages.EXIT,
        ],
        WorkflowStages.SERVICE_START: [
            WorkflowStages.SUBSTANCE_RETURNED,
            WorkflowStages.EXIT,
        ],
        WorkflowStages.SUBSTANCE_RETURNED: [
            WorkflowStages.EXIT,
        ],
        # EXIT is terminal - no valid transitions
    }

    # Stages that can be the first tap (entry points)
    VALID_ENTRY_STAGES: Set[str] = {
        WorkflowStages.QUEUE_JOIN,
        WorkflowStages.SERVICE_START,  # Allows late entry
        WorkflowStages.EXIT,  # Allows exit-only tracking
    }

    def __init__(self, transitions: Optional[Dict[str, List[str]]] = None):
        """
        Initialize with custom transitions or defaults.

        Args:
            transitions: Custom transition rules (stage -> list of valid next stages)
        """
        self._transitions = transitions or self.DEFAULT_TRANSITIONS.copy()

    def is_valid_transition(self, from_stage: str, to_stage: str) -> bool:
        """
        Check if a transition from one stage to another is valid.

        Args:
            from_stage: Current stage
            to_stage: Proposed next stage

        Returns:
            True if transition is valid
        """
        if from_stage not in self._transitions:
            return False
        return to_stage in self._transitions[from_stage]

    def get_valid_next_stages(self, current_stage: str) -> List[str]:
        """
        Get list of valid next stages from current stage.

        Args:
            current_stage: Current workflow stage

        Returns:
            List of valid next stage IDs
        """
        return self._transitions.get(current_stage, [])

    def is_valid_entry(self, stage: str) -> bool:
        """
        Check if a stage can be the first tap for a card.

        Args:
            stage: Stage being tapped

        Returns:
            True if valid entry point
        """
        return stage in self.VALID_ENTRY_STAGES

    def validate_sequence(
        self, existing_stages: List[str], new_stage: str
    ) -> Dict[str, any]:
        """
        Validate if adding a new stage to an existing sequence is valid.

        Args:
            existing_stages: List of stages already recorded (in order)
            new_stage: Stage being added

        Returns:
            Dict with 'valid' (bool), 'reason' (str), and optional 'suggestion' (str)
        """
        # No existing stages - check if valid entry point
        if not existing_stages:
            if new_stage == WorkflowStages.EXIT:
                return {
                    "valid": True,
                    "reason": "Card tapped at EXIT without QUEUE_JOIN - possible missed entry tap",
                    "suggestion": "Verify participant actually used service",
                }
            elif new_stage == WorkflowStages.SERVICE_START:
                return {
                    "valid": True,
                    "reason": "Card tapped at SERVICE_START without QUEUE_JOIN - possible missed entry tap",
                    "suggestion": "Add QUEUE_JOIN event if needed",
                }
            return {"valid": True, "reason": "First tap for this card"}

        last_stage = existing_stages[-1]

        # Check if already exited
        if WorkflowStages.EXIT in existing_stages:
            return {
                "valid": False,
                "reason": "Card already exited - tapping again may indicate: reused card, or participant returned for second service",
                "suggestion": "Check if this is a new visit (should use new card/session)",
            }

        # Validate transition
        if self.is_valid_transition(last_stage, new_stage):
            return {"valid": True, "reason": "Valid transition"}

        # Invalid transition
        valid_next = self.get_valid_next_stages(last_stage)
        if valid_next:
            return {
                "valid": False,
                "reason": f"Invalid transition: {last_stage} -> {new_stage}. Expected one of: {', '.join(valid_next)}",
                "suggestion": "Participant may be at wrong station or using wrong card",
            }

        # Unknown last stage
        return {
            "valid": True,
            "reason": f"Unknown stage sequence: {last_stage} -> {new_stage}",
            "suggestion": "Check service configuration",
        }


# =============================================================================
# Stage Display Labels (defaults)
# =============================================================================

DEFAULT_STAGE_LABELS: Dict[str, str] = {
    WorkflowStages.QUEUE_JOIN: "In Queue",
    WorkflowStages.SERVICE_START: "Being Served",
    WorkflowStages.SUBSTANCE_RETURNED: "Substance Returned",
    WorkflowStages.EXIT: "Completed",
}


def get_stage_label(stage_id: str, labels: Optional[Dict[str, str]] = None) -> str:
    """
    Get display label for a stage.

    Args:
        stage_id: Stage identifier
        labels: Optional custom labels dict

    Returns:
        Human-readable label
    """
    if labels and stage_id in labels:
        return labels[stage_id]
    return DEFAULT_STAGE_LABELS.get(stage_id, stage_id)


# =============================================================================
# Database Constants
# =============================================================================

class DatabaseDefaults:
    """Default values for database operations"""

    GRACE_PERIOD_MINUTES = 5  # Minutes before considering a tap a true duplicate
    STUCK_THRESHOLD_MINUTES = 30  # Minutes before flagging as potentially stuck
    ANOMALY_HIGH_THRESHOLD_MINUTES = 120  # Minutes for high severity anomaly


# =============================================================================
# Feedback Constants
# =============================================================================

class FeedbackPatterns:
    """Default beep/LED patterns for feedback"""

    BEEP_SUCCESS = [0.1]
    BEEP_DUPLICATE = [0.1, 0.05, 0.1]
    BEEP_ERROR = [0.3]
    BEEP_STARTUP = [0.05, 0.05, 0.05]

    LED_FLASH_SHORT = 0.1
    LED_FLASH_MEDIUM = 0.2
    LED_FLASH_LONG = 0.3


# =============================================================================
# Time Units
# =============================================================================

class TimeUnits:
    """Standard time unit conversions"""

    SECONDS_PER_MINUTE = 60
    SECONDS_PER_HOUR = 3600
    SECONDS_PER_DAY = 86400

    MINUTES_PER_HOUR = 60
    MINUTES_PER_DAY = 1440

    HOURS_PER_DAY = 24

    # Common time windows in minutes
    WINDOW_5_MIN = 5
    WINDOW_15_MIN = 15
    WINDOW_30_MIN = 30
    WINDOW_1_HOUR = 60
    WINDOW_4_HOURS = 240
    WINDOW_12_HOURS = 720
    WINDOW_24_HOURS = 1440


# =============================================================================
# Storage Units
# =============================================================================

class StorageUnits:
    """Storage unit conversions"""

    BYTES_PER_KB = 1024
    BYTES_PER_MB = 1024 ** 2
    BYTES_PER_GB = 1024 ** 3

    KB_PER_MB = 1024
    MB_PER_GB = 1024


# =============================================================================
# Hardware Constants
# =============================================================================

class HardwareDefaults:
    """Default hardware-related values"""

    # I2C settings
    DEFAULT_I2C_BUS = 1
    DEFAULT_I2C_ADDRESS = 0x24

    # Temperature thresholds (Celsius)
    TEMP_WARNING = 70
    TEMP_CRITICAL = 80

    # Disk space thresholds (percent)
    DISK_WARNING_PERCENT = 80
    DISK_CRITICAL_PERCENT = 90

    # Raspberry Pi specific paths
    TEMP_PATH = "/sys/class/thermal/thermal_zone0/temp"
    THROTTLE_PATH = "/sys/devices/platform/soc/soc:firmware/get_throttled"


# =============================================================================
# API Constants
# =============================================================================

class APIDefaults:
    """Default API-related values"""

    MAX_EVENTS_PER_REQUEST = 1000
    MAX_TOKEN_ID_LENGTH = 100
    MAX_UID_LENGTH = 100
    MAX_STAGE_LENGTH = 50

    # Request timeout
    DEFAULT_TIMEOUT_SECONDS = 30


# =============================================================================
# Global Transitions Instance
# =============================================================================

# Default workflow transitions instance (can be overridden by service config)
_workflow_transitions: Optional[WorkflowTransitions] = None


def get_workflow_transitions() -> WorkflowTransitions:
    """Get the global workflow transitions instance."""
    global _workflow_transitions
    if _workflow_transitions is None:
        _workflow_transitions = WorkflowTransitions()
    return _workflow_transitions


def set_workflow_transitions(transitions: WorkflowTransitions) -> None:
    """Set a custom workflow transitions instance (e.g., from service config)."""
    global _workflow_transitions
    _workflow_transitions = transitions
