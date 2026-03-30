# FlowState v1

FlowState v1 is a **local-network checkpoint tracking tool** for harm reduction services.

## Active v1 product definition

FlowState v1 is intentionally small:

- **Raspberry Pi is the canonical local backend** (API + dashboard + SQLite).
- **Checkpoint clients are fixed-stage devices** (Pi stations or Android phones).
- **Six-stage lifecycle is fixed**:
  1. `ENTERED`
  2. `FIRST_CONTACT`
  3. `SAMPLE_LOGGED`
  4. `TESTING`
  5. `RESULT_READY`
  6. `COMPLETED`
- **Mobile is a thin checkpoint client only** (not source-of-truth, no export-first architecture).
- **Manual correction is minimal**: admin-protected stage set with basic audit metadata (`who/when/from/to`).
- **Local/offline-first**: designed to run on local LAN with no cloud dependency for core operation.

## Active runtime architecture

### Canonical backend (Pi)
- Runs `tap_station` service
- Hosts canonical SQLite database (`data/events.db` by default)
- Exposes minimal v1 API and dashboard
- Handles CSV export

### Checkpoint clients
- Each client has a fixed assigned stage
- Scans NFC token and submits stage event to Pi backend
- Receives immediate success/error feedback

### Dashboard
- Reads shared state from the same Pi backend
- Shows active count, per-stage counts, and recent events

## Minimal active v1 endpoints

- `GET /health`
- `GET /healthz`
- `GET /readyz`
- `GET /api/stages`
- `POST /api/ingest`
- `GET /api/dashboard`
- `GET /api/export.csv`
- `POST /api/admin/login`
- `POST /api/admin/correct-stage`

## Admin correction (session-cookie auth)

```bash
curl -X POST http://<pi-ip>:8080/api/admin/login \
  -c /tmp/flowstate-admin.cookies \
  -H 'Content-Type: application/json' \
  -d '{"password":"<admin-password>"}'

curl -X POST http://<pi-ip>:8080/api/admin/correct-stage \
  -b /tmp/flowstate-admin.cookies \
  -H 'Content-Type: application/json' \
  -d '{"token_id":"001","target_stage":"TESTING","corrected_by":"supervisor"}'
```

## Quick start (Pi)

1. Install:

```bash
git clone https://github.com/zophiezlan/flowstate.git
cd flowstate
bash scripts/install.sh
```

2. Create config:

```bash
cp config.yaml.example config.yaml
```

3. Set station identity + fixed stage in `config.yaml`:

```yaml
station:
  device_id: "station-entry-1"
  stage: "ENTERED"
  session_id: "festival-2026-01"
```

4. Run service:

```bash
sudo systemctl enable tap-station
sudo systemctl start tap-station
```

## Quick start (mobile checkpoint client)

Serve the mobile client:

```bash
python -m http.server 8000 --directory mobile_app
```

On Android:
- open `http://<host-ip>:8000`
- set Pi URL, stage, session, device ID
- scan cards and sync directly to Pi via `/api/ingest`

## Legacy notice

The repository still contains older docs/modules from pre-v1 exploration (extensions, control panel, advanced platform pages). These are **legacy-only artifacts** and are not part of the active v1 runtime path.

See `docs/LEGACY_STATUS.md` for status and cleanup guidance.
