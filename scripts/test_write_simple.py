#!/usr/bin/env python3
"""
Simplified write test to diagnose the exact issue
Run this on the Raspberry Pi to test writing to a card
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pn532pi import Pn532, Pn532I2c

print("=" * 70)
print("Simple PN532 Write Test")
print("=" * 70)

try:
    # Initialize
    print("\nInitializing PN532...")
    i2c = Pn532I2c(1)
    pn532 = Pn532(i2c)
    pn532.begin()

    version = pn532.getFirmwareVersion()
    if not version:
        print("ERROR: Could not get firmware version")
        sys.exit(1)

    print(f"Firmware: {(version >> 24) & 0xFF}.{(version >> 16) & 0xFF}")
    pn532.SAMConfig()

    # Wait for card
    input("\nPlace card on reader and press Enter...")

    success, uid = pn532.readPassiveTargetID(cardbaudrate=0x00)
    if not success or not uid:
        print("ERROR: No card detected")
        sys.exit(1)

    uid_hex = "".join(["{:02X}".format(b) for b in uid])
    print(f"Card UID: {uid_hex}")

    # Read current page 4 content
    print("\nReading current page 4 content...")
    current = pn532.mifareultralight_ReadPage(4)
    if current:
        print(f"Current: {bytes(current[:4]).hex()} ({repr(bytes(current[:4]))})")

    # Prepare test data
    test_data = bytearray(b"TEST")
    print(f"\nTest data to write: {test_data.hex()} ({repr(bytes(test_data))})")
    print(f"Type: {type(test_data)}, Length: {len(test_data)}")

    input("\nPress Enter to write TEST to page 4 (WARNING: will modify card!)...")

    # Try the write
    print("Calling: pn532.mifareultralight_WritePage(4, test_data)")
    print(f"  where test_data = {test_data}")

    result = pn532.mifareultralight_WritePage(4, test_data)

    print(f"\nWrite result: {result} (type: {type(result)})")

    # Read back
    print("\nReading back page 4...")
    readback = pn532.mifareultralight_ReadPage(4)
    if readback:
        readback_bytes = bytes(readback[:4])
        print(f"Readback: {readback_bytes.hex()} ({repr(readback_bytes)})")

        if readback_bytes == b"TEST":
            print("\n✓ SUCCESS! Write and read-back match!")
        else:
            print(f"\n✗ MISMATCH! Expected TEST, got {repr(readback_bytes)}")
    else:
        print("ERROR: Could not read back")

except Exception as e:
    print(f"\nERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
