# Legacy Status (Post-v1 Consolidation)

This file tracks major legacy residue still present in-tree after v1 consolidation.

## Active v1 path (authoritative)

- Runtime entrypoint: `tap_station/main.py`
- Active web server/API: `tap_station/web_server.py`
- Active dashboard template: `tap_station/templates/dashboard_v1.html`
- Canonical data path: `tap_station/database.py`
- Mobile thin client: `mobile_app/`

## Legacy-only areas currently still in repository

These remain for historical/reference reasons and are not part of active v1 runtime behavior:

- Legacy templates/pages:
  - `tap_station/templates/control.html`
  - `tap_station/templates/public.html`
  - `tap_station/templates/shift.html`
  - `tap_station/templates/insights.html`
  - `tap_station/templates/event_summary.html`
  - `tap_station/templates/monitor.html`
- Extension system modules:
  - `tap_station/registry.py`
  - `tap_station/extension.py`
  - `extensions/*`
- On-site/network-helper modules:
  - `tap_station/onsite_manager.py`
  - `tap_station/wifi_manager.py`
  - `tap_station/mdns_service.py`
  - `tap_station/failover_manager.py`

## Current status labels

- **inactive in v1 runtime**: code exists but not used by active routes/startup path.
- **legacy docs**: documentation retained but not recommended for v1 deployment.

## Recommended follow-up

A dedicated "legacy pruning" pass is recommended to:

1. remove legacy templates no longer routed,
2. remove extension/onsite modules not imported by active runtime,
3. archive or delete legacy docs that conflict with v1 framing,
4. shrink maintenance surface and reduce onboarding confusion.
