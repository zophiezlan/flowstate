# Changelog

## [2.6] - 2026-02-12

### Changed - Extension System Refactor

- **Modular Extension Architecture** - All optional features extracted into pluggable extensions
- **Extension Registry** - Centralized loader with hook dispatch (`on_tap`, `on_startup`, `on_api_routes`, `on_dashboard_stats`, `on_shutdown`)
- **12 Built-in Extensions** - anomalies, event_summary, export, hardware_monitor, insights, manual_corrections, notes, shift_summary, smart_estimates, stuck_cards, substance_tracking, three_stage
- **Codebase Cleanup** - Removed obsolete test files, consolidated logging, improved module organization

### Added

- `tap_station/extension.py` - Extension base class and TapEvent protocol
- `tap_station/registry.py` - Extension loader and hook dispatcher
- `extensions/` directory with 12 feature modules
- `docs/EXTENSIONS.md` - Extension system documentation

---

## [2.5] - 2026-01-25

### Added - Admin Access & Human Error Handling

- **Password-Protected Control Panel** - Secure admin authentication for control panel access
- **Session Management** - Auto-logout after 60 minutes of inactivity (configurable)
- **Sequence Validation** - Detects out-of-order taps with helpful warnings
- **5-Minute Grace Period** - Allows corrections for accidental taps at wrong station
- **Real-Time Anomaly Detection** - 6 anomaly types: forgotten taps, stuck cards, unusual patterns
- **Manual Event Corrections** - Staff can add/remove events with full audit trail
- **Rate Limiting & Input Validation** - Security hardening for web endpoints

---

## [2.4] - 2026-01-22

### Added - Auto-Initialize & Enhanced Metrics

- **Auto-Initialize Cards** - No need to pre-initialize cards before events
- **Sequential Assignment** - System automatically assigns next available token ID
- **Separate Queue Wait & Service Time** - Improved wait time metric clarity

---

## [2.3] - 2026-01-20

### Added - Substance Return Confirmation

- **Substance Return Tracking** - Track when participants' substances are returned after testing
- **Unreturned Substance Alerts** - Proactive alerts when substances not returned within threshold
- **Audit Trail** - Complete timestamped record of substance custody and handback

---

## [2.2.1] - 2025-01-19

### Added - Force-Exit Tool

- **Control Panel Stuck Cards Section** - UI section showing cards stuck in queue >2 hours
- **Bulk Force-Exit Operations** - Select individual or all stuck cards to mark as exited
- **API: `GET /api/control/stuck-cards`** and **`POST /api/control/force-exit`**

### Added - Real-Time Export

- **Dashboard Export Buttons** - One-click CSV downloads (last hour, today, all)
- **API: `GET /api/export`** - CSV generation with time-based filtering

---

## [2.2] - 2025-01-18

### Added - 3-Stage Tracking

- **3-Stage Journey Tracking** - QUEUE_JOIN → SERVICE_START → EXIT
- **Separate Metrics** - Queue wait time vs actual service time
- **Auto-Detection** - System detects 3-stage vs 2-stage mode automatically

---

## [2.1] - 2025-01-17

### Added - Operational Intelligence

- **Public Display (`/public`)** - Large-format queue status for participants
- **Enhanced Staff Alerts** - 8 alert types for proactive monitoring
- **Shift Summary (`/shift`)** - Quick handoff information
- **Activity Monitoring** - Detects station failures, long waits, service anomalies

---

## [2.0] - 2025-01-15

### Changed - Architecture Improvements

- **WAL Mode** - Enabled Write-Ahead Logging for concurrent reads
- **Database Optimization** - Added indexes for common queries
- **Error Handling** - Improved error messages and recovery

---

## [1.5] - 2025-01-10

### Added - Mobile PWA

- **Mobile App** - Progressive Web App for Android phones
- **Offline Support** - Service worker for offline operation
- **Batch Sync** - Background sync when network available

---

## [1.0] - 2025-01-01

### Initial Release

- 2-stage tracking (enter/exit)
- Raspberry Pi + PN532 NFC readers
- SQLite database with web dashboard
- CSV export, buzzer/LED feedback
- systemd service with auto-restart

---

## Version Numbering

- **Major (X.0.0)**: Breaking changes, major feature additions
- **Minor (0.X.0)**: New features, backwards compatible
- **Patch (0.0.X)**: Bug fixes, small improvements

---

**Latest Version:** 2.6
**Status:** Production Ready
