#!/bin/bash
#
# Installation script for on-site setup features
# Installs: WiFi management, mDNS, peer monitoring, failover, watchdog
#
# Usage: sudo bash scripts/install_onsite_features.sh
#

set -e  # Exit on error

echo "=============================================="
echo "  NFC Tap Station - On-Site Features Setup"
echo "=============================================="
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run as root (use sudo)"
    exit 1
fi

# Get the actual user (not root when using sudo)
ACTUAL_USER=${SUDO_USER:-$USER}
USER_HOME=$(eval echo ~$ACTUAL_USER)
INSTALL_DIR="$USER_HOME/nfc-tap-logger"

echo "Installing as user: $ACTUAL_USER"
echo "Installation directory: $INSTALL_DIR"
echo

# ============================================
# Step 1: Install system dependencies
# ============================================
echo "Step 1: Installing system dependencies..."

# Update package lists
apt-get update

# Install WiFi and networking tools
echo "  - Installing WiFi tools..."
apt-get install -y \
    wireless-tools \
    wpasupplicant \
    network-manager \
    hostapd \
    dnsmasq

# Install mDNS/Avahi
echo "  - Installing Avahi (mDNS)..."
apt-get install -y \
    avahi-daemon \
    avahi-utils

# Enable and start avahi-daemon
systemctl enable avahi-daemon
systemctl start avahi-daemon

echo "  ✓ System dependencies installed"
echo

# ============================================
# Step 2: Install Python dependencies
# ============================================
echo "Step 2: Installing Python dependencies..."

# Activate virtual environment and install packages
su - $ACTUAL_USER -c "cd $INSTALL_DIR && source venv/bin/activate && pip install requests pyyaml"

echo "  ✓ Python dependencies installed"
echo

# ============================================
# Step 3: Create WiFi configuration
# ============================================
echo "Step 3: Creating WiFi configuration..."

# Create config directory
mkdir -p "$INSTALL_DIR/config"
chown $ACTUAL_USER:$ACTUAL_USER "$INSTALL_DIR/config"

# Create WiFi networks config file if it doesn't exist
WIFI_CONFIG="$INSTALL_DIR/config/wifi_networks.conf"
if [ ! -f "$WIFI_CONFIG" ]; then
    cat > "$WIFI_CONFIG" << 'EOF'
# WiFi Networks Configuration
# Format: SSID|password|priority (lower priority = connect first)
# Lines starting with # are comments

# Example networks (edit these for your sites):
#Festival-Staff|password123|1
#Site-Medical|pass456|2
#HarmReduction-Net|pass789|3

# Add your networks below:

EOF
    chown $ACTUAL_USER:$ACTUAL_USER "$WIFI_CONFIG"
    echo "  ✓ WiFi config template created at $WIFI_CONFIG"
    echo "    → Edit this file to add your WiFi networks"
else
    echo "  → WiFi config already exists: $WIFI_CONFIG"
fi

echo

# ============================================
# Step 4: Configure passwordless sudo for network commands
# ============================================
echo "Step 4: Configuring passwordless sudo for network commands..."

SUDOERS_FILE="/etc/sudoers.d/tap-station-network"

cat > "$SUDOERS_FILE" << EOF
# Allow tap-station user to manage network without password
$ACTUAL_USER ALL=(ALL) NOPASSWD: /sbin/shutdown
$ACTUAL_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart tap-station
$ACTUAL_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart tap-dashboard
$ACTUAL_USER ALL=(ALL) NOPASSWD: /bin/systemctl stop tap-station
$ACTUAL_USER ALL=(ALL) NOPASSWD: /bin/systemctl start tap-station
$ACTUAL_USER ALL=(ALL) NOPASSWD: /sbin/iwlist
$ACTUAL_USER ALL=(ALL) NOPASSWD: /sbin/wpa_cli
$ACTUAL_USER ALL=(ALL) NOPASSWD: /bin/hostnamectl
EOF

chmod 0440 "$SUDOERS_FILE"
echo "  ✓ Network sudo permissions configured"
echo

# ============================================
# Step 5: Set hostname for mDNS
# ============================================
echo "Step 5: Configuring mDNS hostname..."

# Read device_id from config.yaml
DEVICE_ID=$(grep "device_id:" "$INSTALL_DIR/config.yaml" | head -1 | sed 's/.*device_id: *"\(.*\)".*/\1/' | tr -d '"' | tr -d "'")

if [ -n "$DEVICE_ID" ]; then
    # Generate hostname from device_id
    if [[ "$DEVICE_ID" =~ queue|join ]]; then
        HOSTNAME="tapstation-queue"
    elif [[ "$DEVICE_ID" =~ exit|leave ]]; then
        HOSTNAME="tapstation-exit"
    else
        HOSTNAME="tapstation-$(echo $DEVICE_ID | tr '[:upper:]' '[:lower:]' | tr '_' '-')"
    fi

    echo "  Setting hostname to: $HOSTNAME"
    hostnamectl set-hostname "$HOSTNAME"
    echo "  ✓ Hostname set to $HOSTNAME"
    echo "    → Access via: http://$HOSTNAME.local:8080"
else
    echo "  ⚠️  Could not read device_id from config.yaml"
    echo "    → You may need to set hostname manually"
fi

echo

# ============================================
# Step 6: Create systemd service for watchdog
# ============================================
echo "Step 6: Creating watchdog systemd service..."

WATCHDOG_SERVICE="/etc/systemd/system/tap-watchdog.service"

cat > "$WATCHDOG_SERVICE" << EOF
[Unit]
Description=NFC Tap Station Watchdog
After=network.target tap-station.service

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$INSTALL_DIR/venv/bin/python -m tap_station.watchdog_runner
Restart=always
RestartSec=30

StandardOutput=append:$INSTALL_DIR/logs/watchdog.log
StandardError=append:$INSTALL_DIR/logs/watchdog-error.log

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

echo "  ✓ Watchdog service created"
echo "    → Enable with: sudo systemctl enable tap-watchdog"
echo "    → Start with: sudo systemctl start tap-watchdog"
echo

# ============================================
# Step 7: Update config.yaml with on-site features
# ============================================
echo "Step 7: Checking config.yaml for on-site features..."

# Check if onsite section exists in config.yaml
if ! grep -q "^onsite:" "$INSTALL_DIR/config.yaml"; then
    echo "  → On-site configuration not found in config.yaml"
    echo "    This might be an older config file."
    echo "    Please update your config.yaml or regenerate from the template."
else
    echo "  ✓ On-site configuration found in config.yaml"
fi

echo

# ============================================
# Step 8: Test installation
# ============================================
echo "Step 8: Testing installation..."

# Test avahi-daemon
if systemctl is-active --quiet avahi-daemon; then
    echo "  ✓ Avahi daemon is running"
else
    echo "  ⚠️  Avahi daemon is not running"
fi

# Test WiFi tools
if command -v iwgetid &> /dev/null; then
    echo "  ✓ WiFi tools installed"
else
    echo "  ⚠️  WiFi tools not found"
fi

# Test Python imports
if su - $ACTUAL_USER -c "cd $INSTALL_DIR && source venv/bin/activate && python -c 'from tap_station.onsite_manager import OnSiteManager' 2>/dev/null"; then
    echo "  ✓ Python modules import successfully"
else
    echo "  ⚠️  Python module import failed"
fi

echo

# ============================================
# Installation Complete
# ============================================
echo "=============================================="
echo "  Installation Complete!"
echo "=============================================="
echo
echo "Next steps:"
echo
echo "1. Edit WiFi configuration:"
echo "   nano $INSTALL_DIR/config/wifi_networks.conf"
echo
echo "2. Update config.yaml to enable on-site features:"
echo "   nano $INSTALL_DIR/config.yaml"
echo
echo "3. For peer monitoring, set the peer_hostname in config.yaml:"
echo "   onsite:"
echo "     failover:"
echo "       peer_hostname: \"tapstation-exit.local\""
echo
echo "4. Restart tap-station service:"
echo "   sudo systemctl restart tap-station"
echo
echo "5. (Optional) Enable watchdog service:"
echo "   sudo systemctl enable tap-watchdog"
echo "   sudo systemctl start tap-watchdog"
echo
echo "6. Access your station via:"
echo "   http://$(hostname).local:8080"
echo
echo "=============================================="
echo "  Setup complete! 🎉"
echo "=============================================="
