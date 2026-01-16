# Fresh Raspberry Pi Deployment Guide

Complete guide for deploying NFC Tap Logger on a brand new Raspberry Pi.

---

## 📋 Pre-Deployment Checklist

### Hardware Requirements
- [ ] Raspberry Pi Zero 2 W (or Pi 4)
- [ ] MicroSD card (8GB minimum, 16GB recommended)
- [ ] PN532 NFC module (I2C mode)
- [ ] 100× NTAG215 NFC cards
- [ ] USB-C power bank (10,000mAh minimum)
- [ ] Quality USB-C cable
- [ ] Optional: Piezo buzzer (active, 3-5V)
- [ ] Optional: LEDs (green/red) and 220Ω resistors

### Pre-Installation Preparation
- [ ] Raspberry Pi OS installed on SD card (use Raspberry Pi Imager)
- [ ] SSH enabled on Pi (enable in imager or add `ssh` file to boot partition)
- [ ] WiFi configured (if needed for setup)
- [ ] Pi is powered on and accessible
- [ ] PN532 module set to I2C mode (check jumpers/switches)

---

## 🔌 Hardware Setup

### Step 1: PN532 Wiring

Connect PN532 to Raspberry Pi GPIO header:

```
PN532 Pin    →    Raspberry Pi
─────────────────────────────────
VCC          →    Pin 1  (3.3V)     🔴 RED wire
GND          →    Pin 6  (GND)      ⚫ BLACK wire
SDA          →    Pin 3  (GPIO 2)   🔵 BLUE wire
SCL          →    Pin 5  (GPIO 3)   🟡 YELLOW wire
```

**⚠️ CRITICAL:** Use 3.3V (NOT 5V) or you may damage your Pi!

### Step 2: Optional Buzzer Wiring

```
Buzzer Pin   →    Raspberry Pi
─────────────────────────────────
Buzzer +     →    Pin 11 (GPIO 17)
Buzzer -     →    Pin 9  (GND)
```

### Step 3: Verify Connections

- [ ] All connections are secure
- [ ] No loose wires
- [ ] VCC connected to 3.3V (NOT 5V)
- [ ] Ground connections are solid

---

## 💻 Software Installation

### Step 1: Initial System Setup

SSH into your Raspberry Pi:

```bash
ssh pi@raspberrypi.local
# Default password is usually 'raspberry' (change this!)
```

Update the system:

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

### Step 2: Clone Repository

```bash
cd ~
git clone https://github.com/yourusername/nfc-tap-logger.git
cd nfc-tap-logger
```

### Step 3: Run Installation Script

```bash
bash scripts/install.sh
```

The script will:
- ✅ Install Python 3, pip, venv, i2c-tools, git
- ✅ Enable I2C interface
- ✅ Load I2C kernel modules
- ✅ Add user to i2c group
- ✅ Create Python virtual environment
- ✅ Install all Python dependencies
- ✅ Create data/logs/backups directories
- ✅ Configure basic settings (interactive)
- ✅ Install systemd service
- ✅ Optionally enable auto-start on boot

**⚠️ IMPORTANT:** The script will prompt you to reboot if I2C was just enabled.

### Step 4: Reboot (if required)

```bash
sudo reboot
```

Wait 30-60 seconds, then reconnect:

```bash
ssh pi@raspberrypi.local
cd ~/nfc-tap-logger
```

---

## ✅ Post-Installation Verification

### Step 1: Verify I2C

Check if I2C device exists:

```bash
ls -l /dev/i2c-1
# Should show: crw-rw---- 1 root i2c ...
```

Scan I2C bus for PN532:

```bash
sudo i2cdetect -y 1
```

Expected output:
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- 24 -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
...
```

You should see `24` at address 0x24 (PN532).

**If not detected:** Run the I2C troubleshooting script:

```bash
bash scripts/enable_i2c.sh
```

### Step 2: Run Hardware Verification

```bash
source venv/bin/activate
python scripts/verify_hardware.py
```

This will check:
- ✅ I2C bus exists
- ✅ I2C kernel module loaded
- ✅ i2c-tools installed
- ✅ PN532 detected at 0x24
- ✅ NFC reader can read cards
- ✅ GPIO/buzzer working
- ✅ No under-voltage
- ✅ Database read/write

**All checks must pass!**

### Step 3: Configure Station

Edit `config.yaml` for your station:

```bash
nano config.yaml
```

**For Station 1 (Queue Join):**
```yaml
station:
  device_id: "station1"
  stage: "QUEUE_JOIN"
  session_id: "your-event-name-2025"
```

**For Station 2 (Exit):**
```yaml
station:
  device_id: "station2"
  stage: "EXIT"
  session_id: "your-event-name-2025"
```

**⚠️ Important:** Use the SAME `session_id` for all stations at the same event.

### Step 4: Test the Service

Start the service manually first:

```bash
source venv/bin/activate
python -m tap_station.main --config config.yaml
```

You should see:
```
Station ready - waiting for cards...
```

Tap an NFC card and verify:
- [ ] You see log output
- [ ] Buzzer beeps (if connected)
- [ ] No errors in output

Press Ctrl+C to stop.

### Step 5: Enable Systemd Service

```bash
sudo systemctl enable tap-station
sudo systemctl start tap-station
```

Check status:

```bash
sudo systemctl status tap-station
```

Should show: `Active: active (running)`

Monitor logs:

```bash
tail -f logs/tap-station.log
```

---

## 🎴 Card Initialization

Initialize your NFC cards with sequential token IDs:

```bash
source venv/bin/activate
python scripts/init_cards.py --start 1 --end 100
```

Follow the prompts and tap each card when requested.

This creates `data/card_mapping.csv` with UID-to-token mappings.

**⚠️ Important:** Keep this file safe! It's needed for data analysis.

---

## 🔍 Final Checks

Before deploying to your event:

- [ ] Service starts automatically on boot
- [ ] Service auto-restarts if it crashes
- [ ] All cards read successfully
- [ ] Buzzer provides clear feedback
- [ ] Logs are being written
- [ ] Database is being updated
- [ ] Battery provides 8+ hours runtime
- [ ] No under-voltage warnings

### Test Auto-Start

```bash
sudo reboot
```

After reboot, check if service started:

```bash
sudo systemctl status tap-station
```

### Test Auto-Restart

Kill the service and verify it restarts:

```bash
sudo pkill -f tap_station
sleep 10
sudo systemctl status tap-station
# Should show it restarted
```

### Test Battery Life

```bash
# Disable WiFi/Bluetooth to save power
sudo rfkill block wifi
sudo rfkill block bluetooth

# Check power status
vcgencmd get_throttled
# Should return: throttled=0x0
```

### Test Card Reading

Tap 5-10 different cards and verify each:
- [ ] Produces one beep
- [ ] Logs to database
- [ ] Shows in `tail -f logs/tap-station.log`

---

## 📊 Data Export

After your event, export the data:

```bash
source venv/bin/activate
python scripts/export_data.py
```

This creates `export_YYYYMMDD_HHMMSS.csv` with all events.

---

## 🛠️ Troubleshooting

### I2C Issues

**Problem:** `/dev/i2c-1` doesn't exist

**Solution:**
```bash
bash scripts/enable_i2c.sh
sudo reboot
```

**Problem:** PN532 not detected at 0x24

**Check:**
1. Wiring (especially VCC to 3.3V)
2. PN532 mode switches (must be I2C)
3. Connections are secure
4. Try a different I2C bus: `sudo i2cdetect -y 0`

### Service Won't Start

**Check logs:**
```bash
sudo journalctl -u tap-station -n 50 --no-pager
```

**Common issues:**
- Config file missing or invalid
- Python dependencies not installed in venv
- Database directory doesn't exist
- I2C not enabled

### Cards Won't Read

**Check:**
1. Card type (must be NTAG215)
2. Hold card flat against reader antenna
3. Hold for 2-3 seconds
4. Try different card (could be faulty)
5. Check NFC reader: `python scripts/verify_hardware.py`

### Under-Voltage Warnings

```bash
vcgencmd get_throttled
```

If not `0x0`:
- Use better USB cable
- Ensure power bank is charged
- Check power bank provides 5V 2A minimum
- Disable WiFi/Bluetooth to reduce power draw

### Database Locked Errors

```bash
sudo systemctl stop tap-station
ps aux | grep python
# Kill any lingering processes
sudo systemctl start tap-station
```

---

## 📱 Optional: Mobile App Setup

For participants to check their status with phones:

1. Uncomment `ndeflib` in `requirements.txt`
2. Reinstall dependencies:
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Initialize cards with NDEF URLs:
   ```bash
   python scripts/init_cards_with_ndef.py --start 1 --end 100
   ```

See `docs/NFC_TOOLS_INTEGRATION.md` for details.

---

## 🔒 Security Hardening

For production deployment:

### Change Default Password
```bash
passwd
```

### Disable SSH Password Login (use keys)
```bash
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
sudo systemctl restart ssh
```

### Enable Firewall
```bash
sudo apt-get install ufw
sudo ufw allow ssh
sudo ufw enable
```

### Disable Unnecessary Services
```bash
sudo systemctl disable bluetooth
sudo systemctl disable avahi-daemon
```

---

## 📝 Deployment Day Checklist

### Before Event
- [ ] Both stations configured (station1 & station2)
- [ ] All cards initialized
- [ ] Services enabled and running
- [ ] Batteries fully charged
- [ ] Hardware tested and working
- [ ] Backup power banks ready
- [ ] Card mapping CSV backed up

### During Event
- [ ] Monitor logs periodically
- [ ] Check battery status every 2 hours
- [ ] Have backup cards available
- [ ] Note any issues in log file

### After Event
- [ ] Stop services: `sudo systemctl stop tap-station`
- [ ] Export data: `python scripts/export_data.py`
- [ ] Copy data off Pi: `scp pi@raspberrypi.local:~/nfc-tap-logger/export*.csv .`
- [ ] Backup database: `cp data/events.db backups/events_$(date +%Y%m%d).db`
- [ ] Copy card mapping: `scp pi@raspberrypi.local:~/nfc-tap-logger/data/card_mapping.csv .`

---

## 🆘 Emergency Contacts

Keep this information accessible during your event:

- **Project Repository:** https://github.com/yourusername/nfc-tap-logger
- **Documentation:** `docs/` folder
- **I2C Troubleshooting:** `docs/I2C_SETUP.md`
- **Hardware Guide:** `docs/HARDWARE.md`
- **Quick Start:** `docs/QUICKSTART.md`

---

## ✅ Success Criteria

Your deployment is ready when:

✅ Hardware verified (all checks pass)
✅ Service starts on boot
✅ Service auto-restarts on crash
✅ Cards read reliably
✅ Feedback (beeps) work
✅ Events logged to database
✅ Battery lasts 8+ hours
✅ No under-voltage warnings
✅ Data exports successfully

**You're ready to deploy!** 🎉

---

## 📖 Additional Resources

- **Quick Start:** `docs/QUICKSTART.md`
- **Hardware Details:** `docs/HARDWARE.md`
- **I2C Setup:** `docs/I2C_SETUP.md`
- **Troubleshooting:** `docs/TROUBLESHOOTING_FLOWCHART.md`
- **Full README:** `README.md`
