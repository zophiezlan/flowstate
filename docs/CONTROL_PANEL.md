# Control Panel Reference

Quick reference for the web-based control panel.

**Access:** `http://<pi-ip-address>:8080/control`

---

## System Status

Real-time indicators shown at top of control panel:

- **Service Status** - Running (green) or Stopped (red)
- **Total Events** - Number of events logged in current session
- **Uptime** - How long the system has been running
- **Database Size** - Current database file size

---

## Service Management

### Start Service

Starts the tap-station systemd service

```bash
# Equivalent command:
sudo systemctl start tap-station
```

### Stop Service

Stops the tap-station service (stops logging)

```bash
# Equivalent command:
sudo systemctl stop tap-station
```

### Restart Service

Restarts the service (useful after configuration changes)

```bash
# Equivalent command:
sudo systemctl restart tap-station
```

### Service Status

Shows detailed service status and recent logs

```bash
# Equivalent command:
systemctl status tap-station
```

---

## Diagnostics & Verification

### Verify Hardware

Tests NFC reader connection and I2C communication

```bash
# Equivalent command:
python3 scripts/verify_hardware.py
```

**Expected output:** NFC reader detected at I2C address 0x24

### Verify Deployment

Runs full system checks (hardware, config, database, permissions)

```bash
# Equivalent command:
bash scripts/verify_deployment.sh
```

**Use when:** Before event start, after setup changes

### Health Check

Quick health check of running service

```bash
# Equivalent command:
python3 scripts/health_check.py
```

**Shows:** Service status, database connectivity, event counts

### I2C Devices

Scans I2C bus for connected devices

```bash
# Equivalent command:
sudo i2cdetect -y 1
```

**Expected:** Device at 0x24 (PN532 NFC reader)

---

## Data Operations

### Export Data

Exports current session events to CSV file

```bash
# Equivalent command:
python3 scripts/export_data.py
```

**Output location:** `export_YYYYMMDD_HHMMSS.csv`

### Backup Database

Creates timestamped backup of database

```bash
# Equivalent command:
cp data/events.db backups/events_YYYYMMDD_HHMMSS.db
```

**Output location:** `backups/events_YYYYMMDD_HHMMSS.db`

**Use when:** Before major changes, end of event, regularly during long events

### View Recent Events

Shows last 20 logged events

```bash
# Equivalent command:
python3 -c "from tap_station.database import Database; ..."
```

**Shows:** Timestamp, stage, token ID, device ID

### Database Stats

Shows database statistics and event counts

```bash
# Equivalent command:
sqlite3 data/events.db "SELECT COUNT(*) FROM events"
```

**Shows:** Total events (all sessions), events in current session

---

## System Control

⚠️ **Use with caution - these affect system operation**

### Reboot System

Restarts the Raspberry Pi

**Confirmation required**

```bash
# Equivalent command:
sudo reboot
```

**Takes:** ~30 seconds to restart

**Use when:** After system updates, hardware changes, or if system is unresponsive

### Shutdown System

Powers off the Raspberry Pi

**Confirmation required**

```bash
# Equivalent command:
sudo shutdown -h now
```

**Important:** Requires physical access to restart!

**Use when:** End of event, before unplugging power

### View Logs

Shows last 50 lines of application log

```bash
# Equivalent command:
tail -n 50 logs/tap-station.log
```

**Shows:** Recent events, errors, warnings, service activity

### Disk Usage

Shows available disk space

```bash
# Equivalent command:
df -h /
```

**Shows:** Total space, used space, available space, percentage

---

## Development Tools

### Dev Reset

Resets I2C bus and NFC reader (fixes hanging issues)

```bash
# Equivalent command:
python3 scripts/dev_reset.py
```

**Use when:** NFC reader not responding, frequent read errors

### Test Card Read

Tests reading an NFC card

```bash
# Equivalent command:
python3 -c "from tap_station.nfc_reader import NFCReader; ..."
```

**What it does:**

- Creates temporary NFC reader instance
- Attempts to read a card (5 second timeout)
- Reports token ID and UID if successful

**Use when:** Verifying card compatibility, testing reader

### Run Tests

Executes Python test suite

```bash
# Equivalent command:
pytest tests/ -v
```

**Use when:** After code changes, verifying system integrity

### Git Status

Shows git repository status

```bash
# Equivalent command:
git status
```

**Shows:** Modified files, branch, commit status

---

## Troubleshooting with Control Panel

### Service Won't Start

1. Click **Service Status** to see error messages
2. Click **View Logs** to check for errors
3. Click **Verify Hardware** to test NFC reader
4. Click **Verify Deployment** for full diagnostics
5. If hardware issues, try **Dev Reset**
6. Restart service with **Restart Service**

### No Events Being Logged

1. Click **Service Status** - is it running?
2. Click **View Recent Events** - any events at all?
3. Click **Verify Hardware** - reader connected?
4. Click **Test Card Read** - can it read cards?
5. Click **View Logs** - any error messages?

### Low Disk Space

1. Click **Disk Usage** to check available space
2. Click **Export Data** to save events
3. Click **Backup Database** to preserve data
4. Delete old exports/backups via SSH if needed

### System Unresponsive

1. Try **View Logs** to see if server responds
2. If control panel works but service doesn't, try **Restart Service**
3. If control panel doesn't respond, need physical access
4. Last resort: **Reboot System**

---

## Command Output

All commands display real-time output in the terminal section at the bottom of the control panel.

**Output indicators:**

- 🔵 Blue text = Information
- 🟢 Green text = Success
- 🔴 Red text = Errors

**Output features:**

- Scrollable terminal window
- Preserves command history
- Shows full command output
- Errors displayed prominently

---

## Best Practices

### Before Event

✅ Run **Verify Deployment**
✅ Run **Verify Hardware**
✅ Check **Service Status**
✅ Note IP address for access during event

### During Event

✅ Keep control panel tab open for quick access
✅ Check **Service Status** if issues occur
✅ Use **View Recent Events** to verify logging
✅ **Don't** restart/reboot during active service

### After Event

✅ **Export Data** immediately
✅ **Backup Database**
✅ **View Logs** if any issues occurred
✅ **Shutdown System** when done

### General Tips

- Bookmark the control panel URL
- Test commands before the event
- Have backup plan if control panel unavailable
- Keep SSH access available as backup
- Don't execute commands without understanding them
- Confirmations are there for a reason - read them!

---

## Security Considerations

The control panel provides **full system control**. Protect it:

### Network Security

- Keep Pi on private network (not public WiFi)
- Use firewall rules if on shared network
- Don't expose port 8080 to internet

### Access Control

- Only share URL with administrators
- Change default passwords if any
- Monitor access logs
- Consider VPN for remote access

### Future Enhancements

- [ ] Password protection
- [ ] User authentication
- [ ] Role-based access control
- [ ] Audit logging
- [ ] HTTPS support

---

## Common Commands Quick Reference

| Task           | Control Panel Button               | SSH Command                           |
| -------------- | ---------------------------------- | ------------------------------------- |
| Start service  | Service Management → Start Service | `sudo systemctl start tap-station`    |
| Stop service   | Service Management → Stop Service  | `sudo systemctl stop tap-station`     |
| Check hardware | Diagnostics → Verify Hardware      | `python3 scripts/verify_hardware.py`  |
| Export data    | Data Operations → Export Data      | `python3 scripts/export_data.py`      |
| View logs      | System Control → View Logs         | `tail -f logs/tap-station.log`        |
| Reboot         | System Control → Reboot System     | `sudo reboot`                         |
| Backup DB      | Data Operations → Backup Database  | `cp data/events.db backups/backup.db` |

---

## Need Help?

- **Full documentation:** [OPERATIONS.md](OPERATIONS.md)
- **Setup guide:** [SETUP.md](SETUP.md)
- **Troubleshooting:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Issues:** [GitHub Issues](https://github.com/zophiezlan/nfc-tap-logger/issues)

---

**Remember:** The control panel is powerful but simple. When in doubt:

1. Check the logs
2. Verify the hardware
3. Restart the service
4. Fall back to manual methods if needed

Stay calm, the system is designed to be resilient! 💚
