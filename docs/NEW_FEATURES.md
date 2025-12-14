# New Features Guide

## v1.1 Enhancements

Three new features have been added to make the NFC Tap Logger even better:

1. **Visual Setup Guide** - Photos and diagrams for easier hardware setup
2. **NFC Tools App Integration** - Participants can check status with their phones
3. **Health Check & Web Status** - Monitor stations and provide live status

---

## 1. Visual Setup Guide

### What It Is
Comprehensive visual guide with ASCII diagrams, wiring instructions, and photo placeholders.

### Where to Find It
- `docs/VISUAL_SETUP_GUIDE.md`

### How to Use It
1. **For first-time setup:** Follow step-by-step with diagrams
2. **Add your photos:** Take photos during assembly and add them to the guide
3. **Print it:** Give to new volunteers for training

### Key Features
- Color-coded wiring diagrams
- Common mistakes section
- Card placement guide
- Power setup best practices
- Photo checklist for completing the guide

### Example
```
PN532 → Pi
VCC   → Pin 1 (3.3V)  [RED wire]
GND   → Pin 6 (GND)   [BLACK wire]
SDA   → Pin 3 (GPIO2) [BLUE wire]
SCL   → Pin 5 (GPIO3) [YELLOW wire]
```

---

## 2. NFC Tools App Integration

### What It Is
Write URLs to NFC cards that can be read by smartphones using the free NFC Tools app.

### Why It's Useful
- Participants see instant confirmation
- Self-service status checking
- Backup if Pi fails (peer uses phone)
- Professional feel

### How to Enable It

#### Step 1: Install ndeflib (Optional)
```bash
# Uncomment in requirements.txt
nano requirements.txt
# Find line: # ndeflib==0.3.3
# Remove the # to uncomment

# Install
source venv/bin/activate
pip install ndeflib
```

#### Step 2: Initialize Cards with NDEF URLs
```bash
source venv/bin/activate

# Initialize with your web server URL
python scripts/init_cards_with_ndef.py \
  --url https://festival.example.com \
  --start 1 \
  --end 100
```

**What this does:**
- Writes token IDs (001-100) to cards
- Writes NDEF URL: `https://festival.example.com/check?token=001`
- Creates mapping CSV: `data/card_mapping.csv`

#### Step 3: Test with Phone
1. Download **NFC Tools** app (free, iOS/Android)
2. Tap a card with your phone
3. Should see URL displayed
4. Tap URL → opens in browser

### How Participants Use It

**During event:**
1. Participant taps card at station → **BEEP** (as usual)
2. Later, they wonder: "Did it work?"
3. They tap their phone to the card
4. NFC Tools shows: "https://festival.example.com/check?token=001"
5. They tap the URL
6. Browser shows their status

**Status page shows:**
- "You're in queue" (if only checked in)
- "Complete!" (if exited)
- Wait time if complete
- Estimated wait if in queue

### Configuration Options

**Basic (recommended):**
```bash
# Just writes UID mapping, no NDEF
python scripts/init_cards.py
```

**With NDEF URLs:**
```bash
# Writes NDEF URLs for status checking
python scripts/init_cards_with_ndef.py --url https://your-site.com
```

**Testing mode:**
```bash
# Use mock NFC reader (no hardware needed)
python scripts/init_cards_with_ndef.py --mock --url https://test.com
```

---

## 3. Health Check & Web Status

### What It Is
Simple web server that provides:
- Health check endpoint (for monitoring)
- Status check pages (for participants)
- API endpoints (for integrations)

### How to Enable It

#### Start Web Server

**Option A: Standalone**
```bash
source venv/bin/activate
python -m tap_station.web_server --config config.yaml --port 8080
```

**Option B: With systemd (auto-start)**
Create `/etc/systemd/system/tap-station-web.service`:
```ini
[Unit]
Description=NFC Tap Station Web Server
After=network.target tap-station.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/nfc-tap-logger
ExecStart=/home/pi/nfc-tap-logger/venv/bin/python -m tap_station.web_server
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable tap-station-web
sudo systemctl start tap-station-web
```

### Available Endpoints

#### Health Check
```bash
curl http://station1.local:8080/health
```

**Response:**
```json
{
  "status": "ok",
  "device_id": "station1",
  "stage": "QUEUE_JOIN",
  "session": "festival-2025",
  "total_events": 42,
  "timestamp": "2025-06-15T14:30:00"
}
```

**Use case:** Monitoring scripts, uptime checks

#### Home Page
```bash
open http://station1.local:8080/
```

Shows station info (device ID, stage, session, status)

#### Status Check (Participant)
```bash
open http://station1.local:8080/check?token=001
```

Shows participant status with beautiful UI

#### API Status
```bash
curl http://station1.local:8080/api/status/001
```

**Response:**
```json
{
  "token_id": "001",
  "status": "complete",
  "queue_join": "2025-06-15T14:15:00",
  "queue_join_time": "02:15 PM",
  "exit": "2025-06-15T15:30:00",
  "exit_time": "03:30 PM",
  "wait_time_minutes": 75,
  "estimated_wait": 20
}
```

#### API Stats
```bash
curl http://station1.local:8080/api/stats
```

Shows overall session statistics

### Monitoring Setup

**Check all stations:**
```bash
#!/bin/bash
for station in station1 station2; do
  echo "Checking $station..."
  curl -s http://$station.local:8080/health | jq .status
done
```

**Simple uptime monitor:**
```bash
#!/bin/bash
while true; do
  if curl -s http://station1.local:8080/health | grep -q '"status": "ok"'; then
    echo "$(date): Station 1 OK"
  else
    echo "$(date): Station 1 FAILED!"
    # Send alert...
  fi
  sleep 60
done
```

### Integration with NDEF

**Complete workflow:**
1. Initialize cards with NDEF URLs pointing to your web server
2. Start web server on each Pi (or one central server)
3. Participants tap cards → URLs point to web server
4. Web server queries database, shows status

**Example:**
```bash
# Initialize cards
python scripts/init_cards_with_ndef.py --url http://192.168.1.100:8080

# Start web server (on one Pi)
python -m tap_station.web_server --host 0.0.0.0 --port 8080

# Participant taps card with phone
# NFC Tools shows: http://192.168.1.100:8080/check?token=001
# Tap URL → browser shows status page
```

---

## Quick Start: All Three Features

### 1. Setup (One Time)

```bash
# Install Flask
source venv/bin/activate
pip install Flask

# Optional: Install ndeflib for NDEF writing
pip install ndeflib
```

### 2. Initialize Cards with NDEF

```bash
python scripts/init_cards_with_ndef.py \
  --url http://192.168.1.100:8080 \
  --start 1 \
  --end 100
```

### 3. Start Services

```bash
# Terminal 1: Tap station service
sudo systemctl start tap-station

# Terminal 2: Web server
python -m tap_station.web_server --port 8080
```

### 4. Test

**Health check:**
```bash
curl http://localhost:8080/health
```

**Tap a card at station, then check status:**
```bash
curl http://localhost:8080/api/status/001
```

**With phone:**
- Tap card with NFC Tools app
- See URL
- Open in browser
- See status page

---

## Troubleshooting

### Web server won't start

**Error: "Address already in use"**
```bash
# Check what's using port 8080
sudo lsof -i :8080

# Kill it or use different port
python -m tap_station.web_server --port 8081
```

### NDEF writing fails

**"ndeflib not found"**
```bash
pip install ndeflib
```

**Cards don't show URL**
- Check card is NTAG215
- NDEF writing is currently placeholder (needs full implementation)
- For v1, cards still work with UID reading

### Health check returns 500

**Check database access:**
```bash
sqlite3 data/events.db "SELECT COUNT(*) FROM events;"
```

**Check logs:**
```bash
python -m tap_station.web_server --config config.yaml
# Watch for errors
```

---

## What's Next?

These features are production-ready for:
- ✅ Visual setup guide (use it now!)
- ✅ Health check endpoint (monitor your stations)
- ✅ Web status pages (show participants)
- ⏳ NDEF writing (basic implementation, can be enhanced)

### Future Enhancements

**Real-time dashboard:**
- Live event feed
- Charts and graphs
- Wait time trends

**Mobile app:**
- Native iOS/Android apps
- Push notifications
- Better UX than web

**Advanced NDEF:**
- Full NDEF write/read implementation
- Multiple record types
- Card encryption

See `docs/ROADMAP.md` for full roadmap!

---

## Summary

| Feature | Status | Use Case |
|---------|--------|----------|
| Visual Setup Guide | ✅ Ready | Easier hardware assembly |
| Health Check API | ✅ Ready | Monitor stations remotely |
| Web Status Pages | ✅ Ready | Participant self-service |
| NDEF Writing | 🚧 Basic | NFC Tools app integration |

**All features are optional** - the core system works great without them!

Use what helps, skip what doesn't. 🎉
