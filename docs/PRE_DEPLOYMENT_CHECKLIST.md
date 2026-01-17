# Pre-Deployment Checklist

Use this checklist before your event to ensure everything is ready.

**Print this page and check off items as you complete them!**

---

## 📦 Hardware Preparation

### Station 1 (Queue Entry)

- [ ] Raspberry Pi Zero 2 W
- [ ] PN532 NFC reader properly wired
- [ ] USB-C power bank (fully charged, >10,000mAh)
- [ ] USB-C cable
- [ ] SD card with system installed
- [ ] Buzzer wired and working (optional)
- [ ] Weatherproof case or bag
- [ ] "TAP HERE" sign
- [ ] Tape/velcro for mounting

### Station 2 (Exit)

- [ ] Raspberry Pi Zero 2 W
- [ ] PN532 NFC reader properly wired
- [ ] USB-C power bank (fully charged, >10,000mAh)
- [ ] USB-C cable
- [ ] SD card with system installed
- [ ] Buzzer wired and working (optional)
- [ ] Weatherproof case or bag
- [ ] "TAP HERE" sign
- [ ] Tape/velcro for mounting

### NFC Cards

- [ ] 100+ NTAG215 cards initialized
- [ ] Test cards separate from participant cards
- [ ] Card collection box (if collecting cards)

### Backup Equipment

- [ ] Extra power banks (2-4 spares)
- [ ] Extra USB cables
- [ ] Extra NFC cards (uninitializedt)
- [ ] Paper log sheets + pens
- [ ] Printed operations guide
- [ ] Printed this checklist

---

## 💻 Software Verification

### Both Stations

Run these checks on **both** Station 1 and Station 2:

#### 1. Configuration Check

```bash
cd ~/nfc-tap-logger
cat config.yaml
```

**Verify:**

- [ ] `device_id` is unique (station1 vs station2)
- [ ] `stage` is correct (QUEUE_JOIN for Station 1, EXIT for Station 2)
- [ ] `session_id` matches your event (e.g., "festival-2026-summer")
- [ ] `web_server.enabled` is `true`
- [ ] `buzzer_enabled` is `true` (if using buzzer)

#### 2. Hardware Verification

```bash
cd ~/nfc-tap-logger
source venv/bin/activate
python scripts/verify_hardware.py
```

**Expected output:**

- [ ] ✓ I2C enabled
- [ ] ✓ NFC reader detected at 0x24
- [ ] ✓ Can read test card
- [ ] ✓ Buzzer works (if enabled)

#### 3. Full Deployment Verification

```bash
bash scripts/verify_deployment.sh
```

**All checks should pass:**

- [ ] ✓ System dependencies installed
- [ ] ✓ I2C interface enabled
- [ ] ✓ NFC reader detected
- [ ] ✓ Python environment configured
- [ ] ✓ Database initialized
- [ ] ✓ Service configured
- [ ] ✓ All permissions correct

#### 4. Service Status

```bash
sudo systemctl status tap-station
```

**Verify:**

- [ ] Service is enabled
- [ ] Service is running (or start it)
- [ ] No errors in status output

#### 5. Test Card Tap

```bash
# Watch logs
tail -f logs/tap-station.log
```

Then tap a test card:

- [ ] Hear beep (if buzzer enabled)
- [ ] See log entry with token ID and UID
- [ ] Tap same card again - should get double-beep (duplicate)

#### 6. Web Dashboard Access

Find your Pi's IP address:

```bash
hostname -I
```

From phone/laptop, visit:

- [ ] `http://<pi-ip>:8080/health` - Returns JSON with status
- [ ] `http://<pi-ip>:8080/dashboard` - Shows live dashboard
- [ ] `http://<pi-ip>:8080/monitor` - Shows simplified monitor
- [ ] `http://<pi-ip>:8080/control` - Shows control panel

#### 7. Database Check

```bash
sqlite3 data/events.db "SELECT COUNT(*) FROM events WHERE session_id='your-session-id'"
```

- [ ] Returns 0 if fresh start (or expected count if testing)
- [ ] Database file exists and is accessible

---

## 📱 Mobile/Monitoring Setup

### Monitoring Device

- [ ] Tablet or phone charged
- [ ] Connected to same network as Pi
- [ ] Bookmark dashboard URLs
- [ ] Test all dashboard views load
- [ ] Mount tablet in visible location (optional)

### Backup Data Collection

- [ ] Laptop available for emergency data ingest
- [ ] Mobile app tested (if using phone-based backup)
- [ ] Paper log sheets printed and accessible

---

## 🧪 End-to-End Test

**Do a full simulation before the event!**

1. **Station 1 (Queue Entry)**

   - [ ] Tap test card #1
   - [ ] Hear beep
   - [ ] See event in dashboard
   - [ ] Tap same card again - get duplicate beep
   - [ ] Tap different test card #2
   - [ ] See both in queue on dashboard

2. **Station 2 (Exit)**

   - [ ] Tap test card #1
   - [ ] Hear beep
   - [ ] See completion in dashboard
   - [ ] Check "Recent Completions" shows wait time
   - [ ] Tap test card #2
   - [ ] Verify both completed

3. **Dashboard Verification**

   - [ ] "In Queue" count is correct (0 after both exited)
   - [ ] "Completed Today" shows 2
   - [ ] Recent completions show both cards with wait times
   - [ ] Activity chart shows entries
   - [ ] Live event feed shows all taps

4. **Data Export Test**

   ```bash
   python scripts/export_data.py
   ```

   - [ ] CSV file created
   - [ ] Contains all test events
   - [ ] Timestamps correct
   - [ ] Token IDs and stages correct

5. **Clean Up Test Data**

   ```bash
   # Option 1: Delete test session from database
   sqlite3 data/events.db "DELETE FROM events WHERE session_id='your-test-session'"

   # Option 2: Start fresh with new session_id in config.yaml
   nano config.yaml  # Change session_id to event name
   sudo systemctl restart tap-station
   ```

---

## 📋 Documentation & Training

### Printed Materials

- [ ] Operations guide (docs/OPERATIONS.md) - 1 copy per station
- [ ] This checklist - 1 copy
- [ ] Quick reference cards for peer workers
- [ ] Emergency contact info
- [ ] Paper log sheet templates (10-20 sheets)

### Team Training

- [ ] Tech lead knows how to access control panel
- [ ] Peer workers trained on tap workflow
- [ ] Everyone knows beep codes (1 beep = success, 2 beeps = duplicate)
- [ ] Team knows backup procedure (manual logging)
- [ ] Tech lead can export data and backup database
- [ ] Team knows where to find IP addresses

---

## 🔋 Power Management

### Power Banks

- [ ] All power banks fully charged (100%)
- [ ] Charge levels marked/noted
- [ ] Spare power banks ready
- [ ] Charging cables available for recharging

### Power Estimates

- **Raspberry Pi Zero 2 W:** ~500mA @ 5V = 2.5W
- **10,000mAh power bank:** ~10-15 hours continuous
- **20,000mAh power bank:** ~20-30 hours continuous

**Calculate for your event:**

- Event duration: **\_** hours
- Required capacity per station: **\_** mAh
- Power banks per station: **\_**

---

## 🌐 Network Setup (If Using)

- [ ] WiFi network available (or mobile hotspot)
- [ ] Both Pis connected to network
- [ ] IP addresses noted:
  - Station 1: ******\_\_\_\_******
  - Station 2: ******\_\_\_\_******
- [ ] Monitoring device connected to same network
- [ ] Firewall allows port 8080 (if applicable)

**Note:** System works completely offline! Network only needed for live dashboards.

---

## 📦 Physical Setup

### Station 1 (Queue Entry) Location

- [ ] Near registration or queue entry point
- [ ] Visible and accessible
- [ ] Protected from weather (if outdoor)
- [ ] Power bank secure but accessible
- [ ] "TAP HERE" sign visible
- [ ] Peer worker assigned and briefed

### Station 2 (Exit) Location

- [ ] At exit point after service
- [ ] Visible reminder to tap
- [ ] Protected from weather (if outdoor)
- [ ] Power bank secure but accessible
- [ ] "TAP HERE" sign visible
- [ ] Collection box nearby (if collecting cards)

---

## 🚨 Emergency Preparedness

### Contact Information

- Tech lead phone: ******\_\_\_\_******
- Backup tech support: ******\_\_\_\_******
- Venue IT contact: ******\_\_\_\_******

### Backup Plans

- [ ] Manual logging procedure reviewed
- [ ] Paper logs ready
- [ ] Know how to access logs via control panel
- [ ] Know how to restart service via control panel
- [ ] Know when to abandon tech and go manual

### Emergency Commands

- **Restart service:** Control panel → Service Management → Restart
- **View logs:** Control panel → System Control → View Logs
- **Export data:** Control panel → Data Operations → Export Data
- **Backup database:** Control panel → Data Operations → Backup Database

---

## ✅ Final Checks (Day Of Event)

**30 minutes before doors open:**

### Both Stations

- [ ] Power on and booted (wait 30 seconds)
- [ ] Service running: Check control panel status
- [ ] Test tap a card at each station
- [ ] Dashboard accessible from monitoring device
- [ ] Signs mounted and visible
- [ ] Power bank levels checked (should be 100%)
- [ ] Peer workers in position and ready
- [ ] Backup logs and pens at each station

### Tech Lead

- [ ] Control panel bookmarked
- [ ] Dashboard visible on monitoring device
- [ ] IP addresses noted
- [ ] Phone charged and accessible
- [ ] Know how to access both Pis if needed

### Communication

- [ ] Brief team on workflow
- [ ] Review beep codes
- [ ] Explain manual backup procedure
- [ ] Set check-in times (every hour)
- [ ] Confirm who to call for issues

---

## 🎉 During Event - Monitoring Schedule

**Every 30 minutes:**

- [ ] Check dashboard - any alerts?
- [ ] Visual check both stations - still powered?
- [ ] Check peer workers - any issues?

**Every hour:**

- [ ] Check power bank levels
- [ ] Export data snapshot (optional but recommended)
- [ ] Review queue metrics - any patterns?

**If queue goes critical (>20 people):**

- [ ] Use dashboard alerts to make decisions
- [ ] Consider additional volunteers
- [ ] Communicate wait times honestly
- [ ] Prioritize longest waiters

---

## 📊 Post-Event Checklist

### Immediate (Within 30 minutes)

- [ ] Export final data from both stations
- [ ] Backup databases from both stations
- [ ] Note any issues encountered
- [ ] Thank peer workers!

### Within 24 hours

- [ ] Copy data to secure location
- [ ] Analyze data (wait times, throughput, abandonment)
- [ ] Document any hardware issues
- [ ] Note any process improvements for next time

### Equipment Care

- [ ] Recharge all power banks
- [ ] Inspect hardware for damage
- [ ] Store equipment safely
- [ ] Update documentation with lessons learned

---

## 📝 Notes Section

Use this space for event-specific information:

**Event name:** **************\_\_\_\_**************

**Date:** **************\_\_\_\_**************

**Expected attendees:** **************\_\_\_\_**************

**Session ID used:** **************\_\_\_\_**************

**Station 1 IP:** **************\_\_\_\_**************

**Station 2 IP:** **************\_\_\_\_**************

**Issues encountered:**

---

---

---

**Lessons learned:**

---

---

---

**Next time, we should:**

---

---

---

---

## ✨ You're Ready!

If you've checked off all items above, you're ready for a successful deployment!

**Remember:**

- ✅ The system is designed to be resilient
- ✅ Manual logging is always a valid backup
- ✅ Peer worker experience > perfect data
- ✅ You've got this! 💚

For support during event:

- **Operations Guide:** docs/OPERATIONS.md
- **Control Panel:** http://<pi-ip>:8080/control
- **Troubleshooting:** docs/TROUBLESHOOTING.md

**Good luck with your event!** 🎉
