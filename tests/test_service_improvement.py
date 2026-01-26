"""
Tests for the Service Improvement Engine

Tests cover:
- Recommendation generation
- Health scoring
- Pattern detection
- Analysis methods
"""

import pytest
import sqlite3
from datetime import datetime, timedelta

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tap_station.service_improvement import (
    ServiceImprovementEngine,
    ImprovementRecommendation,
    ImprovementCategory,
    ImprovementPriority,
    ImprovementStatus,
    ServicePattern,
    get_improvement_engine,
    analyze_service,
)


@pytest.fixture
def db_connection():
    """Create an in-memory database with test schema"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE events (
            id INTEGER PRIMARY KEY,
            token_id TEXT,
            session_id TEXT,
            stage TEXT,
            timestamp TEXT
        )
    """
    )
    conn.commit()
    return conn


@pytest.fixture
def engine(db_connection):
    """Create a service improvement engine with test database"""
    return ServiceImprovementEngine(
        conn=db_connection,
        target_wait_minutes=30,
        target_throughput_per_hour=12,
        analysis_window_hours=24,
    )


@pytest.fixture
def populated_db(db_connection):
    """Populate database with test events"""
    now = datetime.utcnow()
    events = []

    # Create 10 complete journeys with varying wait times
    for i in range(10):
        token_id = f"token_{i:03d}"
        join_time = now - timedelta(hours=2, minutes=i * 5)
        service_time = join_time + timedelta(minutes=15 + i * 2)
        exit_time = service_time + timedelta(minutes=5)

        events.extend(
            [
                (token_id, "session1", "QUEUE_JOIN", join_time.isoformat()),
                (token_id, "session1", "SERVICE_START", service_time.isoformat()),
                (token_id, "session1", "EXIT", exit_time.isoformat()),
            ]
        )

    # Add some abandoned journeys
    for i in range(3):
        token_id = f"abandoned_{i:03d}"
        join_time = now - timedelta(hours=3, minutes=i * 10)
        events.append((token_id, "session1", "QUEUE_JOIN", join_time.isoformat()))

    db_connection.executemany(
        "INSERT INTO events (token_id, session_id, stage, timestamp) VALUES (?, ?, ?, ?)",
        events,
    )
    db_connection.commit()
    return db_connection


class TestServiceImprovementEngine:
    """Tests for ServiceImprovementEngine"""

    def test_initialization(self, db_connection):
        """Test engine initialization"""
        engine = ServiceImprovementEngine(db_connection)
        assert engine._target_wait == 30
        assert engine._target_throughput == 12
        assert engine._analysis_window == 24

    def test_configure(self, engine):
        """Test configuration updates"""
        engine.configure(
            target_wait_minutes=45,
            target_throughput_per_hour=20,
            analysis_window_hours=12,
        )
        assert engine._target_wait == 45
        assert engine._target_throughput == 20
        assert engine._analysis_window == 12

    def test_analyze_empty_database(self, engine):
        """Test analysis with no data"""
        recommendations = engine.analyze_and_recommend("session1")
        # Should return empty list with no data
        assert isinstance(recommendations, list)

    def test_analyze_with_data(self, populated_db):
        """Test analysis with populated data"""
        engine = ServiceImprovementEngine(populated_db)
        recommendations = engine.analyze_and_recommend("session1")
        assert isinstance(recommendations, list)

    def test_get_quick_wins(self, populated_db):
        """Test quick wins retrieval"""
        engine = ServiceImprovementEngine(populated_db, target_wait_minutes=5)
        quick_wins = engine.get_quick_wins("session1", max_results=3)
        assert isinstance(quick_wins, list)
        assert len(quick_wins) <= 3

    def test_get_service_health_report(self, populated_db):
        """Test health report generation"""
        engine = ServiceImprovementEngine(populated_db)
        report = engine.get_service_health_report("session1")

        assert "timestamp" in report
        assert "session_id" in report
        assert "health_score" in report
        assert "health_status" in report
        assert "metrics" in report
        assert "recommendations" in report
        assert "summary" in report

    def test_acknowledge_recommendation(self, engine):
        """Test recommendation acknowledgment"""
        # Create a recommendation
        rec = engine._create_recommendation(
            category=ImprovementCategory.CAPACITY,
            priority=ImprovementPriority.HIGH,
            title="Test",
            description="Test description",
            rationale="Test rationale",
            suggested_actions=["Action 1"],
            expected_impact="Test impact",
            metrics_affected=["metric1"],
            evidence={},
        )

        # Store it
        engine._recommendations[rec.id] = rec

        # Acknowledge
        result = engine.acknowledge_recommendation(rec.id)
        assert result is True
        assert engine._recommendations[rec.id].status == ImprovementStatus.ACKNOWLEDGED

    def test_dismiss_recommendation(self, engine):
        """Test recommendation dismissal"""
        rec = engine._create_recommendation(
            category=ImprovementCategory.WORKFLOW,
            priority=ImprovementPriority.LOW,
            title="Test",
            description="Test",
            rationale="Test",
            suggested_actions=[],
            expected_impact="",
            metrics_affected=[],
            evidence={},
        )
        engine._recommendations[rec.id] = rec

        result = engine.dismiss_recommendation(rec.id, "Not relevant")
        assert result is True
        assert engine._recommendations[rec.id].status == ImprovementStatus.DISMISSED

    def test_health_score_calculation(self, engine):
        """Test health score calculation"""
        metrics = {"avg_wait_time": 25, "queue_size": 5, "served_today": 50}
        recommendations = []

        score = engine._calculate_health_score(metrics, recommendations)
        assert 0 <= score <= 100

    def test_health_score_with_critical_issues(self, engine):
        """Test health score decreases with critical recommendations"""
        metrics = {"avg_wait_time": 25, "queue_size": 5}

        critical_rec = ImprovementRecommendation(
            id="test",
            category=ImprovementCategory.CAPACITY,
            priority=ImprovementPriority.CRITICAL,
            title="Critical Issue",
            description="",
            rationale="",
            suggested_actions=[],
            expected_impact="",
            metrics_affected=[],
        )

        score = engine._calculate_health_score(metrics, [critical_rec])
        assert score < 100  # Score should be reduced

    def test_health_status_from_score(self, engine):
        """Test health status determination"""
        assert engine._health_status_from_score(95) == "excellent"
        assert engine._health_status_from_score(80) == "good"
        assert engine._health_status_from_score(65) == "fair"
        assert engine._health_status_from_score(45) == "needs_attention"
        assert engine._health_status_from_score(30) == "critical"


class TestImprovementRecommendation:
    """Tests for ImprovementRecommendation dataclass"""

    def test_to_dict(self):
        """Test serialization to dictionary"""
        rec = ImprovementRecommendation(
            id="REC-0001",
            category=ImprovementCategory.QUEUE_MANAGEMENT,
            priority=ImprovementPriority.HIGH,
            title="Test Recommendation",
            description="Test description",
            rationale="Test rationale",
            suggested_actions=["Action 1", "Action 2"],
            expected_impact="Expected impact",
            metrics_affected=["wait_time", "queue_size"],
        )

        result = rec.to_dict()

        assert result["id"] == "REC-0001"
        assert result["category"] == "queue_management"
        assert result["priority"] == "high"
        assert result["title"] == "Test Recommendation"
        assert len(result["suggested_actions"]) == 2


class TestServicePattern:
    """Tests for ServicePattern dataclass"""

    def test_to_dict(self):
        """Test pattern serialization"""
        now = datetime.utcnow()
        pattern = ServicePattern(
            pattern_type="recurring_high_demand",
            description="Test pattern",
            frequency=0.5,
            impact_score=75.0,
            trend="stable",
            data_points=10,
            first_seen=now - timedelta(hours=24),
            last_seen=now,
        )

        result = pattern.to_dict()

        assert result["pattern_type"] == "recurring_high_demand"
        assert result["frequency"] == 0.5
        assert result["impact_score"] == 75.0


class TestConvenienceFunctions:
    """Tests for module-level convenience functions"""

    def test_get_improvement_engine(self, db_connection):
        """Test global engine retrieval"""
        # Reset global
        module = sys.modules["tap_station.service_improvement"]
        module._improvement_engine = None

        engine = get_improvement_engine(db_connection)
        assert engine is not None

        # Should return same instance
        engine2 = get_improvement_engine(db_connection)
        assert engine is engine2

    def test_analyze_service(self, populated_db):
        """Test convenience analysis function"""
        module = sys.modules["tap_station.service_improvement"]
        module._improvement_engine = None

        report = analyze_service(populated_db, "session1")
        assert "health_score" in report
        assert "recommendations" in report
