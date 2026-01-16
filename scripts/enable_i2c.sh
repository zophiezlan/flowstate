#!/bin/bash
#
# I2C Setup and Troubleshooting Script for Raspberry Pi
#
# This script:
# - Checks if I2C is enabled
# - Enables I2C if needed
# - Verifies I2C device exists
# - Provides troubleshooting guidance
#

set -e

echo "=============================================="
echo "NFC Tap Logger - I2C Setup & Troubleshooting"
echo "=============================================="
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "Error: This doesn't appear to be a Raspberry Pi"
    echo "This script is only for Raspberry Pi devices"
    exit 1
fi

# Function to check if I2C is enabled in config
check_i2c_config() {
    local config_file=""

    # Check for config file in different locations
    if [ -f /boot/firmware/config.txt ]; then
        config_file="/boot/firmware/config.txt"
    elif [ -f /boot/config.txt ]; then
        config_file="/boot/config.txt"
    else
        echo "Error: Cannot find Raspberry Pi config.txt"
        echo "Checked: /boot/config.txt and /boot/firmware/config.txt"
        return 1
    fi

    echo "Config file: $config_file"

    if grep -q "^dtparam=i2c_arm=on" "$config_file"; then
        echo "✓ I2C is enabled in $config_file"
        return 0
    else
        echo "✗ I2C is NOT enabled in $config_file"
        return 1
    fi
}

# Function to enable I2C in config
enable_i2c_config() {
    local config_file=""

    if [ -f /boot/firmware/config.txt ]; then
        config_file="/boot/firmware/config.txt"
    elif [ -f /boot/config.txt ]; then
        config_file="/boot/config.txt"
    else
        echo "Error: Cannot find config.txt to enable I2C"
        return 1
    fi

    echo ""
    echo "Enabling I2C in $config_file..."

    # Backup config file
    sudo cp "$config_file" "$config_file.backup.$(date +%Y%m%d-%H%M%S)"

    # Add I2C parameter if not present
    if ! grep -q "^dtparam=i2c_arm=on" "$config_file"; then
        echo "dtparam=i2c_arm=on" | sudo tee -a "$config_file"
        echo "✓ I2C enabled in config"
        return 0
    fi
}

# Function to check if I2C device exists
check_i2c_device() {
    if [ -e /dev/i2c-1 ]; then
        echo "✓ I2C device /dev/i2c-1 exists"
        return 0
    elif [ -e /dev/i2c-0 ]; then
        echo "⚠ I2C device exists at /dev/i2c-0 (some Pi models use bus 0)"
        return 0
    else
        echo "✗ I2C device does NOT exist"
        return 1
    fi
}

# Function to load I2C kernel module
load_i2c_module() {
    if lsmod | grep -q i2c_dev; then
        echo "✓ I2C kernel module (i2c_dev) is loaded"
        return 0
    else
        echo "⚠ I2C kernel module not loaded, loading now..."
        sudo modprobe i2c_dev

        if lsmod | grep -q i2c_dev; then
            echo "✓ I2C kernel module loaded successfully"

            # Add to /etc/modules for auto-load on boot
            if ! grep -q "^i2c-dev" /etc/modules 2>/dev/null; then
                echo "i2c-dev" | sudo tee -a /etc/modules
                echo "✓ Added i2c-dev to /etc/modules for auto-load"
            fi
            return 0
        else
            echo "✗ Failed to load I2C kernel module"
            return 1
        fi
    fi
}

# Function to check user permissions
check_i2c_permissions() {
    if groups | grep -q i2c; then
        echo "✓ User '$USER' is in i2c group"
        return 0
    else
        echo "⚠ User '$USER' is NOT in i2c group"
        echo "  Adding user to i2c group..."
        sudo usermod -a -G i2c "$USER"
        echo "✓ User added to i2c group"
        echo "⚠ You need to log out and back in for group changes to take effect"
        return 1
    fi
}

# Function to scan I2C bus
scan_i2c_bus() {
    echo ""
    echo "Scanning I2C bus for devices..."

    if [ -e /dev/i2c-1 ]; then
        echo "Scanning /dev/i2c-1:"
        i2cdetect -y 1

        # Check for PN532 at 0x24
        if i2cdetect -y 1 | grep -q "24"; then
            echo ""
            echo "✓ PN532 NFC reader detected at address 0x24"
            return 0
        else
            echo ""
            echo "✗ PN532 NOT detected at address 0x24"
            return 1
        fi
    elif [ -e /dev/i2c-0 ]; then
        echo "Scanning /dev/i2c-0:"
        i2cdetect -y 0

        if i2cdetect -y 0 | grep -q "24"; then
            echo ""
            echo "✓ PN532 NFC reader detected at address 0x24 (on bus 0)"
            echo "⚠ Note: Your Pi uses I2C bus 0, not bus 1"
            return 0
        else
            echo ""
            echo "✗ PN532 NOT detected at address 0x24"
            return 1
        fi
    else
        echo "✗ No I2C device found to scan"
        return 1
    fi
}

# Main execution
echo "Step 1: Checking I2C configuration..."
if ! check_i2c_config; then
    echo ""
    read -p "Enable I2C now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        enable_i2c_config
        REBOOT_NEEDED=1
    else
        echo "I2C not enabled. Exiting."
        exit 1
    fi
else
    REBOOT_NEEDED=0
fi

echo ""
echo "Step 2: Checking I2C kernel module..."
load_i2c_module

echo ""
echo "Step 3: Checking I2C device..."
if ! check_i2c_device; then
    if [ $REBOOT_NEEDED -eq 0 ]; then
        echo ""
        echo "=============================================="
        echo "⚠ REBOOT REQUIRED"
        echo "=============================================="
        echo ""
        echo "The I2C configuration has been updated, but"
        echo "the system needs to be rebooted for the"
        echo "/dev/i2c device to be created."
        echo ""
        read -p "Reboot now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo reboot
        else
            echo ""
            echo "Please reboot manually: sudo reboot"
            echo "Then run this script again to verify."
            exit 1
        fi
    else
        echo ""
        echo "=============================================="
        echo "⚠ REBOOT REQUIRED"
        echo "=============================================="
        echo ""
        echo "I2C has been enabled in the config file."
        echo "You MUST reboot for the changes to take effect."
        echo ""
        read -p "Reboot now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo reboot
        else
            echo ""
            echo "Please reboot manually: sudo reboot"
            exit 1
        fi
    fi
fi

echo ""
echo "Step 4: Checking user permissions..."
check_i2c_permissions

echo ""
echo "Step 5: Scanning for PN532 NFC reader..."
if ! scan_i2c_bus; then
    echo ""
    echo "=============================================="
    echo "Troubleshooting: PN532 Not Detected"
    echo "=============================================="
    echo ""
    echo "The I2C bus is working, but the PN532 NFC"
    echo "reader was not detected at address 0x24."
    echo ""
    echo "Please check the following:"
    echo ""
    echo "1. Wiring - Verify connections:"
    echo "   PN532 VCC → Pi Pin 1 (3.3V)"
    echo "   PN532 GND → Pi Pin 6 (GND)"
    echo "   PN532 SDA → Pi Pin 3 (GPIO 2)"
    echo "   PN532 SCL → Pi Pin 5 (GPIO 3)"
    echo ""
    echo "2. PN532 Mode - Check jumpers/switches:"
    echo "   - Must be set to I2C mode"
    echo "   - Some modules have switches or jumpers"
    echo "   - Consult your PN532 module documentation"
    echo ""
    echo "3. Power - Ensure proper power:"
    echo "   - Use 3.3V NOT 5V (5V can damage the Pi)"
    echo "   - Check power LED on PN532 (if present)"
    echo ""
    echo "4. Connections - Check for:"
    echo "   - Loose wires"
    echo "   - Broken solder joints"
    echo "   - Incorrect pin assignments"
    echo ""
    echo "After checking, run this script again:"
    echo "  bash scripts/enable_i2c.sh"
    echo ""
    exit 1
fi

echo ""
echo "=============================================="
echo "✓ I2C Setup Complete!"
echo "=============================================="
echo ""
echo "I2C is properly configured and the PN532"
echo "NFC reader is detected."
echo ""
echo "Next steps:"
echo "  1. Run hardware verification:"
echo "     source venv/bin/activate"
echo "     python scripts/verify_hardware.py"
echo ""
echo "  2. Initialize NFC cards:"
echo "     python scripts/init_cards.py --start 1 --end 100"
echo ""
echo "  3. Start the tap station service:"
echo "     sudo systemctl start tap-station"
echo ""
