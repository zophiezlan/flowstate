# Troubleshooting Guide

Complete troubleshooting guide for NFC Tap Logger system issues.

---

## Quick Diagnosis Flowchart

```
Problem: Station not working
         ↓
    [Is Pi powered?]
         ├─ NO → Check power bank, cable
         └─ YES ↓
              [See activity LED?]
              ├─ NO → Power issue (see Power section)
              └─ YES ↓
                   [Does tap give beep?]
                   ├─ NO → NFC reader issue (see NFC section)
                   ├─ LONG BEEP → Card issue (see Cards section)
                   └─ CORRECT BEEP → Working! ✓
```

---

## Development / Testing Issues

### Problem: Scripts Hang or Freeze

**Symptoms:**

- `verify_deployment.sh` hangs at I2C check
- `init_cards.py` freezes when waiting for card
- Can't run multiple scripts simultaneously

**Cause:**
Service or another process is holding the NFC reader

**Automatic Fix (Recommended):**

Scripts now automatically detect and resolve conflicts! Just run the script normally:

```bash
# These scripts now handle cleanup automatically
python3 scripts/verify_hardware.py
python3 scripts/init_cards.py --start 1 --end 10
python3 scripts/init_cards_with_ndef.py --start 1 --end 10
```

The scripts will:

- Detect if tap-station service is running
- Stop the service automatically (with your permission)
- Clean up any stuck processes
- Verify the NFC reader is accessible
- Restart the service when done (if it was running before)

**Manual Fix (If Automatic Fails):**

```bash
# Option 1: Quick Python reset (no sudo)
python3 scripts/dev_reset.py

# Option 2: Full reset with I2C bus reset (needs sudo)
sudo bash scripts/dev_reset.sh
```

**Legacy Manual Steps:**

```bash
# Stop the service
sudo systemctl stop tap-station

# Kill any hanging processes using specific PIDs
ps aux | grep "tap_station\|init_cards"
kill <PID>

# Reset I2C bus (needs sudo)
sudo modprobe -r i2c_dev
sudo modprobe i2c_dev

# Verify PN532 is detected
i2cdetect -y 1
```

**What the automatic cleanup does:**

- Checks if tap-station service is running and stops it
- Finds Python processes using the NFC reader and terminates them gracefully
- Verifies I2C device accessibility
- Checks PN532 detection
- Optionally resets I2C bus if needed
- Restarts service when script completes (if it was enabled)

---

## I2C / NFC Reader Issues

### Problem: "PN532 not detected at 0x24"

**Symptoms:**

- `verify_hardware.py` fails
- `sudo i2cdetect -y 1` shows no device at 0x24
- Service won't start

**Diagnosis steps:**

1. **Check I2C is enabled**

   ```bash
   ls -la /dev/i2c*
   ```

   - Should show `/dev/i2c-1` (or `/dev/i2c-0` on older Pis)
   - If not found, I2C not enabled

2. **Check wiring**

   ```
   PN532    →    Pi GPIO
   VCC      →    Pin 1 (3.3V) ← RED wire
   GND      →    Pin 6 (GND)  ← BLACK wire
   SDA      →    Pin 3        ← BLUE wire
   SCL      →    Pin 5        ← YELLOW wire
   ```

   - Verify each connection is secure
   - Check no crossed wires
   - Confirm VCC is on 3.3V, NOT 5V

3. **Check PN532 mode**
   - PN532 must be in I2C mode
   - Check DIP switches or solder jumpers
   - Consult module documentation

4. **Try alternate I2C bus**

   ```bash
   sudo i2cdetect -y 0
   ```

   - Some Pis use bus 0 instead of 1
   - If device found on bus 0, update `config.yaml`:

     ```yaml
     nfc:
       i2c_bus: 0
     ```

**Solutions:**

**Enable I2C:**

```bash
bash scripts/enable_i2c.sh
sudo reboot
```

**Manual I2C enable:**

```bash
# Edit boot config
sudo nano /boot/config.txt
# Or on newer Pis:
sudo nano /boot/firmware/config.txt

# Add this line:
dtparam=i2c_arm=on

# Save and reboot
sudo reboot
```

**Check I2C permissions:**

```bash
sudo usermod -a -G i2c,gpio $USER
# Logout and login again
```

**Test with i2cdetect:**

```bash
sudo i2cdetect -y 1
```

Expected output with PN532:

```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- 24 -- -- -- -- -- -- -- -- -- -- --
   ← PN532 should appear at 0x24
```

---

### Problem: NFC Read Failures / Long Beeps

**Symptoms:**

- Cards tap but give long error beep
- Logs show "Failed to read NFC card"
- Works sometimes but unreliable

**Possible causes:**

1. **Wrong card type**
   - **Check:** Are you using NTAG215 cards?
   - **Fix:** Order NTAG215 specifically

2. **Cards not initialized**
   - **Check:** Did you run `init_cards.py`?
   - **Fix:** Initialize cards:

     ```bash
     python scripts/init_cards.py --start 1 --end 100
     ```

3. **Poor contact**
   - **Check:** How long is card held on reader?
   - **Fix:** Hold card flat, centered, for 2+ seconds

4. **Reader distance/orientation**
   - **Check:** Is card touching reader surface?
   - **Fix:** Position reader so card can lay flat on antenna

5. **Power issues**
   - **Check:** `vcgencmd get_throttled`
   - **Fix:** See Power Issues section

6. **Interference**
   - **Check:** Are there metal objects nearby?
   - **Fix:** Remove metal, reposition reader

**Diagnostic tests:**

```bash
# Test NFC reading directly
source venv/bin/activate
python3 << EOF
from pn532pi import Pn532, pn532
from pn532pi import Pn532I2c

i2c = Pn532I2c(1)  # Bus 1
nfc = Pn532(i2c)
nfc.begin()

print("Waiting for card...")
success, uid = nfc.readPassiveTargetID(pn532.PN532_MIFARE_ISO14443A_106KBPS)

if success:
    print(f"Success! UID: {uid.hex()}")
else:
    print("Failed to read card")
EOF
```

---

## Power Issues

### Problem: Pi Throttling / Unstable Operation

**Symptoms:**

- Yellow lightning bolt icon (if display connected)
- Slow operation
- Random reboots
- `vcgencmd get_throttled` shows non-zero value

**Check throttling status:**

```bash
vcgencmd get_throttled
```

**Values:**

- `0x0` = ✓ Good, no throttling
- `0x50000` = ⚠️ Under-voltage detected
- `0x50005` = ⚠️ Currently under-voltage
- Any non-zero = Problem

**Causes & solutions:**

1. **Weak power bank**
   - **Solution:** Use quality 2A+ power bank
   - **Test:** Try different power bank

2. **Bad USB cable**
   - **Solution:** Use thick, short USB-C cable
   - **Test:** Try different cable

3. **Power bank in power-save mode**
   - **Solution:** Some power banks sleep with low draw
   - **Fix:** Tape power button down or use "always-on" mode

4. **Too many peripherals**
   - **Solution:** Disconnect unnecessary USB devices

**Recommended power banks:**

- Anker PowerCore series
- RAVPower
- Minimum 10,000mAh, 2A output

---

### Problem: Pi Won't Boot

**Symptoms:**

- No LED activity
- No response to ping
- Power bank charged but Pi dead

**Diagnostic steps:**

1. **Check power bank**
   - Is it charged? (check indicator LEDs)
   - Is it turned on? (some have power button)
   - Try different power bank

2. **Check cable**
   - Try different USB-C cable
   - Check for bent pins

3. **Check SD card**
   - Remove and reinsert SD card
   - Try SD card in different device
   - Reflash SD card if corrupted

4. **Check for damage**
   - Look for burnt components
   - Smell for burning
   - Check if Pi is hot to touch

**Recovery:**

- Boot from backup SD card
- Reflash OS to SD card
- Replace Pi if hardware failure

---

## Software Issues

### Problem: Service Won't Start

**Check service status:**

```bash
sudo systemctl status tap-station
```

**Common errors:**

**1. "No such file or directory: config.yaml"**

```
Solution:
cd ~/nfc-tap-logger
cp config.yaml.example config.yaml
nano config.yaml  # Edit as needed
sudo systemctl restart tap-station
```

**2. "ModuleNotFoundError: No module named 'pn532pi'"**

```
Solution:
cd ~/nfc-tap-logger
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart tap-station
```

**3. "Permission denied: /dev/i2c-1"**

```
Solution:
sudo usermod -a -G i2c,gpio $USER
# Logout and login, then:
sudo systemctl restart tap-station
```

**4. "Database is locked"**

```
Solution:
sudo systemctl stop tap-station
sleep 5
sudo systemctl start tap-station
```

**View detailed logs:**

```bash
# Service logs
sudo journalctl -u tap-station -n 100 -f

# Application logs
tail -f logs/tap-station.log
```

---

### Problem: Service Keeps Crashing

**Check crash logs:**

```bash
sudo journalctl -u tap-station --since "10 minutes ago"
```

**Common causes:**

1. **Python exception**
   - Check `logs/tap-station.log` for stack trace
   - May be code bug or config error

2. **Hardware failure**
   - PN532 disconnected during operation
   - I2C bus errors

3. **Database corruption**
   - Rare due to WAL mode
   - Restore from backup:

     ```bash
     sudo systemctl stop tap-station
     cp backups/events_BACKUP.db data/events.db
     sudo systemctl start tap-station
     ```

4. **Out of memory**
   - Check: `free -h`
   - Unlikely on Pi Zero 2 W

**Force full restart:**

```bash
sudo systemctl stop tap-station
sudo systemctl daemon-reload
sudo systemctl start tap-station
```

---

### Problem: Database Locked

**Symptoms:**

- "Database is locked" errors
- Can't export data
- Service won't start

**Cause:**
Multiple processes trying to access database simultaneously

**Solution 1: Stop service**

```bash
sudo systemctl stop tap-station
# Wait 5 seconds for WAL checkpoint
sleep 5
# Try operation again
python scripts/export_data.py
```

**Solution 2: Check for stale locks**

```bash
# Check for database lock files
ls -la data/events.db*
# Remove WAL files if service is stopped
rm data/events.db-shm data/events.db-wal
```

**Solution 3: Copy database**

```bash
# If export still fails, copy database first
cp data/events.db /tmp/events_copy.db
# Export from copy
python scripts/export_data.py --db /tmp/events_copy.db
```

**Prevention:**

- WAL mode (enabled by default) prevents most locking
- Don't access database while service running
- Use `--stats` flag instead of direct DB access

---

## Card Issues

### Problem: Cards Not Working

**Symptoms:**

- All cards give error beeps
- `verify_hardware.py` succeeds but real cards fail
- Inconsistent reads

**Diagnostic:**

1. **Check card type**

   ```bash
   python3 << EOF
   from pn532pi import Pn532, Pn532I2c, pn532

   i2c = Pn532I2c(1)
   nfc = Pn532(i2c)
   nfc.begin()

   success, uid = nfc.readPassiveTargetID(pn532.PN532_MIFARE_ISO14443A_106KBPS)
   if success:
       print(f"Card detected: {uid.hex()}")
       print("Card appears to be working")
   else:
       print("Card not detected")
   EOF
   ```

2. **Verify card type**
   - Should be NTAG215 (504 bytes usable)
   - NTAG213 (144 bytes) also works
   - Mifare Classic might not work

3. **Check initialization**

   ```bash
   # List initialized cards
   cat data/card_mapping.csv
   ```

**Solutions:**

**Re-initialize cards:**

```bash
python scripts/init_cards.py --start 1 --end 100
```

**Test single card:**

```bash
python scripts/init_cards.py --start 1 --end 1
# Tap card when prompted
```

**Try different cards:**

- Order NTAG215 from reputable supplier
- Amazon: Search "NTAG215 NFC cards"
- Verify "NFC Forum Type 2" compatible

---

### Problem: Duplicate Taps Not Detected

**Symptoms:**

- Same card tapped multiple times logs multiple events
- Should get double-beep but getting single beep each time

**Check debounce setting:**

```bash
grep debounce config.yaml
```

Should show:

```yaml
nfc:
  debounce_seconds: 1.0
```

**If too short:**

```yaml
nfc:
  debounce_seconds: 3.0 # Increase to 3 seconds
```

**Note:** Debounce only applies within same session. Cards can be tapped at different stations without duplication detection.

---

## Network Issues (If Web Server Enabled)

### Problem: Can't Access Web Status Page

**Check web server enabled:**

```bash
grep -A3 "web_server" config.yaml
```

Should show:

```yaml
web_server:
  enabled: true
  host: "0.0.0.0"
  port: 8080
```

**Check service includes web server:**

```bash
tail -f logs/tap-station.log | grep -i web
```

Should show:

```
INFO: Web server started on 0.0.0.0:8080
```

**Find Pi's IP address:**

```bash
hostname -I
```

**Test locally on Pi:**

```bash
curl http://localhost:8080/health
```

**Test from another device:**

```bash
curl http://<pi-ip>:8080/health
```

**Firewall issues:**

```bash
# Disable firewall temporarily to test
sudo ufw disable
# If that fixes it, allow port:
sudo ufw allow 8080
sudo ufw enable
```

---

## GPIO / Buzzer Issues

### Problem: No Buzzer Sound

**Symptoms:**

- NFC reads work (logs show events)
- No audio feedback

**Check buzzer enabled:**

```bash
grep -A5 "feedback" config.yaml
```

Should show:

```yaml
feedback:
  buzzer_enabled: true
```

**Check GPIO pin:**

```yaml
gpio:
  buzzer: 17 # BCM numbering
```

**Test buzzer directly:**

```bash
python3 << EOF
import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.OUT)

# Beep 3 times
for i in range(3):
    GPIO.output(17, GPIO.HIGH)
    time.sleep(0.2)
    GPIO.output(17, GPIO.LOW)
    time.sleep(0.2)

GPIO.cleanup()
print("If you heard 3 beeps, buzzer works!")
EOF
```

**If no beeps:**

1. Check buzzer wiring
2. Check buzzer type (needs active buzzer, not passive)
3. Try different GPIO pin
4. Check buzzer polarity

---

### Problem: Buzzer Constantly On or Behaving Strangely

**Cause:** GPIO not cleaned up properly

**Fix:**

```bash
# Stop service
sudo systemctl stop tap-station

# Clean up GPIO
python3 << EOF
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.OUT)
GPIO.output(17, GPIO.LOW)
GPIO.cleanup()
EOF

# Restart service
sudo systemctl start tap-station
```

---

## Data Export Issues

### Problem: Export Script Fails

**Check Python environment:**

```bash
cd ~/nfc-tap-logger
source venv/bin/activate
which python
# Should show: /home/pi/nfc-tap-logger/venv/bin/python
```

**Run export with verbose logging:**

```bash
python scripts/export_data.py --config config.yaml
```

**If database locked:**

```bash
# Stop service first
sudo systemctl stop tap-station
sleep 5
python scripts/export_data.py
sudo systemctl start tap-station
```

**If no data:**

```bash
# Check database has events
python -m tap_station.main --stats
```

---

### Problem: Missing Events in Export

**Check session ID:**

```bash
# What session is the data in?
python3 << EOF
import sqlite3
conn = sqlite3.connect('data/events.db')
sessions = conn.execute('SELECT DISTINCT session_id FROM events').fetchall()
print("Sessions in database:", sessions)
conn.close()
EOF
```

**Export specific session:**

```bash
python scripts/export_data.py --session "festival-2026-01"
```

**Export all sessions:**

```bash
python scripts/export_data.py --session ""
```

---

## Emergency Recovery

### Complete System Reset

**If everything is broken:**

```bash
# 1. Stop service
sudo systemctl stop tap-station

# 2. Backup data
mkdir -p ~/backup_$(date +%Y%m%d)
cp data/events.db ~/backup_$(date +%Y%m%d)/
cp config.yaml ~/backup_$(date +%Y%m%d)/
cp logs/tap-station.log ~/backup_$(date +%Y%m%d)/

# 3. Reinstall
cd ~/nfc-tap-logger
git pull
bash scripts/install.sh

# 4. Restore config
cp ~/backup_$(date +%Y%m%d)/config.yaml .

# 5. Test
python scripts/verify_hardware.py

# 6. Start service
sudo systemctl start tap-station
```

---

### SD Card Recovery

**If SD card corrupted:**

1. **Remove SD card from Pi**
2. **Insert into laptop**
3. **Backup data:**

   ```bash
   # Mount SD card (usually automounts)
   cp /media/<sd-card>/home/pi/nfc-tap-logger/data/events.db ~/backup/
   cp /media/<sd-card>/home/pi/nfc-tap-logger/config.yaml ~/backup/
   ```

4. **Reflash OS:**
   - Use Raspberry Pi Imager
   - Fresh install of Raspberry Pi OS Lite

5. **Reinstall software:**
   - Follow [Setup Guide](SETUP.md)

6. **Restore data:**

   ```bash
   cp ~/backup/events.db ~/nfc-tap-logger/data/
   cp ~/backup/config.yaml ~/nfc-tap-logger/
   ```

---

## Getting Help

### Before Asking for Help

**Collect diagnostic information:**

```bash
# System info
uname -a
cat /proc/device-tree/model

# Service status
sudo systemctl status tap-station

# Recent logs
sudo journalctl -u tap-station -n 50 > ~/debug-log.txt
tail -n 100 logs/tap-station.log >> ~/debug-log.txt

# Hardware check
python scripts/verify_hardware.py > ~/hardware-check.txt

# I2C scan
sudo i2cdetect -y 1 > ~/i2c-scan.txt

# Config (sanitized)
cat config.yaml >> ~/config-check.txt
```

**Include in help request:**

- What you were trying to do
- What happened instead
- Error messages (exact text)
- Steps to reproduce
- Output from above diagnostic commands

### Where to Get Help

1. **Check this guide first** - Most issues covered here
2. **Check logs** - `logs/tap-station.log` often explains the issue
3. **GitHub Issues** - [Project Repository](https://github.com/zophiezlan/nfc-tap-logger/issues)
4. **Forum / Community** - If available for your deployment

---

## Prevention Tips

### Before Each Event

- [ ] Test both stations 1 week before
- [ ] Run `verify_hardware.py` on both Pis
- [ ] Check power banks fully charged
- [ ] Verify all cards work
- [ ] Backup SD cards
- [ ] Have spare power banks/cables
- [ ] Print this troubleshooting guide

### During Event

- [ ] Check stations hourly
- [ ] Monitor power levels
- [ ] Have manual backup logs ready
- [ ] Don't troubleshoot during event - switch to manual

### After Event

- [ ] Export data immediately
- [ ] Back up databases
- [ ] Note any issues for next time
- [ ] Recharge all power banks
- [ ] Check hardware for damage

---

## Common Error Messages

| Error                           | Meaning                           | Fix                                   |
| ------------------------------- | --------------------------------- | ------------------------------------- |
| `Failed to initialize PN532`    | Can't communicate with NFC reader | Check I2C wiring, run `enable_i2c.sh` |
| `Database is locked`            | Another process using DB          | Stop service, wait 5 seconds, retry   |
| `Permission denied: /dev/i2c-1` | Not in i2c group                  | `sudo usermod -a -G i2c $USER`        |
| `No module named 'pn532pi'`     | Package not installed             | `pip install -r requirements.txt`     |
| `Config file not found`         | Missing config.yaml               | `cp config.yaml.example config.yaml`  |
| `Under-voltage detected`        | Power supply weak                 | Use better power bank/cable           |
| `Connection timed out`          | NFC read timeout                  | Check card type, increase timeout     |

---

**Still stuck?** Create a GitHub issue with diagnostic output. We're here to help!
