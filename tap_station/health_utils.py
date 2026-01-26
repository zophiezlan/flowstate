"""
Health Check Utilities

This module provides centralized health check functionality for monitoring
system resources, hardware status, and service health.
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from enum import Enum

from .constants import HardwareDefaults, StorageUnits

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels"""

    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthResult:
    """Result of a health check"""

    status: HealthStatus
    message: str
    value: Optional[Any] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            "status": self.status.value,
            "message": self.message,
        }
        if self.value is not None:
            result["value"] = self.value
        if self.details:
            result["details"] = self.details
        return result


class HealthChecker:
    """
    Centralized health checking for system resources and hardware.

    This class consolidates health check logic from web_server.py and
    health_check.py to provide a single, reusable interface.
    """

    def __init__(
        self,
        temp_warning: int = HardwareDefaults.TEMP_WARNING,
        temp_critical: int = HardwareDefaults.TEMP_CRITICAL,
        disk_warning: int = HardwareDefaults.DISK_WARNING_PERCENT,
        disk_critical: int = HardwareDefaults.DISK_CRITICAL_PERCENT,
    ):
        """
        Initialize health checker with configurable thresholds.

        Args:
            temp_warning: Temperature warning threshold (Celsius)
            temp_critical: Temperature critical threshold (Celsius)
            disk_warning: Disk usage warning threshold (percent)
            disk_critical: Disk usage critical threshold (percent)
        """
        self.temp_warning = temp_warning
        self.temp_critical = temp_critical
        self.disk_warning = disk_warning
        self.disk_critical = disk_critical

    # =========================================================================
    # Temperature Monitoring
    # =========================================================================

    def check_temperature(self) -> HealthResult:
        """
        Check CPU temperature.

        Returns:
            HealthResult with temperature status
        """
        temp_path = HardwareDefaults.TEMP_PATH

        if not os.path.exists(temp_path):
            return HealthResult(
                status=HealthStatus.UNKNOWN,
                message="Temperature sensor not available",
                details={"path": temp_path},
            )

        try:
            with open(temp_path, "r") as f:
                temp_raw = f.read().strip()
                temp_c = int(temp_raw) / 1000.0

            if temp_c >= self.temp_critical:
                return HealthResult(
                    status=HealthStatus.CRITICAL,
                    message=f"CPU temperature critical: {temp_c:.1f}°C",
                    value=temp_c,
                    details={"threshold": self.temp_critical},
                )
            elif temp_c >= self.temp_warning:
                return HealthResult(
                    status=HealthStatus.WARNING,
                    message=f"CPU temperature high: {temp_c:.1f}°C",
                    value=temp_c,
                    details={"threshold": self.temp_warning},
                )
            else:
                return HealthResult(
                    status=HealthStatus.OK,
                    message=f"CPU temperature normal: {temp_c:.1f}°C",
                    value=temp_c,
                )

        except (ValueError, IOError) as e:
            logger.warning(f"Failed to read temperature: {e}")
            return HealthResult(
                status=HealthStatus.UNKNOWN, message=f"Failed to read temperature: {e}"
            )

    def get_temperature(self) -> Optional[float]:
        """
        Get current CPU temperature in Celsius.

        Returns:
            Temperature in Celsius, or None if unavailable
        """
        result = self.check_temperature()
        return result.value if result.status != HealthStatus.UNKNOWN else None

    # =========================================================================
    # Disk Space Monitoring
    # =========================================================================

    def check_disk_space(self, path: str = "/") -> HealthResult:
        """
        Check disk space usage.

        Args:
            path: Filesystem path to check

        Returns:
            HealthResult with disk space status
        """
        try:
            statvfs = os.statvfs(path)

            total_bytes = statvfs.f_frsize * statvfs.f_blocks
            free_bytes = statvfs.f_frsize * statvfs.f_bavail
            used_bytes = total_bytes - free_bytes

            total_gb = total_bytes / StorageUnits.BYTES_PER_GB
            free_gb = free_bytes / StorageUnits.BYTES_PER_GB
            used_percent = (used_bytes / total_bytes) * 100 if total_bytes > 0 else 0

            details = {
                "total_gb": round(total_gb, 2),
                "free_gb": round(free_gb, 2),
                "used_percent": round(used_percent, 1),
                "path": path,
            }

            if used_percent >= self.disk_critical:
                return HealthResult(
                    status=HealthStatus.CRITICAL,
                    message=f"Disk space critical: {used_percent:.1f}% used",
                    value=used_percent,
                    details=details,
                )
            elif used_percent >= self.disk_warning:
                return HealthResult(
                    status=HealthStatus.WARNING,
                    message=f"Disk space low: {used_percent:.1f}% used",
                    value=used_percent,
                    details=details,
                )
            else:
                return HealthResult(
                    status=HealthStatus.OK,
                    message=f"Disk space OK: {used_percent:.1f}% used, {free_gb:.1f}GB free",
                    value=used_percent,
                    details=details,
                )

        except OSError as e:
            logger.warning(f"Failed to check disk space: {e}")
            return HealthResult(
                status=HealthStatus.UNKNOWN, message=f"Failed to check disk space: {e}"
            )

    def get_disk_usage(self, path: str = "/") -> Tuple[float, float, float]:
        """
        Get disk usage statistics.

        Args:
            path: Filesystem path to check

        Returns:
            Tuple of (total_gb, free_gb, used_percent)
        """
        result = self.check_disk_space(path)
        if result.details:
            return (
                result.details.get("total_gb", 0),
                result.details.get("free_gb", 0),
                result.details.get("used_percent", 0),
            )
        return (0, 0, 0)

    # =========================================================================
    # Raspberry Pi Throttling Detection
    # =========================================================================

    def check_throttling(self) -> HealthResult:
        """
        Check for Raspberry Pi throttling conditions.

        Throttle flags:
        - Bit 0: Under-voltage detected
        - Bit 1: Arm frequency capped
        - Bit 2: Currently throttled
        - Bit 3: Soft temperature limit active

        Returns:
            HealthResult with throttling status
        """
        throttle_path = HardwareDefaults.THROTTLE_PATH

        if not os.path.exists(throttle_path):
            return HealthResult(
                status=HealthStatus.UNKNOWN,
                message="Throttle status not available (not a Raspberry Pi?)",
            )

        try:
            with open(throttle_path, "r") as f:
                throttle_hex = f.read().strip()
                throttle_value = int(throttle_hex, 16)

            issues = []

            # Check current status (lower 4 bits)
            if throttle_value & 0x1:
                issues.append("under-voltage")
            if throttle_value & 0x2:
                issues.append("frequency-capped")
            if throttle_value & 0x4:
                issues.append("throttled")
            if throttle_value & 0x8:
                issues.append("soft-temp-limit")

            # Check if issues occurred since boot (bits 16-19)
            historical = []
            if throttle_value & 0x10000:
                historical.append("under-voltage-occurred")
            if throttle_value & 0x20000:
                historical.append("frequency-capped-occurred")
            if throttle_value & 0x40000:
                historical.append("throttled-occurred")
            if throttle_value & 0x80000:
                historical.append("soft-temp-limit-occurred")

            details = {
                "raw_value": throttle_hex,
                "current_issues": issues,
                "historical_issues": historical,
            }

            if issues:
                return HealthResult(
                    status=HealthStatus.CRITICAL,
                    message=f"Throttling active: {', '.join(issues)}",
                    value=throttle_value,
                    details=details,
                )
            elif historical:
                return HealthResult(
                    status=HealthStatus.WARNING,
                    message=f"Past throttling detected: {', '.join(historical)}",
                    value=throttle_value,
                    details=details,
                )
            else:
                return HealthResult(
                    status=HealthStatus.OK,
                    message="No throttling detected",
                    value=throttle_value,
                    details=details,
                )

        except (ValueError, IOError) as e:
            logger.warning(f"Failed to read throttle status: {e}")
            return HealthResult(
                status=HealthStatus.UNKNOWN,
                message=f"Failed to read throttle status: {e}",
            )

    def is_throttled(self) -> bool:
        """
        Check if system is currently throttled.

        Returns:
            True if currently experiencing throttling
        """
        result = self.check_throttling()
        return result.status == HealthStatus.CRITICAL

    # =========================================================================
    # I2C Device Detection
    # =========================================================================

    def check_i2c_device(self, bus: int, address: int) -> HealthResult:
        """
        Check if an I2C device is present.

        Args:
            bus: I2C bus number
            address: I2C device address

        Returns:
            HealthResult with device status
        """
        try:
            import smbus2

            bus_obj = smbus2.SMBus(bus)
            try:
                bus_obj.read_byte(address)
                bus_obj.close()
                return HealthResult(
                    status=HealthStatus.OK,
                    message=f"I2C device found at 0x{address:02X} on bus {bus}",
                    details={"bus": bus, "address": hex(address)},
                )
            except OSError:
                bus_obj.close()
                return HealthResult(
                    status=HealthStatus.CRITICAL,
                    message=f"I2C device not responding at 0x{address:02X} on bus {bus}",
                    details={"bus": bus, "address": hex(address)},
                )
        except ImportError:
            return HealthResult(
                status=HealthStatus.UNKNOWN,
                message="smbus2 not installed - cannot check I2C devices",
            )
        except Exception as e:
            return HealthResult(
                status=HealthStatus.CRITICAL,
                message=f"I2C error: {e}",
                details={"bus": bus, "address": hex(address), "error": str(e)},
            )

    # =========================================================================
    # Database Health
    # =========================================================================

    def check_database(self, db_path: str) -> HealthResult:
        """
        Check database file health.

        Args:
            db_path: Path to SQLite database file

        Returns:
            HealthResult with database status
        """
        if not os.path.exists(db_path):
            return HealthResult(
                status=HealthStatus.WARNING,
                message=f"Database file not found: {db_path}",
                details={"path": db_path},
            )

        try:
            import sqlite3

            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.execute("SELECT COUNT(*) FROM events")
            count = cursor.fetchone()[0]
            conn.close()

            file_size = os.path.getsize(db_path)
            size_mb = file_size / StorageUnits.BYTES_PER_MB

            return HealthResult(
                status=HealthStatus.OK,
                message=f"Database OK: {count} events, {size_mb:.1f}MB",
                value=count,
                details={
                    "path": db_path,
                    "event_count": count,
                    "size_mb": round(size_mb, 2),
                },
            )

        except sqlite3.Error as e:
            return HealthResult(
                status=HealthStatus.CRITICAL,
                message=f"Database error: {e}",
                details={"path": db_path, "error": str(e)},
            )
        except Exception as e:
            return HealthResult(
                status=HealthStatus.CRITICAL,
                message=f"Failed to check database: {e}",
                details={"path": db_path, "error": str(e)},
            )

    # =========================================================================
    # Comprehensive Health Check
    # =========================================================================

    def get_full_status(self, db_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Get comprehensive health status for all monitored components.

        Args:
            db_path: Optional database path to check

        Returns:
            Dictionary with status of all components
        """
        status = {
            "temperature": self.check_temperature().to_dict(),
            "disk": self.check_disk_space().to_dict(),
            "throttling": self.check_throttling().to_dict(),
        }

        if db_path:
            status["database"] = self.check_database(db_path).to_dict()

        # Calculate overall status
        statuses = [
            HealthStatus(status["temperature"]["status"]),
            HealthStatus(status["disk"]["status"]),
            HealthStatus(status["throttling"]["status"]),
        ]
        if db_path:
            statuses.append(HealthStatus(status["database"]["status"]))

        if any(s == HealthStatus.CRITICAL for s in statuses):
            overall = HealthStatus.CRITICAL
        elif any(s == HealthStatus.WARNING for s in statuses):
            overall = HealthStatus.WARNING
        elif all(s == HealthStatus.OK for s in statuses):
            overall = HealthStatus.OK
        else:
            overall = HealthStatus.UNKNOWN

        status["overall"] = overall.value

        return status


# =============================================================================
# Global Instance
# =============================================================================

_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get the global health checker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def configure_health_checker(
    temp_warning: int = HardwareDefaults.TEMP_WARNING,
    temp_critical: int = HardwareDefaults.TEMP_CRITICAL,
    disk_warning: int = HardwareDefaults.DISK_WARNING_PERCENT,
    disk_critical: int = HardwareDefaults.DISK_CRITICAL_PERCENT,
) -> HealthChecker:
    """
    Configure and return the global health checker instance.

    Args:
        temp_warning: Temperature warning threshold
        temp_critical: Temperature critical threshold
        disk_warning: Disk usage warning threshold
        disk_critical: Disk usage critical threshold

    Returns:
        Configured HealthChecker instance
    """
    global _health_checker
    _health_checker = HealthChecker(
        temp_warning=temp_warning,
        temp_critical=temp_critical,
        disk_warning=disk_warning,
        disk_critical=disk_critical,
    )
    return _health_checker
