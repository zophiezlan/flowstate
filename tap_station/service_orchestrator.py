"""
Service Orchestrator

This module provides centralized coordination of all quality, integrity, and
customization modules. It serves as the integration layer that wires together:

- Service Improvement Engine (recommendations)
- Adaptive Thresholds (context-aware alerting)
- Custom SLOs (service level objectives)
- Integration Hooks (webhooks and external systems)
- Access Control (RBAC)
- Workflow Validators (per-stage validation)
- Dynamic Configuration (hot reload)

Key Features:
- Centralized initialization and lifecycle management
- Cross-module event coordination
- Unified configuration loading
- Health monitoring across all subsystems
- Service design principles applied holistically

Usage:
    orchestrator = ServiceOrchestrator(database_connection)
    orchestrator.initialize()

    # Access individual managers
    orchestrator.improvement_engine.get_service_health_report(session_id)
    orchestrator.slo_manager.evaluate_all_slos(session_id)
"""

import logging
import sqlite3
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

from .datetime_utils import utc_now

# Import all managers
from .service_improvement import (
    ServiceImprovementEngine,
)
from .adaptive_thresholds import (
    AdaptiveThresholdManager,
    ThresholdChecker,
)
from .custom_slo import (
    CustomSLOManager,
    load_slos_from_config,
)
from .integration_hooks import (
    IntegrationHooksManager,
    IntegrationEventType,
    load_webhooks_from_config,
)
from .access_control import (
    AccessControlManager,
    Permission,
    load_roles_from_config,
)
from .workflow_validators import (
    WorkflowValidationManager,
    ValidationAction,
    ValidationSeverity,
    load_validators_from_config,
)
from .dynamic_config import (
    DynamicConfigurationManager,
    ConfigurationSubscriber,
)

logger = logging.getLogger(__name__)


@dataclass
class SubsystemHealth:
    """Health status of a subsystem"""
    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    last_check: datetime = field(default_factory=utc_now)


class ServiceOrchestrator(ConfigurationSubscriber):
    """
    Central orchestrator for all service quality and customization systems.

    This class:
    - Initializes and manages all subsystem managers
    - Coordinates cross-subsystem events
    - Provides unified health monitoring
    - Handles configuration updates
    - Exposes a clean API for the application layer
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        config_path: Optional[str] = None,
        auto_reload_config: bool = False
    ):
        """
        Initialize the service orchestrator.

        Args:
            conn: Database connection
            config_path: Optional path to configuration file
            auto_reload_config: Enable configuration hot reload
        """
        self._conn = conn
        self._config_path = config_path
        self._auto_reload = auto_reload_config
        self._initialized = False

        # Managers (initialized in initialize())
        self._improvement_engine: Optional[ServiceImprovementEngine] = None
        self._threshold_manager: Optional[AdaptiveThresholdManager] = None
        self._threshold_checker: Optional[ThresholdChecker] = None
        self._slo_manager: Optional[CustomSLOManager] = None
        self._hooks_manager: Optional[IntegrationHooksManager] = None
        self._access_manager: Optional[AccessControlManager] = None
        self._validation_manager: Optional[WorkflowValidationManager] = None
        self._config_manager: Optional[DynamicConfigurationManager] = None

        # Configuration
        self._config: Dict[str, Any] = {}

    def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize all subsystems.

        Args:
            config: Optional configuration dictionary (overrides file)
        """
        if self._initialized:
            logger.warning("Service orchestrator already initialized")
            return

        logger.info("Initializing service orchestrator...")

        # Initialize configuration manager first
        self._config_manager = DynamicConfigurationManager(
            config_path=self._config_path,
            auto_reload=self._auto_reload
        )
        self._config_manager.subscribe(self)

        # Load configuration
        if config:
            self._config_manager.load_from_dict(config)
        self._config = self._config_manager.get() or {}

        # Initialize all managers
        self._init_improvement_engine()
        self._init_threshold_manager()
        self._init_slo_manager()
        self._init_hooks_manager()
        self._init_access_manager()
        self._init_validation_manager()

        # Wire up cross-module events
        self._setup_event_coordination()

        self._initialized = True
        logger.info("Service orchestrator initialized successfully")

    def _init_improvement_engine(self) -> None:
        """Initialize the service improvement engine"""
        improvement_config = self._config.get("service_improvement", {})

        self._improvement_engine = ServiceImprovementEngine(
            conn=self._conn,
            target_wait_minutes=improvement_config.get("target_wait_minutes", 30),
            target_throughput_per_hour=improvement_config.get("target_throughput_per_hour", 12),
            analysis_window_hours=improvement_config.get("analysis_window_hours", 24)
        )
        logger.debug("Service improvement engine initialized")

    def _init_threshold_manager(self) -> None:
        """Initialize the adaptive threshold manager"""
        threshold_config = self._config.get("adaptive_thresholds", {})
        base_thresholds = threshold_config.get("base_thresholds", {})

        self._threshold_manager = AdaptiveThresholdManager(
            conn=self._conn,
            base_thresholds=base_thresholds
        )
        self._threshold_checker = ThresholdChecker(self._threshold_manager)

        # Load custom rules
        for rule_config in threshold_config.get("rules", []):
            self._add_threshold_rule_from_config(rule_config)

        logger.debug("Adaptive threshold manager initialized")

    def _init_slo_manager(self) -> None:
        """Initialize the SLO manager"""
        slo_config = self._config.get("slos", self._config.get("service_level_objectives", {}))
        target_wait = self._config.get("capacity", {}).get("target_wait_minutes", 30)

        self._slo_manager = CustomSLOManager(
            conn=self._conn,
            target_wait_minutes=target_wait
        )

        # Load custom SLOs from config
        # Normalize SLO configuration into a canonical {"slos": [...]} format
        normalized_slo_config: Dict[str, Any] = {"slos": []}
        if isinstance(slo_config, list):
            normalized_slo_config = {"slos": slo_config}
        elif isinstance(slo_config, dict):
            if "definitions" in slo_config:
                normalized_slo_config = {"slos": slo_config["definitions"]}
            elif "slos" in slo_config:
                normalized_slo_config = {"slos": slo_config["slos"]}

        # Load custom SLOs from normalized config
        if normalized_slo_config.get("slos"):
            load_slos_from_config(normalized_slo_config, self._slo_manager)

        logger.debug("SLO manager initialized")

    def _init_hooks_manager(self) -> None:
        """Initialize the integration hooks manager"""
        integrations_config = self._config.get("integrations", {})

        self._hooks_manager = IntegrationHooksManager(
            conn=self._conn,
            async_delivery=integrations_config.get("async_delivery", True)
        )

        # Load webhooks
        load_webhooks_from_config(integrations_config, self._hooks_manager)

        logger.debug("Integration hooks manager initialized")

    def _init_access_manager(self) -> None:
        """Initialize the access control manager"""
        access_config = self._config.get("access_control", {})
        session_timeout = access_config.get("session_timeout_minutes", 60)

        self._access_manager = AccessControlManager(
            conn=self._conn,
            session_timeout_minutes=session_timeout,
            require_authentication=access_config.get("require_authentication", False)
        )

        # Load custom roles
        load_roles_from_config(self._config, self._access_manager)

        logger.debug("Access control manager initialized")

    def _init_validation_manager(self) -> None:
        """Initialize the workflow validation manager"""
        validation_config = self._config.get("workflow", {}).get("validation", {})

        self._validation_manager = WorkflowValidationManager(
            conn=self._conn,
            fail_on_error=validation_config.get("fail_on_error", True),
            fail_on_warning=validation_config.get("fail_on_warning", False)
        )

        # Load validator configurations
        load_validators_from_config(self._config, self._validation_manager)

        logger.debug("Workflow validation manager initialized")

    def _setup_event_coordination(self) -> None:
        """Set up cross-module event coordination"""
        if not self._hooks_manager:
            return

        # Register handlers to emit integration events for important actions
        # This allows external systems to receive notifications

        # Validation warnings/errors trigger alerts
        def on_validation_complete(ctx, results):
            errors = [r for r in results if r.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)]
            if errors:
                self._hooks_manager.emit_alert(
                    alert_type="validation_error",
                    severity="warning",
                    message=f"Validation issues for {ctx.token_id}",
                    details={
                        "token_id": ctx.token_id,
                        "stage": ctx.stage,
                        "errors": [e.to_dict() for e in errors]
                    }
                )

        if self._validation_manager:
            self._validation_manager.add_post_hook(on_validation_complete)

        logger.debug("Event coordination configured")

    def _add_threshold_rule_from_config(self, rule_config: Dict[str, Any]) -> None:
        """Add a threshold rule from configuration"""
        # This would parse the config and add appropriate rules
        # Simplified implementation
        pass

    # =========================================================================
    # Configuration Subscriber Interface
    # =========================================================================

    def on_config_changed(self, old_config, new_config, changes):
        """Handle configuration changes"""
        logger.info(f"Configuration changed: {len(changes)} changes detected")

        # Emit event for external systems
        if self._hooks_manager:
            self._hooks_manager.emit(
                IntegrationEventType.HEALTH_CHECK,
                {
                    "type": "config_changed",
                    "changes": [c.to_dict() for c in changes]
                }
            )

        # Update internal config reference
        self._config = new_config

        # Reconfigure subsystems as needed
        # In a more complex implementation, this would selectively
        # reconfigure only the affected subsystems

    def on_config_reloaded(self, config):
        """Handle configuration reload"""
        logger.info("Configuration reloaded")
        self._config = config

    # =========================================================================
    # Public API - Properties
    # =========================================================================

    @property
    def improvement_engine(self) -> ServiceImprovementEngine:
        """Access the service improvement engine"""
        self._ensure_initialized()
        return self._improvement_engine

    @property
    def threshold_manager(self) -> AdaptiveThresholdManager:
        """Access the adaptive threshold manager"""
        self._ensure_initialized()
        return self._threshold_manager

    @property
    def threshold_checker(self) -> ThresholdChecker:
        """Access the threshold checker"""
        self._ensure_initialized()
        return self._threshold_checker

    @property
    def slo_manager(self) -> CustomSLOManager:
        """Access the SLO manager"""
        self._ensure_initialized()
        return self._slo_manager

    @property
    def hooks_manager(self) -> IntegrationHooksManager:
        """Access the integration hooks manager"""
        self._ensure_initialized()
        return self._hooks_manager

    @property
    def access_manager(self) -> AccessControlManager:
        """Access the access control manager"""
        self._ensure_initialized()
        return self._access_manager

    @property
    def validation_manager(self) -> WorkflowValidationManager:
        """Access the workflow validation manager"""
        self._ensure_initialized()
        return self._validation_manager

    @property
    def config_manager(self) -> DynamicConfigurationManager:
        """Access the configuration manager"""
        self._ensure_initialized()
        return self._config_manager

    def _ensure_initialized(self) -> None:
        """Ensure the orchestrator is initialized"""
        if not self._initialized:
            raise RuntimeError("Service orchestrator not initialized. Call initialize() first.")

    # =========================================================================
    # Public API - Service Operations
    # =========================================================================

    def validate_event(
        self,
        action: ValidationAction,
        stage: str,
        token_id: str,
        session_id: str,
        **kwargs
    ) -> tuple:
        """
        Validate a workflow event.

        Args:
            action: Validation action type
            stage: Target stage
            token_id: Token/card ID
            session_id: Session ID
            **kwargs: Additional validation context

        Returns:
            Tuple of (is_valid, validation_results)
        """
        self._ensure_initialized()
        return self._validation_manager.validate(
            action=action,
            stage=stage,
            token_id=token_id,
            session_id=session_id,
            **kwargs
        )

    def emit_tap_event(
        self,
        stage: str,
        token_id: str,
        session_id: str,
        **extra_data
    ) -> None:
        """
        Emit an integration event for a tap.

        Args:
            stage: Workflow stage
            token_id: Token/card ID
            session_id: Session ID
            **extra_data: Additional event data
        """
        self._ensure_initialized()
        if self._hooks_manager:
            self._hooks_manager.emit_tap_event(stage, token_id, session_id, extra_data)

    def check_permission(
        self,
        user_id: Optional[str],
        permission: Permission
    ) -> bool:
        """
        Check if a user has a permission.

        Args:
            user_id: User ID (None for anonymous)
            permission: Permission to check

        Returns:
            True if permission granted
        """
        self._ensure_initialized()
        decision = self._access_manager.check_permission(user_id, permission)
        return decision.allowed

    def get_service_dashboard(self, session_id: str) -> Dict[str, Any]:
        """
        Get a comprehensive service dashboard.

        Combines data from multiple subsystems for a unified view.

        Args:
            session_id: Session to analyze

        Returns:
            Dashboard data
        """
        self._ensure_initialized()

        # Get health report from improvement engine
        health_report = self._improvement_engine.get_service_health_report(session_id)

        # Get SLO summary
        slo_summary = self._slo_manager.get_slo_summary(session_id)

        # Get integration health
        integration_health = self._hooks_manager.get_health_status()

        return {
            "timestamp": utc_now().isoformat(),
            "session_id": session_id,
            "service_health": {
                "score": health_report["health_score"],
                "status": health_report["health_status"],
                "summary": health_report["summary"]
            },
            "slo_compliance": {
                "status": slo_summary["overall_status"],
                "compliance_rate": slo_summary["compliance_rate"],
                "met": slo_summary["met"],
                "breached": slo_summary["breached"]
            },
            "recommendations": {
                "critical": len(health_report["recommendations"]["critical"]),
                "high": len(health_report["recommendations"]["high"]),
                "top_recommendations": (
                    health_report["recommendations"]["critical"][:2] +
                    health_report["recommendations"]["high"][:2]
                )
            },
            "thresholds": {
                "active_rules": self._threshold_manager.get_active_rules()
            },
            "integrations": {
                "status": integration_health["status"],
                "webhooks": integration_health["enabled_webhooks"]
            },
            "metrics": health_report["metrics"]
        }

    def get_full_health_status(self) -> Dict[str, Any]:
        """
        Get health status of all subsystems.

        Returns:
            Comprehensive health status
        """
        self._ensure_initialized()

        subsystems = []

        # Check each subsystem
        subsystems.append(SubsystemHealth(
            name="improvement_engine",
            status="healthy" if self._improvement_engine else "unhealthy",
            message="Service improvement engine operational"
        ))

        subsystems.append(SubsystemHealth(
            name="threshold_manager",
            status="healthy" if self._threshold_manager else "unhealthy",
            message="Adaptive threshold manager operational"
        ))

        subsystems.append(SubsystemHealth(
            name="slo_manager",
            status="healthy" if self._slo_manager else "unhealthy",
            message="SLO manager operational",
            details={"slo_count": len(self._slo_manager.list_slos())}
        ))

        if self._hooks_manager:
            hooks_health = self._hooks_manager.get_health_status()
            subsystems.append(SubsystemHealth(
                name="hooks_manager",
                status=hooks_health["status"],
                message=f"{hooks_health['enabled_webhooks']} webhooks configured",
                details=hooks_health
            ))

        subsystems.append(SubsystemHealth(
            name="access_manager",
            status="healthy" if self._access_manager else "unhealthy",
            message="Access control operational"
        ))

        subsystems.append(SubsystemHealth(
            name="validation_manager",
            status="healthy" if self._validation_manager else "unhealthy",
            message="Workflow validation operational",
            details={"validators": len(self._validation_manager.list_validators())}
        ))

        subsystems.append(SubsystemHealth(
            name="config_manager",
            status="healthy" if self._config_manager else "unhealthy",
            message=f"Configuration v{self._config_manager.get_current_version()}"
        ))

        # Calculate overall status
        statuses = [s.status for s in subsystems]
        if "unhealthy" in statuses:
            overall = "unhealthy"
        elif "degraded" in statuses:
            overall = "degraded"
        else:
            overall = "healthy"

        return {
            "timestamp": utc_now().isoformat(),
            "overall_status": overall,
            "subsystems": [
                {
                    "name": s.name,
                    "status": s.status,
                    "message": s.message,
                    "details": s.details
                }
                for s in subsystems
            ]
        }

    def shutdown(self) -> None:
        """Shutdown all subsystems gracefully"""
        logger.info("Shutting down service orchestrator...")

        if self._hooks_manager:
            self._hooks_manager.shutdown()

        if self._config_manager:
            self._config_manager.stop_auto_reload()

        self._initialized = False
        logger.info("Service orchestrator shutdown complete")


# =============================================================================
# Global Instance
# =============================================================================

_orchestrator: Optional[ServiceOrchestrator] = None


def get_orchestrator(
    conn: Optional[sqlite3.Connection] = None,
    config_path: Optional[str] = None
) -> ServiceOrchestrator:
    """Get or create the global service orchestrator"""
    global _orchestrator
    if _orchestrator is None:
        if conn is None:
            raise ValueError("Database connection required for first initialization")
        _orchestrator = ServiceOrchestrator(conn, config_path)
    return _orchestrator


def initialize_orchestrator(
    conn: sqlite3.Connection,
    config_path: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> ServiceOrchestrator:
    """Initialize the global orchestrator"""
    global _orchestrator
    _orchestrator = ServiceOrchestrator(conn, config_path)
    _orchestrator.initialize(config)
    return _orchestrator
