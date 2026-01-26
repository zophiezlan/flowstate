# Service Configuration Integration Guide

## Overview

This guide documents the integration of the service configuration system throughout the flowstate codebase. It tracks what has been completed and what remains to be done.

## Integration Status

### ✅ Completed

#### 1. Core Configuration System

- [x] `service_config.yaml` - Comprehensive configuration template
- [x] `service_config_loader.py` - Configuration parser and loader
- [x] `tap_station/service_integration.py` - Integration layer with backward compatibility
- [x] Example configurations in `examples/service_configs/`
- [x] Complete documentation in `docs/SERVICE_CONFIGURATION.md`

#### 2. Backend Integration (web_server.py)

- [x] Import service_integration module
- [x] Initialize ServiceIntegration in **init**
- [x] Replace hardcoded alert thresholds:
  - [x] Queue warning/critical (10/20 → configurable)
  - [x] Wait time warning/critical (45/90 min → configurable)
  - [x] Service inactivity (5/10 min → configurable)
  - [x] Stuck cards threshold (2 hours → configurable)
  - [x] Service variance multiplier (3x → configurable)
  - [x] Capacity utilization (90% → configurable)
- [x] Replace hardcoded capacity values:
  - [x] People per hour (12 → configurable)
  - [x] Queue multiplier (2 → configurable)
  - [x] Default wait estimate (20 min → configurable)
  - [x] Wait time sample size (20 → configurable)
- [x] Use configured alert messages with formatting
- [x] Add `/api/service-config` endpoint for frontend

#### 3. Frontend Helper

- [x] Create `static/js/service-config.js` - JavaScript helper for templates
- [x] Provides functions to access configuration in UI
- [x] Auto-initializes and applies labels on page load

### 🔄 In Progress / Needs Completion

#### 4. HTML Template Updates

The HTML templates need to be updated to use the service configuration dynamically. This involves:

**Required Changes:**

1. Include `service-config.js` in all template files
2. Use `data-label` attributes for configurable text
3. Use `data-service-name` for service name placeholders
4. Load stages dynamically instead of hardcoding

**Templates to Update:**

- [ ] `public.html` - Public queue display
- [ ] `dashboard.html` - Staff dashboard
- [ ] `monitor.html` - Simplified monitor view
- [ ] `control.html` - Control panel
- [ ] `shift.html` - Shift summary
- [ ] Any other templates with hardcoded labels

**Example Update Pattern:**

Before:

```html
<h1>Drug Checking Service</h1>
<div class="metric">
  <div class="value" id="queue-count">0</div>
  <div class="label">people in queue</div>
</div>
```

After:

```html
<script src="{{ url_for('static', filename='js/service-config.js') }}"></script>

<h1 data-service-name>Drug Checking Service</h1>
<div class="metric">
  <div class="value" id="queue-count">0</div>
  <div class="label" data-label="queue_count">people in queue</div>
</div>
```

#### 5. Mobile App Updates

- [ ] Update `mobile_app/index.html` to load stages from `/api/service-config`
- [ ] Dynamically populate stage dropdown instead of hardcoding
- [ ] Use service name from configuration

**Current Code (mobile_app/index.html):**

```html
<select id="stage" required>
  <option value="QUEUE_JOIN">Queue Join</option>
  <option value="EXIT">Exit</option>
</select>
```

**Should Become:**

```html
<select id="stage" required>
  <!-- Populated dynamically from /api/service-config -->
</select>

<script>
  // Load stages from service configuration
  fetch("/api/service-config")
    .then(r => r.json())
    .then(config => {
      const select = document.getElementById("stage")
      config.workflow_stages.forEach(stage => {
        const option = document.createElement("option")
        option.value = stage.id
        option.textContent = stage.label
        select.appendChild(option)
      })
    })
</script>
```

#### 6. Database Schema (Optional Enhancement)

Currently, the database stores stage names as strings. Consider:

- [ ] Add validation to ensure stage names match configured stages
- [ ] Add a stage_labels table for mapping stage IDs to labels
- [ ] Migration script for existing data (if needed)

**Note:** This is optional - the current string-based approach works fine with configuration.

#### 7. Scripts and CLI Tools

Some scripts may reference stages or thresholds directly:

- [ ] `scripts/export_data.py` - Check for stage references
- [ ] `scripts/health_check.py` - May use thresholds
- [ ] `scripts/dev_reset.py` - Check for stage assumptions
- [ ] Any other scripts that assume specific stages

**Pattern:** Scripts should import and use `service_integration` module.

```python
from tap_station.service_integration import get_service_integration

svc = get_service_integration()
first_stage = svc.get_first_stage()  # Instead of hardcoding "QUEUE_JOIN"
last_stage = svc.get_last_stage()    # Instead of hardcoding "EXIT"
```

#### 8. Config.py Stage Normalization

- [x] Review `config.py` stage normalization logic
- [x] Decision: Keep as-is (just normalizes format, doesn't restrict stages)

The current `normalize_stage()` method just ensures consistent formatting (uppercase, handles aliases). This is fine and doesn't conflict with configurable stages.

---

## Testing Checklist

### Backend Testing

- [ ] Test with default configuration (no service_config.yaml)
- [ ] Test with simple_queue.yaml configuration
- [ ] Test with comprehensive_service.yaml configuration
- [ ] Test with multi_location_festival.yaml configuration
- [ ] Verify `/api/service-config` endpoint returns correct data
- [ ] Verify all alert thresholds use configured values
- [ ] Verify capacity calculations use configured values

### Frontend Testing

- [ ] Test public display loads and uses configured labels
- [ ] Test dashboard loads and uses configured service name
- [ ] Test stage labels display correctly in event lists
- [ ] Test refresh interval uses configured value
- [ ] Test conditional display based on configuration (show/hide elements)

### Mobile App Testing

- [ ] Test mobile app loads available stages from API
- [ ] Test mobile app respects configured stage labels
- [ ] Test mobile app works with 2-stage workflow
- [ ] Test mobile app works with 5+ stage workflow

### End-to-End Testing

- [ ] Deploy with simple configuration
- [ ] Scan cards through entire workflow
- [ ] Verify all stages work correctly
- [ ] Change configuration and restart
- [ ] Verify new configuration takes effect
- [ ] Verify backward compatibility with no configuration

---

## Implementation Priority

### High Priority (Should be done soon)

1. **HTML Template Updates** - Most user-facing
2. **Mobile App Updates** - Critical for mobile deployments
3. **Testing** - Ensure everything works

### Medium Priority (Can be done incrementally)

1. **Script Updates** - Less critical, can fall back to defaults
2. **Database Enhancements** - Optional improvements

### Low Priority (Nice to have)

1. **Additional UI enhancements** - Polish and refinements

---

## How to Complete Integration

### Step 1: Update HTML Templates

For each template file:

1. Add script tag at the beginning:

```html
<script src="{{ url_for('static', filename='js/service-config.js') }}"></script>
```

1. Add `data-service-name` to service name elements:

```html
<h1 data-service-name>Drug Checking Service</h1>
```

1. Add `data-label` to configurable label elements:

```html
<span data-label="queue_count">people in queue</span>
<span data-label="wait_time">estimated wait</span>
<span data-label="served_today">served today</span>
```

1. Test the page - labels should update automatically

### Step 2: Update Mobile App

1. Add fetch to load configuration on page load
2. Dynamically populate stage dropdown
3. Store configuration for use throughout app

### Step 3: Test Thoroughly

1. Test with each example configuration
2. Verify all UI elements update correctly
3. Test workflow with different stage configurations

### Step 4: Update Scripts (as needed)

1. Import service_integration in scripts
2. Use helper functions instead of hardcoded values
3. Add error handling for missing configuration

---

## Backward Compatibility

**IMPORTANT:** All changes maintain backward compatibility:

- System works without `service_config.yaml` (uses defaults)
- Falls back gracefully if configuration unavailable
- Existing deployments continue to work unchanged
- No database schema changes required

---

## Future Enhancements

Consider these for future versions:

1. **Configuration UI** - Web interface to edit service_config.yaml
2. **Multiple Profiles** - Switch between configurations without restart
3. **Real-time Config Reload** - Update configuration without restart
4. **Configuration Validation** - Web UI to validate config before saving
5. **Workflow Builder** - Visual editor for workflow stages
6. **Multi-language Support** - Full i18n with language selection
7. **Custom Fields** - User-defined data fields per stage
8. **Advanced Alerts** - Conditional alerts based on complex rules

---

## Questions & Troubleshooting

### Q: Do I need to update every HTML file?

A: Yes, for full configurability. But you can do it incrementally - start with public.html and dashboard.html (most used).

### Q: What if I don't include service-config.js?

A: Templates will still work, but will show hardcoded default labels instead of configured ones.

### Q: Can I mix configured and hardcoded labels?

A: Yes! Only elements with `data-label` attributes will be updated. Others keep their hardcoded text.

### Q: How do I test my changes?

A:

1. Copy an example config: `cp examples/service_configs/simple_queue.yaml service_config.yaml`
2. Restart the service
3. Check browser console for "Service configuration loaded: [name]"
4. Verify labels match your configuration

### Q: What if JavaScript is disabled?

A: Fallback content will be shown (the hardcoded text). System still functions, just without dynamic labels.

---

## Getting Help

- Review `docs/SERVICE_CONFIGURATION.md` for configuration details
- Check `examples/service_configs/README.md` for example patterns
- Look at `static/js/service-config.js` for available helper functions
- Test with browser DevTools console to debug issues

---

## Contributing

If you complete integration for a component:

1. Update this document (mark items as completed)
2. Add tests for the integration
3. Document any issues or learnings
4. Submit a pull request

---

## Summary

**What's Done:**

- ✅ Core configuration system
- ✅ Backend integration (all thresholds, capacity, alerts)
- ✅ API endpoint for frontend
- ✅ JavaScript helper for templates

**What's Next:**

- 🔄 Update HTML templates to use service-config.js
- 🔄 Update mobile app to load stages dynamically
- 🔄 Test with different configurations
- 🔄 Update scripts as needed

**Estimated Effort:**

- Template updates: 1-2 hours (mostly find-and-replace)
- Mobile app: 30 minutes
- Testing: 1 hour
- Script updates: 30 minutes per script (as needed)

Total: 3-4 hours for full integration
