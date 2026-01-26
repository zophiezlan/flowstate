# Service Configuration Guide

## Overview

The flowstate system is designed to be **fully configurable** for different festival-based community drug checking services. Each service has different needs, workflows, staffing models, capacity, and operational parameters. The service configuration system allows you to customize every aspect of the system without modifying code.

## Quick Start

### 1. Choose Your Configuration Template

Select the example that best matches your service model:

```bash
# Simple queue service (2 stages: join → exit)
cp examples/service_configs/simple_queue.yaml service_config.yaml

# Comprehensive service (5 stages: queue → intake → testing → results → exit)
cp examples/service_configs/comprehensive_service.yaml service_config.yaml

# Multi-location festival
cp examples/service_configs/multi_location_festival.yaml service_config.yaml

# Or start with the default template
# (already present in the repository as service_config.yaml)
```

### 2. Customize for Your Service

Edit `service_config.yaml` and customize:

```yaml
service:
  name: "Your Service Name"
  organization: "Your Organization"
  hours:
    schedule: "Your service hours"

workflow:
  stages:
    # Define your workflow stages

capacity:
  people_per_hour: <your capacity>
  avg_service_minutes: <your average time>

alerts:
  queue:
    warning_threshold: <when to warn staff>
    critical_threshold: <when it's critical>
```

### 3. Test Your Configuration

```bash
# Validate configuration syntax
python service_config_loader.py

# Test the integration
python tap_station/service_integration.py

# Run the system
sudo systemctl restart flowstate  # or your start command
```

## Configuration Sections

### Service Identity

Define who you are and what you do:

```yaml
service:
  name: "Festival Drug Checking"
  description: "Harm Reduction & Substance Analysis"
  type: "festival" # Options: festival, venue, popup, mobile
  organization: "Community Harm Reduction"
  contact:
    display: true
    info: "Ask any peer worker for help"
  hours:
    display: true
    schedule: "2:00 PM - 10:00 PM"
    timezone: "AEDT"
```

**Customization tips:**

- Use a clear, welcoming service name
- Include location info in contact if you have multiple sites
- Update service hours daily if they change

### Workflow Stages

This is the **most important** configuration - it defines how participants move through your service.

#### Understanding Stages

Each stage represents a distinct step in your service process:

```yaml
workflow:
  stages:
    - id: "QUEUE_JOIN" # Internal identifier (use CAPS_WITH_UNDERSCORES)
      label: "In Queue" # What users see
      description: "Waiting" # Detailed description
      order: 1 # Sequence number
      required: true # Must everyone go through this?
      visible_to_public: true # Show on public display?
      duration_estimate: 0 # Minutes (used for wait calculation)
      icon: "⏰" # Optional emoji
```

#### Common Workflow Patterns

**Pattern 1: Simple Queue (2 stages)**

```yaml
stages:
  - { id: "QUEUE_JOIN", label: "Waiting", order: 1, required: true }
  - { id: "EXIT", label: "Complete", order: 2, required: true }
```

Best for:

- Small services
- Quick check-in/check-out
- Limited staff

**Pattern 2: Standard Service (3 stages)**

```yaml
stages:
  - {
      id: "QUEUE_JOIN",
      label: "In Queue",
      order: 1,
      required: true,
      duration_estimate: 0,
    }
  - {
      id: "SERVICE_START",
      label: "Being Served",
      order: 2,
      required: true,
      duration_estimate: 5,
    }
  - {
      id: "EXIT",
      label: "Complete",
      order: 3,
      required: true,
      duration_estimate: 0,
    }
```

Best for:

- Medium-sized services
- Track when service actually starts
- Distinguish waiting vs. being served

**Pattern 3: Comprehensive Workflow (5+ stages)**

```yaml
stages:
  - { id: "QUEUE_JOIN", label: "Queue", order: 1 }
  - { id: "INTAKE", label: "Check-in", order: 2, duration_estimate: 3 }
  - {
      id: "TESTING",
      label: "Testing",
      order: 3,
      duration_estimate: 10,
      visible_to_public: false,
    }
  - { id: "RESULTS", label: "Results", order: 4, duration_estimate: 7 }
  - { id: "EXIT", label: "Complete", order: 5 }
```

Best for:

- Large services
- Specialized staff roles
- Detailed tracking needed
- Research/evaluation

#### Workflow Behavior

```yaml
workflow:
  allow_skip_stages: false # Can stages be skipped?
  allow_repeat_stages: false # Can someone go through a stage twice?
  enforce_stage_order: true # Must stages be in order?
```

### Capacity & Throughput

Configure how many people you can serve:

```yaml
capacity:
  people_per_hour: 12 # Your maximum throughput
  avg_service_minutes: 5 # Average time per person
  default_wait_estimate: 20 # Default if no data available
  queue_multiplier: 2 # Used for quick estimates (pos × multiplier = min)
```

#### How to Calculate Your Capacity

**Method 1: From Service Time**

```
Capacity = 60 / avg_service_minutes
```

Example: 5 min per person = 60/5 = 12 people/hour

**Method 2: From Staff**

```
Capacity = (60 / avg_service_minutes) × num_parallel_stations
```

Example: 5 min per person, 2 stations = 12 × 2 = 24 people/hour

**Method 3: Measure It**

- Track actual throughput during a shift
- Count completions per hour
- Use the real number

#### Peak Hours Adjustment

Reduce capacity during busy times when service may slow:

```yaml
capacity:
  people_per_hour: 12
  multipliers:
    peak_hours: 0.8 # 20% reduction during peak
    off_peak: 1.0 # Normal during off-peak

  peak_hours:
    enabled: true
    ranges:
      - start: "20:00" # 8 PM
        end: "23:00" # 11 PM
```

### Alert Thresholds

Set when the system should alert your staff:

```yaml
alerts:
  queue:
    warning_threshold: 10 # Yellow alert at 10 people
    critical_threshold: 20 # Red alert at 20 people

  wait_time:
    warning_minutes: 45 # Warn if wait > 45 min
    critical_minutes: 90 # Critical if > 90 min

  service_inactivity:
    warning_minutes: 5 # Warn if no activity for 5 min
    critical_minutes: 10 # Critical if no activity for 10 min

  stuck_cards:
    threshold_hours: 2 # Alert if someone hasn't exited in 2 hours
```

#### Choosing Good Thresholds

**Queue Length Thresholds**

Ask yourself:

- At what queue length should I consider calling in more staff? → **Warning**
- At what length is the queue unmanageable? → **Critical**

| Service Size     | Warning | Critical | Reasoning                           |
| ---------------- | ------- | -------- | ----------------------------------- |
| Small (≤8/hr)    | 5       | 10       | Limited capacity, queue builds fast |
| Medium (8-15/hr) | 10      | 20       | Moderate buffer                     |
| Large (≥15/hr)   | 15      | 30       | Can handle larger queues            |

**Wait Time Thresholds**

Consider:

- What's an acceptable wait for your participants?
- What's your service level goal?
- When does waiting become harmful (people leave, unsafe substance use)?

**Inactivity Thresholds**

- **Warning**: Long enough to be unusual, short enough to catch issues
- **Critical**: Definitely a problem (staff break, system issue, emergency)

For most services:

- Warning: 5-10 minutes
- Critical: 10-15 minutes

### UI Labels & Text

Customize all user-facing text:

```yaml
ui:
  labels:
    queue_count: "waiting" # Instead of "people in queue"
    wait_time: "wait time"
    served_today: "people helped" # Instead of "served today"
    avg_service_time: "avg time"
    service_status: "status"

    # Status values
    status_active: "ACTIVE"
    status_idle: "IDLE"
    status_stopped: "STOPPED"
```

**Internationalization**

You can configure labels in any language:

```yaml
ui:
  labels:
    queue_count: "en attente" # French
    wait_time: "temps d'attente"
    served_today: "servi aujourd'hui"
```

### Display Settings

Control what appears on public displays:

```yaml
ui:
  public_display:
    show_queue_positions: true # Show position in queue?
    show_wait_estimates: true # Show estimated wait?
    show_served_count: true # Show people served today?
    show_avg_time: true # Show average service time?
    show_service_hours: true # Show operating hours?
    refresh_interval_seconds: 5 # How often to refresh

  dashboard:
    show_individual_queue_positions: true
    max_recent_events: 15 # How many recent events to show
    max_recent_completions: 10 # How many recent completions
    analytics_history_hours: 12 # How far back for analytics
```

### Staffing & Roles

Define staff types and permissions:

```yaml
staffing:
  require_staff_id: false # Must staff identify themselves?

  roles:
    - id: "peer_worker"
      label: "Peer Worker"
      description: "Service provider"
      permissions:
        - "scan_nfc"
        - "view_queue"
        - "view_dashboard"

    - id: "coordinator"
      label: "Coordinator"
      description: "Shift supervisor"
      permissions:
        - "scan_nfc"
        - "view_queue"
        - "view_dashboard"
        - "view_analytics"
        - "force_exit_participant"
        - "manage_alerts"

  shifts:
    enabled: true
    duration_hours: 4
    handoff_checklist:
      - "Review current queue status"
      - "Check for stuck cards"
      - "Note any issues"
```

### Locations & Multi-Site

Configure multiple service locations:

```yaml
locations:
  multi_location: true # Enable multi-location mode
  shared_queue: false # Each location has its own queue

  sites:
    - id: "main_stage"
      name: "Main Stage Area"
      description: "Near main stage"
      enabled: true
      stations:
        - device_id: "main_station1"
          description: "Main Station 1"
        - device_id: "main_station2"
          description: "Main Station 2"

    - id: "camping"
      name: "Camping Zone"
      description: "In camping area"
      enabled: true
      stations:
        - device_id: "camp_station1"
          description: "Camp Station"

  show_all_locations: true # Show all locations on public display
```

## Advanced Configuration

### Custom Alert Messages

Personalize alert messages for your team:

```yaml
alerts:
  messages:
    queue_warning: "Queue building up - {count} waiting"
    queue_critical: "LONG QUEUE: {count} people - need more staff NOW"
    wait_warning: "Wait time about {minutes} min - monitor closely"
    wait_critical: "Wait is {minutes} min - add staff or redirect"
    inactivity_warning: "No scans for {minutes} min - check station"
    inactivity_critical: "STATION DOWN? No activity for {minutes} min"
```

### Custom Data Collection

(Future feature - planned)

```yaml
data_collection:
  custom_fields:
    enabled: true
    fields:
      - id: "substance_type"
        label: "Substance Type"
        type: "select"
        options: ["Powder", "Pill", "Crystal"]
        required_at_stages: ["SERVICE_START"]
```

### Integration & Webhooks

(Future feature - planned)

```yaml
integrations:
  webhooks:
    enabled: true
    endpoints:
      - url: "https://your-system.com/webhook"
        events: ["queue_critical", "service_stopped"]
        auth_header: "Bearer YOUR_TOKEN"
```

## Testing Your Configuration

### Pre-Deployment Checklist

- [ ] Configuration file is valid YAML (no syntax errors)
- [ ] Service name and organization are correct
- [ ] Workflow stages match your actual process
- [ ] Capacity settings reflect your real capacity
- [ ] Alert thresholds are appropriate for your service size
- [ ] UI labels are clear and in the right language
- [ ] All staff understand the workflow stages
- [ ] Test with actual NFC cards before going live

### Validation Commands

```bash
# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('service_config.yaml'))"

# Test configuration loader
python service_config_loader.py

# Test service integration
python tap_station/service_integration.py

# View configuration summary
python -c "from service_config_loader import load_service_config; c=load_service_config(); print(f'{c.service_name}: {len(c.workflow_stages)} stages, {c.people_per_hour} ppl/hr')"
```

### Testing Workflow

1. **Walkthrough Test**: Use test cards and walk through each stage
2. **Timing Test**: Time how long each stage actually takes
3. **Capacity Test**: Measure real throughput during setup
4. **Alert Test**: Verify alerts trigger at expected thresholds
5. **Staff Training**: Ensure all staff can navigate the workflow

## Migration Guide

### From Hardcoded to Configured

If you're using an older version with hardcoded stages:

#### Before (Hardcoded)

```python
# Hardcoded stages in code
QUEUE_JOIN = "QUEUE_JOIN"
SERVICE_START = "SERVICE_START"
EXIT = "EXIT"
```

#### After (Configured)

```python
# Stages from configuration
from tap_station.service_integration import get_first_stage, get_last_stage

first_stage = get_first_stage()  # Gets first stage from config
last_stage = get_last_stage()    # Gets last stage from config
```

The system maintains **backward compatibility** - if no configuration file exists, it uses the original hardcoded values.

## Troubleshooting

### Configuration Not Loading

**Problem**: System uses default values instead of your configuration

**Solutions**:

1. Check file location: `service_config.yaml` should be in project root
2. Check file permissions: `ls -la service_config.yaml`
3. Check YAML syntax: `python -c "import yaml; yaml.safe_load(open('service_config.yaml'))"`
4. Check logs: `journalctl -u flowstate -n 50`

### Stages Not Appearing

**Problem**: Custom stages don't show up

**Solutions**:

1. Verify stage order numbers are sequential
2. Check `visible_to_public: true` if they should show on displays
3. Restart the service after config changes
4. Check logs for parsing errors

### Alerts Not Triggering

**Problem**: Alerts don't appear when expected

**Solutions**:

1. Verify threshold values are reasonable
2. Check that queue is actually exceeding thresholds
3. Test with deliberately high queue counts
4. Check alert message configuration

### Wait Time Estimates Wrong

**Problem**: Estimated wait times are inaccurate

**Solutions**:

1. Measure real service time: time actual participants
2. Update `avg_service_minutes` to match reality
3. Adjust `queue_multiplier` based on observations
4. Consider peak hour multipliers if service slows during busy times
5. Remember: estimates improve over time with real data

## Best Practices

### 1. Start Simple

- Begin with a basic workflow (2-3 stages)
- Add complexity only if needed
- Test thoroughly before adding stages

### 2. Match Reality

- Configure workflow to match actual process
- Don't add stages you won't actually track
- Update configuration as your service evolves

### 3. Measure, Don't Guess

- Time your actual service delivery
- Count real throughput
- Adjust configuration based on data

### 4. Conservative Thresholds

- Set alerts early rather than late
- Better to over-alert than under-alert
- Adjust based on experience

### 5. Clear Communication

- Use clear, simple labels
- Match terminology your staff uses
- Consider your participant population

### 6. Document Your Changes

- Keep notes on why you set specific values
- Track what works and what doesn't
- Share learnings with other services

### 7. Version Control

- Keep your `service_config.yaml` in version control
- Document changes in commit messages
- Tag configurations for specific events

## Example Scenarios

### Scenario 1: Small Festival Popup

**Context**:

- 200-person festival
- 1-2 peer workers
- Quick reagent testing only
- 4-hour service window

**Configuration**:

```yaml
service:
  name: "Safer Partying Pop-up"
  type: "popup"

workflow:
  stages:
    - { id: "QUEUE_JOIN", label: "Waiting", order: 1 }
    - { id: "EXIT", label: "Done", order: 2 }

capacity:
  people_per_hour: 8
  avg_service_minutes: 7

alerts:
  queue:
    warning_threshold: 5
    critical_threshold: 10
  wait_time:
    warning_minutes: 30
    critical_minutes: 60
```

### Scenario 2: Large Multi-Day Festival

**Context**:

- 5,000-person festival
- 6-8 staff members
- Comprehensive testing (FTIR, GC/MS available)
- Multiple service locations
- 72-hour operation

**Configuration**:

```yaml
service:
  name: "Festival Harm Reduction"
  type: "festival"

workflow:
  stages:
    - { id: "QUEUE_JOIN", label: "Queue", order: 1, duration_estimate: 0 }
    - { id: "INTAKE", label: "Check-in", order: 2, duration_estimate: 3 }
    - {
        id: "TESTING",
        label: "Testing",
        order: 3,
        duration_estimate: 12,
        visible_to_public: false,
      }
    - { id: "RESULTS", label: "Results", order: 4, duration_estimate: 8 }
    - { id: "EXIT", label: "Complete", order: 5, duration_estimate: 0 }

capacity:
  people_per_hour: 15
  avg_service_minutes: 20
  peak_hours:
    enabled: true
    ranges:
      - { start: "22:00", end: "02:00" }

alerts:
  queue:
    warning_threshold: 15
    critical_threshold: 30
  wait_time:
    warning_minutes: 60
    critical_minutes: 120

locations:
  multi_location: true
  sites:
    - { id: "main", name: "Main Stage", enabled: true }
    - { id: "camp", name: "Camping", enabled: true }
```

## Getting Help

- Review the example configurations in `examples/service_configs/`
- Check the inline documentation in `service_config.yaml`
- Review source code in `service_config_loader.py`
- Open an issue on GitHub for bugs or feature requests
- Share your configuration with the community!

## Contributing

Have a configuration for a service model not covered here? Please contribute!

1. Create your configuration
2. Test it at an event
3. Document the use case
4. Submit a pull request with your example

Help other harm reduction services learn from your experience!
