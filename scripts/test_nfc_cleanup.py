#!/usr/bin/env python3
"""
Test script for NFC cleanup functionality

This script tests the automatic cleanup and conflict resolution.
Run this to verify the cleanup manager works as expected.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tap_station.nfc_cleanup import NFCCleanupManager


def test_detection_only():
    """Test conflict detection without auto-fix"""
    print("=" * 60)
    print("Test 1: Detection Only (No Auto-Fix)")
    print("=" * 60)
    print()

    manager = NFCCleanupManager(auto_fix=False, require_sudo=False)
    success, messages = manager.check_and_cleanup(
        stop_service=False, reset_i2c=False
    )

    print("Results:")
    for msg in messages:
        print(f"  {msg}")

    print()
    print(f"Status: {'✓ PASS' if success else '✗ ISSUES DETECTED'}")
    print()

    return success


def test_auto_fix():
    """Test conflict detection with auto-fix"""
    print("=" * 60)
    print("Test 2: Detection with Auto-Fix")
    print("=" * 60)
    print()

    manager = NFCCleanupManager(auto_fix=True, require_sudo=True)
    success, messages = manager.check_and_cleanup(
        stop_service=True, reset_i2c=False
    )

    print("Results:")
    for msg in messages:
        print(f"  {msg}")

    print()
    print(f"Status: {'✓ PASS' if success else '✗ FAILED'}")
    print()

    return success


def test_convenience_function():
    """Test the convenience function"""
    print("=" * 60)
    print("Test 3: Convenience Function")
    print("=" * 60)
    print()

    from tap_station.nfc_cleanup import cleanup_before_nfc_access

    success = cleanup_before_nfc_access(
        stop_service=True,
        reset_i2c=False,
        require_sudo=True,
        verbose=True,
    )

    print()
    print(f"Status: {'✓ PASS' if success else '✗ FAILED'}")
    print()

    return success


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("NFC Cleanup Manager Test Suite")
    print("=" * 60)
    print()

    results = {}

    # Test 1: Detection only
    try:
        results["Detection"] = test_detection_only()
    except Exception as e:
        print(f"✗ Test 1 failed with exception: {e}")
        results["Detection"] = False

    # Test 2: Auto-fix
    try:
        results["Auto-Fix"] = test_auto_fix()
    except Exception as e:
        print(f"✗ Test 2 failed with exception: {e}")
        results["Auto-Fix"] = False

    # Test 3: Convenience function
    try:
        results["Convenience"] = test_convenience_function()
    except Exception as e:
        print(f"✗ Test 3 failed with exception: {e}")
        results["Convenience"] = False

    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    print()

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status} {test_name}")

    print()

    all_passed = all(results.values())
    if all_passed:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
