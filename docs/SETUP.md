# Setup Guide (v1)

This guide covers the active FlowState v1 deployment model:

- Raspberry Pi as canonical backend
- SQLite on Pi
- Fixed-stage checkpoint clients
- Local-network/offline-first operation

## 1) Install on Raspberry Pi

```bash
git clone https://github.com/zophiezlan/flowstate.git
cd flowstate
bash scripts/install.sh
```

## 2) Configure station

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml`:

```yaml
station:
  device_id: "station-entry-1"
  stage: "ENTERED"  # ENTERED, FIRST_CONTACT, SAMPLE_LOGGED, TESTING, RESULT_READY, COMPLETED
  session_id: "festival-2026-01"

web_server:
  enabled: true
  host: "0.0.0.0"
  port: 8080
  admin:
    password: "CHANGE-ME-BEFORE-DEPLOYMENT"
```

## 3) Start service

```bash
sudo systemctl enable tap-station
sudo systemctl start tap-station
sudo systemctl status tap-station
```

## 4) Validate backend

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/api/stages
```

## 5) Configure checkpoint clients

- Pi station or mobile device per checkpoint
- Assign one fixed stage per client
- Point clients to Pi backend URL

## 6) Dashboard and export

- Dashboard: `http://<pi-ip>:8080/dashboard`
- CSV export: `http://<pi-ip>:8080/api/export.csv`

## Minimal admin correction

1. Login:

```bash
curl -X POST http://<pi-ip>:8080/api/admin/login \
  -c /tmp/flowstate-admin.cookies \
  -H 'Content-Type: application/json' \
  -d '{"password":"<admin-password>"}'
```

2. Correct stage:

```bash
curl -X POST http://<pi-ip>:8080/api/admin/correct-stage \
  -b /tmp/flowstate-admin.cookies \
  -H 'Content-Type: application/json' \
  -d '{"token_id":"001","target_stage":"TESTING","corrected_by":"supervisor"}'
```

## Legacy notice

Pre-v1 setup paths involving extension-driven control panels, dynamic workflow engines, or platform-like operational tooling are legacy-only and not part of active v1 deployment.
