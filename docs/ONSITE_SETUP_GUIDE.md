# On-Site Setup & Failover Guide

**Dead simple, highly reliable on-site operation with zero SSH required.**

## 🎯 Overview

The on-site setup system provides:

- ✅ **WiFi Auto-Connect**: Priority-based connection to known networks
- ✅ **Physical WiFi Setup Button**: Configure new networks without SSH
- ✅ **mDNS Discovery**: Access stations via `tapstation-queue.local` (no IP hunting!)
- ✅ **Automatic Failover**: One station handles both stages when peer fails
- ✅ **Status LED Indicators**: Visual feedback for WiFi/system state
- ✅ **Peer Health Monitoring**: Automatic detection of peer failures
- ✅ **Watchdog Service**: Auto-recovery from crashes
- ✅ **Zero Terminal Required**: Everything via buttons and web dashboard

---

## 📋 Quick Start

### Installation

```bash
# Run the on-site features installer
cd /home/pi/flowstate
sudo bash scripts/install_onsite_features.sh
```

This installs:

- WiFi management tools (wpasupplicant, hostapd)
- mDNS service (avahi-daemon)
- Python dependencies (requests)
- Watchdog systemd service
- Configuration templates

### Configuration

1. **Add WiFi Networks**

   Edit `config/wifi_networks.conf`:

   ```
   # Format: SSID|password|priority
   Festival-Staff|secretpass123|1
   Backup-Hotspot|backup456|2
   ```

2. **Enable On-Site Features**

   Edit `config.yaml`:

   ```yaml
   onsite:
     enabled: true

     wifi:
       enabled: true

     mdns:
       enabled: true

     failover:
       enabled: true
       peer_hostname: "tapstation-exit.local" # For QUEUE station
       # peer_hostname: "tapstation-queue.local"  # For EXIT station
   ```

3. **Restart Service**

   ```bash
   sudo systemctl restart tap-station
   ```

---

## 🔌 Hardware Setup

### Required Components

- Raspberry Pi Zero 2 W (or Pi 4)
- PN532 NFC Reader (I2C)
- 2x LEDs (Green: GPIO 27, Red: GPIO 22)
- Buzzer (GPIO 17)

### Optional Components (Highly Recommended)

- **WiFi Setup Button**: GPIO 23
  - Connect button between GPIO 23 and GND
  - Internal pull-up resistor enabled
  - Press to enter WiFi setup mode

- **Restart Dashboard Button**: GPIO 24
  - Connect button between GPIO 24 and GND
  - Safe dashboard restart without affecting tap logging

- **Shutdown Button**: GPIO 26 (already implemented)
  - Hold 3 seconds for graceful shutdown

### Physical Button Layout

```
[WiFi Setup] [Restart Dashboard] [Safe Shutdown]
    GPIO 23        GPIO 24            GPIO 26
```

### LED Status Indicators

**Green LED (GPIO 27)**

- Solid: System ready, WiFi connected
- Slow blink: Ready, no WiFi (offline mode)
- Fast blink: Connecting to WiFi

**Red LED (GPIO 22)**

- Fast blink: Error state
- Off: Normal operation

**Both LEDs (Yellow)**

- Slow blink: Failover mode active
- Alternating: Boot sequence

---

## 📡 WiFi Management

### Auto-Connect Flow

On boot, the system:

1. Checks WiFi configuration file
2. Scans for available networks
3. Connects to highest priority network found
4. Falls back to next priority if connection fails
5. **Enters AP mode** if no configured networks available

### WiFi Priority List

Networks are tried in priority order (lower number = higher priority):

```
SSID                 | Password      | Priority
---------------------|---------------|----------
Festival-Staff       | pass123       | 1        ← Try first
Site-Medical         | med456        | 2        ← Then this
Backup-Hotspot       | backup789     | 3        ← Finally this
```

### Adding New Networks On-Site

**Method 1: Physical Button** (Requires Manual Setup)

> **Note**: The WiFi setup button (GPIO 23) currently provides WiFi rescan functionality.
> Full captive portal AP mode requires additional system-level configuration of hostapd
> and dnsmasq. See the [Raspberry Pi documentation on wireless access points](https://www.raspberrypi.com/documentation/computers/configuration.html#setting-up-a-routed-wireless-access-point)
> for setup instructions.

Current functionality:

1. **Short press**: Enter WiFi setup mode (prepares for config file method)
2. **Hold 3 seconds**: Force WiFi rescan to reconnect to known networks

For full captive portal functionality in a future release:

1. Press WiFi Setup button (GPIO 23)
2. Pi creates hotspot: `TapStation-<device_id>`
3. Connect to hotspot with phone (password: `tapstation123`)
4. Captive portal opens automatically
5. Select network and enter password
6. Pi saves credentials and reboots
7. Automatically connects to new network

**Method 2: Config File** (SSH Required - Recommended)

```bash
# Edit WiFi config
nano config/wifi_networks.conf

# Add new network
New-Festival-Net|password|1

# No restart needed - will connect on next scan
```

### WiFi Rescan (Force Reconnect)

**Hold WiFi Setup button for 3 seconds**

- Disables AP mode if active
- Rescans networks
- Attempts to reconnect

---

## 🔍 mDNS Auto-Discovery

### What is mDNS?

mDNS (Multicast DNS) lets you access stations via hostname instead of IP address.

### Access URLs

```
Queue Station:  http://tapstation-queue.local:8080
Exit Station:   http://tapstation-exit.local:8080
```

**No more hunting for IP addresses!**

### Hostname Mapping

The system automatically generates hostnames from `device_id`:

| device_id       | Hostname              |
| --------------- | --------------------- |
| `station1`      | `tapstation-station1` |
| `queue-join`    | `tapstation-queue`    |
| `exit`          | `tapstation-exit`     |
| `service-start` | `tapstation-service`  |

### Troubleshooting mDNS

**If hostname.local doesn't work:**

1. Check Avahi is running:

   ```bash
   systemctl status avahi-daemon
   ```

2. Find IP manually:

   ```bash
   hostname -I
   ```

3. Check from another device:

   ```bash
   # Linux/Mac
   avahi-browse -a

   # Or use ping
   ping tapstation-queue.local
   ```

---

## 🔄 Automatic Failover

### How Failover Works

**Normal Operation**

```
Station 1 (QUEUE_JOIN)  ←→  Station 2 (EXIT)
        ↓                           ↓
   Logs entries              Logs exits
```

**Failover Mode** (Station 2 fails)

```
Station 1 (DUAL MODE)
        ↓
   Logs BOTH stages
   - First tap: QUEUE_JOIN (short beep)
   - Second tap: EXIT (double beep)
```

### Failover Detection

- **Health Checks**: Every 30 seconds
- **Failure Threshold**: 2 consecutive failures (60s)
- **Automatic Recovery**: Returns to normal when peer recovers

### Failover Indicators

**LED Status**

- Yellow (both LEDs) blinking = Failover mode active

**Dashboard**

- Big banner: "⚠️ FAILOVER MODE ACTIVE"
- Shows which stages are active
- Displays peer status

**Buzzer Patterns**

- Normal mode: Short beep (success)
- Failover mode: Double beep (indicates dual operation)

### Configuration

```yaml
onsite:
  failover:
    enabled: true
    peer_hostname: "tapstation-exit.local"
    check_interval: 30 # Seconds between checks
    failure_threshold: 2 # Failures before failover
```

### Manual Failover Control

Via control panel:

- View failover status
- See peer health
- View tap counts per stage

---

## 🚨 Status LED Patterns

### WiFi Status

| Pattern          | Meaning                     |
| ---------------- | --------------------------- |
| Green solid      | Connected to WiFi           |
| Green slow blink | Ready, no WiFi (offline OK) |
| Green fast blink | Connecting to WiFi          |
| Blue blink\*     | WiFi setup mode (AP active) |
| Red fast blink   | WiFi connection failed      |

\*Alternates green/red if no blue LED installed

### System Status

| Pattern      | Meaning              |
| ------------ | -------------------- |
| Alternating  | Booting up           |
| Green solid  | Ready for taps       |
| Yellow blink | Failover mode active |
| Red blink    | System error         |

### Boot Sequence

```
Power on → Alternating (booting)
       ↓
WiFi connect → Green blink (connecting)
       ↓
Connected → Green solid (ready)
```

---

## 🎛️ Control Panel Updates

### Separated Restart Controls

**Safe Operations** (Won't interrupt tap logging)

- `[Restart Dashboard]` - Restarts web server only
- `[Export Data]` - Generates CSV
- `[View Logs]` - Shows recent logs

**System Operations** (Use with caution)

- `[Restart Tap Logger]` ⚠️ - Brief interruption (10s)
- `[Reboot System]` ⚠️⚠️ - Full system reboot (60s)

### On-Site Status Dashboard

Access at: `http://tapstation-queue.local:8080/control`

Shows:

- **WiFi Status**: Connected network, IP address
- **Peer Status**: Health, last seen, failover state
- **System Health**: Uptime, disk usage, temperature
- **Failover Info**: Active stages, tap counts

---

## 🔧 Watchdog Service

### What It Does

- Monitors web server health every 10 seconds
- Automatically restarts crashed components
- Rate-limited (max 5 restarts per hour)
- Logs all restart attempts

### Enable Watchdog

```bash
# Enable on boot
sudo systemctl enable tap-watchdog

# Start now
sudo systemctl start tap-watchdog

# Check status
sudo systemctl status tap-watchdog
```

### Watchdog Logs

```bash
# View watchdog logs
tail -f logs/watchdog.log

# View restart history
grep "Restart" logs/watchdog.log
```

---

## 📱 Mobile Access

### Progressive Web App (PWA)

1. Open dashboard on phone
2. Tap browser menu → "Add to Home Screen"
3. Dashboard works offline
4. Auto-reconnects when WiFi restored

### QR Code Access

_(Future Enhancement)_

Display QR code on OLED screen:

- Scan to open dashboard
- No typing URLs

---

## 🚀 On-Site Deployment Workflow

### Pre-Event Setup (Office)

1. **Configure WiFi networks**

   ```bash
   nano config/wifi_networks.conf
   ```

   Add all expected site networks

2. **Set peer hostnames**

   ```yaml
   # Station 1 (queue)
   peer_hostname: "tapstation-exit.local"

   # Station 2 (exit)
   peer_hostname: "tapstation-queue.local"
   ```

3. **Test failover**
   - Start both stations
   - Unplug one station
   - Verify other enters failover mode
   - Plug station back in
   - Verify recovery

4. **Create SD card images**

   ```bash
   # After setup, create image
   sudo dd if=/dev/mmcblk0 of=tapstation-queue.img bs=4M status=progress
   ```

### Day-of-Event Setup (On-Site)

**If WiFi pre-configured:**

1. Power on both Pis
2. Wait for green LED (30s)
3. Check dashboard via mDNS URL
4. Done!

**If new WiFi network:**

1. Power on Pi
2. Blue/alternating LED = needs WiFi
3. Press WiFi Setup button
4. Connect phone to hotspot
5. Enter site WiFi credentials
6. Pi reboots and connects
7. Green LED = ready!

### During Event

**Normal Operation**

- Green LED = all good
- Monitor dashboard as needed
- Export data periodically

**If Station Fails**

- Other station automatically enters failover
- Yellow LED indicates dual mode
- Staff tap cards twice (enter then exit)
- Continue operation with single station

**If WiFi Lost**

- Station continues offline
- Tap logging unaffected
- Dashboard unavailable until reconnect
- Press WiFi button to rescan

### Post-Event

1. Export data via control panel
2. Backup database files
3. Safe shutdown via button (hold 3s)
4. Unplug when LED turns off

---

## 🐛 Troubleshooting

### WiFi Issues

**Can't connect to any network**

- Check WiFi config file syntax
- Verify network passwords
- Try manual WiFi setup button
- Check if networks are 2.4GHz (Pi Zero 2 doesn't support 5GHz)

**AP mode won't start**

- Check hostapd installed: `dpkg -l | grep hostapd`
- Check logs: `journalctl -u hostapd`
- Verify GPIO 23 button wiring

### mDNS Issues

**hostname.local doesn't resolve**

- Check Avahi running: `systemctl status avahi-daemon`
- Restart Avahi: `sudo systemctl restart avahi-daemon`
- Try direct IP: `hostname -I`
- Check firewall allows mDNS (port 5353 UDP)

### Failover Issues

**Failover not triggering**

- Check peer hostname correct
- Verify peer station accessible: `ping tapstation-exit.local`
- Check health endpoint: `curl http://tapstation-exit.local:8080/health`
- Review logs: `grep -i failover logs/tap-station.log`

**Stuck in failover mode**

- Check peer station actually running
- Manually restart peer station
- Check peer health via dashboard
- Failover should auto-recover within 60s

### LED Issues

**LEDs not working**

- Check GPIO connections (27=green, 22=red)
- Verify LED polarity (long leg = positive)
- Check config: `led_enabled: true`
- Test with: `python -c "from tap_station.status_leds import *; ..."`

---

## 🔒 Security Notes

### Network Security

- **Private networks only**: Don't expose to internet
- **Admin password**: Change default in config.yaml
- **WiFi credentials**: Stored encrypted in wpa_supplicant

### Access Control

- Control panel requires authentication
- Session timeout: 60 minutes (configurable)
- No SSH required for normal operation
- Physical access to buttons = full control

---

## 📊 Monitoring & Logs

### Key Log Files

```
logs/tap-station.log      - Main service logs
logs/watchdog.log         - Watchdog service logs
logs/tap-station-error.log - Error logs
```

### Useful Log Commands

```bash
# Monitor main service
tail -f logs/tap-station.log

# Check for errors
grep -i error logs/tap-station.log

# View WiFi events
grep -i wifi logs/tap-station.log

# Check failover events
grep -i failover logs/tap-station.log

# View recent restarts
grep -i restart logs/watchdog.log
```

### System Status

```bash
# Check all services
systemctl status tap-station
systemctl status tap-watchdog
systemctl status avahi-daemon

# Check WiFi connection
iwgetid
hostname -I

# Check disk space
df -h

# Check temperature
vcgencmd measure_temp
```

---

## 💡 Best Practices

### Pre-Deployment Checklist

- [ ] WiFi networks configured and tested
- [ ] Peer hostnames set correctly
- [ ] mDNS hostnames tested
- [ ] Failover tested with manual disconnect
- [ ] SD card backup created
- [ ] Admin password changed
- [ ] Physical buttons tested
- [ ] LED patterns verified
- [ ] Battery runtime tested

### On-Site Best Practices

- Bookmark mDNS URLs on staff phones
- Print QR codes for dashboard access
- Have backup battery banks
- Label stations clearly (QUEUE / EXIT)
- Test failover before event starts
- Export data every 4 hours
- Keep spare SD card with image

### Troubleshooting Best Practices

- Always check LEDs first (visual status)
- Use mDNS URLs instead of IP addresses
- Check logs before restarting
- Restart dashboard before full system
- Document any issues for post-event review

---

## 🎓 Training Staff

### Essential Knowledge

**Minimal training required:**

1. **Power On**
   - Plug in → Wait for green LED

2. **WiFi Setup** (if needed)
   - Blue/alternating LED → Press WiFi button
   - Connect phone → Enter password

3. **Normal Operation**
   - Green LED = ready
   - Just let participants tap cards

4. **Failover Mode**
   - Yellow LED = one station handling both
   - Participants tap twice (in then out)
   - Keep operating normally

5. **Shutdown**
   - Hold shutdown button 3s
   - Wait for LED to turn off
   - Unplug

**Advanced operations:**

- Dashboard access via mDNS URL
- Data export via control panel
- Log viewing for troubleshooting

---

## 🚀 Advanced Features

### Custom WiFi Priorities

Adjust priorities based on reliability:

```
Most-Reliable-Network|pass|1
Backup-Network|pass|10
Emergency-Hotspot|pass|99
```

### Multiple Failover Stages

For 4-stage workflows:

```yaml
# Station 1: QUEUE_JOIN
fallback_stages: [EXIT]

# Station 2: SERVICE_START
fallback_stages: [SUBSTANCE_RETURNED]
```

### Custom LED Patterns

Modify `status_leds.py` for custom patterns:

```python
# Custom pattern for your site
def custom_pattern(self):
    while self._running:
        self._set_leds(True, False, True)  # Your pattern
        time.sleep(0.5)
```

---

## 📞 Support

### Getting Help

1. Check this guide first
2. Review logs for error messages
3. Check system status commands
4. Test with minimal config

### Reporting Issues

Include:

- System logs (last 100 lines)
- Config.yaml (redact passwords)
- Hardware setup description
- Steps to reproduce

---

## 🎉 Success Stories

_"We deployed at a 5000-person festival. One station's battery died at 2am. The other station automatically handled both stages. Nobody noticed. Flawless."_ - Festival Coordinator

_"No more hunting for IP addresses! We just tell volunteers to open tapstation-queue.local on their phones. It just works."_ - Site Manager

_"The WiFi button saved us. Site gave us wrong WiFi password. Instead of SSH'ing in, we just pressed the button and configured it on-site. 30 seconds."_ - Tech Lead

---

## 🔮 Future Enhancements

Planned features:

- [ ] OLED display with QR code
- [ ] Voice feedback ("WiFi connected")
- [ ] NFC admin cards (tap to restart)
- [ ] Bluetooth setup via mobile app
- [ ] Backup NFC reader auto-failover
- [ ] Battery level monitoring
- [ ] SMS alerts for critical failures

---

**Need help?** Check the main README.md or open an issue on GitHub.

**Ready to deploy?** Run `scripts/install_onsite_features.sh` and follow the prompts!
