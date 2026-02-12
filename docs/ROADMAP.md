# Development Roadmap

## Overview

Potential future enhancements for FlowState, rated by effort and value. Many previously planned features have been implemented (see CHANGELOG.md).

## Completed (formerly planned)

- ~~Health Check Endpoint~~ - Implemented (Flask web server)
- ~~Smartphone Fallback~~ - Implemented (Android PWA in `mobile_app/`)
- ~~Real-Time Dashboard~~ - Implemented (11 templates with live updates)
- ~~NFC Tools App Integration~~ - Implemented (NDEF writing via `ndef_writer.py`)
- ~~Troubleshooting Flowchart~~ - Implemented (in `docs/TROUBLESHOOTING.md`)

---

## Potential Enhancements

### Quick Wins

| Enhancement | Effort | Value |
|-------------|--------|-------|
| Laminated quick-start cards for field staff | 1d | High |
| Visual setup guide with photos | 1d | High |
| Video tutorials (setup, operations, troubleshooting) | 2-3d | Medium |

### Medium Effort

| Enhancement | Effort | Value |
|-------------|--------|-------|
| QR code fallback (phone camera scan) | 3d | Medium |
| Per-user admin accounts (replace shared password) | 3d | Medium |
| SMS/email alerts for critical conditions | 3-5d | Medium |
| Docker deployment for server/cloud use | 2-3d | Low |

### Advanced

| Enhancement | Effort | Value |
|-------------|--------|-------|
| Multi-station network sync (Redis/MQTT) | 1-2w | Medium |
| Participant-facing status (scan card to check position) | 2w | Low |
| Multi-event longitudinal tracking | 1w | Low |
| Cross-station database replication | 2w | Low |
| iOS NFC support (when Apple opens Web NFC) | -- | Blocked |

---

## Deployment Options

| Option | Best For | Pros | Cons |
|--------|----------|------|------|
| Pi-Only (current primary) | Main deployment | Reliable, offline, tested | Hardware cost |
| Smartphone-Only (PWA) | Small events, backup | No hardware needed | Battery drain, less reliable |
| Hybrid (Pi + Phone) | Critical deployments | Best reliability | More complexity |

---

## Guiding Principle

Every feature adds complexity. Only build what solves real problems observed at events.
