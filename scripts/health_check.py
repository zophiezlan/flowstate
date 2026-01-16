#!/usr/bin/env python3
"""
Health Check Dashboard

Quick system status check for NFC Tap Logger.
Shows hardware status, service status, disk space, and recent activity.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import subprocess
from datetime import datetime
from pathlib import Path


class HealthCheck:
    """System health check dashboard"""

    def __init__(self):
        self.checks = []
        self.warnings = []
        self.errors = []

    def print_header(self, title):
        """Print formatted section header"""
        print(f"\n{'=' * 60}")
        print(f"{title}")
        print(f"{'=' * 60}\n")

    def check_status(self, name, status, message="", level="info"):
        """Record and print check status"""
        if status:
            symbol = "✓"
        else:
            symbol = "✗"
            if level == "error":
                self.errors.append(name)
            elif level == "warning":
                self.warnings.append(name)

        print(f"{symbol} {name:.<45} {'OK' if status else 'FAIL'}")
        if message:
            print(f"  {message}")

        return status

    def check_config(self):
        """Check configuration file"""
        self.print_header("Configuration")

        config_exists = Path("config.yaml").exists()
        self.check_status("Configuration file exists", config_exists, level="error")

        if config_exists:
            try:
                import yaml

                with open("config.yaml") as f:
                    config = yaml.safe_load(f)

                self.check_status("Config file is valid YAML", True)

                # Check required fields
                required = ["device_id", "stage", "session_id"]
                for field in required:
                    has_field = field in config
                    self.check_status(
                        f"  Has '{field}' field", has_field, level="error"
                    )

                # Show current config
                if all(field in config for field in required):
                    print(f"\n  Device ID:  {config['device_id']}")
                    print(f"  Stage:      {config['stage']}")
                    print(f"  Session ID: {config['session_id']}")

            except Exception as e:
                self.check_status("Config file parsing", False, str(e), level="error")

    def check_i2c(self):
        """Check I2C hardware"""
        self.print_header("I2C Hardware")

        # Check I2C device
        i2c_exists = os.path.exists("/dev/i2c-1") or os.path.exists("/dev/i2c-0")
        self.check_status("I2C device exists", i2c_exists, level="error")

        if not i2c_exists:
            print("  To fix: bash scripts/enable_i2c.sh")
            return

        # Check if PN532 detected
        try:
            i2c_bus = 1 if os.path.exists("/dev/i2c-1") else 0
            result = subprocess.run(
                ["i2cdetect", "-y", str(i2c_bus)],
                capture_output=True,
                text=True,
                timeout=5,
            )

            pn532_found = "24" in result.stdout
            self.check_status("PN532 detected at 0x24", pn532_found, level="error")

            if not pn532_found:
                print("  Check PN532 wiring and I2C mode")

        except FileNotFoundError:
            self.check_status(
                "i2c-tools installed",
                False,
                "Run: sudo apt-get install i2c-tools",
                level="warning",
            )
        except subprocess.TimeoutExpired:
            self.check_status(
                "I2C bus responding", False, "I2C bus timeout", level="error"
            )
        except Exception as e:
            self.check_status("I2C scan", False, str(e), level="error")

    def check_nfc(self):
        """Check NFC reader"""
        self.print_header("NFC Reader")

        try:
            from tap_station.nfc_reader import NFCReader

            NFCReader()  # Test initialization
            self.check_status("PN532 initialization", True)

        except ImportError:
            self.check_status(
                "pn532pi installed", False, "Run: pip install pn532pi", level="error"
            )
        except Exception as e:
            self.check_status("PN532 initialization", False, str(e), level="error")

    def check_gpio(self):
        """Check GPIO/buzzer"""
        self.print_header("GPIO / Buzzer")

        try:
            import RPi.GPIO as GPIO

            self.check_status("RPi.GPIO available", True)

            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(17, GPIO.OUT)
            GPIO.cleanup()

            self.check_status("GPIO access", True)

        except ImportError:
            self.check_status(
                "RPi.GPIO available", False, "Not on Raspberry Pi", level="warning"
            )
        except Exception as e:
            self.check_status("GPIO access", False, str(e), level="warning")

    def check_database(self):
        """Check database"""
        self.print_header("Database")

        db_path = Path("data/events.db")
        db_exists = db_path.exists()
        self.check_status("Database file exists", db_exists, level="info")

        if db_exists:
            # Get database size
            size_mb = db_path.stat().st_size / (1024 * 1024)
            print(f"  Database size: {size_mb:.2f} MB")

            # Try to connect and get event count
            try:
                from tap_station.database import Database

                db = Database("data/events.db", wal_mode=False)

                event_count = db.get_event_count()
                self.check_status(
                    "Database accessible", True, f"{event_count} events logged"
                )

                # Get recent events
                cursor = db.conn.execute(
                    """
                    SELECT COUNT(*) FROM events
                    WHERE timestamp > datetime('now', '-1 hour')
                """
                )
                recent_count = cursor.fetchone()[0]
                print(f"  Events in last hour: {recent_count}")

                # Get today's events
                cursor = db.conn.execute(
                    """
                    SELECT COUNT(*) FROM events
                    WHERE date(timestamp) = date('now')
                """
                )
                today_count = cursor.fetchone()[0]
                print(f"  Events today: {today_count}")

                db.close()

            except Exception as e:
                self.check_status("Database accessible", False, str(e), level="error")

    def check_disk(self):
        """Check disk space"""
        self.print_header("Disk Space")

        try:
            result = subprocess.run(["df", "-h", "."], capture_output=True, text=True)
            lines = result.stdout.strip().split("\n")

            if len(lines) >= 2:
                parts = lines[1].split()
                used_percent = int(parts[4].rstrip("%"))

                status = used_percent < 90
                level = (
                    "error"
                    if used_percent >= 90
                    else "warning"
                    if used_percent >= 80
                    else "info"
                )

                self.check_status(
                    "Disk space available",
                    status,
                    f"{parts[3]} free ({parts[4]} used)",
                    level=level,
                )

        except Exception as e:
            self.check_status("Disk space check", False, str(e), level="warning")

    def check_power(self):
        """Check power/temperature"""
        self.print_header("Power & Temperature")

        # Check under-voltage
        try:
            result = subprocess.run(
                ["vcgencmd", "get_throttled"], capture_output=True, text=True
            )
            throttled = result.stdout.strip().split("=")[1]
            no_throttle = throttled == "0x0"

            self.check_status(
                "No under-voltage detected",
                no_throttle,
                f"Status: {throttled}",
                level="warning",
            )

            if not no_throttle:
                print("  Check power supply and USB cable")

        except Exception as e:
            self.check_status("Power check", False, str(e), level="info")

        # Check temperature
        try:
            result = subprocess.run(
                ["vcgencmd", "measure_temp"], capture_output=True, text=True
            )
            temp_str = result.stdout.strip().split("=")[1]
            temp_c = float(temp_str.rstrip("'C"))

            temp_ok = temp_c < 80
            level = "error" if temp_c >= 80 else "warning" if temp_c >= 70 else "info"

            self.check_status("Temperature normal", temp_ok, f"{temp_c}°C", level=level)

        except Exception as e:
            self.check_status("Temperature check", False, str(e), level="info")

    def check_service(self):
        """Check systemd service status"""
        self.print_header("Service Status")

        try:
            result = subprocess.run(
                ["systemctl", "is-active", "tap-station"],
                capture_output=True,
                text=True,
            )

            is_active = result.stdout.strip() == "active"
            self.check_status("Service running", is_active, level="info")

            if is_active:
                # Get service uptime
                result = subprocess.run(
                    [
                        "systemctl",
                        "show",
                        "tap-station",
                        "--property=ActiveEnterTimestamp",
                    ],
                    capture_output=True,
                    text=True,
                )
                print(f"  {result.stdout.strip()}")

        except FileNotFoundError:
            print("  Service not installed")
            print("  To install: sudo cp tap-station.service /etc/systemd/system/")
            print("              sudo systemctl enable tap-station")
        except Exception as e:
            self.check_status("Service check", False, str(e), level="info")

    def check_logs(self):
        """Check log files"""
        self.print_header("Recent Logs")

        log_files = ["logs/tap-station.log", "logs/tap-station-error.log"]

        for log_file in log_files:
            log_path = Path(log_file)
            if log_path.exists():
                # Get last 5 lines
                try:
                    with open(log_path) as f:
                        lines = f.readlines()
                        recent_lines = lines[-5:] if len(lines) > 5 else lines

                    print(f"\n{log_file} (last 5 lines):")
                    print("─" * 60)
                    for line in recent_lines:
                        print("  " + line.rstrip())

                except Exception as e:
                    print(f"  Could not read {log_file}: {e}")
            else:
                print(f"\n{log_file}: Not found")

    def print_summary(self):
        """Print summary"""
        self.print_header("Health Check Summary")

        if not self.errors and not self.warnings:
            print("✓ All systems operational!")
        else:
            if self.errors:
                print(f"✗ {len(self.errors)} critical error(s):")
                for error in self.errors:
                    print(f"  - {error}")

            if self.warnings:
                print(f"\n⚠ {len(self.warnings)} warning(s):")
                for warning in self.warnings:
                    print(f"  - {warning}")

        print("\nFor detailed troubleshooting:")
        print("  - docs/TROUBLESHOOTING_FLOWCHART.md")
        print("  - docs/HARDWARE.md")
        print("  - README.md")

    def run(self, quick=False):
        """Run all health checks"""
        self.print_header("NFC Tap Logger - Health Check")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        self.check_config()
        self.check_i2c()
        self.check_nfc()

        if not quick:
            self.check_gpio()
            self.check_database()
            self.check_disk()
            self.check_power()
            self.check_service()
            self.check_logs()

        self.print_summary()


def main():
    """Entry point for health check"""
    import argparse

    parser = argparse.ArgumentParser(description="System health check dashboard")
    parser.add_argument(
        "--quick", action="store_true", help="Quick check (skip optional tests)"
    )

    args = parser.parse_args()

    health = HealthCheck()
    health.run(quick=args.quick)

    # Exit with error code if critical errors found
    return 1 if health.errors else 0


if __name__ == "__main__":
    sys.exit(main())
