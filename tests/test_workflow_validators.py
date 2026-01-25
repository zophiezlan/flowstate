"""
Tests for the Workflow Validators System

Tests cover:
- Built-in validators
- Custom validators
- Validation orchestration
- Validation results
"""

import pytest
import sqlite3
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tap_station.workflow_validators import (
    WorkflowValidationManager,
    ValidationContext,
    ValidationResult,
    ValidationSeverity,
    ValidationAction,
    MinimumWaitTimeValidator,
    MaximumWaitTimeValidator,
    DuplicateStageValidator,
    ServiceHoursValidator,
    SubstanceReturnValidator,
    CustomFunctionValidator,
    get_validation_manager,
    load_validators_from_config,
)


@pytest.fixture
def db_connection():
    """Create an in-memory database"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY,
            token_id TEXT,
            session_id TEXT,
            stage TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    return conn


@pytest.fixture
def manager(db_connection):
    """Create a validation manager"""
    return WorkflowValidationManager(conn=db_connection)


@pytest.fixture
def context():
    """Create a basic validation context"""
    return ValidationContext(
        action=ValidationAction.TRANSITION,
        stage="SERVICE_START",
        token_id="token_001",
        session_id="session1",
        previous_stage="QUEUE_JOIN",
        timestamp=datetime.utcnow(),
        event_data={},
        journey_history=[
            {
                "stage": "QUEUE_JOIN",
                "timestamp": (datetime.utcnow() - timedelta(minutes=15)).isoformat()
            }
        ]
    )


class TestValidationResult:
    """Tests for ValidationResult dataclass"""

    def test_creation(self):
        """Test result creation"""
        result = ValidationResult(
            valid=True,
            severity=ValidationSeverity.INFO,
            message="Validation passed",
            code="TEST001"
        )
        assert result.valid is True
        assert result.severity == ValidationSeverity.INFO

    def test_to_dict(self):
        """Test serialization"""
        result = ValidationResult(
            valid=False,
            severity=ValidationSeverity.ERROR,
            message="Validation failed",
            code="TEST002",
            suggestion="Fix the issue",
            data={"key": "value"}
        )
        d = result.to_dict()

        assert d["valid"] is False
        assert d["severity"] == "error"
        assert d["suggestion"] == "Fix the issue"


class TestMinimumWaitTimeValidator:
    """Tests for MinimumWaitTimeValidator"""

    def test_valid_wait_time(self):
        """Test validation passes with sufficient wait"""
        validator = MinimumWaitTimeValidator(min_wait_seconds=30)
        context = ValidationContext(
            action=ValidationAction.TRANSITION,
            stage="SERVICE_START",
            token_id="token",
            session_id="session",
            previous_stage="QUEUE_JOIN",
            timestamp=datetime.utcnow(),
            event_data={},
            journey_history=[
                {"stage": "QUEUE_JOIN", "timestamp": (datetime.utcnow() - timedelta(minutes=5)).isoformat()}
            ]
        )

        result = validator.validate(context)
        assert result.valid is True

    def test_invalid_wait_time(self):
        """Test validation fails with insufficient wait"""
        validator = MinimumWaitTimeValidator(min_wait_seconds=60)
        context = ValidationContext(
            action=ValidationAction.TRANSITION,
            stage="SERVICE_START",
            token_id="token",
            session_id="session",
            previous_stage="QUEUE_JOIN",
            timestamp=datetime.utcnow(),
            event_data={},
            journey_history=[
                {"stage": "QUEUE_JOIN", "timestamp": (datetime.utcnow() - timedelta(seconds=10)).isoformat()}
            ]
        )

        result = validator.validate(context)
        assert result.valid is False
        assert result.severity == ValidationSeverity.WARNING


class TestMaximumWaitTimeValidator:
    """Tests for MaximumWaitTimeValidator"""

    def test_normal_wait_time(self):
        """Test validation passes with normal wait"""
        validator = MaximumWaitTimeValidator(max_wait_minutes=180)
        context = ValidationContext(
            action=ValidationAction.TRANSITION,
            stage="SERVICE_START",
            token_id="token",
            session_id="session",
            previous_stage="QUEUE_JOIN",
            timestamp=datetime.utcnow(),
            event_data={},
            journey_history=[
                {"stage": "QUEUE_JOIN", "timestamp": (datetime.utcnow() - timedelta(minutes=30)).isoformat()}
            ]
        )

        result = validator.validate(context)
        assert result.valid is True

    def test_excessive_wait_time(self):
        """Test validation warns with excessive wait"""
        validator = MaximumWaitTimeValidator(max_wait_minutes=60)
        context = ValidationContext(
            action=ValidationAction.TRANSITION,
            stage="SERVICE_START",
            token_id="token",
            session_id="session",
            previous_stage="QUEUE_JOIN",
            timestamp=datetime.utcnow(),
            event_data={},
            journey_history=[
                {"stage": "QUEUE_JOIN", "timestamp": (datetime.utcnow() - timedelta(hours=3)).isoformat()}
            ]
        )

        result = validator.validate(context)
        # Still valid but with warning
        assert result.valid is True
        assert result.severity == ValidationSeverity.WARNING


class TestDuplicateStageValidator:
    """Tests for DuplicateStageValidator"""

    def test_no_duplicate(self):
        """Test validation passes with no duplicate"""
        validator = DuplicateStageValidator()
        context = ValidationContext(
            action=ValidationAction.TRANSITION,
            stage="SERVICE_START",
            token_id="token",
            session_id="session",
            previous_stage="QUEUE_JOIN",
            timestamp=datetime.utcnow(),
            event_data={},
            journey_history=[
                {"stage": "QUEUE_JOIN", "timestamp": (datetime.utcnow() - timedelta(minutes=10)).isoformat()}
            ]
        )

        result = validator.validate(context)
        assert result.valid is True

    def test_duplicate_detected(self):
        """Test validation fails with recent duplicate"""
        validator = DuplicateStageValidator(allow_repeat_after_minutes=60)
        context = ValidationContext(
            action=ValidationAction.TRANSITION,
            stage="SERVICE_START",
            token_id="token",
            session_id="session",
            previous_stage="QUEUE_JOIN",
            timestamp=datetime.utcnow(),
            event_data={},
            journey_history=[
                {"stage": "QUEUE_JOIN", "timestamp": (datetime.utcnow() - timedelta(minutes=30)).isoformat()},
                {"stage": "SERVICE_START", "timestamp": (datetime.utcnow() - timedelta(minutes=5)).isoformat()}
            ]
        )

        result = validator.validate(context)
        assert result.valid is False


class TestServiceHoursValidator:
    """Tests for ServiceHoursValidator"""

    def test_within_hours(self):
        """Test validation passes within service hours"""
        validator = ServiceHoursValidator(start_hour=0, end_hour=24)  # 24h service
        context = ValidationContext(
            action=ValidationAction.ENTRY,
            stage="QUEUE_JOIN",
            token_id="token",
            session_id="session",
            previous_stage=None,
            timestamp=datetime.utcnow(),
            event_data={},
            journey_history=[]
        )

        result = validator.validate(context)
        assert result.valid is True


class TestSubstanceReturnValidator:
    """Tests for SubstanceReturnValidator"""

    def test_substance_returned(self):
        """Test validation passes when substance returned"""
        validator = SubstanceReturnValidator()
        context = ValidationContext(
            action=ValidationAction.TRANSITION,
            stage="EXIT",
            token_id="token",
            session_id="session",
            previous_stage="SUBSTANCE_RETURNED",
            timestamp=datetime.utcnow(),
            event_data={},
            journey_history=[
                {"stage": "QUEUE_JOIN", "timestamp": "..."},
                {"stage": "SERVICE_START", "timestamp": "..."},
                {"stage": "SUBSTANCE_RETURNED", "timestamp": "..."}
            ]
        )

        result = validator.validate(context)
        assert result.valid is True

    def test_substance_not_returned(self):
        """Test validation warns when substance not returned"""
        validator = SubstanceReturnValidator(require_return=False)
        context = ValidationContext(
            action=ValidationAction.TRANSITION,
            stage="EXIT",
            token_id="token",
            session_id="session",
            previous_stage="SERVICE_START",
            timestamp=datetime.utcnow(),
            event_data={},
            journey_history=[
                {"stage": "QUEUE_JOIN", "timestamp": "..."},
                {"stage": "SERVICE_START", "timestamp": "..."}
            ]
        )

        result = validator.validate(context)
        # Valid but warns (require_return=False)
        assert result.valid is True
        assert result.severity == ValidationSeverity.WARNING


class TestCustomFunctionValidator:
    """Tests for CustomFunctionValidator"""

    def test_custom_validator_passes(self):
        """Test custom validator that passes"""
        def always_pass(ctx):
            return ValidationResult(
                valid=True,
                severity=ValidationSeverity.INFO,
                message="Custom check passed",
                code="CUSTOM001"
            )

        validator = CustomFunctionValidator(
            validator_id="custom_pass",
            name="Custom Pass",
            description="Always passes",
            validate_func=always_pass
        )

        context = ValidationContext(
            action=ValidationAction.TRANSITION,
            stage="EXIT",
            token_id="token",
            session_id="session",
            previous_stage="SERVICE_START",
            timestamp=datetime.utcnow(),
            event_data={},
            journey_history=[]
        )

        result = validator.validate(context)
        assert result.valid is True
        assert result.code == "CUSTOM001"

    def test_custom_validator_fails(self):
        """Test custom validator that fails"""
        def always_fail(ctx):
            return ValidationResult(
                valid=False,
                severity=ValidationSeverity.ERROR,
                message="Custom check failed",
                code="CUSTOM002"
            )

        validator = CustomFunctionValidator(
            validator_id="custom_fail",
            name="Custom Fail",
            description="Always fails",
            validate_func=always_fail
        )

        context = ValidationContext(
            action=ValidationAction.TRANSITION,
            stage="EXIT",
            token_id="token",
            session_id="session",
            previous_stage="SERVICE_START",
            timestamp=datetime.utcnow(),
            event_data={},
            journey_history=[]
        )

        result = validator.validate(context)
        assert result.valid is False


class TestWorkflowValidationManager:
    """Tests for WorkflowValidationManager"""

    def test_initialization(self, manager):
        """Test manager initializes with default validators"""
        validators = manager.list_validators()
        assert len(validators) > 0

    def test_register_validator(self, manager):
        """Test registering a validator"""
        def custom_func(ctx):
            return ValidationResult(True, ValidationSeverity.INFO, "OK", "OK")

        validator = CustomFunctionValidator(
            validator_id="test_custom",
            name="Test Custom",
            description="Test",
            validate_func=custom_func
        )
        manager.register(validator)

        assert manager.get_validator("test_custom") is not None

    def test_unregister_validator(self, manager):
        """Test unregistering a validator"""
        def custom_func(ctx):
            return ValidationResult(True, ValidationSeverity.INFO, "OK", "OK")

        validator = CustomFunctionValidator(
            validator_id="removable",
            name="Removable",
            description="Test",
            validate_func=custom_func
        )
        manager.register(validator)
        result = manager.unregister("removable")

        assert result is True
        assert manager.get_validator("removable") is None

    def test_enable_disable_validator(self, manager):
        """Test enabling/disabling validators"""
        validator_id = "min_wait_time"  # Default validator

        manager.disable_validator(validator_id)
        validator = manager.get_validator(validator_id)
        assert validator.enabled is False

        manager.enable_validator(validator_id)
        validator = manager.get_validator(validator_id)
        assert validator.enabled is True

    def test_validate_action(self, manager, context):
        """Test validating an action"""
        valid, results = manager.validate(
            action=context.action,
            stage=context.stage,
            token_id=context.token_id,
            session_id=context.session_id,
            previous_stage=context.previous_stage,
            timestamp=context.timestamp,
            journey_history=context.journey_history
        )

        assert isinstance(valid, bool)
        assert isinstance(results, list)

    def test_validate_with_hooks(self, manager):
        """Test validation with pre/post hooks"""
        pre_called = []
        post_called = []

        def pre_hook(ctx):
            pre_called.append(ctx.stage)

        def post_hook(ctx, results):
            post_called.append(len(results))

        manager.add_pre_hook(pre_hook)
        manager.add_post_hook(post_hook)

        manager.validate(
            action=ValidationAction.TRANSITION,
            stage="EXIT",
            token_id="token",
            session_id="session",
            journey_history=[]
        )

        assert len(pre_called) == 1
        assert len(post_called) == 1

    def test_list_validators(self, manager):
        """Test listing validators"""
        all_validators = manager.list_validators()
        enabled_only = manager.list_validators(enabled_only=True)

        assert len(all_validators) >= len(enabled_only)


class TestStageValidatorAppliesTo:
    """Tests for StageValidator.applies_to method"""

    def test_applies_to_correct_stage(self):
        """Test validator applies to correct stage"""
        validator = MinimumWaitTimeValidator(stages=["SERVICE_START"])
        context = ValidationContext(
            action=ValidationAction.TRANSITION,
            stage="SERVICE_START",
            token_id="token",
            session_id="session",
            previous_stage="QUEUE_JOIN",
            timestamp=datetime.utcnow(),
            event_data={},
            journey_history=[]
        )

        assert validator.applies_to(context) is True

    def test_does_not_apply_to_wrong_stage(self):
        """Test validator doesn't apply to wrong stage"""
        validator = MinimumWaitTimeValidator(stages=["SERVICE_START"])
        context = ValidationContext(
            action=ValidationAction.TRANSITION,
            stage="EXIT",
            token_id="token",
            session_id="session",
            previous_stage="SERVICE_START",
            timestamp=datetime.utcnow(),
            event_data={},
            journey_history=[]
        )

        assert validator.applies_to(context) is False

    def test_disabled_validator_does_not_apply(self):
        """Test disabled validator doesn't apply"""
        validator = MinimumWaitTimeValidator()
        validator.enabled = False
        context = ValidationContext(
            action=ValidationAction.TRANSITION,
            stage="SERVICE_START",
            token_id="token",
            session_id="session",
            previous_stage="QUEUE_JOIN",
            timestamp=datetime.utcnow(),
            event_data={},
            journey_history=[]
        )

        assert validator.applies_to(context) is False


class TestConfigurationLoading:
    """Tests for configuration loading"""

    def test_load_validators_from_config(self, manager):
        """Test loading validator config"""
        config = {
            "workflow": {
                "validators": [
                    {"id": "min_wait_time", "enabled": False},
                    {"id": "duplicate_stage", "severity": "error"}
                ]
            }
        }

        configured = load_validators_from_config(config, manager)
        assert configured >= 1


class TestConvenienceFunctions:
    """Tests for module-level convenience functions"""

    def test_get_validation_manager(self):
        """Test global manager retrieval"""
        module = sys.modules["tap_station.workflow_validators"]
        module._validation_manager = None

        manager = get_validation_manager()
        assert manager is not None

        manager2 = get_validation_manager()
        assert manager is manager2
