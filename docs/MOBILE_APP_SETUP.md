# Mobile NFC Phone Deployment (Web App)

A fully functional, phone-only NFC tap station that runs as a Progressive Web App (PWA) on Android devices with Web NFC support (Chrome/Edge 89+). It stores taps offline, plays haptics for feedback, and exports JSONL/CSV for ingestion into the same SQLite database the Raspberry Pi workflow uses.

## Prerequisites
- Android phone with NFC and Chrome/Edge (Web NFC enabled by default on Android 13+)
- NFC tags (NTAG215 or similar)
- This repository cloned onto a laptop for serving the PWA and ingesting exports

## 1) Launch the mobile web app
From the repo root:
```bash
python -m http.server 8000 --directory mobile_app
```
Then open `http://<your-laptop-ip>:8000` in Chrome/Edge on the phone and add it to the home screen. The service worker caches the app for offline use after first load.

## 2) Configure the phone as a station
- Set **Session ID** (e.g., `festival-2025`)
- Pick **Stage**: `QUEUE_JOIN` or `EXIT`
- Set **Device ID**: a unique label per phone, e.g., `phone-queue-1`
- Tap **Save**

## 3) Start scanning
- Tap **Start NFC scanning** and present a card.
- The app reads the Web NFC serial number or a text NDEF payload as the token ID.
- Haptics confirm a successful log; the UI shows last token/time and unsynced counts.
- A **Manual token** button exists for fallback when Web NFC is unavailable.

## 4) Export unsynced events
Exports only include unsynced rows so you can export multiple times without duplication.
- Tap **Download JSONL** (preferred for ingestion) or **Download CSV**.
- AirDrop/USB/QR/USB-drive the file to the laptop.
- Tap **Mark all as synced** once transferred so future exports only contain new rows.

## 5) Ingest on the laptop
Use the ingest script to merge phone exports into the main database:
```bash
source venv/bin/activate  # if your virtualenv is set up
python scripts/ingest_mobile_batch.py --input /path/to/mobile-export.jsonl --db data/events.db
```
The script preserves the timestamps from the phone and skips duplicates (same `token_id` + `stage` + `session_id`).

## 6) Analyze/export as usual
Once ingested, `scripts/export_data.py` and downstream R/BI tooling continue to work unchanged because the schema matches the Pi stations. You can mix phone and Pi data in the same session ID.

## Notes
- Web NFC is Android-only; iOS users should stick to Pi stations or enter tokens manually.
- The PWA caches assets for offline use, but the first load requires network.
- If you pre-encode token IDs as text NDEF records, the app will read that field; otherwise it falls back to the tag serial number.
