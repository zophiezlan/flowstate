#!/usr/bin/env python3
"""
Quick development reset utility (no sudo required)
Kills processes and checks status without needing root privileges

NOTE: As of v2.2.2+, most scripts now automatically handle cleanup!
      You usually don't need to run this manually anymore.
      This script is kept for edge cases and manual troubleshooting.
"""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path


def print_header(text):
    """Print colored header"""
    print(f"\n\033[0;34m=== {text} ===\033[0m\n")


def print_success(text):
    """Print success message"""
    print(f"\033[0;32m✓ {text}\033[0m")


def print_warning(text):
    """Print warning message"""
    print(f"\033[1;33m⚠ {text}\033[0m")


def print_error(text):
    """Print error message"""
    print(f"\033[0;31m✗ {text}\033[0m")


def kill_process_by_name(pattern):
    """Kill processes matching pattern"""
    try:
        # Find PIDs
        result = subprocess.run(
            ["pgrep", "-f", pattern], capture_output=True, text=True
        )

        if result.returncode == 0 and result.stdout.strip():
            pids = [int(pid) for pid in result.stdout.strip().split("\n")]

            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                    print(f"  Killed PID {pid}")
                except ProcessLookupError:
                    pass
                except PermissionError:
                    print_warning(f"No permission to kill PID {pid} (use sudo)")

            # Wait for processes to die
            time.sleep(0.5)
            return True

        return False

    except Exception as e:
        print_error(f"Error killing processes: {e}")
        return False


def check_service_status():
    """Check if tap-station service is running"""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "tap-station"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.stdout.strip() == "active"
    except Exception:
        return False


def check_i2c_device():
    """Check if PN532 is detected"""
    try:
        result = subprocess.run(
            ["i2cdetect", "-y", "1"], capture_output=True, text=True, timeout=5
        )
        return "24" in result.stdout
    except Exception:
        return False


def main():
    print("\033[0;34m==============================================")
    print("NFC Tap Logger - Quick Dev Reset")
    print("==============================================\033[0m")

    # Check service status
    print_header("Service Status")
    if check_service_status():
        print_warning("tap-station service is RUNNING")
        print("  Stop it with: sudo systemctl stop tap-station")
        print("  Or run: sudo bash scripts/dev_reset.sh")
    else:
        print_success("tap-station service is stopped")

    # Kill user processes
    print_header("Killing User Processes")

    killed_any = False

    if kill_process_by_name("tap_station/main.py"):
        print_success("Killed main.py processes")
        killed_any = True

    if kill_process_by_name("scripts/init_cards"):
        print_success("Killed init_cards processes")
        killed_any = True

    if kill_process_by_name("scripts/verify_"):
        print_success("Killed verification processes")
        killed_any = True

    if not killed_any:
        print("  No user processes found")

    # Check I2C
    print_header("I2C Hardware Check")

    if Path("/dev/i2c-1").exists():
        print_success("I2C device exists: /dev/i2c-1")

        if check_i2c_device():
            print_success("PN532 detected at address 0x24")
        else:
            print_warning("PN532 not detected (check connections)")
            print("  Run: i2cdetect -y 1")
    else:
        print_error("I2C device not found: /dev/i2c-1")
        print("  Enable I2C: sudo raspi-config")

    # Show recommendations
    print_header("Next Steps")

    if check_service_status():
        print("1. Stop the service:")
        print("   sudo systemctl stop tap-station")
        print("   OR")
        print("   sudo bash scripts/dev_reset.sh")
        print()

    print("2. Run verification:")
    print("   bash scripts/verify_deployment.sh")
    print()
    print("3. Test initialization (mock mode):")
    print("   python3 scripts/init_cards.py --mock")
    print()
    print("4. Start development server:")
    print("   python3 tap_station/main.py")

    print("\n\033[0;32m✓ Quick reset complete\033[0m\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
