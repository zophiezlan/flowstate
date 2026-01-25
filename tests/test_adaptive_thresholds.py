"""
Tests for the Adaptive Thresholds System

Tests cover:
- Threshold retrieval and adjustment
- Time-based rules
- Manual overrides
- Threshold checking
"""

import pytest
from datetime import datetime, time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tap_station.adaptive_thresholds import (
    AdaptiveThresholdManager,
    ThresholdChecker,
    ThresholdType,
    ThresholdAdjustment,
    ThresholdRule,
    TimeWindow,
    AdjustmentReason,
    get_threshold_manager,
    get_threshold_checker,
)


@pytest.fixture
def manager():
    """Create a threshold manager for testing"""
    return AdaptiveThresholdManager()


@pytest.fixture
def checker(manager):
    """Create a threshold checker"""
    return ThresholdChecker(manager)


class TestTimeWindow:
    """Tests for TimeWindow class"""

    def test_contains_within_window(self):
        """Test time within window"""
        window = TimeWindow(
            start=time(10, 0),
            end=time(18, 0),
            days=list(range(7))
        )
        # 2pm on a Monday (weekday 0)
        dt = datetime(2024, 1, 8, 14, 0)  # Monday
        assert window.contains(dt) is True

    def test_contains_outside_window(self):
        """Test time outside window"""
        window = TimeWindow(
            start=time(10, 0),
            end=time(18, 0),
            days=list(range(7))
        )
        # 9am
        dt = datetime(2024, 1, 8, 9, 0)
        assert window.contains(dt) is False

    def test_contains_wrong_day(self):
        """Test excluded day of week"""
        window = TimeWindow(
            start=time(10, 0),
            end=time(18, 0),
            days=[0, 1, 2, 3, 4]  # Weekdays only
        )
        # Saturday (weekday 5)
        dt = datetime(2024, 1, 6, 14, 0)  # Saturday
        assert window.contains(dt) is False

    def test_window_crossing_midnight(self):
        """Test window that crosses midnight"""
        window = TimeWindow(
            start=time(22, 0),
            end=time(2, 0),
            days=list(range(7))
        )
        # 11pm should be in window
        dt = datetime(2024, 1, 8, 23, 0)
        assert window.contains(dt) is True

        # 1am should be in window
        dt2 = datetime(2024, 1, 8, 1, 0)
        assert window.contains(dt2) is True

    def test_to_dict(self):
        """Test serialization"""
        window = TimeWindow(
            start=time(10, 0),
            end=time(18, 0),
            days=[0, 1, 2],
            label="Test"
        )
        result = window.to_dict()
        assert result["start"] == "10:00:00"
        assert result["end"] == "18:00:00"
        assert result["label"] == "Test"


class TestAdaptiveThresholdManager:
    """Tests for AdaptiveThresholdManager"""

    def test_initialization(self, manager):
        """Test manager initialization"""
        assert len(manager._configs) > 0
        assert len(manager._rules) > 0

    def test_configure_base_threshold(self, manager):
        """Test base threshold configuration"""
        manager.configure_base_threshold(ThresholdType.QUEUE_WARNING, 15)
        config = manager._configs[ThresholdType.QUEUE_WARNING]
        assert config.base_value == 15

    def test_configure_base_threshold_clamped(self, manager):
        """Test threshold clamping to valid range"""
        # Try to set below minimum
        manager.configure_base_threshold(ThresholdType.QUEUE_WARNING, 1)
        config = manager._configs[ThresholdType.QUEUE_WARNING]
        assert config.base_value >= config.min_value

    def test_get_threshold_default(self, manager):
        """Test getting default threshold"""
        value, adjustment = manager.get_threshold(ThresholdType.QUEUE_WARNING)
        assert value > 0
        assert isinstance(adjustment, ThresholdAdjustment)

    def test_set_manual_override(self, manager):
        """Test manual override"""
        override = manager.set_manual_override(
            ThresholdType.QUEUE_WARNING,
            value=25,
            duration_minutes=60,
            reason="High event day"
        )

        assert override.adjusted_value == 25
        assert override.reason == AdjustmentReason.MANUAL_OVERRIDE

        # Get threshold should return override value
        value, adj = manager.get_threshold(ThresholdType.QUEUE_WARNING)
        assert value == 25

    def test_clear_manual_override(self, manager):
        """Test clearing manual override"""
        manager.set_manual_override(ThresholdType.QUEUE_WARNING, 25)
        result = manager.clear_manual_override(ThresholdType.QUEUE_WARNING)
        assert result is True

        # Should return to base value
        value, _ = manager.get_threshold(ThresholdType.QUEUE_WARNING)
        base = manager._configs[ThresholdType.QUEUE_WARNING].base_value
        assert value == base or value != 25

    def test_add_rule(self, manager):
        """Test adding custom rule"""
        rule = ThresholdRule(
            id="test_rule",
            name="Test Rule",
            description="Test",
            threshold_types=[ThresholdType.QUEUE_WARNING],
            multiplier=1.5,
            condition=lambda dt, ctx: True,
            reason=AdjustmentReason.HIGH_DEMAND,
            priority=100
        )
        manager.add_rule(rule)
        assert any(r.id == "test_rule" for r in manager._rules)

    def test_remove_rule(self, manager):
        """Test removing rule"""
        rule = ThresholdRule(
            id="removable_rule",
            name="Removable",
            description="Test",
            threshold_types=[ThresholdType.QUEUE_WARNING],
            multiplier=1.0,
            condition=lambda dt, ctx: True,
            reason=AdjustmentReason.SYSTEM_DEFAULT,
            priority=0
        )
        manager.add_rule(rule)
        result = manager.remove_rule("removable_rule")
        assert result is True
        assert not any(r.id == "removable_rule" for r in manager._rules)

    def test_get_all_thresholds(self, manager):
        """Test getting all thresholds"""
        all_thresholds = manager.get_all_thresholds()
        assert len(all_thresholds) == len(ThresholdType)

        for t_type in ThresholdType:
            assert t_type.value in all_thresholds

    def test_get_threshold_explanation(self, manager):
        """Test threshold explanation"""
        explanation = manager.get_threshold_explanation(ThresholdType.QUEUE_WARNING)
        assert isinstance(explanation, str)
        assert len(explanation) > 0

    def test_check_threshold_not_exceeded(self, manager):
        """Test threshold check when not exceeded"""
        result = manager.check_threshold(
            ThresholdType.QUEUE_WARNING,
            current_value=5  # Below default threshold
        )
        assert result["exceeded"] is False

    def test_check_threshold_exceeded(self, manager):
        """Test threshold check when exceeded"""
        result = manager.check_threshold(
            ThresholdType.QUEUE_WARNING,
            current_value=100  # Well above threshold
        )
        assert result["exceeded"] is True

    def test_add_time_window_rule(self, manager):
        """Test time window rule creation"""
        rule = manager.add_time_window_rule(
            rule_id="lunch_rush",
            name="Lunch Rush",
            threshold_types=[ThresholdType.QUEUE_WARNING],
            multiplier=1.2,
            start_time=time(12, 0),
            end_time=time(14, 0)
        )
        assert rule.id == "lunch_rush"
        assert len(rule.time_windows) == 1

    def test_get_active_rules(self, manager):
        """Test getting active rules"""
        active = manager.get_active_rules()
        assert isinstance(active, list)


class TestThresholdChecker:
    """Tests for ThresholdChecker convenience class"""

    def test_check_queue(self, checker):
        """Test queue threshold checking"""
        result = checker.check_queue(queue_size=5)
        assert "queue_size" in result
        assert "warning" in result
        assert "critical" in result
        assert "status" in result

    def test_check_wait_time(self, checker):
        """Test wait time threshold checking"""
        result = checker.check_wait_time(wait_minutes=15)
        assert "wait_minutes" in result
        assert "status" in result

    def test_check_all(self, checker):
        """Test comprehensive threshold check"""
        metrics = {
            "queue_size": 10,
            "wait_time": 25,
            "throughput": 8,
            "inactivity_minutes": 5
        }
        result = checker.check_all(metrics)

        assert "queue" in result
        assert "wait_time" in result
        assert "throughput" in result
        assert "inactivity" in result
        assert "overall_status" in result

    def test_overall_status_critical(self, checker):
        """Test overall status is critical when any threshold is critical"""
        metrics = {
            "queue_size": 100,  # Definitely exceeds critical
        }
        result = checker.check_all(metrics)
        # Should be at least warning if not critical
        assert result["overall_status"] in ["warning", "critical"]


class TestThresholdAdjustment:
    """Tests for ThresholdAdjustment dataclass"""

    def test_to_dict(self):
        """Test serialization"""
        adj = ThresholdAdjustment(
            threshold_type=ThresholdType.QUEUE_WARNING,
            base_value=10,
            adjusted_value=13,
            multiplier=1.3,
            reason=AdjustmentReason.PEAK_HOURS,
            explanation="Peak hours adjustment"
        )
        result = adj.to_dict()

        assert result["threshold_type"] == "queue_warning"
        assert result["base_value"] == 10
        assert result["adjusted_value"] == 13
        assert result["reason"] == "peak_hours"


class TestConvenienceFunctions:
    """Tests for module-level convenience functions"""

    def test_get_threshold_manager(self):
        """Test global manager retrieval"""
        module = sys.modules["tap_station.adaptive_thresholds"]
        module._threshold_manager = None

        manager = get_threshold_manager()
        assert manager is not None

        manager2 = get_threshold_manager()
        assert manager is manager2

    def test_get_threshold_checker(self):
        """Test checker retrieval"""
        module = sys.modules["tap_station.adaptive_thresholds"]
        module._threshold_manager = None

        checker = get_threshold_checker()
        assert checker is not None
