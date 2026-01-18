# Example Service Configurations

This directory contains example service configurations for different types of festival-based community drug checking services. Each configuration demonstrates how to customize the NFC-Tap-Logger system for specific service models and operational needs.

## Available Examples

### 1. Simple Queue (`simple_queue.yaml`)
**Use case:** Small festival or popup service with limited staff

**Workflow:** Join Queue → Exit (2 stages)

**Characteristics:**
- Simple two-stage workflow
- Lower capacity (8 people/hour)
- Conservative alert thresholds
- Minimal UI complexity
- Single location

**Best for:**
- Small festivals (< 500 people)
- Popup harm reduction events
- Services with 1-2 staff members
- Quick check-in/check-out only

---

### 2. Comprehensive Service (`comprehensive_service.yaml`)
**Use case:** Large festival with full harm reduction program

**Workflow:** Queue → Intake → Testing → Results → Substance Returned → Exit (6 stages)

**Characteristics:**
- Multi-stage workflow with detailed tracking
- Higher capacity (15 people/hour)
- Staff role differentiation (intake, technician, counselor)
- Shift management enabled
- Advanced analytics
- Hidden internal stages (testing) from public view
- **Substance return confirmation for accountability**

**Best for:**
- Large festivals (> 2,000 people)
- Services with specialized staff roles
- Detailed substance analysis programs
- Services requiring comprehensive data collection
- Services where accountability is critical

---

### 3. Substance Return Tracking (`substance_return_tracking.yaml`)
**Use case:** Services requiring accountability for substance custody and return

**Workflow:** Queue → Service Start → Substance Returned → Exit (4 stages)

**Characteristics:**
- Substance return confirmation stage
- Alerts for unreturned substances
- Audit trail for accountability
- Incident prevention focus
- Staff accountability tracking

**Best for:**
- Services where trust is paramount
- Preventing "left behind" incidents
- Legal/insurance requirements for custody chain
- Services with history of substance loss incidents
- Building participant confidence

**Key Features:**
- Alerts if substances not returned within threshold time
- Dashboard shows "awaiting return" status
- Shift handoff includes unreturned substance review
- Complete audit trail for all substance movements

---

### 4. Multi-Location Festival (`multi_location_festival.yaml`)
**Use case:** Large festival with services at multiple locations

**Workflow:** Queue → Service Start → Exit (3 stages)

**Characteristics:**
- Multiple service locations across festival site
- Independent queues per location
- Location-specific staffing and alerts
- Festival-wide analytics
- Extended data retention for annual analysis

**Best for:**
- Multi-day festivals
- Large venue with multiple stages/areas
- Distributed service model
- Services wanting to meet people where they are

---

## How to Use These Examples

### Option 1: Copy and Customize
1. Choose the example closest to your service model
2. Copy it to your project root as `service_config.yaml`:
   ```bash
   cp examples/service_configs/simple_queue.yaml service_config.yaml
   ```
3. Edit `service_config.yaml` to match your specific needs

### Option 2: Use as Reference
1. Start with the default `service_config.yaml` in the project root
2. Refer to these examples for ideas and configuration patterns
3. Mix and match settings from different examples

### Option 3: Create Your Own
1. Use the main `service_config.yaml` template
2. Uncomment and customize sections based on your needs
3. Test thoroughly before deployment

---

## Key Configuration Areas to Customize

### Must Customize
- **Service identity** - Name, description, organization
- **Service hours** - Operating schedule
- **Workflow stages** - Match your actual service process
- **Capacity settings** - Based on your staffing and throughput
- **Alert thresholds** - Based on your capacity and queue expectations

### Should Customize
- **UI labels** - Match your terminology and language
- **Staffing roles** - Define your staff types and permissions
- **Alert messages** - Customize for your team's communication style
- **Locations** - Configure stations and service points

### Optional Customization
- **Peak hours** - Define busy periods for capacity adjustment
- **Shift management** - Enable if you have formal shift handoffs
- **Custom data fields** - Add service-specific tracking
- **Advanced features** - Enable analytics, predictions, etc.

---

## Configuration Tips

### Starting Simple
If you're new to the system or setting up for the first time:
1. Start with `simple_queue.yaml` configuration
2. Test with your team during setup
3. Gradually add complexity as needed
4. Monitor what works and what doesn't

### Matching Workflow to Reality
Your configured workflow should match your actual service process:
- **Don't add stages you won't actually track** - Keep it simple
- **Do match participant experience** - Stages should represent real steps
- **Consider staff workflow** - Stages should be easy for staff to identify
- **Test the workflow** - Walk through with your team before the event

### Capacity and Wait Time Accuracy
For accurate wait time estimates:
1. **Measure your actual service time** - Time several participants
2. **Count staff capacity** - How many can you serve simultaneously?
3. **Account for complexity** - More stages = more time
4. **Be conservative** - Better to overestimate wait time

Example calculation:
- Average service time: 5 minutes per person
- Staff can serve 3 people simultaneously
- Capacity = (60 min / 5 min) × 3 = 36 people per hour

### Alert Thresholds
Set thresholds based on your capacity and goals:
- **Queue warning** - When you should consider adding staff
- **Queue critical** - When you must add staff or risk service breakdown
- **Wait time warning** - Acceptable maximum wait
- **Wait time critical** - Unacceptable wait time

Example for different service sizes:

| Service Size | Queue Warning | Queue Critical | Wait Warning | Wait Critical |
|--------------|---------------|----------------|--------------|---------------|
| Small (< 10/hr) | 5 people | 10 people | 30 min | 60 min |
| Medium (10-15/hr) | 10 people | 20 people | 45 min | 90 min |
| Large (> 15/hr) | 15 people | 30 people | 60 min | 120 min |

---

## Testing Your Configuration

Before deploying at an event:

1. **Syntax check** - Run the configuration loader:
   ```bash
   python service_config_loader.py
   ```

2. **Simulate workflow** - Walk through the stages with test cards

3. **Verify UI** - Check that all labels display correctly

4. **Test alerts** - Verify thresholds trigger at expected points

5. **Staff training** - Ensure all staff understand the workflow and stages

---

## Common Configuration Patterns

### Pattern: Fast-Track Queue
Some services want to differentiate between simple checks and complex analysis:

```yaml
workflow:
  stages:
    - id: "QUEUE_JOIN"
      label: "In Queue"
    - id: "TRIAGE"
      label: "Assessment"
      description: "Determine service level needed"
    - id: "QUICK_CHECK"
      label: "Quick Check"
      description: "Simple reagent test"
      required: false
    - id: "FULL_ANALYSIS"
      label: "Full Analysis"
      description: "Detailed lab testing"
      required: false
    - id: "RESULTS"
      label: "Results"
    - id: "EXIT"
      label: "Complete"
```

### Pattern: Separate Entry/Exit Stations
For services with physical separation between intake and results:

```yaml
locations:
  sites:
    - id: "main"
      name: "Main Service"
      stations:
        - device_id: "intake_station"
          description: "Entry/Queue Join"
        - device_id: "service_station"
          description: "Service/Testing"
        - device_id: "exit_station"
          description: "Results/Exit"
```

### Pattern: Peak Hour Adjustment
Reduce capacity during busy times when service may slow down:

```yaml
capacity:
  people_per_hour: 12
  multipliers:
    peak_hours: 0.75  # Reduce to 9/hr during peak
  peak_hours:
    enabled: true
    ranges:
      - start: "22:00"
        end: "02:00"
```

---

## Need Help?

- Review the main `service_config.yaml` for detailed inline documentation
- Check the `service_config_loader.py` code for available options
- Test configurations in a safe environment before deployment
- Start simple and add complexity incrementally

---

## Contributing

If you create a configuration for a different service model that might be useful to others, consider contributing it as an example! Open a pull request with:
- The configuration file
- A description of the service model
- Key characteristics and use case
- Any lessons learned during deployment
