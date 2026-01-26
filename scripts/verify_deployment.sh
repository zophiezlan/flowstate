#!/bin/bash
#
# Deployment Verification Script
#
# Comprehensive checks for fresh Raspberry Pi deployment
# Run this after installation to verify everything is ready
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track overall success
ALL_PASSED=true

echo "=============================================="
echo "FlowState - Deployment Verification"
echo "=============================================="
echo ""

# Function to print test result
print_result() {
    local test_name="$1"
    local passed="$2"
    local message="${3:-}"

    if [ "$passed" = "true" ]; then
        echo -e "${GREEN}✓${NC} $test_name"
    else
        echo -e "${RED}✗${NC} $test_name"
        ALL_PASSED=false
    fi

    if [ -n "$message" ]; then
        echo "  $message"
    fi
}

# Function to print section header
print_header() {
    echo ""
    echo -e "${BLUE}=== $1 ===${NC}"
    echo ""
}

# Check if on Raspberry Pi
print_header "System Check"

if [ -f /proc/device-tree/model ]; then
    MODEL=$(cat /proc/device-tree/model)
    print_result "Running on Raspberry Pi" true "$MODEL"
else
    print_result "Running on Raspberry Pi" false "Not a Raspberry Pi"
fi

# Check Raspberry Pi OS version
if [ -f /etc/os-release ]; then
    OS_NAME=$(grep "^PRETTY_NAME=" /etc/os-release | cut -d'"' -f2)
    print_result "Operating System" true "$OS_NAME"
fi

# Check system dependencies
print_header "System Dependencies"

# Python 3
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    print_result "Python 3 installed" true "$PYTHON_VERSION"
else
    print_result "Python 3 installed" false "Not found"
fi

# pip
if command -v pip3 &> /dev/null; then
    print_result "pip3 installed" true
else
    print_result "pip3 installed" false "Not found"
fi

# i2c-tools
if command -v i2cdetect &> /dev/null; then
    print_result "i2c-tools installed" true
else
    print_result "i2c-tools installed" false "Not found"
fi

# git
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version)
    print_result "git installed" true "$GIT_VERSION"
else
    print_result "git installed" false "Not found"
fi

# Check I2C setup
print_header "I2C Configuration"

# I2C device exists
if [ -e /dev/i2c-1 ]; then
    print_result "I2C device exists" true "/dev/i2c-1"
    I2C_BUS=1
elif [ -e /dev/i2c-0 ]; then
    print_result "I2C device exists" true "/dev/i2c-0 (using bus 0)"
    I2C_BUS=0
else
    print_result "I2C device exists" false "Not found - I2C not enabled"
    I2C_BUS=-1
fi

# I2C kernel module
if lsmod | grep -q i2c_dev; then
    print_result "I2C kernel module loaded" true "i2c_dev"
else
    print_result "I2C kernel module loaded" false "i2c_dev not loaded"
fi

# I2C config file
if [ -f /boot/firmware/config.txt ]; then
    CONFIG_FILE="/boot/firmware/config.txt"
elif [ -f /boot/config.txt ]; then
    CONFIG_FILE="/boot/config.txt"
else
    CONFIG_FILE=""
fi

if [ -n "$CONFIG_FILE" ]; then
    if grep -q "^dtparam=i2c_arm=on" "$CONFIG_FILE"; then
        print_result "I2C enabled in config" true "$CONFIG_FILE"
    else
        print_result "I2C enabled in config" false "Not enabled in $CONFIG_FILE"
    fi
fi

# User in i2c group
if groups | grep -q i2c; then
    print_result "User in i2c group" true
else
    print_result "User in i2c group" false "Run: sudo usermod -a -G i2c $USER"
fi

# PN532 detection
if [ $I2C_BUS -ge 0 ]; then
    if command -v i2cdetect &> /dev/null; then
        if i2cdetect -y $I2C_BUS | grep -q " 24"; then
            print_result "PN532 detected" true "Address 0x24 on bus $I2C_BUS"
        else
            print_result "PN532 detected" false "Not found at 0x24"
            echo "  Run: sudo i2cdetect -y $I2C_BUS"
        fi
    fi
fi

# Check project structure
print_header "Project Files"

# Get installation directory
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$INSTALL_DIR"

# Check for key files
FILES=(
    "config.yaml"
    "requirements.txt"
    "scripts/install.sh"
    "scripts/verify_hardware.py"
    "tap_station/main.py"
    "tap_station/nfc_reader.py"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        print_result "File exists: $file" true
    else
        print_result "File exists: $file" false
    fi
done

# Check directories
print_header "Directories"

DIRS=(
    "data"
    "logs"
    "backups"
    "scripts"
    "tap_station"
    "tests"
    "docs"
)

for dir in "${DIRS[@]}"; do
    if [ -d "$dir" ]; then
        print_result "Directory exists: $dir" true
    else
        print_result "Directory exists: $dir" false
    fi
done

# Check virtual environment
print_header "Python Virtual Environment"

if [ -d "venv" ]; then
    print_result "Virtual environment exists" true "venv/"

    # Check if pn532pi is installed
    if [ -f "venv/bin/python" ]; then
        if venv/bin/python -c "import pn532pi" 2>/dev/null; then
            print_result "pn532pi installed" true
        else
            print_result "pn532pi installed" false "Run: source venv/bin/activate && pip install -r requirements.txt"
        fi

        # Check other key packages
        if venv/bin/python -c "import yaml" 2>/dev/null; then
            print_result "PyYAML installed" true
        else
            print_result "PyYAML installed" false
        fi

        # Check if RPi.GPIO is installed (may fail on non-Pi)
        if venv/bin/python -c "import RPi.GPIO" 2>/dev/null; then
            print_result "RPi.GPIO installed" true
        else
            print_result "RPi.GPIO installed" false "May be OK if not on Pi"
        fi
    fi
else
    print_result "Virtual environment exists" false "Run: python3 -m venv venv"
fi

# Check configuration
print_header "Configuration"

if [ -f "config.yaml" ]; then
    # Extract key config values
    DEVICE_ID=$(grep "device_id:" config.yaml | awk '{print $2}' | tr -d '"' || echo "")
    STAGE=$(grep "stage:" config.yaml | head -1 | awk '{print $2}' | tr -d '"' || echo "")
    SESSION_ID=$(grep "session_id:" config.yaml | awk '{print $2}' | tr -d '"' || echo "")

    if [ -n "$DEVICE_ID" ]; then
        print_result "Device ID configured" true "$DEVICE_ID"
    else
        print_result "Device ID configured" false "Not set in config.yaml"
    fi

    if [ -n "$STAGE" ]; then
        print_result "Stage configured" true "$STAGE"
    else
        print_result "Stage configured" false "Not set in config.yaml"
    fi

    if [ -n "$SESSION_ID" ]; then
        print_result "Session ID configured" true "$SESSION_ID"
    else
        print_result "Session ID configured" false "Not set in config.yaml"
    fi
fi

# Check systemd service
print_header "Systemd Service"

SERVICE_FILE="/etc/systemd/system/tap-station.service"

if [ -f "$SERVICE_FILE" ]; then
    print_result "Service file exists" true "$SERVICE_FILE"

    # Check if service is enabled
    if systemctl is-enabled tap-station &>/dev/null; then
        print_result "Service enabled" true "Will start on boot"
    else
        print_result "Service enabled" false "Run: sudo systemctl enable tap-station"
    fi

    # Check if service is running
    if systemctl is-active tap-station &>/dev/null; then
        print_result "Service running" true
    else
        print_result "Service running" false "Run: sudo systemctl start tap-station"
    fi
else
    print_result "Service file exists" false "Not installed"
fi

# Check power status
print_header "Power Status"

if command -v vcgencmd &> /dev/null; then
    THROTTLED=$(vcgencmd get_throttled 2>/dev/null | cut -d'=' -f2 || echo "unknown")

    if [ "$THROTTLED" = "0x0" ]; then
        print_result "No under-voltage" true "Power supply OK"
    else
        print_result "No under-voltage" false "Status: $THROTTLED - Check power supply"
    fi

    # Temperature
    TEMP=$(vcgencmd measure_temp 2>/dev/null | cut -d'=' -f2 || echo "unknown")
    if [ "$TEMP" != "unknown" ]; then
        print_result "Temperature" true "$TEMP"
    fi
fi

# Check disk space
print_header "Disk Space"

DISK_USAGE=$(df -h . | tail -1 | awk '{print $5}' | tr -d '%')
DISK_AVAIL=$(df -h . | tail -1 | awk '{print $4}')

if [ "$DISK_USAGE" -lt 80 ]; then
    print_result "Disk space" true "${DISK_AVAIL} available"
else
    print_result "Disk space" false "Only ${DISK_AVAIL} available (${DISK_USAGE}% used)"
fi

# Summary
echo ""
echo "=============================================="
echo "Verification Summary"
echo "=============================================="
echo ""

if [ "$ALL_PASSED" = "true" ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "Your deployment is ready. Next steps:"
    echo ""
    echo "  1. Initialize cards:"
    echo "     source venv/bin/activate"
    echo "     python scripts/init_cards.py --start 1 --end 100"
    echo ""
    echo "  2. Test the service:"
    echo "     sudo systemctl start tap-station"
    echo "     tail -f logs/tap-station.log"
    echo ""
    echo "  3. Test card reading by tapping a few cards"
    echo ""
    echo "  4. Verify auto-start:"
    echo "     sudo reboot"
    echo "     # After reboot: sudo systemctl status tap-station"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some checks failed!${NC}"
    echo ""
    echo "Please fix the issues above before deploying."
    echo ""
    echo "Common fixes:"
    echo "  - I2C issues: bash scripts/enable_i2c.sh && sudo reboot"
    echo "  - Missing deps: bash scripts/install.sh"
    echo "  - Service setup: bash scripts/install.sh"
    echo ""
    echo "For detailed help, see:"
    echo "  - docs/SETUP.md"
    echo "  - docs/TROUBLESHOOTING.md"
    echo "  - README.md"
    echo ""
    exit 1
fi
