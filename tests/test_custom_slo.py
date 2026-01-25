"""
Tests for the Custom SLO System

Tests cover:
- SLO definition and evaluation
- Built-in metrics
- SLO summary and budgets
- Configuration loading
"""

import pytest
import sqlite3
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tap_station.custom_slo import (
    CustomSLOManager,
    CustomSLODefinition,
    SLOTarget,
    SLOResult,
    SLOBudget,
    SLOMetricType,
    SLOStatus,
    get_slo_manager,
    load_slos_from_config,
)


@pytest.fixture
def db_connection():
    """Create an in-memory database with test schema"""
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
def populated_db(db_connection):
    """Populate database with test events"""
    now = datetime.utcnow()
    events = []

    # Create complete journeys with varying wait times
    for i in range(20):
        token_id = f"token_{i:03d}"
        join_time = now - timedelta(hours=2, minutes=i * 3)
        service_time = join_time + timedelta(minutes=10 + i)  # Wait varies 10-29 min
        return_time = service_time + timedelta(minutes=3)
        exit_time = return_time + timedelta(minutes=2)

        events.extend([
            (token_id, "session1", "QUEUE_JOIN", join_time.isoformat()),
            (token_id, "session1", "SERVICE_START", service_time.isoformat()),
            (token_id, "session1", "SUBSTANCE_RETURNED", return_time.isoformat()),
            (token_id, "session1", "EXIT", exit_time.isoformat()),
        ])

    # Add incomplete journeys (no exit)
    for i in range(3):
        token_id = f"incomplete_{i:03d}"
        join_time = now - timedelta(hours=1, minutes=i * 5)
        events.append((token_id, "session1", "QUEUE_JOIN", join_time.isoformat()))

    db_connection.executemany(
        "INSERT INTO events (token_id, session_id, stage, timestamp) VALUES (?, ?, ?, ?)",
        events
    )
    db_connection.commit()
    return db_connection


@pytest.fixture
def manager(db_connection):
    """Create an SLO manager"""
    return CustomSLOManager(conn=db_connection, target_wait_minutes=30)


class TestSLOTarget:
    """Tests for SLOTarget class"""

    def test_evaluate_gte_met(self):
        """Test >= operator when target met"""
        target = SLOTarget(operator=">=", value=80.0)
        is_met, status = target.evaluate(85.0)
        assert is_met is True
        assert status == SLOStatus.MET

    def test_evaluate_gte_not_met(self):
        """Test >= operator when target not met"""
        target = SLOTarget(operator=">=", value=80.0)
        is_met, status = target.evaluate(75.0)
        assert is_met is False
        assert status == SLOStatus.BREACHED

    def test_evaluate_gte_at_risk(self):
        """Test >= operator with warning threshold"""
        target = SLOTarget(operator=">=", value=80.0, warning_threshold=70.0)
        is_met, status = target.evaluate(72.0)
        assert is_met is False
        assert status == SLOStatus.AT_RISK

    def test_evaluate_lte_met(self):
        """Test <= operator when target met"""
        target = SLOTarget(operator="<=", value=30.0)
        is_met, status = target.evaluate(25.0)
        assert is_met is True
        assert status == SLOStatus.MET

    def test_evaluate_lte_not_met(self):
        """Test <= operator when target not met"""
        target = SLOTarget(operator="<=", value=30.0)
        is_met, status = target.evaluate(35.0)
        assert is_met is False
        assert status == SLOStatus.BREACHED

    def test_to_dict(self):
        """Test serialization"""
        target = SLOTarget(operator=">=", value=95.0, warning_threshold=90.0)
        result = target.to_dict()
        assert result["operator"] == ">="
        assert result["value"] == 95.0
        assert result["warning_threshold"] == 90.0


class TestCustomSLODefinition:
    """Tests for CustomSLODefinition dataclass"""

    def test_creation(self):
        """Test SLO definition creation"""
        slo = CustomSLODefinition(
            id="test_slo",
            name="Test SLO",
            description="Test description",
            metric_type=SLOMetricType.PERCENTAGE,
            target=SLOTarget(operator=">=", value=95.0),
            window_hours=24,
            metric_id="completion_rate"
        )
        assert slo.id == "test_slo"
        assert slo.enabled is True

    def test_to_dict(self):
        """Test serialization"""
        slo = CustomSLODefinition(
            id="test_slo",
            name="Test SLO",
            description="Test",
            metric_type=SLOMetricType.PERCENTAGE,
            target=SLOTarget(operator=">=", value=95.0),
            tags=["core", "participant"]
        )
        result = slo.to_dict()

        assert result["id"] == "test_slo"
        assert result["metric_type"] == "percentage"
        assert "core" in result["tags"]


class TestCustomSLOManager:
    """Tests for CustomSLOManager"""

    def test_initialization(self, manager):
        """Test manager initialization with default SLOs"""
        slos = manager.list_slos()
        assert len(slos) > 0

    def test_define_slo(self, manager):
        """Test defining a new SLO"""
        slo = CustomSLODefinition(
            id="custom_test",
            name="Custom Test",
            description="Test SLO",
            metric_type=SLOMetricType.PERCENTAGE,
            target=SLOTarget(operator=">=", value=90.0),
            metric_id="completion_rate"
        )
        manager.define_slo(slo)

        retrieved = manager.get_slo("custom_test")
        assert retrieved is not None
        assert retrieved.name == "Custom Test"

    def test_define_slo_from_dict(self, manager):
        """Test defining SLO from config dictionary"""
        config = {
            "id": "dict_slo",
            "name": "Dict SLO",
            "description": "From dict",
            "metric_type": "percentage",
            "target_operator": ">=",
            "target_value": 85.0,
            "warning_threshold": 80.0,
            "metric_id": "completion_rate",
            "window_hours": 12,
            "tags": ["test"]
        }
        slo = manager.define_slo_from_dict(config)

        assert slo.id == "dict_slo"
        assert slo.target.value == 85.0
        assert slo.target.warning_threshold == 80.0

    def test_remove_slo(self, manager):
        """Test removing an SLO"""
        slo = CustomSLODefinition(
            id="removable",
            name="Removable",
            description="Test",
            metric_type=SLOMetricType.COUNT,
            target=SLOTarget(operator=">=", value=10)
        )
        manager.define_slo(slo)
        result = manager.remove_slo("removable")
        assert result is True
        assert manager.get_slo("removable") is None

    def test_list_slos(self, manager):
        """Test listing SLOs"""
        slos = manager.list_slos()
        assert isinstance(slos, list)
        assert all(s.enabled for s in slos)

    def test_list_slos_by_tags(self, manager):
        """Test filtering SLOs by tags"""
        slos = manager.list_slos(tags=["core"])
        # Default SLOs have 'core' tag
        assert len(slos) > 0

    def test_evaluate_slo(self, populated_db):
        """Test evaluating an SLO"""
        manager = CustomSLOManager(populated_db)
        result = manager.evaluate_slo("completion_rate_slo", "session1")

        assert result is not None
        assert isinstance(result, SLOResult)
        assert result.slo_id == "completion_rate_slo"
        assert 0 <= result.current_value <= 100

    def test_evaluate_nonexistent_slo(self, manager):
        """Test evaluating non-existent SLO"""
        result = manager.evaluate_slo("nonexistent", "session1")
        assert result is None

    def test_evaluate_all_slos(self, populated_db):
        """Test evaluating all SLOs"""
        manager = CustomSLOManager(populated_db)
        results = manager.evaluate_all_slos("session1")

        assert isinstance(results, dict)
        assert len(results) > 0

    def test_get_slo_summary(self, populated_db):
        """Test getting SLO summary"""
        manager = CustomSLOManager(populated_db)
        summary = manager.get_slo_summary("session1")

        assert "overall_status" in summary
        assert "total_slos" in summary
        assert "met" in summary
        assert "breached" in summary
        assert "compliance_rate" in summary
        assert "results" in summary

    def test_calculate_error_budget(self, populated_db):
        """Test error budget calculation"""
        manager = CustomSLOManager(populated_db)
        budget = manager.calculate_error_budget("completion_rate_slo", "session1")

        assert budget is not None
        assert isinstance(budget, SLOBudget)
        assert budget.total_budget_minutes > 0


class TestBuiltinMetrics:
    """Tests for built-in metric calculations"""

    def test_calc_wait_time_avg(self, populated_db):
        """Test average wait time calculation"""
        manager = CustomSLOManager(populated_db)
        avg_wait = manager._calc_wait_time_avg("session1", 24)
        assert avg_wait >= 0

    def test_calc_completion_rate(self, populated_db):
        """Test completion rate calculation"""
        manager = CustomSLOManager(populated_db)
        rate = manager._calc_completion_rate("session1", 24)
        # We have 20 complete and 3 incomplete
        assert 80 <= rate <= 100

    def test_calc_throughput(self, populated_db):
        """Test throughput calculation"""
        manager = CustomSLOManager(populated_db)
        throughput = manager._calc_throughput("session1", 24)
        assert throughput >= 0

    def test_calc_service_time_avg(self, populated_db):
        """Test service time calculation"""
        manager = CustomSLOManager(populated_db)
        svc_time = manager._calc_service_time_avg("session1", 24)
        assert svc_time >= 0

    def test_calc_substance_return_rate(self, populated_db):
        """Test substance return rate"""
        manager = CustomSLOManager(populated_db)
        rate = manager._calc_substance_return_rate("session1", 24)
        # All our complete journeys have substance return
        assert rate > 90


class TestSLOResult:
    """Tests for SLOResult dataclass"""

    def test_to_dict(self):
        """Test result serialization"""
        result = SLOResult(
            slo_id="test",
            slo_name="Test SLO",
            target_value=95.0,
            current_value=92.0,
            status=SLOStatus.AT_RISK,
            compliance_percentage=96.8,
            window_hours=24,
            evaluated_at=datetime.utcnow()
        )

        d = result.to_dict()
        assert d["slo_id"] == "test"
        assert d["status"] == "at_risk"
        assert d["compliance_percentage"] == 96.8


class TestSLOBudget:
    """Tests for SLOBudget dataclass"""

    def test_to_dict(self):
        """Test budget serialization"""
        budget = SLOBudget(
            slo_id="test",
            total_budget_minutes=420,  # 7 hours
            remaining_budget_minutes=300,
            burn_rate=0.5,
            estimated_exhaustion=datetime.utcnow() + timedelta(hours=10)
        )

        d = budget.to_dict()
        assert d["total_budget_minutes"] == 420
        assert "remaining_percentage" in d


class TestConfigurationLoading:
    """Tests for configuration loading"""

    def test_load_slos_from_config(self, db_connection):
        """Test loading SLOs from config dict"""
        manager = CustomSLOManager(db_connection)
        initial_count = len(manager.list_slos())

        config = {
            "slos": [
                {
                    "id": "config_slo_1",
                    "name": "Config SLO 1",
                    "metric_type": "percentage",
                    "target_operator": ">=",
                    "target_value": 90.0,
                    "metric_id": "completion_rate"
                },
                {
                    "id": "config_slo_2",
                    "name": "Config SLO 2",
                    "metric_type": "duration",
                    "target_operator": "<=",
                    "target_value": 30.0,
                    "metric_id": "wait_time_avg"
                }
            ]
        }

        loaded = load_slos_from_config(config, manager)
        assert loaded == 2
        assert len(manager.list_slos()) == initial_count + 2


class TestConvenienceFunctions:
    """Tests for module-level convenience functions"""

    def test_get_slo_manager(self, db_connection):
        """Test global manager retrieval"""
        # Reset the module-level singleton without re-importing the module
        get_slo_manager.__globals__["_slo_manager"] = None

        manager = get_slo_manager(db_connection)
        assert manager is not None

        manager2 = get_slo_manager(db_connection)
        assert manager is manager2
