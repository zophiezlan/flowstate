"""
NFC Reader Cleanup Utilities

Shared utilities for managing NFC reader state, stopping conflicting services,
and resetting I2C bus. Used by all scripts that access the NFC reader to ensure
clean state before operation.
"""

import os
import sys
import subprocess
import time
import logging
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)


class NFCCleanupManager:
    """Manages NFC reader cleanup and service conflicts"""

    def __init__(self, auto_fix: bool = True, require_sudo: bool = False):
        """
        Initialize cleanup manager

        Args:
            auto_fix: If True, automatically fix issues. If False, only detect.
            require_sudo: If True, will use sudo for operations that need it
        """
        self.auto_fix = auto_fix
        self.require_sudo = require_sudo

    def check_and_cleanup(
        self, stop_service: bool = True, reset_i2c: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Check for NFC reader conflicts and optionally fix them

        Args:
            stop_service: If True, stop tap-station service if running
            reset_i2c: If True, reset I2C bus (requires sudo)

        Returns:
            Tuple of (success, list of messages/warnings)
        """
        messages = []
        issues_found = []

        # Check if service is running
        service_running, service_msg = self._check_service()
        if service_running:
            issues_found.append("service")
            messages.append(f"⚠️  tap-station service is running")

            if self.auto_fix and stop_service:
                success = self._stop_service()
                if success:
                    messages.append("✓ Service stopped")
                else:
                    messages.append("✗ Failed to stop service")
                    return False, messages

        # Check for other Python processes using NFC reader
        processes = self._find_nfc_processes()
        if processes:
            issues_found.append("processes")
            messages.append(
                f"⚠️  Found {len(processes)} process(es) using NFC reader"
            )

            if self.auto_fix:
                killed = self._cleanup_processes(processes)
                if killed > 0:
                    messages.append(f"✓ Cleaned up {killed} process(es)")
                    # Give processes time to clean up
                    time.sleep(1)

        # Check I2C device accessibility
        i2c_ok, i2c_msg = self._check_i2c_device()
        if not i2c_ok:
            issues_found.append("i2c")
            messages.append(f"⚠️  {i2c_msg}")

            if self.auto_fix and reset_i2c and self.require_sudo:
                success = self._reset_i2c_bus()
                if success:
                    messages.append("✓ I2C bus reset")
                else:
                    messages.append("✗ Failed to reset I2C bus")

        # Verify PN532 detection if I2C is accessible
        if i2c_ok:
            pn532_ok, pn532_msg = self._check_pn532()
            if not pn532_ok:
                issues_found.append("pn532")
                messages.append(f"⚠️  {pn532_msg}")

                if self.auto_fix and reset_i2c and self.require_sudo:
                    success = self._reset_i2c_bus()
                    if success:
                        messages.append("✓ I2C bus reset, re-checking PN532...")
                        time.sleep(1)
                        pn532_ok, pn532_msg = self._check_pn532()
                        if pn532_ok:
                            messages.append("✓ PN532 now detected")
                        else:
                            messages.append(f"✗ PN532 still not detected: {pn532_msg}")
                            return False, messages

        # If we found issues but didn't auto-fix, return failure
        if issues_found and not self.auto_fix:
            messages.append(
                "\nRun with auto_fix=True or manually fix the issues above"
            )
            return False, messages

        # Success if no remaining issues
        if not issues_found or self.auto_fix:
            if not issues_found:
                messages.append("✓ No conflicts detected, NFC reader ready")
            return True, messages
        else:
            return False, messages

    def _check_service(self) -> Tuple[bool, str]:
        """Check if tap-station service is running"""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "tap-station"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            is_active = result.stdout.strip() == "active"
            return is_active, "Service is active" if is_active else "Service is stopped"
        except FileNotFoundError:
            # systemctl not available (not a systemd system)
            return False, "systemctl not available"
        except Exception as e:
            logger.debug(f"Error checking service: {e}")
            return False, str(e)

    def _stop_service(self) -> bool:
        """Stop the tap-station service"""
        try:
            # Try with sudo first
            cmd = ["sudo", "systemctl", "stop", "tap-station"]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                # Give it time to fully stop
                time.sleep(2)
                return True
            else:
                logger.error(f"Failed to stop service: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error stopping service: {e}")
            return False

    def _find_nfc_processes(self) -> List[Tuple[int, str]]:
        """
        Find Python processes that might be using the NFC reader

        Returns:
            List of (pid, cmdline) tuples
        """
        processes = []

        try:
            # Get current process PID to avoid killing ourselves
            current_pid = os.getpid()

            # Find Python processes with NFC-related patterns
            # These patterns identify common scripts that use the NFC reader
            patterns = [
                "tap_station/main.py",
                "scripts/init_cards",
                "scripts/verify_hardware",
                "nfc_reader",
            ]

            for pattern in patterns:
                try:
                    result = subprocess.run(
                        ["pgrep", "-f", pattern],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )

                    if result.returncode == 0 and result.stdout.strip():
                        # Parse PIDs, filtering empty lines
                        pid_lines = [
                            line.strip()
                            for line in result.stdout.strip().split("\n")
                            if line.strip()
                        ]
                        
                        for pid_str in pid_lines:
                            try:
                                pid = int(pid_str)
                            except ValueError:
                                logger.debug(f"Skipping invalid PID: {pid_str}")
                                continue

                            # Skip current process
                            if pid == current_pid:
                                continue

                            # Get command line
                            try:
                                with open(f"/proc/{pid}/cmdline", "r") as f:
                                    cmdline = f.read().replace("\x00", " ").strip()
                                    processes.append((pid, cmdline))
                            except (FileNotFoundError, PermissionError):
                                # Process might have exited or we don't have permission
                                pass

                except subprocess.TimeoutExpired:
                    logger.debug(f"Timeout searching for pattern: {pattern}")
                except Exception as e:
                    logger.debug(f"Error searching for pattern {pattern}: {e}")

        except Exception as e:
            logger.error(f"Error finding NFC processes: {e}")

        return processes

    def _cleanup_processes(self, processes: List[Tuple[int, str]]) -> int:
        """
        Gracefully terminate processes

        Args:
            processes: List of (pid, cmdline) tuples

        Returns:
            Number of processes killed
        """
        killed = 0

        for pid, cmdline in processes:
            try:
                # Send SIGTERM (graceful shutdown)
                import signal

                os.kill(pid, signal.SIGTERM)
                logger.info(f"Sent SIGTERM to PID {pid}: {cmdline[:60]}")
                killed += 1
            except ProcessLookupError:
                # Process already exited
                pass
            except PermissionError:
                logger.warning(
                    f"No permission to kill PID {pid} (may need sudo)"
                )
            except Exception as e:
                logger.error(f"Error killing PID {pid}: {e}")

        return killed

    def _check_i2c_device(self) -> Tuple[bool, str]:
        """Check if I2C device exists and is accessible"""
        # Check for I2C device
        if os.path.exists("/dev/i2c-1"):
            # Check if we can access it using os.access()
            if os.access("/dev/i2c-1", os.R_OK | os.W_OK):
                return True, "I2C device /dev/i2c-1 accessible"
            else:
                return False, "I2C device exists but no permission (add user to i2c group)"
        elif os.path.exists("/dev/i2c-0"):
            if os.access("/dev/i2c-0", os.R_OK | os.W_OK):
                return True, "I2C device /dev/i2c-0 accessible"
            else:
                return False, "I2C device exists but no permission (add user to i2c group)"
        else:
            return False, "I2C device not found (enable I2C in raspi-config)"

    def _check_pn532(self) -> Tuple[bool, str]:
        """Check if PN532 is detected on I2C bus"""
        try:
            # Determine which bus to check
            i2c_bus = 1 if os.path.exists("/dev/i2c-1") else 0

            result = subprocess.run(
                ["i2cdetect", "-y", str(i2c_bus)],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                # Check for 0x24 in output
                if "24" in result.stdout:
                    return True, f"PN532 detected at 0x24 on bus {i2c_bus}"
                else:
                    return False, f"PN532 not detected at 0x24 on bus {i2c_bus}"
            else:
                return False, f"Error running i2cdetect: {result.stderr}"

        except FileNotFoundError:
            return False, "i2cdetect not found (install i2c-tools)"
        except Exception as e:
            return False, f"Error checking PN532: {e}"

    def _reset_i2c_bus(self) -> bool:
        """Reset I2C bus by reloading kernel modules"""
        try:
            logger.info("Resetting I2C bus...")

            # Unload i2c_dev module
            subprocess.run(
                ["sudo", "modprobe", "-r", "i2c_dev"],
                capture_output=True,
                timeout=5,
            )

            time.sleep(0.5)

            # Reload i2c_dev module
            result = subprocess.run(
                ["sudo", "modprobe", "i2c_dev"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                time.sleep(1)  # Give bus time to stabilize
                return True
            else:
                logger.error(f"Failed to reload i2c_dev: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error resetting I2C bus: {e}")
            return False


def cleanup_before_nfc_access(
    stop_service: bool = True,
    reset_i2c: bool = False,
    require_sudo: bool = False,
    verbose: bool = True,
) -> bool:
    """
    Convenience function to clean up before accessing NFC reader

    Args:
        stop_service: If True, stop tap-station service if running
        reset_i2c: If True, reset I2C bus (requires sudo)
        require_sudo: If True, will use sudo for operations
        verbose: If True, print messages to stdout

    Returns:
        True if cleanup successful and NFC reader ready, False otherwise
    """
    manager = NFCCleanupManager(auto_fix=True, require_sudo=require_sudo)
    success, messages = manager.check_and_cleanup(
        stop_service=stop_service, reset_i2c=reset_i2c
    )

    if verbose:
        for msg in messages:
            print(msg)

    return success
