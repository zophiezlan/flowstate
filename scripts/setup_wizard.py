#!/usr/bin/env python3
"""
Setup Wizard

Interactive first-run configuration for NFC Tap Logger.
Guides user through device setup, tests hardware, and creates config.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
from pathlib import Path


def print_header(title):
    """Print formatted section header"""
    print(f"\n{'=' * 60}")
    print(f"{title}")
    print(f"{'=' * 60}\n")


def print_step(step_num, total_steps, description):
    """Print step header"""
    print(f"\n{'─' * 60}")
    print(f"Step {step_num}/{total_steps}: {description}")
    print(f"{'─' * 60}\n")


def get_input(prompt, default=None, options=None):
    """Get user input with validation"""
    while True:
        if default:
            user_input = input(f"{prompt} [{default}]: ").strip()
            if not user_input:
                return default
        else:
            user_input = input(f"{prompt}: ").strip()

        if options and user_input not in options:
            print(f"Invalid input. Choose from: {', '.join(options)}")
            continue

        return user_input


def test_nfc_reader():
    """Test NFC reader connectivity"""
    print("Testing NFC reader...")

    try:
        from tap_station.nfc_reader import NFCReader

        print("Initializing PN532...")
        reader = NFCReader()

        print("✓ NFC reader initialized successfully!")

        response = get_input("\nWould you like to test card reading? (y/n)", default="y", options=["y", "n"])

        if response == "y":
            print("\nPlease tap an NFC card on the reader (15 second timeout)...")
            result = reader.wait_for_card(timeout=15)

            if result:
                uid, token_id = result
                print(f"✓ Card read successful!")
                print(f"  UID: {uid}")
                print(f"  Token: {token_id}")
                return True
            else:
                print("✗ No card detected. Please check:")
                print("  - Card is NTAG215")
                print("  - Reader antenna position")
                print("  - Card placement")
                return False

        return True

    except ImportError:
        print("✗ pn532pi not installed")
        print("  Run: pip install pn532pi")
        return False

    except Exception as e:
        print(f"✗ Error testing NFC reader: {e}")
        print("  Check I2C connection and PN532 wiring")
        return False


def test_buzzer():
    """Test buzzer/audio feedback"""
    print("Testing buzzer...")

    try:
        from tap_station.feedback import FeedbackController

        feedback = FeedbackController(buzzer_enabled=True, led_enabled=False)

        print("You should hear a short beep...")
        feedback.success()

        response = get_input("Did you hear the beep? (y/n)", default="y", options=["y", "n"])

        feedback.cleanup()

        if response == "y":
            print("✓ Buzzer working!")
            return True
        else:
            print("✗ Buzzer not working. Check wiring:")
            print("  Buzzer+ → GPIO 17 (Pin 11)")
            print("  Buzzer- → GND")
            return False

    except ImportError:
        print("✗ RPi.GPIO not available (not on Raspberry Pi)")
        return False

    except Exception as e:
        print(f"✗ Error testing buzzer: {e}")
        return False


def create_config(device_id, stage, session_id, buzzer_enabled):
    """Create configuration file with correct nested schema"""
    config = {
        'station': {
            'device_id': device_id,
            'stage': stage,
            'session_id': session_id
        },
        'database': {
            'path': 'data/events.db',
            'wal_mode': True
        },
        'nfc': {
            'i2c_bus': 1,
            'address': 0x24,
            'timeout': 2,
            'retries': 3,
            'debounce_seconds': 1.0
        },
        'feedback': {
            'buzzer_enabled': buzzer_enabled,
            'led_enabled': False,
            'gpio': {
                'buzzer': 17,
                'led_green': 27,
                'led_red': 22
            },
            'beep_success': [0.1],
            'beep_duplicate': [0.1, 0.05, 0.1],
            'beep_error': [0.3]
        },
        'logging': {
            'path': 'logs/tap-station.log',
            'level': 'INFO'
        },
        'web_server': {
            'enabled': True,
            'port': 5000,
            'host': '0.0.0.0'
        }
    }

    config_path = Path('config.yaml')

    # Backup existing config
    if config_path.exists():
        backup_path = Path('config.yaml.backup')
        print(f"Backing up existing config to {backup_path}")
        import shutil
        shutil.copy(config_path, backup_path)

    # Write new config
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"✓ Configuration saved to {config_path}")


def main():
    """Run setup wizard"""
    print_header("NFC Tap Logger - Setup Wizard")

    print("Welcome! This wizard will help you set up your NFC Tap Logger.")
    print("\nWhat we'll do:")
    print("  1. Configure device settings")
    print("  2. Test NFC reader")
    print("  3. Test buzzer (optional)")
    print("  4. Create configuration file")
    print("  5. Verify system is ready")

    input("\nPress Enter to start...")

    # Step 1: Device Configuration
    print_step(1, 5, "Device Configuration")

    print("Each tap station needs a unique device ID and stage name.")
    print("\nExample setup:")
    print("  Station 1 (queue entrance): device_id='station-1', stage='join'")
    print("  Station 2 (queue exit):     device_id='station-2', stage='exit'")

    device_id = get_input("\nEnter device ID (e.g., 'station-1')", default="station-1")

    stage_options = ["join", "exit", "checkpoint"]
    print(f"\nAvailable stages: {', '.join(stage_options)}")
    stage = get_input("Enter stage", default="join", options=stage_options + [""])

    if not stage:
        stage = get_input("Enter custom stage name")

    print("\nSession ID groups data from a single event.")
    print("Use the same session ID for all stations at the same event.")
    session_id = get_input("Enter session ID (e.g., 'event-2026-01-16')", default="event-2026-01-16")

    print("\n" + "─" * 60)
    print("Configuration Summary:")
    print(f"  Device ID:  {device_id}")
    print(f"  Stage:      {stage}")
    print(f"  Session ID: {session_id}")
    print("─" * 60)

    confirm = get_input("\nIs this correct? (y/n)", default="y", options=["y", "n"])
    if confirm != "y":
        print("Setup cancelled. Run this wizard again to start over.")
        return 1

    # Step 2: Test NFC Reader
    print_step(2, 5, "NFC Reader Test")

    nfc_ok = test_nfc_reader()

    if not nfc_ok:
        print("\n⚠ Warning: NFC reader test failed!")
        response = get_input("Continue anyway? (y/n)", default="n", options=["y", "n"])
        if response != "y":
            print("\nSetup cancelled.")
            print("\nTo fix NFC issues:")
            print("  1. Run: bash scripts/enable_i2c.sh")
            print("  2. Verify wiring (see docs/HARDWARE.md)")
            print("  3. Check I2C: sudo i2cdetect -y 1")
            return 1

    # Step 3: Test Buzzer
    print_step(3, 5, "Buzzer Test (Optional)")

    test_buzzer_prompt = get_input("Test buzzer? (y/n)", default="y", options=["y", "n"])

    buzzer_enabled = False
    if test_buzzer_prompt == "y":
        buzzer_ok = test_buzzer()
        buzzer_enabled = buzzer_ok
    else:
        print("Skipping buzzer test")
        buzzer_enabled = False

    # Step 4: Create Configuration
    print_step(4, 5, "Create Configuration File")

    create_config(device_id, stage, session_id, buzzer_enabled)

    # Step 5: Final Verification
    print_step(5, 5, "Final Verification")

    print("Running system checks...")

    # Check directories
    dirs_ok = True
    required_dirs = ['data', 'logs', 'backups']
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            print(f"Creating directory: {dir_name}")
            dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✓ Directory exists: {dir_name}")

    # Check database can be created
    try:
        from tap_station.database import Database
        db = Database("data/test.db", wal_mode=True)
        db.close()
        os.remove("data/test.db")
        if os.path.exists("data/test.db-wal"):
            os.remove("data/test.db-wal")
        if os.path.exists("data/test.db-shm"):
            os.remove("data/test.db-shm")
        print("✓ Database can be created")
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        dirs_ok = False

    # Success!
    print_header("Setup Complete!")

    if nfc_ok and dirs_ok:
        print("✓ Your NFC Tap Logger is ready to use!")
    else:
        print("⚠ Setup completed with warnings. Review errors above.")

    print("\nNext steps:")
    print("  1. Initialize cards:")
    print("     python scripts/init_cards.py --start 1 --end 100")
    print("\n  2. Start the service:")
    print("     python -m tap_station.main")
    print("\n  3. Or install as systemd service:")
    print("     sudo cp tap-station.service /etc/systemd/system/")
    print("     sudo systemctl enable tap-station")
    print("     sudo systemctl start tap-station")
    print("\n  4. Check status:")
    print("     python scripts/health_check.py")

    print("\nConfiguration saved to: config.yaml")
    print("For help, see: README.md and docs/")

    return 0


if __name__ == '__main__':
    sys.exit(main())
