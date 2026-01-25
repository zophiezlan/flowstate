"""
Custom Workflow Validators

This module provides a framework for defining custom validation rules
per workflow stage. Validators can enforce business rules, data quality
requirements, and operational constraints.

Key Features:
- Per-stage validation rules
- Custom validator functions
- Configurable validation behavior
- Pre and post transition hooks
- Data enrichment during validation

Service Design Principles:
- Enforce service-specific rules
- Provide clear feedback on validation failures
- Support flexible business logic
- Enable data quality at the point of entry
"""

import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from .datetime_utils import utc_now

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation results"""
    INFO = "info"          # Informational, doesn't block
    WARNING = "warning"    # Warning but allows proceed
    ERROR = "error"        # Blocks the operation
    CRITICAL = "critical"  # Critical block, may need admin


class ValidationAction(Enum):
    """Actions that can trigger validation"""
    TRANSITION = "transition"      # Moving between stages
    ENTRY = "entry"               # First tap (entering workflow)
    EXIT = "exit"                 # Final tap (completing workflow)
    MANUAL_ENTRY = "manual_entry" # Manual data entry
    CORRECTION = "correction"     # Correcting previous entry
    DELETION = "deletion"         # Deleting an event


@dataclass
class ValidationResult:
    """Result of a validation check"""
    valid: bool
    severity: ValidationSeverity
    message: str
    code: str
    suggestion: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    validator_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "valid": self.valid,
            "severity": self.severity.value,
            "message": self.message,
            "code": self.code,
            "suggestion": self.suggestion,
            "data": self.data,
            "validator_id": self.validator_id
        }


@dataclass
class ValidationContext:
    """Context provided to validators"""
    action: ValidationAction
    stage: str
    token_id: str
    session_id: str
    previous_stage: Optional[str]
    timestamp: datetime
    event_data: Dict[str, Any]
    journey_history: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)


class StageValidator(ABC):
    """Abstract base class for stage validators"""

    def __init__(
        self,
        validator_id: str,
        name: str,
        description: str,
        stages: Optional[List[str]] = None,
        actions: Optional[List[ValidationAction]] = None,
        enabled: bool = True,
        severity: ValidationSeverity = ValidationSeverity.ERROR
    ):
        """
        Initialize the validator.

        Args:
            validator_id: Unique identifier
            name: Human-readable name
            description: What this validator checks
            stages: Stages this validator applies to (None = all)
            actions: Actions this validator applies to (None = all)
            enabled: Whether validator is active
            severity: Default severity for failures
        """
        self.validator_id = validator_id
        self.name = name
        self.description = description
        self.stages = stages
        self.actions = actions
        self.enabled = enabled
        self.severity = severity

    def applies_to(self, context: ValidationContext) -> bool:
        """Check if this validator applies to the given context"""
        if not self.enabled:
            return False

        if self.stages and context.stage not in self.stages:
            return False

        if self.actions and context.action not in self.actions:
            return False

        return True

    @abstractmethod
    def validate(self, context: ValidationContext) -> ValidationResult:
        """
        Perform validation.

        Args:
            context: Validation context

        Returns:
            Validation result
        """
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "validator_id": self.validator_id,
            "name": self.name,
            "description": self.description,
            "stages": self.stages,
            "actions": [a.value for a in self.actions] if self.actions else None,
            "enabled": self.enabled,
            "severity": self.severity.value
        }


# =============================================================================
# Built-in Validators
# =============================================================================

class MinimumWaitTimeValidator(StageValidator):
    """Validates that minimum wait time has elapsed"""

    def __init__(
        self,
        min_wait_seconds: int = 30,
        stages: Optional[List[str]] = None
    ):
        super().__init__(
            validator_id="min_wait_time",
            name="Minimum Wait Time",
            description=f"Ensures at least {min_wait_seconds}s between stages",
            stages=stages or ["SERVICE_START", "EXIT"],
            actions=[ValidationAction.TRANSITION],
            severity=ValidationSeverity.WARNING
        )
        self.min_wait_seconds = min_wait_seconds

    def validate(self, context: ValidationContext) -> ValidationResult:
        if not context.journey_history:
            return ValidationResult(
                valid=True,
                severity=ValidationSeverity.INFO,
                message="No prior history",
                code="MWT001",
                validator_id=self.validator_id
            )

        last_event = context.journey_history[-1]
        last_time = datetime.fromisoformat(last_event.get("timestamp", ""))
        elapsed = (context.timestamp - last_time).total_seconds()

        if elapsed < self.min_wait_seconds:
            return ValidationResult(
                valid=False,
                severity=self.severity,
                message=f"Only {elapsed:.0f}s since last stage (minimum: {self.min_wait_seconds}s)",
                code="MWT002",
                suggestion="This may indicate accidental double tap",
                data={"elapsed_seconds": elapsed, "minimum_seconds": self.min_wait_seconds},
                validator_id=self.validator_id
            )

        return ValidationResult(
            valid=True,
            severity=ValidationSeverity.INFO,
            message="Wait time validated",
            code="MWT003",
            validator_id=self.validator_id
        )


class MaximumWaitTimeValidator(StageValidator):
    """Validates that maximum wait time hasn't been exceeded"""

    def __init__(
        self,
        max_wait_minutes: int = 180,
        stages: Optional[List[str]] = None
    ):
        super().__init__(
            validator_id="max_wait_time",
            name="Maximum Wait Time",
            description=f"Warns if more than {max_wait_minutes}min since queue join",
            stages=stages or ["SERVICE_START", "EXIT"],
            actions=[ValidationAction.TRANSITION],
            severity=ValidationSeverity.WARNING
        )
        self.max_wait_minutes = max_wait_minutes

    def validate(self, context: ValidationContext) -> ValidationResult:
        # Find queue join event
        queue_join = next(
            (e for e in context.journey_history if e.get("stage") == "QUEUE_JOIN"),
            None
        )

        if not queue_join:
            return ValidationResult(
                valid=True,
                severity=ValidationSeverity.INFO,
                message="No queue join found",
                code="MAXW001",
                validator_id=self.validator_id
            )

        join_time = datetime.fromisoformat(queue_join.get("timestamp", ""))
        elapsed = (context.timestamp - join_time).total_seconds() / 60

        if elapsed > self.max_wait_minutes:
            return ValidationResult(
                valid=True,  # Valid but warning
                severity=ValidationSeverity.WARNING,
                message=f"Long wait time detected: {elapsed:.0f} minutes",
                code="MAXW002",
                suggestion="Consider checking if this is the correct token",
                data={"elapsed_minutes": elapsed, "threshold_minutes": self.max_wait_minutes},
                validator_id=self.validator_id
            )

        return ValidationResult(
            valid=True,
            severity=ValidationSeverity.INFO,
            message="Wait time within limits",
            code="MAXW003",
            validator_id=self.validator_id
        )


class DuplicateStageValidator(StageValidator):
    """Validates that a stage isn't being repeated"""

    def __init__(
        self,
        allow_repeat_after_minutes: int = 60,
        stages: Optional[List[str]] = None
    ):
        super().__init__(
            validator_id="duplicate_stage",
            name="Duplicate Stage Check",
            description="Prevents duplicate stage entries",
            stages=stages,
            actions=[ValidationAction.TRANSITION, ValidationAction.ENTRY],
            severity=ValidationSeverity.WARNING
        )
        self.allow_after_minutes = allow_repeat_after_minutes

    def validate(self, context: ValidationContext) -> ValidationResult:
        # Check if this stage already exists in history
        for event in context.journey_history:
            if event.get("stage") == context.stage:
                event_time = datetime.fromisoformat(event.get("timestamp", ""))
                elapsed = (context.timestamp - event_time).total_seconds() / 60

                if elapsed < self.allow_after_minutes:
                    return ValidationResult(
                        valid=False,
                        severity=self.severity,
                        message=f"Stage {context.stage} already recorded {elapsed:.0f} minutes ago",
                        code="DUP001",
                        suggestion="This may be a duplicate tap - check token ID",
                        data={"existing_time": event_time.isoformat(), "elapsed_minutes": elapsed},
                        validator_id=self.validator_id
                    )

        return ValidationResult(
            valid=True,
            severity=ValidationSeverity.INFO,
            message="No duplicate detected",
            code="DUP002",
            validator_id=self.validator_id
        )


class QueueCapacityValidator(StageValidator):
    """Validates queue capacity limits"""

    def __init__(
        self,
        max_queue_size: int = 50,
        conn: Optional[sqlite3.Connection] = None
    ):
        super().__init__(
            validator_id="queue_capacity",
            name="Queue Capacity",
            description=f"Ensures queue doesn't exceed {max_queue_size} people",
            stages=["QUEUE_JOIN"],
            actions=[ValidationAction.ENTRY],
            severity=ValidationSeverity.WARNING
        )
        self.max_queue_size = max_queue_size
        self._conn = conn

    def validate(self, context: ValidationContext) -> ValidationResult:
        if not self._conn:
            return ValidationResult(
                valid=True,
                severity=ValidationSeverity.INFO,
                message="Capacity check skipped (no database)",
                code="CAP001",
                validator_id=self.validator_id
            )

        try:
            cursor = self._conn.execute("""
                SELECT COUNT(DISTINCT q.token_id) as queue_size
                FROM events q
                LEFT JOIN events e ON q.token_id = e.token_id
                    AND q.session_id = e.session_id
                    AND e.stage = 'EXIT'
                WHERE q.stage = 'QUEUE_JOIN'
                    AND q.session_id = ?
                    AND e.id IS NULL
            """, (context.session_id,))

            row = cursor.fetchone()
            queue_size = row["queue_size"] if row else 0

            if queue_size >= self.max_queue_size:
                return ValidationResult(
                    valid=False,
                    severity=self.severity,
                    message=f"Queue is at capacity ({queue_size}/{self.max_queue_size})",
                    code="CAP002",
                    suggestion="Consider directing to another service point",
                    data={"queue_size": queue_size, "max_size": self.max_queue_size},
                    validator_id=self.validator_id
                )

            return ValidationResult(
                valid=True,
                severity=ValidationSeverity.INFO,
                message=f"Queue capacity OK ({queue_size}/{self.max_queue_size})",
                code="CAP003",
                data={"queue_size": queue_size, "max_size": self.max_queue_size},
                validator_id=self.validator_id
            )

        except Exception as e:
            logger.error(f"Queue capacity check error: {e}")
            return ValidationResult(
                valid=True,
                severity=ValidationSeverity.INFO,
                message="Capacity check failed",
                code="CAP004",
                validator_id=self.validator_id
            )


class ServiceHoursValidator(StageValidator):
    """Validates operations are within service hours"""

    def __init__(
        self,
        start_hour: int = 10,
        end_hour: int = 23,
        allow_outside_hours: bool = True
    ):
        super().__init__(
            validator_id="service_hours",
            name="Service Hours",
            description=f"Checks if within service hours ({start_hour}:00-{end_hour}:00)",
            stages=["QUEUE_JOIN"],
            actions=[ValidationAction.ENTRY],
            severity=ValidationSeverity.WARNING if allow_outside_hours else ValidationSeverity.ERROR
        )
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.allow_outside = allow_outside_hours

    def validate(self, context: ValidationContext) -> ValidationResult:
        current_hour = context.timestamp.hour

        if self.start_hour <= current_hour < self.end_hour:
            return ValidationResult(
                valid=True,
                severity=ValidationSeverity.INFO,
                message="Within service hours",
                code="HRS001",
                validator_id=self.validator_id
            )

        return ValidationResult(
            valid=self.allow_outside,
            severity=self.severity,
            message=f"Outside service hours ({self.start_hour}:00-{self.end_hour}:00)",
            code="HRS002",
            suggestion="Confirm this entry is intentional",
            data={"current_hour": current_hour, "service_start": self.start_hour, "service_end": self.end_hour},
            validator_id=self.validator_id
        )


class ConcurrentServiceValidator(StageValidator):
    """Validates concurrent service limits"""

    def __init__(
        self,
        max_concurrent: int = 5,
        conn: Optional[sqlite3.Connection] = None
    ):
        super().__init__(
            validator_id="concurrent_service",
            name="Concurrent Service Limit",
            description=f"Ensures no more than {max_concurrent} people in service simultaneously",
            stages=["SERVICE_START"],
            actions=[ValidationAction.TRANSITION],
            severity=ValidationSeverity.WARNING
        )
        self.max_concurrent = max_concurrent
        self._conn = conn

    def validate(self, context: ValidationContext) -> ValidationResult:
        if not self._conn:
            return ValidationResult(
                valid=True,
                severity=ValidationSeverity.INFO,
                message="Concurrent check skipped (no database)",
                code="CONC001",
                validator_id=self.validator_id
            )

        try:
            cursor = self._conn.execute("""
                SELECT COUNT(DISTINCT s.token_id) as in_service
                FROM events s
                LEFT JOIN events e ON s.token_id = e.token_id
                    AND s.session_id = e.session_id
                    AND e.stage = 'EXIT'
                WHERE s.stage = 'SERVICE_START'
                    AND s.session_id = ?
                    AND e.id IS NULL
            """, (context.session_id,))

            row = cursor.fetchone()
            in_service = row["in_service"] if row else 0

            if in_service >= self.max_concurrent:
                return ValidationResult(
                    valid=False,
                    severity=self.severity,
                    message=f"Max concurrent services reached ({in_service}/{self.max_concurrent})",
                    code="CONC002",
                    suggestion="Wait for current services to complete",
                    data={"in_service": in_service, "max_concurrent": self.max_concurrent},
                    validator_id=self.validator_id
                )

            return ValidationResult(
                valid=True,
                severity=ValidationSeverity.INFO,
                message=f"Concurrent services OK ({in_service}/{self.max_concurrent})",
                code="CONC003",
                data={"in_service": in_service, "max_concurrent": self.max_concurrent},
                validator_id=self.validator_id
            )

        except Exception as e:
            logger.error(f"Concurrent service check error: {e}")
            return ValidationResult(
                valid=True,
                severity=ValidationSeverity.INFO,
                message="Concurrent check failed",
                code="CONC004",
                validator_id=self.validator_id
            )


class SubstanceReturnValidator(StageValidator):
    """Validates substance return before exit"""

    def __init__(self, require_return: bool = False):
        super().__init__(
            validator_id="substance_return",
            name="Substance Return Check",
            description="Checks if substance was returned before exit",
            stages=["EXIT"],
            actions=[ValidationAction.TRANSITION],
            severity=ValidationSeverity.WARNING if not require_return else ValidationSeverity.ERROR
        )
        self.require_return = require_return

    def validate(self, context: ValidationContext) -> ValidationResult:
        # Check if SERVICE_START exists (substance was taken)
        has_service = any(e.get("stage") == "SERVICE_START" for e in context.journey_history)
        has_return = any(e.get("stage") == "SUBSTANCE_RETURNED" for e in context.journey_history)

        if has_service and not has_return:
            return ValidationResult(
                valid=not self.require_return,
                severity=self.severity,
                message="Substance not marked as returned",
                code="SUB001",
                suggestion="Confirm substance was returned to participant",
                data={"service_started": has_service, "substance_returned": has_return},
                validator_id=self.validator_id
            )

        return ValidationResult(
            valid=True,
            severity=ValidationSeverity.INFO,
            message="Substance return check passed",
            code="SUB002",
            validator_id=self.validator_id
        )


# =============================================================================
# Custom Function Validator
# =============================================================================

class CustomFunctionValidator(StageValidator):
    """Validator that executes a custom function"""

    def __init__(
        self,
        validator_id: str,
        name: str,
        description: str,
        validate_func: Callable[[ValidationContext], ValidationResult],
        stages: Optional[List[str]] = None,
        actions: Optional[List[ValidationAction]] = None,
        severity: ValidationSeverity = ValidationSeverity.ERROR
    ):
        super().__init__(
            validator_id=validator_id,
            name=name,
            description=description,
            stages=stages,
            actions=actions,
            severity=severity
        )
        self._validate_func = validate_func

    def validate(self, context: ValidationContext) -> ValidationResult:
        try:
            return self._validate_func(context)
        except Exception as e:
            logger.error(f"Custom validator {self.validator_id} error: {e}")
            return ValidationResult(
                valid=True,
                severity=ValidationSeverity.INFO,
                message=f"Validation error: {str(e)}",
                code="CUSTOM_ERR",
                validator_id=self.validator_id
            )


# =============================================================================
# Workflow Validation Manager
# =============================================================================

class WorkflowValidationManager:
    """
    Manages workflow validators and orchestrates validation.

    This manager:
    - Registers and manages validators
    - Runs validators for workflow actions
    - Aggregates validation results
    - Provides validation hooks
    """

    def __init__(
        self,
        conn: Optional[sqlite3.Connection] = None,
        fail_on_error: bool = True,
        fail_on_warning: bool = False
    ):
        """
        Initialize the validation manager.

        Args:
            conn: Database connection for validators that need it
            fail_on_error: Block operations on ERROR severity
            fail_on_warning: Block operations on WARNING severity
        """
        self._conn = conn
        self._validators: Dict[str, StageValidator] = {}
        self._fail_on_error = fail_on_error
        self._fail_on_warning = fail_on_warning

        # Pre/post hooks
        self._pre_hooks: List[Callable[[ValidationContext], None]] = []
        self._post_hooks: List[Callable[[ValidationContext, List[ValidationResult]], None]] = []

        # Load default validators
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default validators"""
        self.register(MinimumWaitTimeValidator())
        self.register(MaximumWaitTimeValidator())
        self.register(DuplicateStageValidator())
        self.register(ServiceHoursValidator())

        if self._conn:
            self.register(QueueCapacityValidator(conn=self._conn))
            self.register(ConcurrentServiceValidator(conn=self._conn))

        self.register(SubstanceReturnValidator())

    def register(self, validator: StageValidator) -> None:
        """Register a validator"""
        self._validators[validator.validator_id] = validator
        logger.info(f"Registered validator: {validator.validator_id}")

    def unregister(self, validator_id: str) -> bool:
        """Unregister a validator"""
        if validator_id in self._validators:
            del self._validators[validator_id]
            return True
        return False

    def enable_validator(self, validator_id: str) -> bool:
        """Enable a validator"""
        if validator_id in self._validators:
            self._validators[validator_id].enabled = True
            return True
        return False

    def disable_validator(self, validator_id: str) -> bool:
        """Disable a validator"""
        if validator_id in self._validators:
            self._validators[validator_id].enabled = False
            return True
        return False

    def add_pre_hook(self, hook: Callable[[ValidationContext], None]) -> None:
        """Add a pre-validation hook"""
        self._pre_hooks.append(hook)

    def add_post_hook(
        self,
        hook: Callable[[ValidationContext, List[ValidationResult]], None]
    ) -> None:
        """Add a post-validation hook"""
        self._post_hooks.append(hook)

    def validate(
        self,
        action: ValidationAction,
        stage: str,
        token_id: str,
        session_id: str,
        previous_stage: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        event_data: Optional[Dict[str, Any]] = None,
        journey_history: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[ValidationResult]]:
        """
        Validate a workflow action.

        Args:
            action: The action being performed
            stage: Target stage
            token_id: Token/card ID
            session_id: Session ID
            previous_stage: Previous stage (for transitions)
            timestamp: Event timestamp
            event_data: Additional event data
            journey_history: History of events for this token
            metadata: Additional metadata

        Returns:
            Tuple of (overall_valid, list of results)
        """
        context = ValidationContext(
            action=action,
            stage=stage,
            token_id=token_id,
            session_id=session_id,
            previous_stage=previous_stage,
            timestamp=timestamp or utc_now(),
            event_data=event_data or {},
            journey_history=journey_history or [],
            metadata=metadata or {}
        )

        # Run pre-hooks
        for hook in self._pre_hooks:
            try:
                hook(context)
            except Exception as e:
                logger.error(f"Pre-validation hook error: {e}")

        # Run validators
        results = []
        for validator in self._validators.values():
            if validator.applies_to(context):
                try:
                    result = validator.validate(context)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Validator {validator.validator_id} error: {e}")
                    results.append(ValidationResult(
                        valid=True,
                        severity=ValidationSeverity.INFO,
                        message=f"Validation error: {str(e)}",
                        code="VAL_ERR",
                        validator_id=validator.validator_id
                    ))

        # Run post-hooks
        for hook in self._post_hooks:
            try:
                hook(context, results)
            except Exception as e:
                logger.error(f"Post-validation hook error: {e}")

        # Determine overall validity
        overall_valid = True
        for result in results:
            if not result.valid:
                if result.severity == ValidationSeverity.ERROR:
                    if self._fail_on_error:
                        overall_valid = False
                elif result.severity == ValidationSeverity.WARNING:
                    if self._fail_on_warning:
                        overall_valid = False
                elif result.severity == ValidationSeverity.CRITICAL:
                    overall_valid = False

        return overall_valid, results

    def list_validators(
        self,
        enabled_only: bool = False
    ) -> List[Dict[str, Any]]:
        """List all validators"""
        validators = self._validators.values()
        if enabled_only:
            validators = [v for v in validators if v.enabled]
        return [v.to_dict() for v in validators]

    def get_validator(self, validator_id: str) -> Optional[StageValidator]:
        """Get a validator by ID"""
        return self._validators.get(validator_id)


# =============================================================================
# Configuration Loading
# =============================================================================

def load_validators_from_config(
    config: Dict[str, Any],
    manager: WorkflowValidationManager
) -> int:
    """
    Load validator configurations from config dictionary.

    Args:
        config: Configuration with 'validators' key
        manager: Validation manager

    Returns:
        Number of validators configured
    """
    validator_configs = config.get("workflow", {}).get("validators", [])
    configured = 0

    for v_config in validator_configs:
        validator_id = v_config.get("id")
        if not validator_id:
            continue

        validator = manager.get_validator(validator_id)
        if validator:
            # Configure existing validator
            if "enabled" in v_config:
                validator.enabled = v_config["enabled"]
            if "severity" in v_config:
                try:
                    validator.severity = ValidationSeverity(v_config["severity"])
                except ValueError:
                    logger.warning(
                        "Invalid validation severity %r for validator %r; keeping existing severity.",
                        v_config.get("severity"),
                        validator_id,
                    )
            configured += 1

    return configured


# =============================================================================
# Global Instance
# =============================================================================

_validation_manager: Optional[WorkflowValidationManager] = None


def get_validation_manager(
    conn: Optional[sqlite3.Connection] = None
) -> WorkflowValidationManager:
    """Get or create the global validation manager"""
    global _validation_manager
    if _validation_manager is None:
        _validation_manager = WorkflowValidationManager(conn)
    return _validation_manager
