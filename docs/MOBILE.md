# Mobile App Guide

Complete guide for using Android phones with NFC as tap stations.

**Alternative to Raspberry Pi:** Use phones you already have instead of dedicated hardware.

---

## Why Use Mobile?

**Advantages:**

- ✅ No Raspberry Pi hardware to buy/maintain
- ✅ Built-in battery, screen, and network
- ✅ Easier setup (no wiring, no GPIO)
- ✅ More portable and familiar to peer workers
- ✅ Can use as backup if Pi stations fail

**Disadvantages:**

- ❌ Requires NFC-capable Android phones (iPhone NFC is read-only)
- ❌ Requires Chrome/Edge browser (for Web NFC support)
- ❌ Phones can be distracting (notifications, calls)
- ❌ May need phone stands/mounts for hands-free operation

**Best for:**

- Events where you already have Android devices
- Testing/pilot deployments
- Backup stations
- Quick deployments without lead time

---

## Requirements

### Hardware

- **Android phone** with NFC
  - Android 8.0+ (API 26+)
  - NFC enabled in settings
  - Chrome or Edge browser (v89+)
- **NTAG215 NFC cards** (same as Pi version)
- **Laptop** for serving PWA and ingesting exports

### Software

- Chrome or Edge browser on Android
- Python 3.9+ on laptop (for ingest script)
- This repository cloned on laptop

---

## Quick Start

### 1. Serve the Mobile App

On your laptop:

```bash
cd ~/flowstate
python -m http.server 8000 --directory mobile_app
```

**Find your laptop's IP address:**

Windows:

```powershell
ipconfig
# Look for "IPv4 Address" under your active network
```

Linux/Mac:

```bash
hostname -I
# or
ifconfig | grep "inet "
```

### 2. Open on Android Phone

1. **Open Chrome or Edge** on the Android phone
2. **Navigate to:** `http://<laptop-ip>:8000`
   - Example: `http://192.168.1.100:8000`
3. **Add to home screen:**
   - Chrome: Menu → "Add to Home Screen"
   - Edge: Menu → "Add to Phone"
   - This enables offline mode after first load

### 3. Configure Station

On the phone:

1. **Set Session ID**
   - Example: `festival-2026-01`
   - Must match across all stations

2. **Choose Stage**
   - `QUEUE_JOIN` for entry station
   - `EXIT` for exit station

3. **Set Device ID**
   - Example: `phone-queue-1`, `phone-exit-1`
   - Must be unique per phone

4. **Tap "Save"** to store settings

### 4. Start Scanning

1. Tap **"Start NFC scanning"**
2. Present an NFC card to the phone's NFC reader
   - Location varies by phone (usually near top or center back)
3. **Feedback on success:**
   - Phone vibrates
   - Shows "Last token" and timestamp
   - Increments "Total taps" counter

### 5. Export Data

**After the event:**

1. **Export from phone:**
   - Tap "Download JSONL" (recommended)
   - Or "Download CSV"
   - File saved to phone's Downloads folder

2. **Transfer to laptop:**
   - USB cable and file transfer
   - AirDrop / Nearby Share
   - Email attachment
   - Cloud storage

3. **Ingest into database:**

   ```bash
   cd ~/flowstate
   source venv/bin/activate
   python scripts/ingest_mobile_batch.py \
     --input /path/to/mobile-export.jsonl \
     --db data/events.db
   ```

4. **Mark as synced on phone:**
   - Tap "Mark all as synced"
   - Future exports only include new taps
   - Prevents duplicate data

---

## Detailed Setup

### Phone Configuration

**Enable NFC:**

1. Settings → Connected devices → Connection preferences
2. Toggle "NFC" on
3. Verify NFC icon appears in status bar

**Enable Web NFC (if needed):**

- Chrome 89+ and Edge 89+ have Web NFC enabled by default on Android
- If not working, check: `chrome://flags` → Search "Web NFC"

**Prevent screen timeout:**

1. Settings → Display → Screen timeout
2. Set to "30 minutes" or use "Caffeine" app
3. Or enable "Developer Options" → "Stay awake"

**Disable distractions:**

1. Enable "Do Not Disturb" mode
2. Turn off auto-rotate (if using mount)
3. Disable auto-brightness (set to high)

### PWA Installation

**Why install as PWA:**

- Works offline after first load
- Service worker caches app
- Faster launch
- Looks like native app

**Installation steps:**

1. Open `http://<laptop-ip>:8000` in Chrome
2. Chrome prompts: "Add NFC Tap Logger to Home screen?"
3. Tap "Add"
4. Icon appears on home screen
5. Launch from home screen for offline use

**Offline capability:**

- After first load, app works without laptop
- Data stored locally in IndexedDB
- Can export anytime, even without network

### Finding NFC Reader Location

**Common locations:**

- **Samsung:** Center back, near camera
- **Google Pixel:** Top back
- **OnePlus:** Center back
- **Motorola:** Center or top back

**How to test:**

1. Launch app and tap "Start NFC scanning"
2. Hold card against different parts of phone back
3. When it vibrates, mark that spot
4. Optional: Put sticker on phone indicating tap zone

---

## During Event Operation

### Peer Worker Workflow

**Same as Pi version:**

1. Hand participant a card
2. "Tap your card here" (point to phone)
3. Wait for vibration/feedback
4. Done!

**Feedback indicators:**

- **Vibration** = Tap logged successfully
- **Screen updates** = Shows last token and time
- **Unsynced count** = How many taps waiting for export

### Monitoring Health

**On-screen status:**

- **Last token** - Most recent card tapped
- **Last time** - Timestamp of last tap
- **Total taps** - Running count for this session
- **Unsynced** - Number of taps not yet exported

**Check battery:**

- Phone shows battery level in status bar
- Bring USB power bank for charging
- Can charge while operating

**Storage:**

- App shows available storage
- Each tap is ~200 bytes
- Thousands of taps fit easily

### Manual Token Entry

**If NFC fails or card damaged:**

1. Tap "Manual token" button
2. Enter token ID (e.g., `042`)
3. Tap "Save"
4. Logs same as NFC tap

**Use cases:**

- Card damaged/won't read
- NFC reader failing
- Participant lost card
- Backup logging

---

## Data Management

### Export Formats

**JSONL (recommended):**

```json
{"token_id":"001","uid":"04a1b2c3","stage":"QUEUE_JOIN","session_id":"festival-2026","device_id":"phone-queue-1","timestamp_ms":1736121600000}
{"token_id":"002","uid":"04d4e5f6","stage":"QUEUE_JOIN","session_id":"festival-2026","device_id":"phone-queue-1","timestamp_ms":1736121615000}
```

**CSV:**

```csv
token_id,uid,stage,session_id,device_id,timestamp_ms
001,04a1b2c3,QUEUE_JOIN,festival-2026,phone-queue-1,1736121600000
002,04d4e5f6,QUEUE_JOIN,festival-2026,phone-queue-1,1736121615000
```

### Ingesting into Main Database

**Basic usage:**

```bash
cd ~/flowstate
source venv/bin/activate

# JSONL (recommended)
python scripts/ingest_mobile_batch.py \
  --input mobile-export.jsonl

# CSV
python scripts/ingest_mobile_batch.py \
  --input mobile-export.csv

# Custom database path
python scripts/ingest_mobile_batch.py \
  --input mobile-export.jsonl \
  --db /path/to/events.db
```

**Output:**

```
INFO Loaded 247 events from mobile-export.jsonl
INFO Inserted 247 new events
INFO Skipped 0 duplicates
INFO Done
```

**Duplicate handling:**

- Script checks for existing (token_id, stage, session_id, timestamp)
- Skips duplicates automatically
- Safe to run multiple times

### Combining Data from Multiple Phones

**Export from each phone:**

1. Phone 1 (Queue): Download `phone-queue-export.jsonl`
2. Phone 2 (Exit): Download `phone-exit-export.jsonl`

**Ingest both:**

```bash
python scripts/ingest_mobile_batch.py --input phone-queue-export.jsonl
python scripts/ingest_mobile_batch.py --input phone-exit-export.jsonl
```

**Data is now merged:**

```bash
python -m tap_station.main --stats
```

Shows combined statistics from all stations.

---

## Mixing Mobile and Raspberry Pi

**You can use both in same event!**

**Scenario 1: Mobile as backup**

- Primary: 2× Raspberry Pi stations
- Backup: 1× Android phone ready if Pi fails
- Same session_id across all

**Scenario 2: Hybrid deployment**

- Station 1 (Queue): Raspberry Pi
- Station 2 (Exit): Android phone
- Works seamlessly - same database format

**Scenario 3: Mobile for additional checkpoints**

- Stations 1 & 2: Raspberry Pis (queue, exit)
- Station 3: Android phone (optional mid-point check)
- Add custom stage: `MIDPOINT`

**Data export:**

- Export Pi data: `python scripts/export_data.py`
- Ingest mobile data: `python scripts/ingest_mobile_batch.py`
- Analyze combined dataset

---

## NFC Tools Integration

**Write NDEF records so participants can check status with their phones.**

### Option A: Static URL

**On card initialization:**

- Write URL: `https://your-site.com/check?token=001`
- Participant taps card with their phone
- Browser opens showing their status

**Setup:**

```bash
# Initialize cards with NDEF URL
python scripts/init_cards_with_ndef.py \
  --start 1 \
  --end 100 \
  --url "https://festival-status.com/check"
```

**Requires:**

- Web server hosting status page
- Internet connection on participant's phone

### Option B: Local Text Record

**On each tap:**

- Update card with: "Token 001 - EXIT at 3:45pm"
- Participant taps with NFC Tools app
- Sees current status offline

**Pros/Cons:**

- ✅ Works offline
- ❌ Slower (writes on each tap)
- ❌ More complex implementation

**Currently:** Option A is implemented in `init_cards_with_ndef.py`

---

## Troubleshooting

### NFC Not Working

**"NFC not supported" error:**

- Check phone has NFC hardware
- Enable NFC in Settings
- Some phones (iPhone) don't support Web NFC

**"NFC scanning failed":**

- Try Chrome instead of Edge (or vice versa)
- Check Web NFC enabled: `chrome://flags`
- Restart browser
- Clear browser cache

**"No tap detected":**

- Find phone's NFC reader location
- Hold card flat for 2+ seconds
- Try different card
- Check card is NTAG215

### App Issues

**"App won't install as PWA":**

- Must use HTTPS or localhost
- Use `http://<ip>:8000` should work on Android
- Check manifest.webmanifest exists

**"App crashes or freezes":**

- Close and reopen from home screen
- Clear browser data
- Reinstall PWA

**"Data disappeared":**

- Check if IndexedDB cleared
- Export frequently to prevent data loss
- Use "Mark as synced" after each export

### Export Issues

**"No events in export":**

- Check "Total taps" > 0
- Try different export format (CSV vs JSONL)
- Check Downloads folder for file

**"Ingest script fails":**

- Verify file format (JSONL or CSV)
- Check file not corrupted
- Run with `--help` to see options

**"Duplicate events":**

- Not a problem - script skips duplicates
- Shows "Skipped N duplicates" in output

---

## Performance & Limitations

### Battery Life

**Typical usage:**

- 4-8 hours continuous scanning
- Varies by phone model and battery capacity
- Use power bank for all-day events

**Tips:**

- Lower screen brightness
- Disable unnecessary apps
- Use battery saver mode (doesn't affect NFC)

### Storage Capacity

**Data size:**

- ~200 bytes per tap
- 1000 taps ≈ 200KB
- Typical event (500 participants, 2 taps each) ≈ 200KB
- No storage concerns for single-day events

### Read Performance

**Typical read time:**

- ~200-500ms per tap
- Fast enough for event use
- Comparable to Raspberry Pi version

**Debounce:**

- 1 second debounce prevents double-taps
- Same card can't log twice within 1 second
- Configurable in app settings

---

## Best Practices

### Setup

- [ ] Test phones 1 week before event
- [ ] Verify Web NFC works on each device
- [ ] Install as PWA for offline capability
- [ ] Configure all stations with same session_id
- [ ] Test export and ingest workflow
- [ ] Have laptop ready for data collection
- [ ] Print quick reference cards for peers

### During Event

- [ ] Keep phones charged (use power banks)
- [ ] Check "Last tap" hourly to verify working
- [ ] Have backup phone ready
- [ ] Export data mid-event (if long event)
- [ ] Don't let phones distract peer workers

### After Event

- [ ] Export from all phones immediately
- [ ] Ingest all exports into one database
- [ ] Verify data completeness
- [ ] Back up raw export files
- [ ] Mark as synced on phones
- [ ] Document any issues

---

## Comparison: Mobile vs Raspberry Pi

| Feature           | Mobile (Android)       | Raspberry Pi         |
| ----------------- | ---------------------- | -------------------- |
| **Setup time**    | 10 minutes             | 45 minutes           |
| **Hardware cost** | $0 (if have phone)     | ~$80/station         |
| **Complexity**    | Low                    | Medium               |
| **Reliability**   | Good                   | Excellent            |
| **Battery**       | 4-8 hours              | 8+ hours             |
| **Weatherproof**  | Depends on phone       | Easy to weatherproof |
| **Feedback**      | Vibration              | Buzzer/LED           |
| **Offline**       | Yes (after first load) | Yes (always)         |
| **Data export**   | Manual download        | Auto-export scripts  |

**Recommendation:**

- **Use mobile** for: Quick deployments, testing, backup stations
- **Use Pi** for: Production events, outdoor/wet conditions, long events

---

## Advanced: Custom Mobile App

**Current solution:** Web NFC PWA (works in browser)

**Want native app?**

- Consider developing dedicated Android app
- Benefits: Better integration, more reliable, custom UI
- Kotlin + NFC API + Room database
- Architecture: Service for background scanning, Room for DB, WorkManager for sync

**PWA limitations:**

- Requires specific browsers (Chrome/Edge)
- Some phones have Web NFC quirks
- Can't customize system notifications

**For most use cases, PWA is sufficient.**

---

## Next Steps

✅ Mobile app set up and tested
✅ Cards work with both Pi and mobile
✅ Export/ingest workflow tested

**Now:**

- Test with peer workers before event
- Prepare backup plan (manual logs)
- See [Operations Guide](OPERATIONS.md) for day-of workflow

---

## Quick Command Reference

```bash
# Serve mobile app
python -m http.server 8000 --directory mobile_app

# Ingest mobile exports
python scripts/ingest_mobile_batch.py --input mobile-export.jsonl

# View combined stats
python -m tap_station.main --stats

# Export all data
python scripts/export_data.py
```

---

**Questions?** See [Troubleshooting](TROUBLESHOOTING.md) or create a GitHub issue.
