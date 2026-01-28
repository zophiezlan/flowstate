"""Health monitoring for tap station service.

Provides disk space monitoring, NFC reader health checks, and
comprehensive service health status for operational visibility.
"""

import logging
import os
import shutil
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Monitors service health including disk space and NFC reader status."""

    def __init__(
        self,
        disk_warning_percent: int = 80,
        disk_critical_percent: int = 90,
        temp_warning_celsius: int = 70,
        temp_critical_celsius: int = 80,
    ):
        """
        Initialize health monitor.

        Args:
            disk_warning_percent: Disk usage threshold for warning
            disk_critical_percent: Disk usage threshold for critical alert
            temp_warning_celsius: CPU temp threshold for warning
            temp_critical_celsius: CPU temp threshold for critical alert
        """
        self.disk_warning_percent = disk_warning_percent
        self.disk_critical_percent = disk_critical_percent
        self.temp_warning_celsius = temp_warning_celsius
        self.temp_critical_celsius = temp_critical_celsius
        self._last_check: Optional[datetime] = None

    def check_disk_space(self, path: str = "/") -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check if disk space is adequate.

        Args:
            path: Path to check disk space for (defaults to root)

        Returns:
            Tuple of (is_ok, message, details_dict)
        """
        try:
            usage = shutil.disk_usage(path)
            total_gb = usage.total / (1024 ** 3)
            used_gb = usage.used / (1024 ** 3)
            free_gb = usage.free / (1024 ** 3)
            percent_used = (usage.used / usage.total) * 100

            details = {
                "total_gb": round(total_gb, 2),
                "used_gb": round(used_gb, 2),
                "free_gb": round(free_gb, 2),
                "percent_used": round(percent_used, 1),
            }

            if percent_used >= self.disk_critical_percent:
                return (
                    False,
                    f"CRITICAL: Disk {percent_used:.1f}% full ({free_gb:.1f}GB free)",
                    details,
                )
            elif percent_used >= self.disk_warning_percent:
                return (
                    True,
                    f"WARNING: Disk {percent_used:.1f}% full ({free_gb:.1f}GB free)",
                    details,
                )
            else:
                return (
                    True,
                    f"OK: Disk {percent_used:.1f}% full ({free_gb:.1f}GB free)",
                    details,
                )

        except Exception as e:
            logger.error(f"Failed to check disk space: {e}")
            return (False, f"ERROR: Could not check disk space: {e}", {})

    def check_cpu_temperature(self) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check CPU temperature (Raspberry Pi specific).

        Returns:
            Tuple of (is_ok, message, details_dict)
        """
        try:
            # Raspberry Pi stores CPU temp in this file
            temp_file = "/sys/class/thermal/thermal_zone0/temp"
            if os.path.exists(temp_file):
                with open(temp_file, "r") as f:
                    temp_millicelsius = int(f.read().strip())
                    temp_celsius = temp_millicelsius / 1000

                details = {"temp_celsius": round(temp_celsius, 1)}

                if temp_celsius >= self.temp_critical_celsius:
                    return (
                        False,
                        f"CRITICAL: CPU temperature {temp_celsius:.1f}°C",
                        details,
                    )
                elif temp_celsius >= self.temp_warning_celsius:
                    return (
                        True,
                        f"WARNING: CPU temperature {temp_celsius:.1f}°C",
                        details,
                    )
                else:
                    return (
                        True,
                        f"OK: CPU temperature {temp_celsius:.1f}°C",
                        details,
                    )
            else:
                # Not running on Raspberry Pi
                return (True, "N/A: Not running on Raspberry Pi", {})

        except Exception as e:
            logger.debug(f"Could not read CPU temperature: {e}")
            return (True, f"N/A: Could not read temperature: {e}", {})

    def check_database(self, db_path: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check database file health.

        Args:
            db_path: Path to SQLite database file

        Returns:
            Tuple of (is_ok, message, details_dict)
        """
        try:
            if not os.path.exists(db_path):
                return (False, "ERROR: Database file not found", {"exists": False})

            # Check file size
            size_bytes = os.path.getsize(db_path)
            size_mb = size_bytes / (1024 * 1024)

            # Check for WAL file
            wal_path = db_path + "-wal"
            has_wal = os.path.exists(wal_path)
            wal_size_mb = 0
            if has_wal:
                wal_size_mb = os.path.getsize(wal_path) / (1024 * 1024)

            details = {
                "exists": True,
                "size_mb": round(size_mb, 2),
                "has_wal": has_wal,
                "wal_size_mb": round(wal_size_mb, 2),
            }

            # Large WAL file might indicate issues
            if wal_size_mb > 50:
                return (
                    True,
                    f"WARNING: Large WAL file ({wal_size_mb:.1f}MB)",
                    details,
                )

            return (True, f"OK: Database {size_mb:.1f}MB", details)

        except Exception as e:
            logger.error(f"Failed to check database: {e}")
            return (False, f"ERROR: Could not check database: {e}", {})

    def get_health_status(
        self,
        db_path: Optional[str] = None,
        nfc_reader: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive health status.

        Args:
            db_path: Optional path to database file
            nfc_reader: Optional NFCReader instance to check

        Returns:
            Dict with health status for all components
        """
        self._last_check = datetime.utcnow()

        status = {
            "timestamp": self._last_check.isoformat(),
            "overall": "ok",
            "checks": {},
        }

        # Disk space
        disk_ok, disk_msg, disk_details = self.check_disk_space()
        status["checks"]["disk"] = {
            "ok": disk_ok,
            "message": disk_msg,
            **disk_details,
        }
        if not disk_ok:
            status["overall"] = "critical"
        elif "WARNING" in disk_msg:
            status["overall"] = "warning"

        # CPU temperature
        temp_ok, temp_msg, temp_details = self.check_cpu_temperature()
        status["checks"]["cpu_temp"] = {
            "ok": temp_ok,
            "message": temp_msg,
            **temp_details,
        }
        if not temp_ok and status["overall"] != "critical":
            status["overall"] = "critical"
        elif "WARNING" in temp_msg and status["overall"] == "ok":
            status["overall"] = "warning"

        # Database
        if db_path:
            db_ok, db_msg, db_details = self.check_database(db_path)
            status["checks"]["database"] = {
                "ok": db_ok,
                "message": db_msg,
                **db_details,
            }
            if not db_ok and status["overall"] != "critical":
                status["overall"] = "critical"

        # NFC reader (basic connectivity check)
        if nfc_reader:
            try:
                # Try a simple operation to verify reader is responsive
                nfc_ok = hasattr(nfc_reader, "conn") and nfc_reader.connected
                status["checks"]["nfc_reader"] = {
                    "ok": nfc_ok,
                    "message": "OK: NFC reader connected" if nfc_ok else "ERROR: NFC reader not connected",
                }
                if not nfc_ok and status["overall"] != "critical":
                    status["overall"] = "critical"
            except Exception as e:
                status["checks"]["nfc_reader"] = {
                    "ok": False,
                    "message": f"ERROR: NFC reader check failed: {e}",
                }

        return status

    def log_health_status(
        self,
        db_path: Optional[str] = None,
        nfc_reader: Optional[Any] = None,
    ) -> None:
        """Log health status at appropriate log levels."""
        status = self.get_health_status(db_path, nfc_reader)

        if status["overall"] == "critical":
            logger.critical(f"Health check CRITICAL: {status}")
        elif status["overall"] == "warning":
            logger.warning(f"Health check WARNING: {status}")
        else:
            logger.info(f"Health check OK")
