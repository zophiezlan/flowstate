#!/bin/bash
#
# Installation script for FlowState on Raspberry Pi
#
# This script:
# - Installs system dependencies (Python, i2c-tools, git, etc.)
# - Enables I2C interface
# - Creates virtual environment
# - Installs Python dependencies
# - Sets up systemd service
# - Creates necessary directories
# - Performs basic configuration
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "======================================"
echo "FlowState - Installation Script"
echo "======================================"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Error: Please run as regular user (not root)${NC}"
    echo "The script will prompt for sudo when needed"
    exit 1
fi

# Check if on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo -e "${YELLOW}Warning: This doesn't appear to be a Raspberry Pi${NC}"
    echo "Installation will continue but hardware features may not work"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    MODEL=$(cat /proc/device-tree/model)
    echo -e "${GREEN}Detected: $MODEL${NC}"
    echo ""
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
echo -e "${BLUE}Step 2: Installing system dependencies...${NC}"
echo "This may take a few minutes..."
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-setuptools \
    build-essential \
    i2c-tools \
    git \
    wget \
    curl

echo -e "${GREEN}✓ System dependencies installed${NC}"

# Enable I2C
echo ""
echo -e "${BLUE}Step 3: Enabling I2C...${NC}"

# Find config file location (varies by Raspberry Pi OS version)
CONFIG_FILE=""
if [ -f /boot/firmware/config.txt ]; then
    CONFIG_FILE="/boot/firmware/config.txt"
elif [ -f /boot/config.txt ]; then
    CONFIG_FILE="/boot/config.txt"
else
    echo -e "${YELLOW}Warning: Could not find config.txt${NC}"
    echo "You may need to enable I2C manually using raspi-config"
    I2C_ENABLED=0
fi

if [ -n "$CONFIG_FILE" ]; then
    # Backup config file
    sudo cp "$CONFIG_FILE" "$CONFIG_FILE.backup.$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true

    if ! grep -q "^dtparam=i2c_arm=on" "$CONFIG_FILE"; then
        echo "Enabling I2C in $CONFIG_FILE"
        echo "dtparam=i2c_arm=on" | sudo tee -a "$CONFIG_FILE"
        I2C_ENABLED=1
        echo -e "${GREEN}✓ I2C enabled${NC}"
    else
        echo -e "${GREEN}✓ I2C already enabled in $CONFIG_FILE${NC}"
        I2C_ENABLED=0
    fi
fi

# Load I2C kernel module
if ! lsmod | grep -q i2c_dev; then
    echo "Loading I2C kernel module..."
    sudo modprobe i2c_dev 2>/dev/null || true
fi

# Add i2c_dev to /etc/modules for auto-load on boot
if ! grep -q "^i2c-dev" /etc/modules 2>/dev/null; then
    echo "i2c-dev" | sudo tee -a /etc/modules
    echo -e "${GREEN}✓ I2C module configured for auto-load${NC}"
fi

# Create i2c group if it doesn't exist
if ! getent group i2c > /dev/null 2>&1; then
    sudo groupadd i2c 2>/dev/null || true
fi

# Add user to i2c group
echo ""
echo -e "${BLUE}Step 4: Adding user to i2c group...${NC}"
if groups | grep -q i2c; then
    echo -e "${GREEN}✓ User already in i2c group${NC}"
else
    sudo usermod -a -G i2c "$USER"
    echo -e "${GREEN}✓ User added to i2c group${NC}"
    echo -e "${YELLOW}Note: Group change will take effect after logout/login or reboot${NC}"
fi

# Create virtual environment
echo ""
echo -e "${BLUE}Step 5: Creating Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

# Activate virtual environment and install dependencies
echo ""
echo -e "${BLUE}Step 6: Installing Python dependencies...${NC}"
echo "This may take a few minutes..."
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# Verify key packages
if python -c "import pn532pi" 2>/dev/null; then
    echo -e "${GREEN}✓ pn532pi installed${NC}"
else
    echo -e "${RED}✗ pn532pi installation failed${NC}"
fi

if python -c "import yaml" 2>/dev/null; then
    echo -e "${GREEN}✓ PyYAML installed${NC}"
else
    echo -e "${RED}✗ PyYAML installation failed${NC}"
fi

echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Create necessary directories
echo ""
echo -e "${BLUE}Step 7: Creating directories...${NC}"
mkdir -p data logs backups
chmod 755 data logs backups
touch data/.gitkeep logs/.gitkeep backups/.gitkeep
echo -e "${GREEN}✓ Directories created (data, logs, backups)${NC}"

# Copy example config if config.yaml doesn't exist
if [ ! -f "config.yaml" ]; then
    echo ""
    echo -e "${BLUE}Step 8: Creating default configuration...${NC}"

    # Copy from example template first
    if [ -f "config.yaml.example" ]; then
        cp config.yaml.example config.yaml
        echo "Created config.yaml from config.yaml.example"
    else
        echo -e "${RED}ERROR: config.yaml.example not found!${NC}"
        echo "Cannot create configuration file. Please check installation."
        exit 1
    fi

    # Prompt for basic configuration
    echo ""
    echo "Please provide basic configuration:"
    echo "(You can change these later by editing config.yaml)"
    echo ""
    read -p "Device ID (e.g., station1, station2): " DEVICE_ID
    DEVICE_ID=${DEVICE_ID:-station1}

    read -p "Stage (QUEUE_JOIN or EXIT): " STAGE
    STAGE=${STAGE:-QUEUE_JOIN}

    read -p "Session ID (e.g., festival-2025-summer): " SESSION_ID
    SESSION_ID=${SESSION_ID:-test-session-2025}

    # Update config with user values
    sed -i.bak "s/device_id: \".*\"/device_id: \"$DEVICE_ID\"/" config.yaml
    sed -i.bak "s/stage: \".*\"/stage: \"$STAGE\"/" config.yaml
    sed -i.bak "s/session_id: \".*\"/session_id: \"$SESSION_ID\"/" config.yaml
    rm -f config.yaml.bak

    echo ""
    echo -e "${GREEN}✓ Configuration file created: config.yaml${NC}"
    echo "  Device ID: $DEVICE_ID"
    echo "  Stage: $STAGE"
    echo "  Session ID: $SESSION_ID"
else
    echo ""
    echo -e "${YELLOW}Step 8: Configuration file already exists (skipped)${NC}"
    echo "Current config:"
    grep "device_id:" config.yaml || true
    grep "stage:" config.yaml | head -1 || true
    grep "session_id:" config.yaml || true
fi

# Install systemd service
echo ""
echo "Step 9: Installing systemd service..."

# Create service file
SERVICE_FILE="/etc/systemd/system/tap-station.service"
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=FlowState Station Service
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

# Configure sudoers for passwordless systemctl commands (needed for web control panel)
echo ""
echo "Step 10: Configuring passwordless sudo for systemctl..."
SUDOERS_FILE="/etc/sudoers.d/tap-station"
if [ ! -f "$SUDOERS_FILE" ]; then
    sudo tee "$SUDOERS_FILE" > /dev/null << SUDOEOF
# Allow $USER to control tap-station service without password
$USER ALL=(ALL) NOPASSWD: /bin/systemctl start tap-station
$USER ALL=(ALL) NOPASSWD: /bin/systemctl stop tap-station
$USER ALL=(ALL) NOPASSWD: /bin/systemctl restart tap-station
$USER ALL=(ALL) NOPASSWD: /bin/systemctl status tap-station
$USER ALL=(ALL) NOPASSWD: /bin/systemctl daemon-reload
$USER ALL=(ALL) NOPASSWD: /bin/systemctl enable tap-station
$USER ALL=(ALL) NOPASSWD: /bin/systemctl disable tap-station
$USER ALL=(ALL) NOPASSWD: /usr/sbin/i2cdetect
$USER ALL=(ALL) NOPASSWD: /sbin/reboot
$USER ALL=(ALL) NOPASSWD: /sbin/shutdown
SUDOEOF
    sudo chmod 0440 "$SUDOERS_FILE"
    echo -e "${GREEN}✓ Sudoers configured for control panel${NC}"
else
    echo -e "${YELLOW}Sudoers file already exists (skipped)${NC}"
fi

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
echo -e "${GREEN}Installation Complete!${NC}"
echo "======================================"
echo ""

if [ $I2C_ENABLED -eq 1 ]; then
    echo -e "${YELLOW}⚠ IMPORTANT: I2C was just enabled.${NC}"
    echo -e "${YELLOW}You MUST reboot for changes to take effect:${NC}"
    echo ""
    echo "  sudo reboot"
    echo ""
    echo "After reboot, continue with these steps:"
else
    echo "Next steps:"
fi

echo ""
echo "1. Verify hardware:"
echo "   bash scripts/verify_deployment.sh"
echo ""
echo "2. Or manually check I2C:"
echo "   sudo i2cdetect -y 1"
echo "   (Should show device at address 0x24)"
echo ""
echo "3. Run full hardware verification:"
echo "   source venv/bin/activate"
echo "   python scripts/verify_hardware.py"
echo ""
echo "4. Test the service:"
echo "   sudo systemctl start tap-station"
echo "   tail -f logs/tap-station.log"
echo ""
echo "5. Initialize cards:"
echo "   source venv/bin/activate"
echo "   python scripts/init_cards.py --start 1 --end 100"
echo "   (The script will automatically stop the service if needed)"
echo ""
echo "6. After your event, export data:"
echo "   python scripts/export_data.py"
echo ""
echo "Note: Scripts now automatically handle NFC reader conflicts!"
echo "      No need to manually run dev_reset scripts in most cases."
echo ""
echo "For detailed deployment guide:"
echo "  docs/SETUP.md"
echo ""
echo "For troubleshooting:"
echo "  docs/TROUBLESHOOTING.md"
echo "  README.md"
echo ""
