# Substance Return Confirmation Guide

**Version:** 2.3  
**Date:** January 18, 2026  
**Feature:** Substance custody and return tracking

---

## Overview

The **Substance Return Confirmation** system adds a critical accountability layer to drug checking services. It tracks when participants' substances are received and, most importantly, **confirmed as returned** to the participant.

This addresses a critical need in harm reduction services: **ensuring substances are never left behind**.

---

## Why This Matters

### The Problem

In typical drug checking services:

1. Participant gives substance to staff for testing
2. Staff performs analysis
3. Staff discusses results
4. Participant should get substance back
5. **BUT** - Sometimes substances get left behind because:
   - Staff forget to hand back
   - Participant forgets to pick up
   - Communication breakdown
   - Rush during busy periods
   - No formal handoff process

### The Impact

**For Participants:**
- Lost trust in service
- Loss of substances (financial/emotional impact)
- Won't return or recommend service
- Perceived lack of professionalism

**For Service:**
- Incident reports and complaints
- Legal/insurance issues
- Damaged reputation
- Staff disputes about responsibility
- No audit trail

**For Harm Reduction:**
- Reduced service utilization
- Undermines community trust
- Barriers to reaching at-risk populations

### The Solution

A **formal confirmation system** that:
- ✅ Creates accountability for staff
- ✅ Provides audit trail
- ✅ Alerts when substances not returned
- ✅ Builds participant trust
- ✅ Prevents incidents
- ✅ Empowers participants with autonomy

---

## How It Works

### 4-Stage Workflow with Confirmation

```
1. QUEUE_JOIN           Participant enters with substance
         ↓
2. SERVICE_START        Staff receives substance, begins testing
         ↓
3. SUBSTANCE_RETURNED   ← NEW! Staff confirms handback
         ↓
4. EXIT                 Participant leaves with substance
```

### The Critical Moment

**SUBSTANCE_RETURNED stage:**
- Staff physically hands substance back to participant
- **Staff taps participant's NFC card** to confirm handback
- System records: who, when, which substance
- Creates timestamped proof of return
- Participant sees visual/audio confirmation

---

## Setup Instructions

### Physical Station Layout

**Option A: Dedicated Return Station (Recommended)**

```
[Entry]        [Testing Area]      [Return Station]     [Exit]
Station 1  →   Station 2       →   Station 3        →  Station 4
QUEUE_JOIN     SERVICE_START       SUBSTANCE_RETURNED   EXIT
```

**Best for:** High-volume services, clear separation of duties

**Option B: Combined Service/Return Station**

```
[Entry]        [Service Area]              [Exit]
Station 1  →   Station 2 (dual-purpose)  → Station 3
QUEUE_JOIN     SERVICE_START +             EXIT
               SUBSTANCE_RETURNED
```

**Best for:** Smaller services, single staff member handling full interaction

**Option C: Mobile Return Confirmation**

```
[Entry]        [Service Area]      [Exit]
Station 1  →   Phone (mobile)  →  Station 2
QUEUE_JOIN     SERVICE_START +     EXIT
               SUBSTANCE_RETURNED
               (staff carries phone)
```

**Best for:** Budget-conscious, flexible services

---

## Configuration

### Enable in `config.yaml`

**Station 3 (Dedicated Return Station):**

```yaml
station:
  device_id: "station3"
  stage: "SUBSTANCE_RETURNED"
  session_id: "festival-2026-summer"
```

### Enable in `service_config.yaml`

Add the stage to your workflow:

```yaml
workflow:
  stages:
    - id: "QUEUE_JOIN"
      label: "Queue"
      order: 1
      required: true

    - id: "SERVICE_START"
      label: "Service Started"
      order: 2
      required: true

    - id: "SUBSTANCE_RETURNED"
      label: "Substance Returned"
      description: "Confirmed handback to participant"
      order: 3
      required: true  # Make this required!
      visible_to_public: true
      duration_estimate: 1
      icon: "🤝"

    - id: "EXIT"
      label: "Complete"
      order: 4
      required: true
```

### Configure Alerts

Add alerts for unreturned substances:

```yaml
alerts:
  unreturned_substances:
    warning_minutes: 15   # Alert after 15 min
    critical_minutes: 30  # Critical after 30 min

  messages:
    unreturned_substance_warning: "⚠️ Substance not returned: Token {token} ({minutes} min)"
    unreturned_substance_critical: "🚨 URGENT: Substance unreturned for {minutes} min - Token {token}"
```

---

## Staff Workflow

### For Staff at Service Area

**When beginning service:**

1. Participant hands you their card AND substance
2. **Tap card on SERVICE_START station**
3. Safely store substance (labeled/tracked)
4. Perform testing/analysis
5. Discuss results with participant

**When returning substance:**

6. Retrieve participant's substance
7. Physically hand substance back to participant
8. **Tap card on SUBSTANCE_RETURNED station** ← CRITICAL
9. Direct participant to exit station

### Training Points

**Train ALL staff on:**

- "Return confirmation is NOT optional"
- "Tap the card WHEN you hand back the substance, not before, not after"
- "This protects you AND the participant"
- "Takes 2 seconds, prevents incidents"
- "If you can't find substance, escalate immediately"

**Make it a habit:**

- "Hand back + Tap = Complete"
- Physical handoff = Card tap
- No tap = No proof of return

---

## Dashboard Features

### New Metrics

When SUBSTANCE_RETURNED stage is enabled:

**Status Indicators:**
- **Awaiting Return:** Participants who completed service but haven't gotten substance back
- **Return Time:** Average time between service completion and return
- **Return Rate:** % of participants who got substances back

**Alerts Section:**
- 🟡 **Warning:** Substance unreturned for 15+ minutes
- 🔴 **Critical:** Substance unreturned for 30+ minutes
- Shows token ID, time elapsed, staff member

**Shift Summary:**
- Total substances received today
- Total substances returned today
- Currently awaiting return: [number]
- Longest unreturned time: [minutes]

### Example Dashboard View

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Current Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  In Queue: 5 people
  Being Served: 3 people
  Awaiting Return: 2 people ⚠️
  
  Alerts:
  🟡 Token #042 - Substance unreturned (18 min)
  🔴 Token #067 - Substance unreturned (35 min) URGENT
  
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Today's Stats
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Substances Received: 87
  Substances Returned: 85
  Return Rate: 97.7%
  
  Avg Return Time: 2.3 min ✓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Operational Benefits

### 1. Incident Prevention

**Before substance return tracking:**
- "I think I gave it back?"
- No proof of return
- Participant vs staff disputes
- Lost substances go unreported

**After substance return tracking:**
- Timestamped proof of handback
- Clear accountability chain
- Disputes resolved with data
- Proactive alerts prevent losses

### 2. Trust Building

**Participant perspective:**
- "I saw them tap my card when they gave it back"
- "The system tracks my substance"
- "I trust this service"
- "I'll recommend this to friends"

**Service perspective:**
- "We can prove we returned it"
- "Our return rate is 99.2%"
- "Zero substance loss incidents this year"
- "Participants trust us"

### 3. Autonomy & Empowerment

**Participants can:**
- Check status online: "Has my substance been returned?"
- See timestamps: "Service started at 14:30, returned at 14:38"
- Have proof for their own records
- Feel in control of their substances

### 4. Operational Intelligence

**Service coordinators can:**
- Identify bottlenecks: "Return taking too long?"
- Monitor staff performance: "Which staff forget returns?"
- Track trends: "Return time increases during peak hours"
- Prevent issues: "Alert triggered, go check on Token #042"

### 5. Legal & Insurance

**Documentation provides:**
- Audit trail for liability protection
- Proof of duty of care
- Evidence for insurance claims
- Compliance documentation
- Incident investigation data

---

## Best Practices

### DO ✓

✅ Make SUBSTANCE_RETURNED a **required** stage  
✅ Train ALL staff thoroughly  
✅ Monitor alerts actively during shifts  
✅ Review unreturned substances at shift handoff  
✅ Document any incidents where return delayed  
✅ Place return station in convenient location  
✅ Test workflow before event  
✅ Include in pre-event checklist

### DON'T ✗

❌ Don't allow staff to skip return confirmation  
❌ Don't tap card before physically handing back  
❌ Don't ignore "unreturned substance" alerts  
❌ Don't use same station for service + return (if possible)  
❌ Don't assume participants will remember to pick up  
❌ Don't dismiss importance during training  
❌ Don't forget to check for unreturned substances at event end

---

## End-of-Event Protocol

### Before Closing Service

**Critical checklist:**

1. **Check dashboard for unreturned substances**
   - Any tokens in "awaiting return" status?
   - Review each one

2. **Physical inventory check**
   - Are any substances still in storage?
   - Match against system records

3. **Attempt contact**
   - If substance unreturned, try to locate participant
   - Check if they're still on-site

4. **Document outcomes**
   - Substances returned: Mark in system
   - Substances unclaimed: Document in incident report
   - Follow service policy for unclaimed substances

5. **Data export**
   - Export day's data including return confirmations
   - Archive for audit purposes

---

## Troubleshooting

### Dashboard not showing return metrics

**Check:**

1. Is SUBSTANCE_RETURNED stage configured?
   ```bash
   grep "SUBSTANCE_RETURNED" service_config.yaml
   ```

2. Are any return events logged?
   ```bash
   # Use database path from your config.yaml (typically data/events.db)
   sqlite3 data/events.db "SELECT COUNT(*) FROM events WHERE stage='SUBSTANCE_RETURNED'"
   ```

3. Is station configured correctly?
   ```yaml
   stage: "SUBSTANCE_RETURNED"  # Must be exact
   ```

### Alerts not triggering

**Possible causes:**

- Alert thresholds not configured in `service_config.yaml`
- Time thresholds too high (try lower values for testing)
- System clock issues (check time sync)

**Fix:**

```yaml
alerts:
  unreturned_substances:
    warning_minutes: 5  # Lower for testing
    critical_minutes: 10
```

### Staff forgetting to tap

**Solutions:**

- Add visual reminder at return area: "REMEMBER TO TAP CARD!"
- Include in staff checklist
- Peer reminders: "Did you tap?"
- Review return rate at shift handoff
- Positive reinforcement: "Great job, 100% return rate today!"

### Participant left without substance

**Emergency protocol:**

1. Check last known location (dashboard)
2. Announce over radio/comms
3. Check if they're still in venue
4. If found: Complete return + tap card
5. If not found: Document incident, secure substance
6. Follow service policy for unclaimed items

---

## Real-World Scenarios

### Scenario 1: Busy Rush

**Situation:**
- 15 people in queue
- Staff rushing
- Risk of forgetting returns

**Solution:**
- Return confirmation FORCES the step
- Dashboard shows who's awaiting return
- Alerts prevent anyone being forgotten
- Data shows if rush causes longer return times

### Scenario 2: Staff Dispute

**Situation:**
- Participant claims substance not returned
- Staff claims it was returned
- No proof either way

**Solution:**
- Check system: "SUBSTANCE_RETURNED event logged at 14:38"
- Timestamped proof
- Staff protected from false claims
- Participant can be shown the record

### Scenario 3: End of Night

**Situation:**
- 2am, event ending
- 3 substances still in storage
- Whose are they?

**Solution:**
- Dashboard shows: "Tokens #045, #067, #089 awaiting return"
- Can attempt to locate participants
- Clear record of unreturned substances
- Proper documentation for incident reports

---

## Success Metrics

### Track These KPIs

**Return Rate:**
- Goal: 100% (or as close as possible)
- Calculate: (Substances returned / Substances received) × 100

**Average Return Time:**
- Goal: < 5 minutes from service completion
- Calculate: Average time between SERVICE_START and SUBSTANCE_RETURNED

**Alert Response Time:**
- Goal: < 5 minutes to respond to alert
- Track: Time from alert to resolution

**Incident Rate:**
- Goal: 0 unreturned substances at event end
- Track: Substances left unclaimed

### Example Report

```
Festival: Summer Lights 2026
Date: July 15-17, 2026

Substance Return Performance:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Substances Received: 342
Total Substances Returned: 341
Return Rate: 99.7% ✓

Avg Return Time: 2.8 minutes ✓
Longest Return Time: 28 minutes

Alerts Triggered: 8
Avg Response Time: 3.2 minutes ✓

Unreturned at Event End: 1
Reason: Participant departed early
Action: Substance secured per policy

Incidents: 0 ✓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Recommendation: Excellent performance.
System prevented potential issues.
```

---

## Next Steps

### Implementation Plan

**Week 1: Planning**
- Review this guide with team
- Decide on station layout
- Customize service_config.yaml
- Plan training sessions

**Week 2: Setup**
- Configure stations
- Test workflow
- Train staff
- Create visual aids

**Week 3: Testing**
- Run mock scenarios
- Validate alerts
- Verify dashboard
- Refine procedures

**Day Of: Deployment**
- Pre-event checklist
- Station verification
- Staff refresher
- Monitor throughout event

**Post-Event: Review**
- Export data
- Calculate metrics
- Team debrief
- Document improvements

---

## Support & Resources

**Documentation:**
- [3-Stage Tracking Guide](3_STAGE_TRACKING.md) - Understanding stages
- [Operations Guide](OPERATIONS.md) - Day-of-event workflow
- [Service Configuration](SERVICE_CONFIGURATION.md) - Customization

**Configuration Examples:**
- `examples/service_configs/substance_return_tracking.yaml`
- `examples/service_configs/comprehensive_service.yaml`

**Questions?**
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Open GitHub issue
- Contact development team

---

**Protect your participants. Protect your staff. Build trust. 🤝**
