"""Hardware monitor extension - Pi hardware status checks."""

import logging
import os
import subprocess
from datetime import datetime, timezone

from flask import jsonify

from tap_station.extension import Extension

logger = logging.getLogger(__name__)


class HardwareMonitorExtension(Extension):
    """Raspberry Pi hardware status monitoring."""

    name = "hardware_monitor"
    order = 50

    def on_api_routes(self, app, db, config):
        from tap_station.web_server import require_admin_auth

        @app.route("/api/control/hardware-status")
        @require_admin_auth
        def api_hardware_status():
            """Get hardware component status."""
            try:
                status = _get_hardware_status(config)
                return jsonify(status), 200
            except Exception as e:
                logger.error("Hardware status check failed: %s", e)
                return jsonify({"error": str(e)}), 500

        def _get_hardware_status(config):
            status = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "components": {},
            }

            # I2C Status
            try:
                i2c_exists = os.path.exists("/dev/i2c-1") or os.path.exists(
                    "/dev/i2c-0"
                )
                status["components"]["i2c"] = {
                    "status": "ok" if i2c_exists else "error",
                    "message": (
                        "I2C bus available" if i2c_exists else "I2C not found"
                    ),
                    "critical": True,
                }
            except Exception:
                status["components"]["i2c"] = {
                    "status": "unknown",
                    "message": "Cannot check",
                    "critical": True,
                }

            # GPIO Status
            try:
                import RPi.GPIO as GPIO

                status["components"]["gpio"] = {
                    "status": "ok",
                    "message": "GPIO available",
                    "details": {
                        "buzzer": (
                            f"GPIO {config.gpio_buzzer}"
                            if config.buzzer_enabled
                            else "Disabled"
                        ),
                        "green_led": (
                            f"GPIO {config.gpio_led_green}"
                            if config.led_enabled
                            else "Disabled"
                        ),
                        "red_led": (
                            f"GPIO {config.gpio_led_red}"
                            if config.led_enabled
                            else "Disabled"
                        ),
                    },
                    "critical": False,
                }
            except ImportError:
                status["components"]["gpio"] = {
                    "status": "warning",
                    "message": "Not on Raspberry Pi",
                    "critical": False,
                }
            except Exception as e:
                status["components"]["gpio"] = {
                    "status": "error",
                    "message": str(e),
                    "critical": False,
                }

            # RTC Status
            try:
                if os.path.exists("/dev/rtc0") or os.path.exists(
                    "/dev/rtc1"
                ):
                    result = subprocess.run(
                        ["sudo", "hwclock", "-r"],
                        capture_output=True, text=True, timeout=2,
                    )
                    if result.returncode == 0:
                        status["components"]["rtc"] = {
                            "status": "ok",
                            "message": "RTC available",
                            "time": result.stdout.strip(),
                            "critical": False,
                        }
                    else:
                        status["components"]["rtc"] = {
                            "status": "warning",
                            "message": "RTC not readable",
                            "critical": False,
                        }
                else:
                    status["components"]["rtc"] = {
                        "status": "info",
                        "message": "No RTC detected (using system time)",
                        "critical": False,
                    }
            except Exception:
                status["components"]["rtc"] = {
                    "status": "info",
                    "message": "RTC check unavailable",
                    "critical": False,
                }

            # Temperature
            try:
                result = subprocess.run(
                    ["vcgencmd", "measure_temp"],
                    capture_output=True, text=True, timeout=2,
                )
                if result.returncode == 0:
                    temp_str = (
                        result.stdout.strip().split("=")[1].replace("'C", "")
                    )
                    temp = float(temp_str)
                    temp_status = (
                        "ok" if temp < 70
                        else ("warning" if temp < 80 else "error")
                    )
                    status["components"]["temperature"] = {
                        "status": temp_status,
                        "message": f"{temp}\u00b0C",
                        "value": temp,
                        "critical": temp >= 80,
                    }
                else:
                    status["components"]["temperature"] = {
                        "status": "unknown",
                        "message": "Cannot read temperature",
                        "critical": False,
                    }
            except Exception:
                status["components"]["temperature"] = {
                    "status": "unknown",
                    "message": "Temperature unavailable",
                    "critical": False,
                }

            # Under-voltage check
            try:
                result = subprocess.run(
                    ["vcgencmd", "get_throttled"],
                    capture_output=True, text=True, timeout=2,
                )
                if result.returncode == 0:
                    throttled = result.stdout.strip().split("=")[1]
                    is_throttled = throttled != "0x0"
                    status["components"]["power"] = {
                        "status": "error" if is_throttled else "ok",
                        "message": (
                            "Under-voltage detected!"
                            if is_throttled
                            else "Power OK"
                        ),
                        "throttled_hex": throttled,
                        "critical": is_throttled,
                    }
                else:
                    status["components"]["power"] = {
                        "status": "unknown",
                        "message": "Cannot check power",
                        "critical": False,
                    }
            except Exception:
                status["components"]["power"] = {
                    "status": "unknown",
                    "message": "Power check unavailable",
                    "critical": False,
                }

            # Disk space
            try:
                stat = os.statvfs("/")
                free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
                total_gb = (stat.f_blocks * stat.f_frsize) / (1024**3)
                percent_used = ((total_gb - free_gb) / total_gb) * 100

                disk_status = (
                    "ok" if percent_used < 80
                    else ("warning" if percent_used < 90 else "error")
                )
                status["components"]["disk"] = {
                    "status": disk_status,
                    "message": f"{free_gb:.1f} GB free of {total_gb:.1f} GB",
                    "percent_used": round(percent_used, 1),
                    "free_gb": round(free_gb, 1),
                    "critical": percent_used >= 90,
                }
            except Exception:
                status["components"]["disk"] = {
                    "status": "unknown",
                    "message": "Disk info unavailable",
                    "critical": False,
                }

            return status


extension = HardwareMonitorExtension()
