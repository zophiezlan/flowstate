"""
Validation Utilities

This module provides centralized validation logic for API requests,
event data, and other input validation needs.
"""

import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass

from .constants import APIDefaults, WorkflowStages

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation operation"""
    valid: bool
    error: Optional[str] = None
    warnings: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {"valid": self.valid}
        if self.error:
            result["error"] = self.error
        if self.warnings:
            result["warnings"] = self.warnings
        return result


class EventValidator:
    """
    Validates event data for the tap station API.

    This class consolidates validation logic from web_server.py to provide
    a clean, reusable interface for validating incoming event data.
    """

    def __init__(
        self,
        max_events_per_request: int = APIDefaults.MAX_EVENTS_PER_REQUEST,
        max_token_id_length: int = APIDefaults.MAX_TOKEN_ID_LENGTH,
        max_uid_length: int = APIDefaults.MAX_UID_LENGTH,
        max_stage_length: int = APIDefaults.MAX_STAGE_LENGTH,
    ):
        """
        Initialize the validator with configurable limits.

        Args:
            max_events_per_request: Maximum events allowed in a single batch
            max_token_id_length: Maximum token_id field length
            max_uid_length: Maximum uid field length
            max_stage_length: Maximum stage field length
        """
        self.max_events = max_events_per_request
        self.max_token_id_length = max_token_id_length
        self.max_uid_length = max_uid_length
        self.max_stage_length = max_stage_length

    def validate_event_batch(
        self, events: Any
    ) -> Tuple[ValidationResult, List[Dict[str, Any]]]:
        """
        Validate a batch of events.

        Args:
            events: The events data to validate (should be a list of dicts)

        Returns:
            Tuple of (ValidationResult, list of valid events)
        """
        warnings = []

        # Check type
        if not isinstance(events, list):
            return (
                ValidationResult(
                    valid=False,
                    error="Invalid format: expected list of events"
                ),
                [],
            )

        # Check size
        if len(events) > self.max_events:
            return (
                ValidationResult(
                    valid=False,
                    error=f"Payload too large: max {self.max_events} events per request"
                ),
                [],
            )

        if len(events) == 0:
            return (
                ValidationResult(
                    valid=False,
                    error="Empty payload: no events to process"
                ),
                [],
            )

        # Validate individual events
        valid_events = []
        invalid_count = 0

        for i, event in enumerate(events):
            result = self.validate_single_event(event)
            if result.valid:
                valid_events.append(event)
                if result.warnings:
                    warnings.extend(result.warnings)
            else:
                invalid_count += 1
                logger.warning(f"Invalid event at index {i}: {result.error}")

        if invalid_count > 0:
            warnings.append(f"{invalid_count} invalid event(s) skipped")

        if not valid_events:
            return (
                ValidationResult(
                    valid=False,
                    error="No valid events in payload"
                ),
                [],
            )

        return (
            ValidationResult(
                valid=True,
                warnings=warnings if warnings else None
            ),
            valid_events,
        )

    def validate_single_event(self, event: Any) -> ValidationResult:
        """
        Validate a single event.

        Args:
            event: Event data to validate

        Returns:
            ValidationResult indicating success or failure
        """
        warnings = []

        # Must be a dictionary
        if not isinstance(event, dict):
            return ValidationResult(
                valid=False,
                error="Event must be an object"
            )

        # Required fields
        required_fields = ["token_id", "stage"]
        missing = [f for f in required_fields if f not in event]
        if missing:
            return ValidationResult(
                valid=False,
                error=f"Missing required fields: {', '.join(missing)}"
            )

        # Validate token_id
        token_id = event.get("token_id")
        if not self._validate_string_field(token_id, "token_id", self.max_token_id_length):
            return ValidationResult(
                valid=False,
                error=f"Invalid token_id: must be non-empty string <= {self.max_token_id_length} chars"
            )

        # Validate uid (optional but validate if present)
        uid = event.get("uid")
        if uid is not None and not self._validate_string_field(uid, "uid", self.max_uid_length):
            return ValidationResult(
                valid=False,
                error=f"Invalid uid: must be string <= {self.max_uid_length} chars"
            )

        # Validate stage
        stage = event.get("stage")
        if not self._validate_string_field(stage, "stage", self.max_stage_length):
            return ValidationResult(
                valid=False,
                error=f"Invalid stage: must be non-empty string <= {self.max_stage_length} chars"
            )

        # Normalize and check stage
        normalized_stage = WorkflowStages.normalize(str(stage))
        if normalized_stage == "UNKNOWN":
            warnings.append(f"Unrecognized stage: {stage}")

        # Validate timestamp if present
        timestamp = event.get("timestamp") or event.get("timestamp_ms")
        if timestamp is not None:
            timestamp_result = self._validate_timestamp(timestamp)
            if not timestamp_result.valid:
                warnings.append(f"Invalid timestamp format: {timestamp_result.error}")

        return ValidationResult(
            valid=True,
            warnings=warnings if warnings else None
        )

    def _validate_string_field(
        self, value: Any, field_name: str, max_length: int
    ) -> bool:
        """Validate a string field"""
        if value is None:
            return False
        if not isinstance(value, str):
            # Try to convert
            try:
                value = str(value)
            except Exception:
                return False
        return len(value) > 0 and len(value) <= max_length

    def _validate_timestamp(self, timestamp: Any) -> ValidationResult:
        """Validate a timestamp value"""
        try:
            if isinstance(timestamp, (int, float)):
                # Assume milliseconds since epoch
                parsed_dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
            elif isinstance(timestamp, str):
                if timestamp.isdigit():
                    parsed_dt = datetime.fromtimestamp(int(timestamp) / 1000, tz=timezone.utc)
                else:
                    parsed_dt = datetime.fromisoformat(timestamp)
                    if parsed_dt.tzinfo is None:
                        parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
            else:
                return ValidationResult(
                    valid=False,
                    error="Timestamp must be ISO string or milliseconds since epoch"
                )

            # Validate reasonable time range (not too far in past or future)
            now = datetime.now(timezone.utc)
            max_age_hours = 24  # Accept events up to 24 hours old
            max_future_minutes = 5  # Accept events up to 5 minutes in future

            min_valid = now - timedelta(hours=max_age_hours)
            max_valid = now + timedelta(minutes=max_future_minutes)

            timestamp_warnings = []
            if parsed_dt < min_valid:
                timestamp_warnings.append(
                    f"Timestamp is more than {max_age_hours} hours in the past"
                )
            elif parsed_dt > max_valid:
                timestamp_warnings.append(
                    f"Timestamp is more than {max_future_minutes} minutes in the future"
                )

            return ValidationResult(valid=True, warnings=timestamp_warnings if timestamp_warnings else None)
        except (ValueError, OSError) as e:
            return ValidationResult(
                valid=False,
                error=str(e)
            )

    def normalize_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize an event to standard format.

        Args:
            event: Event data to normalize

        Returns:
            Normalized event dictionary
        """
        # Get values with fallbacks
        token_id = str(event.get("token_id") or event.get("tokenId") or "UNKNOWN")
        uid = str(event.get("uid") or event.get("serial") or token_id)
        stage = WorkflowStages.normalize(str(event.get("stage") or "UNKNOWN"))
        session_id = str(event.get("session_id") or event.get("sessionId") or "UNKNOWN")
        device_id = str(event.get("device_id") or event.get("deviceId") or "mobile")

        # Handle timestamp
        ts_value = event.get("timestamp_ms") or event.get("timestamp") or event.get("timestampMs")
        timestamp = self._coerce_timestamp(ts_value)

        return {
            "token_id": token_id,
            "uid": uid,
            "stage": stage,
            "session_id": session_id,
            "device_id": device_id,
            "timestamp": timestamp,
        }

    def _coerce_timestamp(self, value: Any) -> datetime:
        """Convert various timestamp formats to datetime"""
        if value is None:
            return datetime.now(timezone.utc)

        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value

        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)

        if isinstance(value, str):
            try:
                if value.isdigit():
                    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
                dt = datetime.fromisoformat(value)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                logger.warning(f"Could not parse timestamp '{value}', using current time")

        return datetime.now(timezone.utc)


class TokenValidator:
    """Validates token IDs and stage names"""

    # Pattern for valid token IDs (alphanumeric, 1-10 chars)
    TOKEN_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{1,10}$")

    # Pattern for UIDs (8+ hex characters)
    UID_PATTERN = re.compile(r"^[0-9A-Fa-f]{8,}$")

    @classmethod
    def is_valid_token_id(cls, token_id: str, strict: bool = False) -> bool:
        """
        Check if a string looks like a valid token ID.

        Args:
            token_id: String to check
            strict: If True, only allow numeric IDs (backward compatibility)

        Returns:
            True if it looks like a valid token ID
        """
        if not isinstance(token_id, str):
            return False
        
        if strict:
            # Legacy: only numeric
            return bool(re.compile(r"^\d{1,4}$").match(token_id))
        
        return bool(cls.TOKEN_ID_PATTERN.match(token_id))

    @classmethod
    def looks_like_uid(cls, value: str) -> bool:
        """
        Check if a string looks like a raw UID (uninitialized card).

        Args:
            value: String to check

        Returns:
            True if it looks like a UID (8+ hex chars)
        """
        if not isinstance(value, str):
            return False
        return bool(cls.UID_PATTERN.match(value))

    @classmethod
    def needs_initialization(cls, token_id: str) -> bool:
        """
        Check if a token ID indicates the card needs initialization.

        Args:
            token_id: Token ID to check

        Returns:
            True if the card should be auto-initialized
        """
        return cls.looks_like_uid(token_id) and not cls.is_valid_token_id(token_id)


class StageValidator:
    """Validates workflow stage names"""
    
    @classmethod
    def is_valid_stage(cls, stage: str) -> bool:
        """
        Check if a stage name is valid.
        
        Args:
            stage: Stage name to validate
            
        Returns:
            True if stage is recognized
        """
        if not isinstance(stage, str):
            return False
        
        normalized = WorkflowStages.normalize(stage)
        return normalized in WorkflowStages.ALL_STAGES
    
    @classmethod
    def validate_stage_or_raise(cls, stage: str) -> str:
        """
        Validate stage and return normalized version, or raise ValueError.
        
        Args:
            stage: Stage name to validate
            
        Returns:
            Normalized stage name
            
        Raises:
            ValueError: If stage is invalid
        """
        if not isinstance(stage, str):
            raise ValueError(f"Stage must be a string, got {type(stage)}")
        
        normalized = WorkflowStages.normalize(stage)
        
        if normalized == "UNKNOWN":
            raise ValueError(f"Unknown stage: {stage}. Valid stages: {', '.join(WorkflowStages.ALL_STAGES)}")
        
        return normalized


# =============================================================================
# Global Validator Instance
# =============================================================================

_event_validator: Optional[EventValidator] = None


def get_event_validator() -> EventValidator:
    """Get the global event validator instance."""
    global _event_validator
    if _event_validator is None:
        _event_validator = EventValidator()
    return _event_validator


def configure_event_validator(
    max_events_per_request: int = APIDefaults.MAX_EVENTS_PER_REQUEST,
    max_token_id_length: int = APIDefaults.MAX_TOKEN_ID_LENGTH,
    max_uid_length: int = APIDefaults.MAX_UID_LENGTH,
    max_stage_length: int = APIDefaults.MAX_STAGE_LENGTH,
) -> EventValidator:
    """
    Configure and return the global event validator instance.

    Args:
        max_events_per_request: Maximum events per batch
        max_token_id_length: Maximum token ID length
        max_uid_length: Maximum UID length
        max_stage_length: Maximum stage length

    Returns:
        Configured EventValidator instance
    """
    global _event_validator
    _event_validator = EventValidator(
        max_events_per_request=max_events_per_request,
        max_token_id_length=max_token_id_length,
        max_uid_length=max_uid_length,
        max_stage_length=max_stage_length,
    )
    return _event_validator
