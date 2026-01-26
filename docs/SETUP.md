# Setup Guide

Complete guide for deploying FlowState on Raspberry Pi hardware.

## Quick Reference

| Task                   | Estimated Time             |
| ---------------------- | -------------------------- |
| Hardware assembly      | 10 minutes                 |
| Software installation  | 15 minutes                 |
| Card initialization    | 20 minutes (for 100 cards) |
| Total first-time setup | ~45 minutes                |

**Already set up?** Skip to [Operations Guide](OPERATIONS.md) for day-of-event workflow.

---

## Hardware Requirements

### Essential Components

- **Raspberry Pi Zero 2 W** (or Pi 4)
  - 512MB RAM, WiFi/Bluetooth
  - Comes with GPIO header pre-soldered (WH version)
- **PN532 NFC Module** (I2C mode)
  - Blue PCB version recommended
  - Must support I2C communication
- **NTAG215 NFC Cards** (100× recommended)
  - 540 bytes storage per card
  - Rewritable
- **USB-C Power Bank** (10,000mAh minimum)
  - Quality cable essential for stable power
- **MicroSD Card** (8GB minimum, 16GB+ recommended)
  - Class 10 or better for reliability

### Optional Components

- **Piezo Buzzer** (active, 3-5V)
  - Audio feedback for taps
- **LEDs** (green/red) + 220Ω resistors
  - Visual feedback
- **Weatherproof enclosure**
  - Protection for outdoor use
- **Velcro/mounting tape**
  - Secure positioning

---

## Part 1: Hardware Setup

### Step 1: Prepare the Raspberry Pi

1. **Install Raspberry Pi OS:**
   - Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
   - Choose: "Raspberry Pi OS Lite" (64-bit recommended)
   - Enable SSH in advanced options
   - Configure WiFi (if needed for setup)
   - Write to SD card

2. **Boot the Pi:**
   - Insert SD card
   - Connect power
   - Wait ~30 seconds for first boot
   - SSH into Pi: `ssh pi@raspberrypi.local`

### Step 2: Configure PN532 for I2C Mode

**Important:** PN532 modules have DIP switches or jumpers to select communication mode.

**For modules with DIP switches:**

```
Switch 1: OFF (I2C mode)
Switch 2: ON  (I2C mode)
```

**For modules with solder jumpers:**

- Bridge I2C pads (usually marked "SEL0" and "SEL1")
- Consult your module's documentation

### Step 3: Wire PN532 to Raspberry Pi

**Critical:** Use 3.3V, NOT 5V! Using 5V can damage your Raspberry Pi.

```
PN532 Pin    →    Raspberry Pi GPIO
─────────────────────────────────────────
VCC          →    Pin 1  (3.3V)     🔴 RED
GND          →    Pin 6  (GND)      ⚫ BLACK
SDA          →    Pin 3  (GPIO 2)   🔵 BLUE
SCL          →    Pin 5  (GPIO 3)   🟡 YELLOW
```

**Pin diagram:**

```
Pi Zero GPIO Header (top view)
    3.3V [ 1] [ 2] 5V
 GPIO 2  [ 3] [ 4] 5V
 GPIO 3  [ 5] [ 6] GND
         [ 7] [ 8]
     GND [ 9] [10]
         ...
```

**Visual verification:**

- Red wire → Pin 1 (top left, square pad)
- Blue wire → Pin 3 (second row, left)
- Yellow wire → Pin 5 (third row, left)
- Black wire → Pin 6 (third row, right)

### Step 4: Wire Optional Components (Recommended)

For easier wiring, use an 830-point breadboard to organize all connections. See detailed breadboard layout in `wiring_schematic.md`.

**Buzzer (Optional but recommended):**

```
Buzzer Pin   →    Raspberry Pi GPIO
──────────────────────────────────────
Positive (+) →    Pin 11 (GPIO 17)
Negative (-) →    Any GND pin
```

**LEDs with 220Ω Resistors (Optional but recommended):**

```
LED          →    Raspberry Pi GPIO
──────────────────────────────────────
Green LED    →    Pin 13 (GPIO 27) → 220Ω resistor → LED anode (+) → LED cathode (-) → GND
Red LED      →    Pin 15 (GPIO 22) → 220Ω resistor → LED anode (+) → LED cathode (-) → GND
```

**Important:** Always connect resistor in series between GPIO and LED anode (long leg).

**Shutdown Button (Optional but recommended):**

```
Button Pin   →    Raspberry Pi GPIO
──────────────────────────────────────
Button leg 1 →    Pin 37 (GPIO 26)
Button leg 2 →    Pin 39 (GND)
```

The button uses internal pull-up resistor (no external resistor needed). Press and hold for 3 seconds to trigger clean shutdown.

**DS3231 RTC Module:**

```
RTC Pin      →    Raspberry Pi GPIO (shared I2C bus)
──────────────────────────────────────
VCC          →    Pin 1 (3.3V)
GND          →    Pin 6 (GND)
SDA          →    Pin 3 (GPIO 2) - shared with PN532 and OLED
SCL          →    Pin 5 (GPIO 3) - shared with PN532 and OLED
```

**Note:** Install CR1220 backup battery in RTC module before use.

### Step 5: Double-Check Connections

Before powering on:

- [ ] VCC connected to 3.3V (Pin 1), NOT 5V
- [ ] All connections secure
- [ ] No loose wires touching other pins
- [ ] PN532 set to I2C mode
- [ ] LED resistors in series (220Ω between GPIO and LED anode)
- [ ] CR1220 battery installed in RTC module

---

## Part 2: Software Installation

### Step 1: Clone Repository

```bash
cd ~
git clone https://github.com/zophiezlan/flowstate.git
cd flowstate
```

### Step 2: Run Installation Script

```bash
bash scripts/install.sh
```

The script will:

1. Install system packages (Python 3.9+, i2c-tools, build tools)
2. Enable I2C interface
3. Create Python virtual environment
4. Install Python dependencies
5. Configure systemd service
6. Create data/logs directories
7. Copy example config

**Expected output:**

```
✓ System packages installed
✓ I2C interface enabled
✓ Virtual environment created
✓ Python packages installed
✓ Systemd service configured
✓ Directories created
✓ Config file ready

⚠ REBOOT REQUIRED to enable I2C
```

### Step 3: Reboot

```bash
sudo reboot
```

Wait 30 seconds, then SSH back in.

### Step 4: Verify Hardware

```bash
cd ~/flowstate
source venv/bin/activate
python scripts/verify_hardware.py
```

**Expected output:**

```
============================================================
I2C Bus Check
============================================================
I2C device exists................................... ✓ PASS
I2C kernel module loaded............................ ✓ PASS
i2c-tools installed................................. ✓ PASS
PN532 detected at 0x24.............................. ✓ PASS

============================================================
NFC Reader Check
============================================================
pn532pi library installed........................... ✓ PASS
PN532 initialization................................ ✓ PASS
PN532 firmware version.............................. ✓ PASS
  Firmware: v1.6

============================================================
GPIO Check
============================================================
RPi.GPIO available.................................. ✓ PASS
Buzzer GPIO (17) accessible......................... ✓ PASS

============================================================
Power Status
============================================================
No throttling detected.............................. ✓ PASS
  Status: 0x0 (good)
```

**If checks fail**, see [Troubleshooting](TROUBLESHOOTING.md).

### Step 5: Configure DS3231 RTC (Optional but Recommended)

The DS3231 RTC maintains accurate time even when the Pi is powered off. This is critical for accurate timestamps during events.

**1. Enable RTC overlay:**

```bash
sudo nano /boot/config.txt
```

Add this line at the end:

```
dtoverlay=i2c-rtc,ds3231
```

Save and exit (Ctrl+X, Y, Enter).

**2. Disable fake-hwclock:**

```bash
sudo apt-get -y remove fake-hwclock
sudo update-rc.d -f fake-hwclock remove
```

**3. Reboot to load RTC:**

```bash
sudo reboot
```

**4. Verify RTC detection:**

```bash
sudo i2cdetect -y 1
```

You should see `UU` at address 0x68 (indicates RTC is in use by kernel):

```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- 24 -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- UU -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```

**5. Set system time from RTC:**

```bash
# Read current time from RTC
sudo hwclock -r

# If RTC time is correct, set system time from RTC
sudo hwclock -s

# If RTC time is wrong, set it from system time (ensure Pi has network time first)
sudo hwclock -w
```

**6. Test RTC persistence:**

```bash
# Set a test time
date

# Write to RTC
sudo hwclock -w

# Reboot
sudo reboot

# After reboot, check time is maintained
date
```

The RTC will now maintain time across reboots and power cycles (battery backup required).

---

## Part 3: Configuration

### Step 1: Edit Config File

```bash
nano config.yaml
```

### Step 2: Configure Station Settings

**For Station 1 (Queue Entry):**

```yaml
station:
  device_id: "station1"
  stage: "QUEUE_JOIN"
  session_id: "festival-2026-01"
```

**For Station 2 (Exit):**

```yaml
station:
  device_id: "station2"
  stage: "EXIT"
  session_id: "festival-2026-01"
```

**Important:** Use the same `session_id` for both stations at the same event.

### Step 3: Configure Hardware Pins (If Needed)

If you wired components to different GPIO pins:

```yaml
feedback:
  buzzer_enabled: true
  led_enabled: true

  gpio:
    buzzer: 17 # BCM pin number
    led_green: 27
    led_red: 22
```

### Step 4: Optional Settings

**Enable/disable shutdown button:**

```yaml
shutdown_button:
  enabled: true # Enable shutdown button on GPIO 26
  gpio_pin: 26 # BCM pin number
  hold_time: 3.0 # Seconds to hold for shutdown
```

Press and hold button for 3 seconds to trigger a clean system shutdown.

**Disable buzzer/LEDs:**

```yaml
feedback:
  buzzer_enabled: false
  led_enabled: false
```

**Adjust debounce time:**

```yaml
nfc:
  debounce_seconds: 2.0 # Ignore same card for 2 seconds
```

**Enable web status server:**

```yaml
web_server:
  enabled: true
  host: "0.0.0.0"
  port: 8080
```

**Configure shutdown button passwordless sudo (if enabled):**

If you enabled the shutdown button, configure passwordless sudo for safe shutdowns:

```bash
sudo visudo -f /etc/sudoers.d/tap-station
```

Add this line (replace `pi` with your username):

```
pi ALL=(ALL) NOPASSWD: /sbin/shutdown
```

Save and exit. This allows the shutdown button to work without password prompts.

Save and exit: `Ctrl+X`, `Y`, `Enter`

---

## Part 4: Initialize NFC Cards

You need to initialize cards before first use.

### Option A: Simple Initialization (UID only)

Uses the card's built-in UID as the token ID:

```bash
source venv/bin/activate
python scripts/init_cards.py --start 1 --end 100
```

**Workflow:**

1. Script prompts you to tap a card
2. Tap card on reader
3. Script reads UID and assigns token ID (001, 002, etc.)
4. Beep confirms success
5. Repeat for all cards

**Creates:** `data/card_mapping.csv` mapping UIDs to token IDs

### Option B: NDEF Initialization (NFC Tools Compatible)

Writes NDEF records so participants can tap their phones to check status:

```bash
source venv/bin/activate
python scripts/init_cards_with_ndef.py \
  --start 1 \
  --end 100 \
  --url "https://your-server.com/check"
```

**This writes:**

- Token ID as text record
- URL pointing to status page

**Requires:** `ndeflib` package (installed by default)

### Tips for Card Initialization

- **Label cards:** Write token ID on cards with marker
- **Work in batches:** Do 20-30 cards at a time
- **Backup mapping:** Copy `data/card_mapping.csv` to safe location
- **Re-initialization:** Cards can be re-initialized anytime

---

## Part 5: Testing

### Test 1: Start Service Manually

```bash
source venv/bin/activate
python -m tap_station.main --config config.yaml
```

**Expected output:**

```
============================================================
FlowState Station Starting
Device: station1
Stage: QUEUE_JOIN
Session: festival-2026-01
============================================================
INFO: Database initialized
INFO: NFC reader initialized
INFO: Feedback controller initialized
INFO: Ready for NFC taps
```

**Test a tap:**

1. Hold NFC card near reader
2. Listen for beep
3. Check console for log entry

Press `Ctrl+C` to stop.

### Test 2: Enable Systemd Service

```bash
sudo systemctl enable tap-station
sudo systemctl start tap-station
```

**Check status:**

```bash
sudo systemctl status tap-station
```

**Expected:**

```
● tap-station.service - FlowState Station
   Active: active (running) since ...
   Main PID: 1234 (python)
```

**View live logs:**

```bash
tail -f logs/tap-station.log
```

### Test 3: Test Auto-Restart

```bash
# Find process
ps aux | grep tap_station

# Kill it
sudo kill -9 <PID>

# Check if it restarted
sleep 5
sudo systemctl status tap-station
```

Should show `active (running)` with a new PID.

### Test 4: Test Reboot Persistence

```bash
sudo reboot
```

After reboot:

```bash
sudo systemctl status tap-station
```

Should be running automatically.

---

## Part 6: Pre-Event Checklist

One week before event:

- [ ] Both Pis boot successfully
- [ ] PN532 readers detected on both stations
- [ ] Buzzers working
- [ ] Services auto-start on boot
- [ ] Config files correct (check device_id, stage, session_id)
- [ ] All 100 cards initialized
- [ ] Card mapping backed up
- [ ] Power banks fully charged
- [ ] Spare power bank available
- [ ] Cables tested and working
- [ ] SD cards backed up
- [ ] Weatherproof cases ready
- [ ] "TAP HERE" signs printed
- [ ] Peer guide printed ([Operations Guide](OPERATIONS.md))

---

## Backup & Recovery

### Backup Before Event

```bash
# Backup database
cp data/events.db backups/events_$(date +%Y%m%d).db

# Backup config
cp config.yaml backups/config_$(date +%Y%m%d).yaml

# Backup card mapping
cp data/card_mapping.csv backups/card_mapping_$(date +%Y%m%d).csv
```

### Restore from Backup

```bash
# Restore database
cp backups/events_YYYYMMDD.db data/events.db

# Restart service
sudo systemctl restart tap-station
```

### Complete SD Card Image

After successful setup:

```bash
# On your laptop (not the Pi)
sudo dd if=/dev/sdX of=tap-station-master.img bs=4M status=progress
gzip tap-station-master.img
```

Can restore this image to any SD card for quick deployment.

---

## Common Setup Issues

### "PN532 not detected at 0x24"

**Cause:** Wiring issue or wrong I2C mode

**Fix:**

1. Check all 4 wire connections
2. Verify PN532 is in I2C mode (check DIP switches)
3. Try other I2C bus: `sudo i2cdetect -y 0`
4. Check for loose connections

### "I2C device not found"

**Cause:** I2C not enabled

**Fix:**

```bash
bash scripts/enable_i2c.sh
sudo reboot
```

### "Permission denied on GPIO"

**Cause:** User not in gpio group

**Fix:**

```bash
sudo usermod -a -G gpio,i2c $USER
# Logout and login again
```

### "Database locked"

**Cause:** Multiple processes accessing database

**Fix:**

```bash
sudo systemctl stop tap-station
# Wait 5 seconds
sudo systemctl start tap-station
```

### Service won't start

**Check logs:**

```bash
sudo journalctl -u tap-station -n 50
```

**Common causes:**

- Missing config file
- Wrong Python path
- Missing dependencies

**For more issues**, see [Troubleshooting Guide](TROUBLESHOOTING.md).

---

## Part 7: Post-Installation Verification

### Automated Verification (Recommended)

Run the comprehensive verification script:

```bash
bash scripts/verify_deployment.sh
```

This checks everything automatically. If all passes, you're ready!

### Manual Verification Checklist

**Hardware:**

- [ ] PN532 detected at 0x24: `sudo i2cdetect -y 1`
- [ ] All wiring connections secure
- [ ] Buzzer working (if connected)

**Software:**

- [ ] Python 3.9+: `python3 --version`
- [ ] Virtual environment created: `ls -d venv`
- [ ] All packages installed: `pip list | grep pn532pi`
- [ ] Config file exists and correct: `cat config.yaml`

**Directories:**

- [ ] `data/` directory exists
- [ ] `logs/` directory exists
- [ ] `backups/` directory exists

**Service:**

- [ ] Service file exists: `sudo systemctl cat tap-station`
- [ ] Service enabled: `sudo systemctl is-enabled tap-station`
- [ ] Service active: `sudo systemctl status tap-station`
- [ ] Logs being written: `tail logs/tap-station.log`

**Power:**

- [ ] No under-voltage: `vcgencmd get_throttled` (should be `0x0`)
- [ ] Acceptable temperature: `vcgencmd measure_temp`
- [ ] Sufficient disk space: `df -h`

### Reliability Tests

**Test 1: Basic operation**

```bash
source venv/bin/activate
python -m tap_station.main --config config.yaml
# Tap a card, should beep and log
```

- [ ] Service starts without errors
- [ ] Card tap produces beep
- [ ] Event logged to console

**Test 2: Service mode**

```bash
sudo systemctl start tap-station
tail -f logs/tap-station.log
# Tap a card
```

- [ ] Service starts successfully
- [ ] Card tap logged to file
- [ ] Beep feedback works

**Test 3: Auto-start on boot**

```bash
sudo reboot
# After reboot (~30 seconds):
sudo systemctl status tap-station
```

- [ ] Service started automatically
- [ ] Status shows "active (running)"
- [ ] Can tap cards immediately

**Test 4: Auto-restart on crash**

```bash
# Kill the process
sudo pkill -f tap_station
sleep 10
sudo systemctl status tap-station
```

- [ ] Service restarted automatically
- [ ] Status shows "active (running)"
- [ ] Ready to accept taps

**Test 5: Database integrity**

```bash
source venv/bin/activate
python -c "from tap_station.database import Database; db = Database('data/events.db'); print(f'Events: {db.get_event_count()}')"
```

- [ ] Database accessible
- [ ] Event count matches test taps
- [ ] No corruption errors

**Test 6: Data export**

```bash
source venv/bin/activate
python scripts/export_data.py
```

- [ ] Export CSV created
- [ ] Contains all test events
- [ ] Timestamps are accurate

### Final Verification

**All systems go when:**

- ✅ Automated verification passes
- ✅ Service runs reliably
- ✅ Cards initialize successfully
- ✅ Auto-start/restart works
- ✅ Data export works

---

## Next Steps

✅ Hardware assembled
✅ Software installed
✅ Cards initialized
✅ Service tested
✅ Deployment verified

**Ready for deployment!** See:

- [Operations Guide](OPERATIONS.md) - Day-of-event workflow
- [Troubleshooting](TROUBLESHOOTING.md) - Fix common issues
- [Mobile Guide](MOBILE.md) - Use phones instead of Pis

---

## Quick Command Reference

```bash
# Check service status
sudo systemctl status tap-station

# View logs
tail -f logs/tap-station.log

# Restart service
sudo systemctl restart tap-station

# Check I2C
sudo i2cdetect -y 1

# Check power
vcgencmd get_throttled

# Export data
python scripts/export_data.py

# View stats
python -m tap_station.main --stats
```
