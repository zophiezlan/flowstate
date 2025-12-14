#!/bin/bash
#
# Installation script for NFC Tap Logger on Raspberry Pi
#
# This script:
# - Installs system dependencies
# - Enables I2C
# - Creates virtual environment
# - Installs Python dependencies
# - Sets up systemd service
# - Creates necessary directories
#

set -e  # Exit on error

echo "======================================"
echo "NFC Tap Logger - Installation Script"
echo "======================================"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Please run as regular user (not root)"
    echo "The script will prompt for sudo when needed"
    exit 1
fi

# Check if on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "Warning: This doesn't appear to be a Raspberry Pi"
    echo "Installation will continue but hardware features may not work"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Get installation directory
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Installation directory: $INSTALL_DIR"
cd "$INSTALL_DIR"

# Update package lists
echo ""
echo "Step 1: Updating package lists..."
sudo apt-get update

# Install system dependencies
echo ""
echo "Step 2: Installing system dependencies..."
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    i2c-tools \
    git

# Enable I2C
echo ""
echo "Step 3: Enabling I2C..."
if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt; then
    echo "Enabling I2C in /boot/config.txt"
    echo "dtparam=i2c_arm=on" | sudo tee -a /boot/config.txt
    I2C_ENABLED=1
else
    echo "I2C already enabled"
    I2C_ENABLED=0
fi

# Load I2C kernel module
if ! lsmod | grep -q i2c_dev; then
    echo "Loading I2C kernel module"
    sudo modprobe i2c_dev
fi

# Add i2c_dev to /etc/modules for auto-load on boot
if ! grep -q "^i2c-dev" /etc/modules; then
    echo "i2c-dev" | sudo tee -a /etc/modules
fi

# Add user to i2c group
echo ""
echo "Step 4: Adding user to i2c group..."
sudo usermod -a -G i2c "$USER"

# Create virtual environment
echo ""
echo "Step 5: Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created"
else
    echo "Virtual environment already exists"
fi

# Activate virtual environment and install dependencies
echo ""
echo "Step 6: Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "Python dependencies installed"

# Create necessary directories
echo ""
echo "Step 7: Creating directories..."
mkdir -p data logs backups
touch data/.gitkeep logs/.gitkeep backups/.gitkeep
echo "Directories created"

# Copy example config if config.yaml doesn't exist
if [ ! -f "config.yaml" ]; then
    echo ""
    echo "Step 8: Creating default configuration..."
    cp config.yaml config.yaml.example 2>/dev/null || true

    # Prompt for basic configuration
    echo ""
    echo "Please provide basic configuration:"
    read -p "Device ID (e.g., station1): " DEVICE_ID
    read -p "Stage (QUEUE_JOIN or EXIT): " STAGE
    read -p "Session ID (e.g., festival-2025-summer): " SESSION_ID

    # Update config with user input
    sed -i "s/device_id: \"station1\"/device_id: \"$DEVICE_ID\"/" config.yaml
    sed -i "s/stage: \"QUEUE_JOIN\"/stage: \"$STAGE\"/" config.yaml
    sed -i "s/session_id: \"test-session-2025\"/session_id: \"$SESSION_ID\"/" config.yaml

    echo "Configuration file created: config.yaml"
else
    echo ""
    echo "Step 8: Configuration file already exists (skipped)"
fi

# Install systemd service
echo ""
echo "Step 9: Installing systemd service..."

# Create service file
SERVICE_FILE="/etc/systemd/system/tap-station.service"
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=NFC Tap Station Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python -m tap_station.main --config $INSTALL_DIR/config.yaml
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "Systemd service created: $SERVICE_FILE"

# Reload systemd
sudo systemctl daemon-reload

# Ask if user wants to enable service
echo ""
read -p "Enable tap-station service to start on boot? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo systemctl enable tap-station
    echo "Service enabled"
fi

# Installation complete
echo ""
echo "======================================"
echo "Installation Complete!"
echo "======================================"
echo ""
echo "Hardware verification:"
echo "  Run: sudo i2cdetect -y 1"
echo "  Should show device at address 0x24"
echo ""
echo "Test the service:"
echo "  sudo systemctl start tap-station"
echo "  sudo systemctl status tap-station"
echo "  tail -f logs/tap-station.log"
echo ""
echo "Initialize cards:"
echo "  source venv/bin/activate"
echo "  python scripts/init_cards.py --start 1 --end 100"
echo ""
echo "Export data:"
echo "  python scripts/export_data.py"
echo ""

if [ $I2C_ENABLED -eq 1 ]; then
    echo "IMPORTANT: I2C was just enabled."
    echo "You must reboot for changes to take effect:"
    echo "  sudo reboot"
    echo ""
fi

echo "For more information, see README.md"
echo ""
