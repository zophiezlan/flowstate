#!/usr/bin/env python3
"""
Debug script to understand pn532pi write function signatures
Run this on the Raspberry Pi to help diagnose the write issue
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import inspect
from pn532pi import Pn532, Pn532I2c

print("=" * 70)
print("PN532 Write Function Diagnostic")
print("=" * 70)

# Inspect the write function
print("\n1. Inspecting mifareultralight_WritePage method:")
print("-" * 70)
method = Pn532.mifareultralight_WritePage
print(f"Signature: {inspect.signature(method)}")
print(f"\nDocstring: {method.__doc__ or 'None'}")

try:
    source = inspect.getsource(method)
    print(f"\nSource code:")
    print(source)
except Exception as e:
    print(f"\nCould not get source: {e}")

# Try to get parameter info
print("\n2. Parameter analysis:")
print("-" * 70)
sig = inspect.signature(method)
for param_name, param in sig.parameters.items():
    print(f"  {param_name}: {param.annotation if param.annotation != inspect.Parameter.empty else 'no annotation'}")
    print(f"    Default: {param.default if param.default != inspect.Parameter.empty else 'no default'}")

# Now let's actually test different calling conventions with a real card
print("\n3. Testing write operations (requires card on reader):")
print("-" * 70)

try:
    # Initialize reader
    i2c = Pn532I2c(1)
    pn532 = Pn532(i2c)
    pn532.begin()

    version = pn532.getFirmwareVersion()
    if not version:
        print("ERROR: Could not communicate with PN532")
        sys.exit(1)

    print(f"PN532 Firmware: {(version >> 24) & 0xFF}.{(version >> 16) & 0xFF}")
    pn532.SAMConfig()

    input("\nPlace a card on the reader and press Enter to continue...")

    # Read card
    success, uid = pn532.readPassiveTargetID(cardbaudrate=0x00)
    if not success or not uid:
        print("ERROR: No card detected")
        sys.exit(1)

    uid_hex = "".join(["{:02X}".format(b) for b in uid])
    print(f"Card detected: {uid_hex}")

    # Test data to write (4 bytes: "TST\x00")
    test_data = b"TST\x00"
    test_page = 4  # Page 4 is first user-writable page on NTAG215

    print(f"\nWill test writing {repr(test_data)} to page {test_page}")
    print("WARNING: This will modify the card!")
    response = input("Continue? (y/n): ").strip().lower()
    if response != 'y':
        print("Aborted")
        sys.exit(0)

    # Try different calling methods
    methods_to_try = [
        ("bytes object", lambda: pn532.mifareultralight_WritePage(test_page, test_data)),
        ("bytearray", lambda: pn532.mifareultralight_WritePage(test_page, bytearray(test_data))),
        ("list of ints", lambda: pn532.mifareultralight_WritePage(test_page, [int(b) for b in test_data])),
        ("tuple of ints", lambda: pn532.mifareultralight_WritePage(test_page, tuple([int(b) for b in test_data]))),
        ("unpacked ints", lambda: pn532.mifareultralight_WritePage(test_page, *[int(b) for b in test_data])),
        ("comma-separated ints", lambda: pn532.mifareultralight_WritePage(test_page, test_data[0], test_data[1], test_data[2], test_data[3])),
    ]

    successful_method = None

    for method_name, method_func in methods_to_try:
        print(f"\nTrying: {method_name}")
        try:
            result = method_func()
            print(f"  Result: {result}")
            print(f"  Result type: {type(result)}")

            if result or result is None:
                # Try to verify by reading back
                try:
                    readback = pn532.mifareultralight_ReadPage(test_page)
                    if readback:
                        readback_bytes = bytes(readback[:4])
                        print(f"  Readback: {repr(readback_bytes)}")
                        if readback_bytes == test_data:
                            print(f"  ✓ SUCCESS! This method works!")
                            successful_method = method_name
                            break
                        else:
                            print(f"  ✗ Readback doesn't match")
                except Exception as e:
                    print(f"  Could not verify: {e}")
        except TypeError as e:
            print(f"  ✗ TypeError: {e}")
        except Exception as e:
            print(f"  ✗ Exception: {type(e).__name__}: {e}")

    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)
    if successful_method:
        print(f"✓ Successful method: {successful_method}")
    else:
        print("✗ No method worked!")

    # Additional library info
    print("\n4. Library information:")
    print("-" * 70)
    import pn532pi
    print(f"pn532pi version: {getattr(pn532pi, '__version__', 'unknown')}")
    print(f"pn532pi file location: {pn532pi.__file__}")

    # List all methods containing 'write' or 'Write'
    print("\nAvailable write methods:")
    for attr in dir(Pn532):
        if 'write' in attr.lower():
            method = getattr(Pn532, attr)
            if callable(method):
                try:
                    sig = inspect.signature(method)
                    print(f"  {attr}{sig}")
                except:
                    print(f"  {attr}(...)")

except Exception as e:
    print(f"\nFATAL ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
