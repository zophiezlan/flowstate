# Extension System

FlowState uses a modular extension system. All optional features are implemented as extensions that hook into the core application lifecycle.

## Architecture

Extensions live in `extensions/<name>/` and subclass `Extension` from `tap_station.extension`. The `ExtensionRegistry` (`tap_station/registry.py`) loads, sorts by `order`, and dispatches hooks.

### Lifecycle Hooks

| Hook | When | Purpose |
|------|------|---------|
| `on_startup(ctx)` | Once at startup | Initialize state. `ctx` has `db`, `config`, `nfc`, `app` |
| `on_tap(event)` | After NFC read, before DB write | Inspect or mutate the `TapEvent` |
| `on_dashboard_stats(stats)` | After core assembles stats | Inject additional dashboard metrics |
| `on_api_routes(app, db, config)` | Once at startup | Register Flask routes |
| `on_shutdown()` | On graceful shutdown | Cleanup resources |

### TapEvent

Extensions that implement `on_tap` receive a mutable `TapEvent`:

```python
@dataclass
class TapEvent:
    uid: str
    token_id: str
    stage: str
    device_id: str
    session_id: str
    extra: Dict[str, Any]  # for inter-extension data
```

### Load Order

Extensions are sorted by `order` (lower runs first). Current ordering:

- `three_stage` (40) - needs to run before other stat extensions
- `smart_estimates` (45), `substance_tracking` (45)
- Everything else (50)

### Discovery

Each extension package must expose one of:
- An `extension` attribute (pre-built instance)
- A `create()` factory function

---

## Configuration

Enable extensions in `config.yaml`:

```yaml
extensions:
  enabled:
    - anomalies
    - event_summary
    - export
    - hardware_monitor
    - insights
    - manual_corrections
    - notes
    - shift_summary
    - smart_estimates
    - stuck_cards
    - substance_tracking
    - three_stage
```

Remove any extension from the list to disable it. Order in the list doesn't matter (extensions sort by their own `order` attribute).

---

## Built-in Extensions

### anomalies

Real-time anomaly detection and alerting for human errors.

- **Hooks:** `on_api_routes`
- **Routes:** `GET /api/control/anomalies` (admin)
- **Detects:** Forgotten taps, stuck cards, sequence errors, unusual patterns, throughput drops, time variance

### event_summary

End-of-day summary report with goals and assessments.

- **Hooks:** `on_api_routes`
- **Routes:** `/event-summary` (page), `GET /api/event-summary`
- **Metrics:** Total served, wait times (avg/median), peak queue, throughput, abandonment rate

### export

CSV data export from the dashboard.

- **Hooks:** `on_api_routes`
- **Routes:** `GET /api/export?filter=hour|today|all`
- **Output:** CSV download with auto-generated filename

### hardware_monitor

Raspberry Pi hardware health monitoring.

- **Hooks:** `on_api_routes`
- **Routes:** `GET /api/control/hardware-status` (admin)
- **Checks:** I2C bus, GPIO pins, RTC, CPU temperature, power throttling, disk space

### insights

Service quality metrics with SLI/SLO tracking.

- **Hooks:** `on_api_routes`
- **Routes:** `/insights` (page), `GET /api/service-insights`
- **Metrics:** Quality scores, target compliance, component breakdowns

### manual_corrections

Manual event add/remove with audit trail.

- **Hooks:** `on_api_routes`
- **Routes:** `POST /api/control/manual-event` (admin), `POST /api/control/remove-event` (admin)
- **Features:** Validates timestamps (30-day range), requires operator_id and reason, rate-limited

### notes

Operational notes during shifts.

- **Hooks:** `on_startup`, `on_api_routes`
- **Routes:** `GET /api/notes`, `POST /api/notes`
- **Features:** Staff can add timestamped notes during events, retrieved in reverse chronological order

### shift_summary

Shift handoff reports.

- **Hooks:** `on_startup`, `on_api_routes`
- **Routes:** `/shift` (page), `GET /api/shift-summary`
- **Metrics:** Current queue, completions (last 4h), average wait, busiest hour, uptime, longest wait

### smart_estimates

Intelligent wait time prediction using recent completion data.

- **Hooks:** `on_startup`, `on_dashboard_stats`
- **Behavior:** Uses 30-minute rolling window of completions. Confidence levels: high (5+ samples), medium (2-4), low (<2). Falls back to overall average. Capped at 2 hours.
- **Injects:** `smart_wait_estimate` into dashboard stats

### stuck_cards

Stuck card detection and bulk force-exit.

- **Hooks:** `on_startup`, `on_api_routes`
- **Routes:** `GET /api/control/stuck-cards` (admin), `POST /api/control/force-exit` (admin)
- **Behavior:** Identifies cards in queue >2 hours. Force-exit logs EXIT events with `device_id = "manual_force_exit"`.

### substance_tracking

Substance return accountability tracking.

- **Hooks:** `on_startup`, `on_dashboard_stats`
- **Behavior:** Monitors pending returns (SERVICE_START without SUBSTANCE_RETURNED/EXIT). Tracks return rate percentage.
- **Injects:** `substance_return` stats (pending, completed, rate) into dashboard
- **Requires:** `SUBSTANCE_RETURNED` stage in service config

### three_stage

Separates queue wait time from service time in 3-stage workflows.

- **Hooks:** `on_startup`, `on_dashboard_stats`
- **Behavior:** Calculates average queue wait, service time, and total time from recent journeys (last 20). Counts currently in-service participants.
- **Injects:** `avg_queue_wait_minutes`, `avg_service_time_minutes`, `in_service`, `has_3stage_data` into dashboard

---

## Creating an Extension

1. Create `extensions/my_feature/__init__.py`:

```python
from tap_station.extension import Extension

class MyFeatureExtension(Extension):
    name = "my_feature"
    order = 50

    def on_startup(self, ctx):
        self.db = ctx["db"]
        self.config = ctx["config"]

    def on_api_routes(self, app, db, config):
        @app.route("/api/my-feature")
        def api_my_feature():
            return {"status": "ok"}

    def on_dashboard_stats(self, stats):
        stats["my_metric"] = 42

extension = MyFeatureExtension()
```

2. Enable in `config.yaml`:

```yaml
extensions:
  enabled:
    - my_feature
```

3. Restart the service. The registry will discover and load your extension.

### Guidelines

- Keep extensions focused on a single feature
- Use `on_api_routes` for new endpoints, `on_dashboard_stats` for dashboard metrics
- Use `on_tap` sparingly - it runs on every NFC read
- Handle errors gracefully - a failing extension shouldn't crash the core
- Use the `resolve_stage()` helper from `tap_station.extension` for stage name resolution
