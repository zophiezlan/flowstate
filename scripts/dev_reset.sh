#!/bin/bash
# Development Reset Script
# Stops all services, kills processes, and resets I2C for clean dev environment
#
# NOTE: As of v2.2.2+, most scripts now automatically handle cleanup!
#       You usually don't need to run this manually anymore.
#       This script is kept for edge cases and manual troubleshooting.

set -e

COLOR_RESET='\033[0m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_RED='\033[0;31m'
COLOR_BLUE='\033[0;34m'

echo -e "${COLOR_BLUE}=============================================="
echo "NFC Tap Logger - Development Reset"
echo -e "==============================================${COLOR_RESET}\n"

# Check if running with sudo for service operations
if [[ $EUID -ne 0 ]] && command -v systemctl &> /dev/null; then
   echo -e "${COLOR_YELLOW}⚠ This script needs sudo for some operations${COLOR_RESET}"
   echo "Re-running with sudo..."
   sudo "$0" "$@"
   exit $?
fi

echo -e "${COLOR_BLUE}=== Stopping Services ===${COLOR_RESET}\n"

# Stop tap-station service if it exists
if command -v systemctl &> /dev/null; then
    if systemctl list-units --type=service --all | grep -q "tap-station"; then
        echo "Stopping tap-station service..."
        systemctl stop tap-station 2>/dev/null || true
        echo -e "${COLOR_GREEN}✓ Service stopped${COLOR_RESET}"
    else
        echo "No tap-station service found"
    fi
else
    echo "systemctl not available (non-systemd system)"
fi

echo ""
echo -e "${COLOR_BLUE}=== Killing Python Processes ===${COLOR_RESET}\n"

# Find and kill any Python processes running our scripts
KILLED=0

# Kill main.py processes
if pgrep -f "tap_station/main.py" > /dev/null; then
    echo "Killing main.py processes..."
    pkill -f "tap_station/main.py" || true
    KILLED=1
fi

# Kill init_cards.py processes
if pgrep -f "scripts/init_cards" > /dev/null; then
    echo "Killing init_cards processes..."
    pkill -f "scripts/init_cards" || true
    KILLED=1
fi

# Kill any other Python processes that might be using I2C
if pgrep -f "pn532" > /dev/null; then
    echo "Killing PN532-related processes..."
    pkill -f "pn532" || true
    KILLED=1
fi

if [ $KILLED -eq 1 ]; then
    echo -e "${COLOR_GREEN}✓ Processes killed${COLOR_RESET}"
    sleep 1  # Give time for cleanup
else
    echo "No processes found to kill"
fi

echo ""
echo -e "${COLOR_BLUE}=== Clearing Lock Files ===${COLOR_RESET}\n"

# Remove any PID files
if [ -f "/var/run/tap-station.pid" ]; then
    rm -f /var/run/tap-station.pid
    echo -e "${COLOR_GREEN}✓ Removed PID file${COLOR_RESET}"
fi

# Remove any socket files
if [ -S "/tmp/tap-station.sock" ]; then
    rm -f /tmp/tap-station.sock
    echo -e "${COLOR_GREEN}✓ Removed socket file${COLOR_RESET}"
fi

if [ ! -f "/var/run/tap-station.pid" ] && [ ! -S "/tmp/tap-station.sock" ]; then
    echo "No lock files found"
fi

echo ""
echo -e "${COLOR_BLUE}=== Resetting I2C Bus ===${COLOR_RESET}\n"

# Check if I2C device exists
if [ -e /dev/i2c-1 ]; then
    echo "Resetting I2C bus..."
    
    # Unload and reload I2C kernel modules
    if lsmod | grep -q i2c_dev; then
        modprobe -r i2c_dev 2>/dev/null || true
        sleep 0.5
        modprobe i2c_dev
        echo -e "${COLOR_GREEN}✓ I2C modules reloaded${COLOR_RESET}"
    else
        modprobe i2c_dev
        echo -e "${COLOR_GREEN}✓ I2C module loaded${COLOR_RESET}"
    fi
    
    sleep 1
    
    # Verify I2C is working
    if command -v i2cdetect &> /dev/null; then
        echo "Scanning I2C bus..."
        if i2cdetect -y 1 | grep -q "24"; then
            echo -e "${COLOR_GREEN}✓ PN532 detected at 0x24${COLOR_RESET}"
        else
            echo -e "${COLOR_YELLOW}⚠ PN532 not detected (may need physical reconnection)${COLOR_RESET}"
        fi
    fi
else
    echo -e "${COLOR_RED}✗ I2C device /dev/i2c-1 not found${COLOR_RESET}"
    echo "Run: sudo raspi-config -> Interface Options -> I2C -> Enable"
fi

echo ""
echo -e "${COLOR_BLUE}=== Optional Cleanup ===${COLOR_RESET}\n"

# Ask about log cleanup
read -p "Clear logs? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -d "logs" ]; then
        rm -rf logs/*.log logs/*.log.* 2>/dev/null || true
        echo -e "${COLOR_GREEN}✓ Logs cleared${COLOR_RESET}"
    fi
fi

# Ask about test data cleanup
read -p "Clear test data (data/*.db, data/*.csv)? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -d "data" ]; then
        rm -f data/*.db data/*.csv 2>/dev/null || true
        echo -e "${COLOR_GREEN}✓ Test data cleared${COLOR_RESET}"
    fi
fi

echo ""
echo -e "${COLOR_GREEN}=============================================="
echo "✓ Development Reset Complete"
echo -e "==============================================${COLOR_RESET}\n"

echo "You can now run:"
echo "  - bash scripts/verify_deployment.sh"
echo "  - python3 scripts/init_cards.py --mock"
echo "  - python3 tap_station/main.py"
echo ""
