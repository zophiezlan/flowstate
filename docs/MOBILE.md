# Mobile Checkpoint Client (v1)

FlowState mobile is a **thin checkpoint client** for v1.

## What mobile is (v1)

- A stage-assigned NFC scanning client
- A sender of events to Pi backend (`/api/ingest`)
- A short-lived local retry queue during temporary disconnects

## What mobile is not (v1)

- Not a standalone deployment mode
- Not a source of truth
- Not an export-first / ingest-later primary workflow

## Requirements

- Android device with NFC enabled
- Chrome/Edge with Web NFC support
- Access to the local network where Pi backend is running

## Setup

1. Serve mobile app:

```bash
python -m http.server 8000 --directory mobile_app
```

2. Open on Android at `http://<host-ip>:8000`.
3. Configure:
   - **Pi URL**: `http://<pi-ip>:8080`
   - **Session ID**: same as deployment session
   - **Device ID**: unique per phone
   - **Stage**: one fixed v1 stage for this device
4. Start NFC scanning and scan tokens.

## Sync behavior

- Taps are queued locally if needed and synced to Pi with `POST /api/ingest`.
- Queue is bounded to reduce long-lived local accumulation.
- Active operation should keep Pi reachable and sync frequently.

## Operational guidance

- Assign one fixed stage per phone.
- Keep devices on same LAN as Pi backend.
- Use dashboard on Pi backend for shared live state.

## Legacy note

Older mobile docs/workflows in repository history describe export/import batch flows. Those are legacy-only and not the active v1 operating model.
