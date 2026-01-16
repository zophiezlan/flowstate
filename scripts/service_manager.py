#!/usr/bin/env python3
"""
Service Manager

Helper script for managing the tap-station systemd service.
"""

import sys
import subprocess
import argparse


def run_command(cmd, check=True):
    """Run a command and return output"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=check
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return False, e.stdout, e.stderr


def is_service_installed():
    """Check if service is installed"""
    success, _, _ = run_command("systemctl list-unit-files | grep -q tap-station", check=False)
    return success


def install_service():
    """Install systemd service"""
    print("Installing tap-station systemd service...")

    if is_service_installed():
        print("✓ Service is already installed")
        return True

    # Copy service file
    success, out, err = run_command(
        "sudo cp tap-station.service /etc/systemd/system/",
        check=False
    )

    if not success:
        print(f"✗ Failed to install service: {err}")
        return False

    # Reload systemd
    success, _, _ = run_command("sudo systemctl daemon-reload", check=False)
    if not success:
        print("✗ Failed to reload systemd")
        return False

    print("✓ Service installed successfully")
    return True


def enable_service():
    """Enable service to start on boot"""
    print("Enabling tap-station service...")

    success, out, err = run_command("sudo systemctl enable tap-station", check=False)

    if success:
        print("✓ Service enabled (will start on boot)")
        return True
    else:
        print(f"✗ Failed to enable service: {err}")
        return False


def disable_service():
    """Disable service from starting on boot"""
    print("Disabling tap-station service...")

    success, out, err = run_command("sudo systemctl disable tap-station", check=False)

    if success:
        print("✓ Service disabled (will not start on boot)")
        return True
    else:
        print(f"✗ Failed to disable service: {err}")
        return False


def start_service():
    """Start the service"""
    print("Starting tap-station service...")

    success, out, err = run_command("sudo systemctl start tap-station", check=False)

    if success:
        print("✓ Service started")
        return True
    else:
        print(f"✗ Failed to start service: {err}")
        return False


def stop_service():
    """Stop the service"""
    print("Stopping tap-station service...")

    success, out, err = run_command("sudo systemctl stop tap-station", check=False)

    if success:
        print("✓ Service stopped")
        return True
    else:
        print(f"✗ Failed to stop service: {err}")
        return False


def restart_service():
    """Restart the service"""
    print("Restarting tap-station service...")

    success, out, err = run_command("sudo systemctl restart tap-station", check=False)

    if success:
        print("✓ Service restarted")
        return True
    else:
        print(f"✗ Failed to restart service: {err}")
        return False


def status_service():
    """Show service status"""
    print("tap-station service status:")
    print("=" * 60)

    success, out, err = run_command("systemctl status tap-station", check=False)
    print(out)

    if not success:
        print("\nService is not running or not installed")
        print("\nTo install:")
        print("  python scripts/service_manager.py install")
        print("  python scripts/service_manager.py enable")
        print("  python scripts/service_manager.py start")

    return success


def logs_service(lines=50, follow=False):
    """Show service logs"""
    if follow:
        print(f"Following tap-station logs (Ctrl+C to stop)...")
        run_command("sudo journalctl -u tap-station -f", check=False)
    else:
        print(f"Last {lines} lines of tap-station logs:")
        print("=" * 60)
        success, out, err = run_command(f"sudo journalctl -u tap-station -n {lines}", check=False)
        print(out)


def main():
    """Entry point"""
    parser = argparse.ArgumentParser(description='Manage tap-station systemd service')

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Install command
    subparsers.add_parser('install', help='Install systemd service')

    # Enable/disable commands
    subparsers.add_parser('enable', help='Enable service to start on boot')
    subparsers.add_parser('disable', help='Disable service from starting on boot')

    # Start/stop/restart commands
    subparsers.add_parser('start', help='Start the service')
    subparsers.add_parser('stop', help='Stop the service')
    subparsers.add_parser('restart', help='Restart the service')

    # Status command
    subparsers.add_parser('status', help='Show service status')

    # Logs command
    logs_parser = subparsers.add_parser('logs', help='Show service logs')
    logs_parser.add_argument('-n', '--lines', type=int, default=50, help='Number of lines to show')
    logs_parser.add_argument('-f', '--follow', action='store_true', help='Follow logs in real-time')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    commands = {
        'install': install_service,
        'enable': enable_service,
        'disable': disable_service,
        'start': start_service,
        'stop': stop_service,
        'restart': restart_service,
        'status': status_service,
        'logs': lambda: logs_service(args.lines, args.follow) if args.command == 'logs' else None
    }

    if args.command in commands:
        result = commands[args.command]()
        return 0 if result or result is None else 1
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
