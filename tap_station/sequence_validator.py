"""
Sequence Validation Engine

This module provides a comprehensive sequence validation system for workflow
stages. It enforces workflow rules, detects sequence violations, and provides
actionable suggestions for correction.

Features:
- Configurable workflow transitions
- Customizable validation rules
- Support for optional stages
- Grace periods and time-based validation
- Detailed violation reporting
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from .datetime_utils import utc_now, from_iso
from .constants import WorkflowStages

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """Represents a validation issue found during sequence checking"""
    severity: ValidationSeverity
    code: str
    message: str
    suggestion: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "suggestion": self.suggestion,
            "context": self.context
        }


@dataclass
class SequenceValidationResult:
    """Result of sequence validation"""
    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    corrected_sequence: Optional[List[str]] = None

    @property
    def has_errors(self) -> bool:
        """Check if there are any error-level issues"""
        return any(
            i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)
            for i in self.issues
        )

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warning-level issues"""
        return any(i.severity == ValidationSeverity.WARNING for i in self.issues)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "valid": self.valid,
            "issues": [i.to_dict() for i in self.issues],
            "suggestions": self.suggestions,
            "has_errors": self.has_errors,
            "has_warnings": self.has_warnings
        }


@dataclass
class StageDefinition:
    """Defines a workflow stage with its properties"""
    id: str
    label: str
    required: bool = True
    repeatable: bool = False
    order: int = 0
    min_duration_minutes: int = 0
    max_duration_minutes: int = 0  # 0 = no limit
    allowed_predecessors: Set[str] = field(default_factory=set)
    allowed_successors: Set[str] = field(default_factory=set)
    validators: List[Callable[[Dict], bool]] = field(default_factory=list)


class SequenceValidator:
    """
    Validates event sequences against workflow rules.

    This validator checks that events follow the correct sequence
    based on configurable workflow definitions and provides detailed
    feedback for corrections.
    """

    # Standard validation codes
    CODES = {
        "INVALID_ENTRY": "SEQ001",
        "INVALID_TRANSITION": "SEQ002",
        "REPEATED_STAGE": "SEQ003",
        "SKIPPED_REQUIRED": "SEQ004",
        "POST_TERMINAL": "SEQ005",
        "TIMING_VIOLATION": "SEQ006",
        "MISSING_EXIT": "SEQ007",
        "UNEXPECTED_STAGE": "SEQ008",
    }

    def __init__(
        self,
        stages: Optional[List[StageDefinition]] = None,
        allow_skip_optional: bool = True,
        allow_late_entry: bool = True,
        enforce_timing: bool = False
    ):
        """
        Initialize sequence validator.

        Args:
            stages: List of stage definitions (uses defaults if not provided)
            allow_skip_optional: Whether optional stages can be skipped
            allow_late_entry: Whether entry at non-first stages is allowed
            enforce_timing: Whether to enforce min/max duration rules
        """
        self._stages = self._build_stage_map(stages or self._default_stages())
        self._stage_order = {s.id: s.order for s in self._stages.values()}
        self._allow_skip_optional = allow_skip_optional
        self._allow_late_entry = allow_late_entry
        self._enforce_timing = enforce_timing
        self._terminal_stages: Set[str] = {WorkflowStages.EXIT}
        self._entry_stages: Set[str] = {WorkflowStages.QUEUE_JOIN, WorkflowStages.SERVICE_START}

    def _default_stages(self) -> List[StageDefinition]:
        """Get default stage definitions"""
        return [
            StageDefinition(
                id=WorkflowStages.QUEUE_JOIN,
                label="In Queue",
                required=True,
                order=1,
                allowed_successors={WorkflowStages.SERVICE_START, WorkflowStages.SUBSTANCE_RETURNED, WorkflowStages.EXIT}
            ),
            StageDefinition(
                id=WorkflowStages.SERVICE_START,
                label="Being Served",
                required=False,
                order=2,
                allowed_predecessors={WorkflowStages.QUEUE_JOIN},
                allowed_successors={WorkflowStages.SUBSTANCE_RETURNED, WorkflowStages.EXIT}
            ),
            StageDefinition(
                id=WorkflowStages.SUBSTANCE_RETURNED,
                label="Substance Returned",
                required=False,
                order=3,
                allowed_predecessors={WorkflowStages.QUEUE_JOIN, WorkflowStages.SERVICE_START},
                allowed_successors={WorkflowStages.EXIT}
            ),
            StageDefinition(
                id=WorkflowStages.EXIT,
                label="Completed",
                required=True,
                order=4,
                allowed_predecessors={WorkflowStages.QUEUE_JOIN, WorkflowStages.SERVICE_START, WorkflowStages.SUBSTANCE_RETURNED}
            ),
        ]

    def _build_stage_map(self, stages: List[StageDefinition]) -> Dict[str, StageDefinition]:
        """Build a map of stage ID to definition"""
        return {s.id: s for s in stages}

    def configure_stages(self, stages: List[StageDefinition]) -> None:
        """
        Reconfigure the validator with new stage definitions.

        Args:
            stages: New list of stage definitions
        """
        self._stages = self._build_stage_map(stages)
        self._stage_order = {s.id: s.order for s in self._stages.values()}
        logger.info(f"Sequence validator reconfigured with {len(stages)} stages")

    def set_terminal_stages(self, stages: Set[str]) -> None:
        """Set which stages are terminal (no transitions after)"""
        self._terminal_stages = stages

    def set_entry_stages(self, stages: Set[str]) -> None:
        """Set which stages are valid entry points"""
        self._entry_stages = stages

    def validate_transition(
        self,
        from_stage: Optional[str],
        to_stage: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SequenceValidationResult:
        """
        Validate a single stage transition.

        Args:
            from_stage: Previous stage (None for first tap)
            to_stage: Stage being transitioned to
            context: Optional context (timestamps, token_id, etc.)

        Returns:
            Validation result with any issues found
        """
        context = context or {}
        issues = []
        suggestions = []

        # Check if to_stage is known
        if to_stage not in self._stages:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code=self.CODES["UNEXPECTED_STAGE"],
                message=f"Unknown stage: {to_stage}",
                suggestion=f"Valid stages: {', '.join(self._stages.keys())}",
                context={"stage": to_stage}
            ))
            return SequenceValidationResult(valid=False, issues=issues)

        # First tap validation
        if from_stage is None:
            if to_stage not in self._entry_stages:
                if self._allow_late_entry:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        code=self.CODES["INVALID_ENTRY"],
                        message=f"First tap at {to_stage} instead of entry stage",
                        suggestion="Consider adding missed entry tap",
                        context={"stage": to_stage, "expected": list(self._entry_stages)}
                    ))
                else:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code=self.CODES["INVALID_ENTRY"],
                        message=f"Invalid entry point: {to_stage}",
                        suggestion=f"First tap must be at: {', '.join(self._entry_stages)}",
                        context={"stage": to_stage}
                    ))
                    return SequenceValidationResult(valid=False, issues=issues)

            return SequenceValidationResult(
                valid=True,
                issues=issues,
                suggestions=suggestions
            )

        # Check for post-terminal transition
        if from_stage in self._terminal_stages:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                code=self.CODES["POST_TERMINAL"],
                message=f"Cannot transition from terminal stage {from_stage}",
                suggestion="This may indicate a reused card or second visit",
                context={"from": from_stage, "to": to_stage}
            ))
            return SequenceValidationResult(valid=False, issues=issues)

        # Check if transition is allowed
        from_def = self._stages.get(from_stage)
        to_def = self._stages[to_stage]

        # Check predecessor/successor rules
        valid_transition = True
        if from_def and from_def.allowed_successors:
            if to_stage not in from_def.allowed_successors:
                valid_transition = False
        if to_def.allowed_predecessors:
            if from_stage not in to_def.allowed_predecessors:
                valid_transition = False

        if not valid_transition:
            # Check if we're skipping optional stages
            if self._allow_skip_optional:
                skipped = self._get_skipped_stages(from_stage, to_stage)
                if all(not self._stages[s].required for s in skipped):
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.INFO,
                        code=self.CODES["SKIPPED_REQUIRED"],
                        message=f"Skipped optional stages: {', '.join(skipped)}",
                        context={"skipped": skipped}
                    ))
                else:
                    required_skipped = [s for s in skipped if self._stages[s].required]
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        code=self.CODES["SKIPPED_REQUIRED"],
                        message=f"Skipped required stages: {', '.join(required_skipped)}",
                        suggestion="Add missing stage taps if participant went through them",
                        context={"skipped": required_skipped}
                    ))
            else:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code=self.CODES["INVALID_TRANSITION"],
                    message=f"Invalid transition: {from_stage} -> {to_stage}",
                    suggestion=f"Expected next stages: {', '.join(from_def.allowed_successors if from_def else [])}",
                    context={"from": from_stage, "to": to_stage}
                ))
                return SequenceValidationResult(valid=False, issues=issues)

        # Timing validation
        if self._enforce_timing and context.get("from_timestamp") and context.get("to_timestamp"):
            timing_issues = self._validate_timing(
                from_stage, to_stage,
                context["from_timestamp"], context["to_timestamp"]
            )
            issues.extend(timing_issues)

        return SequenceValidationResult(
            valid=not any(i.severity == ValidationSeverity.ERROR for i in issues),
            issues=issues,
            suggestions=suggestions
        )

    def validate_sequence(
        self,
        stages: List[str],
        timestamps: Optional[List[datetime]] = None
    ) -> SequenceValidationResult:
        """
        Validate a complete sequence of stages.

        Args:
            stages: List of stage IDs in order
            timestamps: Optional list of corresponding timestamps

        Returns:
            Validation result with all issues found
        """
        all_issues = []
        all_suggestions = []

        if not stages:
            return SequenceValidationResult(valid=True)

        # Validate entry
        result = self.validate_transition(None, stages[0])
        all_issues.extend(result.issues)
        all_suggestions.extend(result.suggestions)

        # Validate each transition
        for i in range(1, len(stages)):
            context = {}
            if timestamps and len(timestamps) > i:
                context["from_timestamp"] = timestamps[i - 1]
                context["to_timestamp"] = timestamps[i]

            result = self.validate_transition(stages[i - 1], stages[i], context)
            all_issues.extend(result.issues)
            all_suggestions.extend(result.suggestions)

        # Check for repeated non-repeatable stages
        seen = set()
        for stage in stages:
            if stage in seen:
                stage_def = self._stages.get(stage)
                if stage_def and not stage_def.repeatable:
                    all_issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        code=self.CODES["REPEATED_STAGE"],
                        message=f"Stage {stage} appears multiple times",
                        suggestion="This may indicate accidental duplicate taps",
                        context={"stage": stage}
                    ))
            seen.add(stage)

        # Check if sequence ends properly
        if stages[-1] not in self._terminal_stages:
            all_issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                code=self.CODES["MISSING_EXIT"],
                message="Sequence does not end at a terminal stage",
                suggestion="Journey may be incomplete",
                context={"last_stage": stages[-1], "terminal_stages": list(self._terminal_stages)}
            ))

        valid = not any(i.severity == ValidationSeverity.ERROR for i in all_issues)
        return SequenceValidationResult(
            valid=valid,
            issues=all_issues,
            suggestions=all_suggestions
        )

    def suggest_next_stages(
        self,
        current_sequence: List[str]
    ) -> List[str]:
        """
        Suggest valid next stages based on current sequence.

        Args:
            current_sequence: List of stages completed so far

        Returns:
            List of valid next stage IDs
        """
        if not current_sequence:
            return list(self._entry_stages)

        last_stage = current_sequence[-1]

        # No transitions from terminal stages
        if last_stage in self._terminal_stages:
            return []

        stage_def = self._stages.get(last_stage)
        if not stage_def:
            return []

        if stage_def.allowed_successors:
            return list(stage_def.allowed_successors)

        # Fall back to all stages with higher order
        current_order = self._stage_order.get(last_stage, 0)
        return [
            s_id for s_id, order in self._stage_order.items()
            if order > current_order
        ]

    def _get_skipped_stages(self, from_stage: str, to_stage: str) -> List[str]:
        """Get list of stages that would be skipped in a transition"""
        from_order = self._stage_order.get(from_stage, 0)
        to_order = self._stage_order.get(to_stage, 0)

        return [
            s_id for s_id, order in self._stage_order.items()
            if from_order < order < to_order
        ]

    def _validate_timing(
        self,
        from_stage: str,
        to_stage: str,
        from_time: datetime,
        to_time: datetime
    ) -> List[ValidationIssue]:
        """Validate timing between stages"""
        issues = []

        from_def = self._stages.get(from_stage)
        if not from_def:
            return issues

        duration = (to_time - from_time).total_seconds() / 60  # minutes

        if from_def.min_duration_minutes and duration < from_def.min_duration_minutes:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code=self.CODES["TIMING_VIOLATION"],
                message=f"Stage {from_stage} completed too quickly ({duration:.1f}min < {from_def.min_duration_minutes}min)",
                suggestion="This may indicate a data entry error or skipped process",
                context={
                    "stage": from_stage,
                    "duration": duration,
                    "minimum": from_def.min_duration_minutes
                }
            ))

        if from_def.max_duration_minutes and duration > from_def.max_duration_minutes:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                code=self.CODES["TIMING_VIOLATION"],
                message=f"Stage {from_stage} took unusually long ({duration:.1f}min > {from_def.max_duration_minutes}min)",
                suggestion="This may indicate a forgotten tap or extended service",
                context={
                    "stage": from_stage,
                    "duration": duration,
                    "maximum": from_def.max_duration_minutes
                }
            ))

        return issues


# =============================================================================
# Global Instance
# =============================================================================

_sequence_validator: Optional[SequenceValidator] = None


def get_sequence_validator() -> SequenceValidator:
    """Get the global sequence validator instance"""
    global _sequence_validator
    if _sequence_validator is None:
        _sequence_validator = SequenceValidator()
    return _sequence_validator


def configure_sequence_validator(
    stages: Optional[List[StageDefinition]] = None,
    **kwargs
) -> SequenceValidator:
    """Configure and return the global sequence validator"""
    global _sequence_validator
    _sequence_validator = SequenceValidator(stages=stages, **kwargs)
    return _sequence_validator
