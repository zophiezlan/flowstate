# Troubleshooting Flowchart

## 🔍 Quick Problem Solver

---

## Problem: No Beep When Card Tapped

```
START: Card tapped, no beep
    ↓
[Is the Pi powered on?]
    ├─ NO → Plug in power bank
    │        Check USB cable connected
    │        Wait 30 seconds for boot
    │        Try again
    └─ YES ↓

[Can you see any lights on Pi?]
    ├─ NO → Power issue
    │        ├─ Check power bank charged
    │        ├─ Try different USB cable
    │        └─ Swap power bank
    └─ YES ↓

[Run: sudo i2cdetect -y 1]
    ├─ Shows "24" → PN532 detected ✓
    │                ↓
    │   [Is card NTAG215?]
    │       ├─ NO → Get correct cards
    │       └─ YES ↓
    │           [Hold card flat on reader for 2+ seconds]
    │               ├─ Still fails → Try different card
    │               └─ Works → Problem solved!
    │
    └─ No "24" shown → PN532 not detected
                       ↓
        [Check wiring]
            ├─ VCC → Pin 1 (3.3V) ✓
            ├─ GND → Pin 6 (GND) ✓
            ├─ SDA → Pin 3 (GPIO2) ✓
            └─ SCL → Pin 5 (GPIO3) ✓

        [Still not working?]
            └─ Try: sudo i2cdetect -y 0
                   (Some Pis use bus 0)
```

---

## Problem: I2C Not Working / /dev/i2c-1 Not Found

```
START: Error "No such file or directory: '/dev/i2c-1'"
    ↓
[Check if I2C device exists]
    Run: ls -la /dev/i2c*
    ↓
    ├─ /dev/i2c-1 exists → Device exists ✓
    │                      ↓
    │   [Check permissions]
    │       Run: groups
    │       ├─ "i2c" shown → Permissions OK ✓
    │       │                └─ Problem is with PN532, see above
    │       └─ "i2c" NOT shown → Permission issue
    │           └─ FIX: sudo usermod -a -G i2c $USER
    │                  Log out and back in
    │                  Try again
    │
    └─ NO /dev/i2c* → I2C NOT enabled
                      ↓
        [Enable I2C automatically]
            Run: bash scripts/enable_i2c.sh
            ├─ Script will guide you
            └─ Will prompt for reboot
                ↓
        [Or enable I2C manually]
            ├─ Find config file:
            │   • /boot/firmware/config.txt (newer Pi OS)
            │   • /boot/config.txt (older Pi OS)
            │
            ├─ Edit config:
            │   sudo nano /boot/firmware/config.txt
            │   Add line: dtparam=i2c_arm=on
            │   Save and exit
            │
            ├─ Load kernel module:
            │   sudo modprobe i2c_dev
            │   echo "i2c-dev" | sudo tee -a /etc/modules
            │
            └─ REBOOT (required!):
                sudo reboot
                ↓
        [After reboot, verify]
            Run: ls -la /dev/i2c*
            Should see: /dev/i2c-1
            ↓
            Run: sudo i2cdetect -y 1
            Should show "24" for PN532
            ↓
            Run: python scripts/verify_hardware.py
            All I2C checks should pass ✓
```

**Common I2C Issues:**

1. **Just installed, never rebooted**
   - Solution: `sudo reboot` (required after enabling I2C)

2. **/dev/i2c-0 exists but not /dev/i2c-1**
   - Some Pi models use bus 0
   - Update config.yaml: `i2c_bus: 0`
   - Or update code to use bus 0

3. **Permission denied errors**
   - Add user to i2c group
   - Log out and back in (required!)

4. **I2C enabled but PN532 not detected**
   - Check wiring (see Problem: No Beep When Card Tapped)
   - Check PN532 is in I2C mode (jumpers/switches)
   - Try: `sudo i2cdetect -y 0` (alternate bus)

---

## Problem: Service Won't Start

```
START: sudo systemctl start tap-station fails
    ↓
[Check status: sudo systemctl status tap-station]
    ↓
[Look for error message]
    ├─ "config.yaml not found"
    │   └─ FIX: cp config.yaml.example config.yaml
    │           Edit with your station info
    │
    ├─ "No module named 'pn532pi'"
    │   └─ FIX: source venv/bin/activate
    │           pip install -r requirements.txt
    │
    ├─ "Permission denied: data/events.db"
    │   └─ FIX: mkdir -p data logs backups
    │           chmod 755 data logs backups
    │
    ├─ "Database is locked"
    │   └─ FIX: killall python3
    │           rm data/events.db-wal (if exists)
    │           sudo systemctl start tap-station
    │
    └─ Other error
        └─ FIX: Check logs
                tail -100 logs/tap-station.log
                Look for clues
```

---

## Problem: Random Reboots

```
START: Pi keeps restarting
    ↓
[Check: vcgencmd get_throttled]
    ├─ Returns "0x0" → Power OK ✓
    │                  ↓
    │   [Check SD card]
    │       └─ Try different SD card
    │          May be corrupted
    │
    └─ Returns "0x50000" or similar → UNDER-VOLTAGE!
                                      ↓
        [Fix power supply]
            ├─ Use better quality power bank
            ├─ Try different USB cable (thicker gauge)
            ├─ Ensure 5V 2A minimum output
            └─ Avoid cheap cables/adapters
```

---

## Problem: Cards Read Slowly

```
START: Takes >5 seconds to register tap
    ↓
[Check database size]
    └─ ls -lh data/events.db
       ├─ >100MB → Large database
       │           └─ FIX: Export and archive old data
       │                  python scripts/export_data.py
       │                  mv data/events.db backups/
       │                  Restart service
       │
       └─ <10MB → Normal size
                  ↓
        [Check CPU/memory]
            └─ top
               Look for high CPU usage
               ├─ Normal: python ~20-30% CPU
               └─ High: >70% CPU → Restart service
```

---

## Problem: Data Export Fails

```
START: export_data.py errors
    ↓
[Error: "Database is locked"]
    └─ FIX: sudo systemctl stop tap-station
            Run export again
            sudo systemctl start tap-station

[Error: "No events to export"]
    └─ CHECK: Database actually has data?
              sqlite3 data/events.db "SELECT COUNT(*) FROM events;"
              ├─ 0 → No events logged
              └─ >0 → Check session_id filter

[Error: "Permission denied"]
    └─ FIX: Check you're in project directory
            cd ~/nfc-tap-logger
            source venv/bin/activate
```

---

## Problem: Buzzer Not Working

```
START: No sound when card tapped
    ↓
[Check config.yaml]
    feedback:
      buzzer_enabled: true  ← Must be true
      gpio:
        buzzer: 17          ← Check pin number

[Buzzer connected?]
    ├─ Buzzer+ → GPIO 17 (Pin 11)
    └─ Buzzer- → GND

[Test manually]
    └─ python3
       >>> import RPi.GPIO as GPIO
       >>> GPIO.setmode(GPIO.BCM)
       >>> GPIO.setup(17, GPIO.OUT)
       >>> GPIO.output(17, True)  # Should beep
       >>> GPIO.output(17, False)

       ├─ Beeps → Config issue
       │          Check config.yaml
       │          Restart service
       │
       └─ Silent → Hardware issue
                   ├─ Check buzzer polarity
                   ├─ Try different buzzer
                   └─ Check wiring
```

---

## Quick Reference: Useful Commands

```bash
# Check service status
sudo systemctl status tap-station

# View logs (live)
tail -f logs/tap-station.log

# View logs (last 50 lines)
tail -50 logs/tap-station.log

# Restart service
sudo systemctl restart tap-station

# Check I2C devices
sudo i2cdetect -y 1

# Check power/battery
vcgencmd get_throttled
vcgencmd measure_temp

# Count events in database
sqlite3 data/events.db "SELECT COUNT(*) FROM events;"

# Check recent events
python -m tap_station.main --stats

# Test without hardware
python -m tap_station.main --mock-nfc
```

---

## Still Stuck?

1. **Check the full README.md** - detailed troubleshooting
2. **Check docs/HARDWARE.md** - wiring details
3. **Post logs** - someone can help debug
4. **Start fresh** - reflash SD card, reinstall

---

## Prevention Tips

✅ **Use quality power supplies** - cheap cables cause 90% of problems
✅ **Test before event** - run for 1 hour, verify stability
✅ **Keep spare SD card** - pre-configured, ready to swap
✅ **Label cables** - "Station 1", "Station 2" prevents mix-ups
✅ **Document your setup** - take photos, note any quirks

---

**Most problems are power or wiring. Start there.** 🔌
