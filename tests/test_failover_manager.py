"""Tests for failover manager"""

import pytest
from tap_station.failover_manager import FailoverManager


class TestFailoverManager:
    """Test failover manager functionality"""

    def test_initialization(self):
        """Test failover manager initialization"""
        mgr = FailoverManager(primary_stage="QUEUE_JOIN", fallback_stages=["EXIT"])

        assert mgr.primary_stage == "QUEUE_JOIN"
        assert mgr.fallback_stages == ["EXIT"]
        assert mgr.failover_active is False
        assert mgr.active_stages == ["QUEUE_JOIN"]

    def test_enable_failover(self):
        """Test enabling failover mode"""
        mgr = FailoverManager(primary_stage="QUEUE_JOIN", fallback_stages=["EXIT"])

        result = mgr.enable_failover()

        assert result is True
        assert mgr.failover_active is True
        assert mgr.active_stages == ["QUEUE_JOIN", "EXIT"]
        assert mgr.failover_start_time is not None

    def test_enable_failover_already_active(self):
        """Test enabling failover when already active"""
        mgr = FailoverManager(primary_stage="QUEUE_JOIN", fallback_stages=["EXIT"])

        mgr.enable_failover()
        result = mgr.enable_failover()  # Try to enable again

        assert result is False  # Should return False since already active

    def test_disable_failover(self):
        """Test disabling failover mode"""
        mgr = FailoverManager(primary_stage="QUEUE_JOIN", fallback_stages=["EXIT"])

        mgr.enable_failover()
        assert mgr.failover_active is True

        result = mgr.disable_failover()

        assert result is True
        assert mgr.failover_active is False
        assert mgr.active_stages == ["QUEUE_JOIN"]
        assert mgr.failover_start_time is None

    def test_disable_failover_not_active(self):
        """Test disabling failover when not active"""
        mgr = FailoverManager(primary_stage="QUEUE_JOIN", fallback_stages=["EXIT"])

        result = mgr.disable_failover()

        assert result is False  # Should return False since not active

    def test_get_stage_for_tap_number_not_in_failover(self):
        """Test stage selection when not in failover mode"""
        mgr = FailoverManager(primary_stage="QUEUE_JOIN", fallback_stages=["EXIT"])

        # Not in failover mode - always return primary
        assert mgr.get_stage_for_tap_number(1) == "QUEUE_JOIN"
        assert mgr.get_stage_for_tap_number(2) == "QUEUE_JOIN"
        assert mgr.get_stage_for_tap_number(3) == "QUEUE_JOIN"

    def test_get_stage_for_tap_number_simple_alternation(self):
        """Test stage alternation in failover mode with 2 stages"""
        mgr = FailoverManager(primary_stage="QUEUE_JOIN", fallback_stages=["EXIT"])

        mgr.enable_failover()

        # Simple alternation: odd = primary, even = fallback
        assert mgr.get_stage_for_tap_number(1) == "QUEUE_JOIN"  # 1st tap - primary
        assert mgr.get_stage_for_tap_number(2) == "EXIT"  # 2nd tap - fallback
        assert mgr.get_stage_for_tap_number(3) == "QUEUE_JOIN"  # 3rd tap - primary
        assert mgr.get_stage_for_tap_number(4) == "EXIT"  # 4th tap - fallback
        assert mgr.get_stage_for_tap_number(5) == "QUEUE_JOIN"  # 5th tap - primary

    def test_get_stage_for_tap_number_multiple_fallback_stages(self):
        """Test stage cycling with multiple fallback stages"""
        mgr = FailoverManager(
            primary_stage="QUEUE_JOIN", fallback_stages=["SUBSTANCE_PICKUP", "EXIT"]
        )

        mgr.enable_failover()

        # Cycle through all active stages
        # active_stages = ["QUEUE_JOIN", "SUBSTANCE_PICKUP", "EXIT"]
        assert mgr.get_stage_for_tap_number(1) == "QUEUE_JOIN"  # tap 1 - stage 0
        assert mgr.get_stage_for_tap_number(2) == "SUBSTANCE_PICKUP"  # tap 2 - stage 1
        assert mgr.get_stage_for_tap_number(3) == "EXIT"  # tap 3 - stage 2
        assert (
            mgr.get_stage_for_tap_number(4) == "QUEUE_JOIN"
        )  # tap 4 - stage 0 (cycle)
        assert mgr.get_stage_for_tap_number(5) == "SUBSTANCE_PICKUP"  # tap 5 - stage 1

    def test_record_tap(self):
        """Test recording taps in failover manager"""
        mgr = FailoverManager(primary_stage="QUEUE_JOIN", fallback_stages=["EXIT"])

        mgr.enable_failover()

        # Record some taps
        mgr.record_tap("QUEUE_JOIN")
        mgr.record_tap("EXIT")
        mgr.record_tap("QUEUE_JOIN")

        assert mgr.tap_counts["QUEUE_JOIN"] == 2
        assert mgr.tap_counts["EXIT"] == 1

    def test_should_use_alternate_beep(self):
        """Test alternate beep determination"""
        mgr = FailoverManager(primary_stage="QUEUE_JOIN", fallback_stages=["EXIT"])

        # Not in failover - no alternate beep
        assert mgr.should_use_alternate_beep("QUEUE_JOIN") is False

        mgr.enable_failover()

        # In failover - use alternate beep for fallback stages
        assert mgr.should_use_alternate_beep("QUEUE_JOIN") is False  # primary
        assert mgr.should_use_alternate_beep("EXIT") is True  # fallback

    def test_get_status(self):
        """Test status reporting"""
        mgr = FailoverManager(primary_stage="QUEUE_JOIN", fallback_stages=["EXIT"])

        status = mgr.get_status()

        assert status["failover_active"] is False
        assert status["primary_stage"] == "QUEUE_JOIN"
        assert status["fallback_stages"] == ["EXIT"]
        assert status["active_stages"] == ["QUEUE_JOIN"]

        # Activate and record some taps
        mgr.enable_failover()
        mgr.record_tap("QUEUE_JOIN")
        mgr.record_tap("EXIT")

        status = mgr.get_status()

        assert status["failover_active"] is True
        assert status["active_stages"] == ["QUEUE_JOIN", "EXIT"]
        assert status["tap_counts"] == {"QUEUE_JOIN": 1, "EXIT": 1}
        assert status["failover_start_time"] is not None

    def test_failover_callbacks(self):
        """Test failover enable/disable callbacks"""
        enabled_called = []
        disabled_called = []

        def on_enable():
            enabled_called.append(True)

        def on_disable():
            disabled_called.append(True)

        mgr = FailoverManager(
            primary_stage="QUEUE_JOIN",
            fallback_stages=["EXIT"],
            on_failover_enable=on_enable,
            on_failover_disable=on_disable,
        )

        # Enable failover - should trigger callback
        mgr.enable_failover()
        assert len(enabled_called) == 1
        assert len(disabled_called) == 0

        # Disable failover - should trigger callback
        mgr.disable_failover()
        assert len(enabled_called) == 1
        assert len(disabled_called) == 1
