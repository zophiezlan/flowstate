# Post-Installation Verification Checklist

Quick checklist to verify your fresh Raspberry Pi deployment is ready.

---

## 📋 Automated Verification

**Run the automated verification script:**

```bash
bash scripts/verify_deployment.sh
```

This checks everything automatically. If all passes, you're ready to deploy!

---

## ✅ Manual Verification (if needed)

### System Setup
- [ ] Raspberry Pi OS is up to date
- [ ] SSH access works
- [ ] Internet connection available (for initial setup)

### Hardware Connections
- [ ] PN532 VCC → Pi Pin 1 (3.3V)
- [ ] PN532 GND → Pi Pin 6 (GND)
- [ ] PN532 SDA → Pi Pin 3 (GPIO 2)
- [ ] PN532 SCL → Pi Pin 5 (GPIO 3)
- [ ] Optional: Buzzer connected to GPIO 17
- [ ] All connections are secure

### System Dependencies
- [ ] Python 3 installed (`python3 --version`)
- [ ] pip installed (`pip3 --version`)
- [ ] i2c-tools installed (`which i2cdetect`)
- [ ] git installed (`git --version`)

### I2C Configuration
- [ ] I2C enabled in `/boot/config.txt` or `/boot/firmware/config.txt`
- [ ] I2C device exists (`ls -l /dev/i2c-1`)
- [ ] i2c_dev kernel module loaded (`lsmod | grep i2c_dev`)
- [ ] User in i2c group (`groups | grep i2c`)
- [ ] PN532 detected at 0x24 (`sudo i2cdetect -y 1`)

### Python Environment
- [ ] Virtual environment created (`ls -d venv`)
- [ ] pn532pi installed (`venv/bin/python -c "import pn532pi"`)
- [ ] PyYAML installed (`venv/bin/python -c "import yaml"`)
- [ ] RPi.GPIO installed (`venv/bin/python -c "import RPi.GPIO"`)
- [ ] Flask installed (for web server)

### Project Structure
- [ ] Directory `data/` exists
- [ ] Directory `logs/` exists
- [ ] Directory `backups/` exists
- [ ] File `config.yaml` exists
- [ ] File `requirements.txt` exists
- [ ] All Python modules in `tap_station/` present

### Configuration
- [ ] `config.yaml` has correct `device_id`
- [ ] `config.yaml` has correct `stage` (QUEUE_JOIN or EXIT)
- [ ] `config.yaml` has correct `session_id`
- [ ] GPIO pins configured correctly in config
- [ ] I2C bus and address configured correctly

### Systemd Service
- [ ] Service file exists at `/etc/systemd/system/tap-station.service`
- [ ] Service is enabled (`sudo systemctl is-enabled tap-station`)
- [ ] Service can start (`sudo systemctl start tap-station`)
- [ ] Service status is active (`sudo systemctl status tap-station`)
- [ ] Logs are being written (`tail logs/tap-station.log`)

### Hardware Functionality
- [ ] NFC reader can be initialized
- [ ] Test card can be read successfully
- [ ] Buzzer produces sound (if connected)
- [ ] Database can be written to
- [ ] Database can be read from

### Power & Performance
- [ ] No under-voltage warnings (`vcgencmd get_throttled` returns `0x0`)
- [ ] CPU temperature acceptable (`vcgencmd measure_temp`)
- [ ] Sufficient disk space available (`df -h`)
- [ ] Battery provides 8+ hours runtime (test if possible)

### Service Reliability
- [ ] Service starts automatically on boot
- [ ] Service restarts on crash (test with `sudo pkill -f tap_station`)
- [ ] Database survives crash (WAL mode)
- [ ] Logs rotate properly

---

## 🎴 Card Initialization

After all checks pass, initialize your NFC cards:

```bash
source venv/bin/activate
python scripts/init_cards.py --start 1 --end 100
```

Verify:
- [ ] All 100 cards initialized successfully
- [ ] `data/card_mapping.csv` created
- [ ] Card mapping file has 100 entries
- [ ] Each card reads with correct token ID

---

## 🔍 Final Tests

### Test 1: Manual Card Reading
```bash
source venv/bin/activate
python -m tap_station.main --config config.yaml
```
- [ ] Service starts without errors
- [ ] Tapping card produces beep
- [ ] Card UID and token logged
- [ ] No errors in console

### Test 2: Service Mode
```bash
sudo systemctl start tap-station
tail -f logs/tap-station.log
```
- [ ] Service starts successfully
- [ ] "Station ready" message appears
- [ ] Tapping card logs event
- [ ] Beep feedback works

### Test 3: Database
```bash
source venv/bin/activate
python -c "from tap_station.database import Database; db = Database('data/events.db'); print(f'Events: {db.get_event_count()}')"
```
- [ ] Database accessible
- [ ] Event count matches test taps

### Test 4: Auto-Start
```bash
sudo reboot
# After reboot:
sudo systemctl status tap-station
```
- [ ] Service started automatically
- [ ] No errors in status
- [ ] Can tap cards immediately

### Test 5: Auto-Restart
```bash
sudo pkill -f tap_station
sleep 10
sudo systemctl status tap-station
```
- [ ] Service restarted automatically
- [ ] No data loss
- [ ] Service is active again

---

## 📊 Data Export Test

Test the data export functionality:

```bash
source venv/bin/activate
python scripts/export_data.py
```

Verify:
- [ ] Export CSV file created
- [ ] CSV contains all test events
- [ ] CSV format is correct
- [ ] Timestamps are accurate

---

## 🚀 Ready for Deployment

**All checks passed? You're ready!**

Your deployment is complete when:
- ✅ All automated checks pass
- ✅ All manual checks pass (if performed)
- ✅ Cards are initialized
- ✅ Service runs reliably
- ✅ Data export works

---

## 🆘 If Checks Fail

### I2C Issues
```bash
bash scripts/enable_i2c.sh
sudo reboot
```

### Python Dependencies
```bash
source venv/bin/activate
pip install -r requirements.txt --force-reinstall
```

### Service Issues
```bash
sudo systemctl daemon-reload
sudo systemctl restart tap-station
sudo journalctl -u tap-station -n 50
```

### Complete Reinstall
```bash
bash scripts/install.sh
```

---

## 📖 Additional Resources

- **Detailed Guide:** `docs/FRESH_DEPLOYMENT_GUIDE.md`
- **I2C Troubleshooting:** `docs/I2C_SETUP.md`
- **Hardware Guide:** `docs/HARDWARE.md`
- **Quick Start:** `docs/QUICKSTART.md`
- **Full README:** `README.md`

---

**Good luck with your deployment!** 🎉
