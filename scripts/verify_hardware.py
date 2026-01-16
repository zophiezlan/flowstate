#!/usr/bin/env python3
"""
Hardware Verification Script

Verify that all hardware components are working:
- I2C bus
- PN532 NFC reader
- GPIO (buzzer/LEDs)
- Power/battery status
"""

import sys
import os
import subprocess
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_header(title):
    """Print formatted section header"""
    print(f"\n{'=' * 60}")
    print(f"{title}")
    print(f"{'=' * 60}")


def print_result(test_name, passed, message=""):
    """Print test result"""
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{test_name:.<50} {status}")
    if message:
        print(f"  {message}")


def check_i2c():
    """Check if I2C is enabled and working"""
    print_header("I2C Bus Check")

    # Check if I2C device exists
    i2c_device_exists = os.path.exists('/dev/i2c-1') or os.path.exists('/dev/i2c-0')

    if not i2c_device_exists:
        print_result("I2C device exists", False, "/dev/i2c-1 not found")
        print("\n  ⚠ I2C is not enabled or system needs reboot")
        print("\n  To fix this issue:")
        print("    1. Run the I2C setup script:")
        print("       bash scripts/enable_i2c.sh")
        print("\n    2. Or manually enable I2C:")
        print("       - Edit /boot/config.txt or /boot/firmware/config.txt")
        print("       - Add line: dtparam=i2c_arm=on")
        print("       - Reboot: sudo reboot")
        print("\n    3. After reboot, run this verification again")
        print("\n  For detailed troubleshooting, see docs/HARDWARE.md")
        return False

    # Determine which I2C bus to use
    i2c_bus = 1 if os.path.exists('/dev/i2c-1') else 0
    print_result("I2C device exists", True, f"/dev/i2c-{i2c_bus}")

    # Check if i2c_dev module is loaded
    try:
        result = subprocess.run(['lsmod'], capture_output=True, text=True)
        i2c_loaded = 'i2c_dev' in result.stdout
        print_result("I2C kernel module loaded", i2c_loaded)

        if not i2c_loaded:
            print("  Try: sudo modprobe i2c_dev")
            return False
    except Exception as e:
        print_result("Check I2C module", False, str(e))
        return False

    # Check if i2c-tools is installed
    try:
        result = subprocess.run(['which', 'i2cdetect'], capture_output=True)
        i2c_tools = result.returncode == 0
        print_result("i2c-tools installed", i2c_tools)

        if not i2c_tools:
            print("  Try: sudo apt-get install i2c-tools")
            return False
    except Exception as e:
        print_result("Check i2c-tools", False, str(e))
        return False

    # Scan I2C bus for devices
    try:
        result = subprocess.run(
            ['i2cdetect', '-y', str(i2c_bus)],
            capture_output=True,
            text=True
        )

        # Check if 0x24 (PN532) is detected
        pn532_found = '24' in result.stdout
        print_result("PN532 detected at 0x24", pn532_found)

        if not pn532_found:
            print("\n  ✗ PN532 NFC reader not found on I2C bus")
            print("\n  Check PN532 wiring:")
            print("    VCC → 3.3V (Pin 1)")
            print("    GND → GND (Pin 6)")
            print("    SDA → GPIO 2 (Pin 3)")
            print("    SCL → GPIO 3 (Pin 5)")
            print("\n  Check PN532 mode:")
            print("    - Ensure PN532 is set to I2C mode (not SPI/UART)")
            print("    - Check jumpers/switches on the module")
            print("\n  I2C scan output:")
            print(result.stdout)
            print("\n  Run I2C setup script for troubleshooting:")
            print("    bash scripts/enable_i2c.sh")
            return False

        return True

    except Exception as e:
        print_result("Scan I2C bus", False, str(e))
        print(f"  Try: sudo i2cdetect -y {i2c_bus}")
        return False


def check_nfc_reader():
    """Check if PN532 NFC reader is working"""
    print_header("NFC Reader Check")

    # Check if I2C device exists first
    if not os.path.exists('/dev/i2c-1') and not os.path.exists('/dev/i2c-0'):
        print_result("NFC reader test", False, "I2C device not found")
        print("  ⚠ Cannot test NFC reader without I2C enabled")
        print("  Fix I2C issues first (see I2C Bus Check section above)")
        return False

    # Determine which I2C bus to use
    i2c_bus = 1 if os.path.exists('/dev/i2c-1') else 0

    try:
        from tap_station.nfc_reader import NFCReader

        print(f"Initializing PN532 reader on I2C bus {i2c_bus}...")
        reader = NFCReader(i2c_bus=i2c_bus, address=0x24)
        print_result("PN532 initialized", True)

        # Wait for user to be ready with card
        print("\n" + "=" * 60)
        print("Ready to test NFC card reading")
        print("=" * 60)
        print("\nPlease have an NFC card ready (NTAG215 recommended)")
        print("You will have 15 seconds to tap the card after pressing Enter")
        input("\nPress Enter when ready to test card reading...")

        print("\nWaiting for NFC card (tap within 15 seconds)...")
        result = reader.wait_for_card(timeout=15)

        if result:
            uid, token_id = result
            print_result("Card read successful", True, f"UID: {uid}, Token: {token_id}")
            return True
        else:
            print_result("Card read", False, "No card detected within timeout")
            print("  Make sure card is NTAG215")
            print("  Hold card flat against reader antenna")
            print("  Try again if needed")
            return False

    except ImportError:
        print_result("pn532pi installed", False, "Missing dependency")
        print("  Try: pip install pn532pi")
        return False

    except Exception as e:
        error_msg = str(e)
        print_result("NFC reader test", False, error_msg)

        # Provide specific guidance for common errors
        if "No such file or directory" in error_msg and "/dev/i2c" in error_msg:
            print("\n  ⚠ I2C device not accessible")
            print("  Run: bash scripts/enable_i2c.sh")
        elif "Failed to communicate with PN532" in error_msg:
            print("\n  ⚠ PN532 not responding")
            print("  Check wiring and ensure PN532 is in I2C mode")
        elif "Permission denied" in error_msg:
            print("\n  ⚠ Permission issue")
            print("  Add user to i2c group: sudo usermod -a -G i2c $USER")
            print("  Then log out and back in")

        return False


def check_gpio():
    """Check GPIO functionality (buzzer/LEDs)"""
    print_header("GPIO Check")

    try:
        import RPi.GPIO as GPIO
        print_result("RPi.GPIO available", True)

        # Setup test pins
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        test_pin = 17  # Buzzer pin
        GPIO.setup(test_pin, GPIO.OUT)

        print(f"\nTesting GPIO {test_pin} (buzzer pin)...")
        print("You should hear a short beep...")

        # Beep
        GPIO.output(test_pin, GPIO.HIGH)
        time.sleep(0.2)
        GPIO.output(test_pin, GPIO.LOW)

        GPIO.cleanup()

        response = input("Did you hear a beep? (y/n): ").strip().lower()
        success = response == 'y'

        print_result("GPIO/Buzzer working", success)

        if not success:
            print("  Check buzzer wiring:")
            print("    Buzzer+ → GPIO 17 (Pin 11)")
            print("    Buzzer- → GND")

        return success

    except ImportError:
        print_result("RPi.GPIO available", False, "Not on Raspberry Pi")
        return False

    except Exception as e:
        print_result("GPIO test", False, str(e))
        return False


def check_battery():
    """Check battery/power status"""
    print_header("Power/Battery Check")

    try:
        # Check for under-voltage
        result = subprocess.run(
            ['vcgencmd', 'get_throttled'],
            capture_output=True,
            text=True
        )

        throttled = result.stdout.strip().split('=')[1]
        no_throttle = throttled == '0x0'

        print_result("No under-voltage detected", no_throttle, f"Status: {throttled}")

        if not no_throttle:
            print("  Under-voltage detected!")
            print("  Check power supply:")
            print("    - Use quality USB cable")
            print("    - Ensure power bank has sufficient charge")
            print("    - Power bank should provide 5V 2A minimum")
            return False

        # Get temperature
        result = subprocess.run(
            ['vcgencmd', 'measure_temp'],
            capture_output=True,
            text=True
        )

        temp = result.stdout.strip()
        print(f"  CPU Temperature: {temp}")

        return True

    except Exception as e:
        print_result("Power check", False, str(e))
        return False


def check_database():
    """Check if database can be created and written"""
    print_header("Database Check")

    try:
        from tap_station.database import Database

        # Create test database
        test_db = "data/test.db"

        print("Creating test database...")
        db = Database(test_db, wal_mode=True)

        # Log test event
        success = db.log_event(
            token_id="000",
            uid="TEST1234",
            stage="TEST",
            device_id="test",
            session_id="test"
        )

        print_result("Database write", success)

        # Read back
        count = db.get_event_count()
        print_result("Database read", count > 0, f"{count} events")

        db.close()

        # Clean up
        os.remove(test_db)
        if os.path.exists(test_db + "-wal"):
            os.remove(test_db + "-wal")
        if os.path.exists(test_db + "-shm"):
            os.remove(test_db + "-shm")

        return success

    except Exception as e:
        print_result("Database test", False, str(e))
        return False


def main():
    """Run all hardware verification checks"""
    print("\n" + "=" * 60)
    print("NFC Tap Logger - Hardware Verification")
    print("=" * 60)

    results = {}

    # Run checks
    results['I2C'] = check_i2c()
    results['NFC'] = check_nfc_reader()
    results['GPIO'] = check_gpio()
    results['Power'] = check_battery()
    results['Database'] = check_database()

    # Summary
    print_header("Verification Summary")

    all_passed = all(results.values())

    for component, passed in results.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {component}")

    print()

    if all_passed:
        print("✓ All checks passed! Hardware is ready.")
        print("\nNext steps:")
        print("  1. Initialize cards: python scripts/init_cards.py")
        print("  2. Start service: sudo systemctl start tap-station")
        print("  3. Monitor logs: tail -f logs/tap-station.log")
        return 0
    else:
        print("✗ Some checks failed. Please fix the issues above.")
        print("\nFor help, see:")
        print("  - docs/HARDWARE.md")
        print("  - README.md")
        return 1


if __name__ == '__main__':
    sys.exit(main())
