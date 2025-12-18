# Mobile-Only NFC Tap Logger

An alternate deployment that removes Raspberry Pis entirely and uses NFC-capable Android phones as the tap stations. It keeps the same wait-time logging goals while leaning on hardware teams already carry.

## Goals
- **Zero bespoke hardware**: Only require an Android phone with NFC.
- **Offline-first**: Still log taps with no network.
- **Same data model**: Preserve the existing `events` schema so exports stay compatible.
- **Fast feedback**: Vibration/sound cues replace the Pi buzzer.

## Architecture
- **Two phone roles**: Each phone is configured as a stage (e.g., `QUEUE_JOIN` or `EXIT`). A third phone can act as an admin/export device.
- **Local store**: SQLite on-device with WAL enabled; mirrored schema: `events(token_id, device_id, stage, session_id, timestamp_ms, synced_at_ms)`.
- **NFC read path**: Android NFC reader → debounce duplicate reads within 1s → write event → haptic/audio feedback.
- **Health indicators**: On-screen status card showing last scan time, battery level, free space, and unsynced count.
- **Export/sync**:
  - **QR/ble export**: Generate a CSV QR chunk stream or BLE file transfer for completely offline handoff.
  - **LAN sync**: If Wi‑Fi is available, phones can POST JSONL batches to a laptop running `scripts/ingest_mobile_batch.py` (new thin script reusing existing database models).
- **Crash safety**: Use foreground service (Android) or Keep Awake (PWA) to avoid process suspension during long shifts.

## Implementation Options
### Option A: Android app (recommended)
- Kotlin app targeting API 26+ (Android 8+) for broad hardware support.
- Uses `NfcAdapter.enableReaderMode` for tap handling, `Room` for SQLite, and `WorkManager` for deferred sync.
- Ships an "Admin" screen to change stage/session IDs, run storage checks, and trigger exports.

### Option B: Web NFC PWA (Chromium Android)
- Runs in Chrome/Edge on Android with Web NFC enabled.
- Uses IndexedDB for storage and the same JSONL batch export format.
- Requires a keep-awake mechanism and manual install as a PWA; not all phones/browsers support Web NFC.

## User Flows
1. **Setup**
   - Install app (APK) or PWA.
   - Set `session_id` and stage (`QUEUE_JOIN` or `EXIT`).
   - Optional: preload token mappings via CSV import.
2. **Tapping**
   - Person receives NTAG215 card.
   - Tap at queue phone → vibration + short beep + on-screen confirmation of token ID and time.
   - Tap at exit phone → same feedback.
3. **Monitoring**
   - Operator checks status widget for battery, last tap, unsynced count.
4. **Export**
   - At shift end, open Admin → Export → choose CSV QR / BLE / LAN sync.
   - Collected data is merged into the existing `data/events.db` using the ingest script.

## Compatibility & Data Model
- Token IDs remain numeric to stay aligned with `data/card_mapping.csv`.
- Stage names mirror Pi configuration to keep downstream analytics unchanged.
- Timestamps stored in milliseconds since epoch, UTC.
- Exports use the same column order as `events` CSV exports today.

## Rollout Plan
- Pilot with two Android devices while keeping Pi stations as backup.
- Validate read reliability in noisy RF environments (cashless terminals nearby).
- Add rubber bumpers/straps so phones can be mounted where the old PN532s sat.
- Gather feedback on vibration/audio feedback adequacy and adjust defaults.

## What exists now
- **Web NFC PWA** in `mobile_app/`: Runs offline after first load, supports haptics, duplicate debouncing, and manual token entry fallback. Exports JSONL/CSV files that mirror the Pi event schema.
- **Ingestion script** `scripts/ingest_mobile_batch.py`: Accepts JSONL or CSV exports and appends to `data/events.db` while skipping duplicates.
- **Automated tests** verifying JSONL/CSV import paths and duplicate handling.

See `docs/MOBILE_APP_SETUP.md` for step-by-step deployment on Android phones.
