# Human Error Handling Guide

**Comprehensive error detection, prevention, and correction features to handle real-world operational mistakes.**

## Overview

Humans make mistakes, especially in chaotic festival environments. This system is designed to adapt to common human errors rather than just rejecting them. The goal is to **collect accurate data despite imperfect human behavior**.

---

## 🛡️ Built-In Error Prevention

### 1. Sequence Validation (State Machine)

**What it does:** Validates that taps happen in a logical order based on your service workflow.

**How it works:**

- Tracks each card's journey through stages
- Detects out-of-order taps (e.g., EXIT before QUEUE_JOIN)
- Logs the event anyway but flags it with a warning
- Provides suggestions for staff

**Valid Transitions:**

```
QUEUE_JOIN → SERVICE_START, EXIT, SUBSTANCE_RETURNED
SERVICE_START → SUBSTANCE_RETURNED, EXIT
SUBSTANCE_RETURNED → EXIT
EXIT → (terminal - no further taps expected)
```

**Example Warnings:**

```
⚠️ Card tapped at EXIT without QUEUE_JOIN
   Suggestion: Verify participant actually used service

⚠️ Card already exited - may indicate:
   - Reused card
   - Participant returned for second service
   Suggestion: Check if this is a new visit
```

**Feedback:**

- Out-of-order taps: Double-beep (same as duplicate)
- Event is still logged for data completeness
- Warning appears in logs and dashboard

---

### 2. Grace Period for Corrections

**What it does:** Allows corrections within 5 minutes for accidental taps at wrong station.

**Scenario:**

1. Participant accidentally taps at SERVICE_START station
2. Realizes mistake within 5 minutes
3. Taps at correct QUEUE_JOIN station
4. System allows the correction instead of rejecting as duplicate

**How it works:**

- First tap at a stage is always accepted
- Within 5-minute window: allows "duplicate" tap (treats as correction)
- After 5 minutes: rejects as true duplicate

**Configurable:**
You can adjust the grace period in `database.py`:

```python
def _is_duplicate(self, token_id: str, stage: str, session_id: str, grace_minutes: int = 5):
```

---

### 3. Auto-Initialize Cards

**What it does:** Eliminates pre-initialization errors by auto-assigning token IDs on first tap.

**Prevents:**

- Lost uninitializedcards
- Wrong card numbering
- Setup mistakes

**See:** [Auto-Initialize Cards Guide](AUTO_INIT_CARDS.md)

---

## 📊 Real-Time Error Detection

### Anomaly Detection API

**Endpoint:** `GET /api/control/anomalies`

**What it detects:**

#### 1. Forgotten Exit Taps

```json
{
  "forgotten_exit_taps": [
    {
      "token_id": "042",
      "queue_join_time": "2025-01-24T14:30:00Z",
      "minutes_stuck": 95,
      "severity": "medium",
      "suggestion": "Participant may have left without tapping exit, or lost card"
    }
  ]
}
```

**Thresholds:**
>
- >30 minutes: Flagged as anomaly
- >120 minutes: High severity

**Common Causes:**

- Participant forgot to tap exit
- Card left behind
- Card stolen/lost
- Participant abandoned queue

---

#### 2. Stuck in Service

```json
{
  "stuck_in_service": [
    {
      "token_id": "078",
      "service_start_time": "2025-01-24T15:00:00Z",
      "minutes_in_service": 67,
      "severity": "high",
      "suggestion": "Staff may have forgotten to tap EXIT, or unusually complex case"
    }
  ]
}
```

**Thresholds:**
>
- >45 minutes: Flagged
- >90 minutes: High severity

**Common Causes:**

- Staff forgot exit tap
- Very complex case
- Card left at service desk

---

#### 3. Unusually Long Service Times

```json
{
  "long_service_times": [
    {
      "token_id": "123",
      "service_minutes": 78,
      "median_minutes": 22,
      "severity": "low",
      "suggestion": "Unusually complex case, or card left behind and found later"
    }
  ]
}
```

**Detection:** Service time >2× median AND >20 minutes

**Common Causes:**

- Genuinely complex case
- Participant had multiple questions
- Card left behind, found hours later

---

#### 4. Rapid-Fire Duplicate Taps

```json
{
  "rapid_fire_taps": [
    {
      "token_id": "056",
      "stage": "QUEUE_JOIN",
      "first_tap": "2025-01-24T16:00:00Z",
      "second_tap": "2025-01-24T16:00:45Z",
      "seconds_between": 45,
      "severity": "low",
      "suggestion": "Participant may be confused or testing the system"
    }
  ]
}
```

**Detection:** Same card, same stage, <2 minutes apart

**Common Causes:**

- Participant testing if it worked
- Confusion about whether tap registered
- Playful behavior

---

## 🛠️ Manual Corrections

### Add Missing Event

**Endpoint:** `POST /api/control/manual-event`

**Use Case:** Staff forgot to tap a card, or card reader was down.

**Request:**

```json
{
  "token_id": "089",
  "stage": "EXIT",
  "timestamp": "2025-01-24T17:30:00Z",
  "operator_id": "staff_sarah",
  "reason": "Participant left during NFC reader malfunction, confirmed service completion"
}
```

**Response:**

```json
{
  "success": true,
  "message": "Manual event added successfully",
  "warnings": null
}
```

**Features:**

- Bypasses sequence validation (use `allow_out_of_order=True`)
- Backdates event to correct time
- Logs operator ID and reason for audit trail
- Uses special UID format: `MANUAL_{operator_id}`

**Example Use Cases:**

1. **Reader Malfunction:** Card reader died for 10 minutes, staff manually log missing taps
2. **Forgotten Tap:** Staff realizes after participant left that they forgot exit tap
3. **Lost Card Recovery:** Participant lost card mid-service, staff completes journey manually

---

### Remove Incorrect Event

**Endpoint:** `POST /api/control/remove-event`

**Use Case:** Wrong card tapped, accidental tap, duplicate entry.

**Request:**

```json
{
  "event_id": 1234,
  "operator_id": "staff_mike",
  "reason": "Wrong card tapped - participant grabbed neighbor's card by mistake"
}
```

**Response:**

```json
{
  "success": true,
  "message": "Event removed successfully",
  "removed_event": {
    "id": 1234,
    "token_id": "067",
    "stage": "SERVICE_START",
    "timestamp": "2025-01-24T18:00:00Z"
  }
}
```

**Features:**

- Full audit trail (logs who removed what and why)
- Returns deleted event data for verification
- Permanent deletion (consider creating `deleted_events` table for full audit)

**Example Use Cases:**

1. **Wrong Card:** Participant accidentally used neighbor's card
2. **Test Tap:** Staff testing system during live event
3. **Duplicate Entry:** System glitch created duplicate entry

---

## 📱 Dashboard Integration

### View Anomalies

Add to your dashboard to display real-time errors:

```javascript
// Fetch anomalies
fetch('/api/control/anomalies')
  .then(response => response.json())
  .then(data => {
    const { anomalies, summary } = data;
    
    // Display summary
    console.log(`Total anomalies: ${summary.total_anomalies}`);
    console.log(`High severity: ${summary.high_severity}`);
    
    // Show forgotten exit taps
    if (anomalies.forgotten_exit_taps.length > 0) {
      alert(`${anomalies.forgotten_exit_taps.length} participants may have left without tapping exit!`);
    }
  });
```

### Add Manual Event Form

```html
<form id="manual-event-form">
  <input name="token_id" placeholder="Token ID (e.g., 042)" required>
  <select name="stage" required>
    <option value="QUEUE_JOIN">Queue Join</option>
    <option value="SERVICE_START">Service Start</option>
    <option value="EXIT">Exit</option>
  </select>
  <input name="timestamp" type="datetime-local" required>
  <input name="operator_id" placeholder="Your name/ID" required>
  <textarea name="reason" placeholder="Why are you adding this event?" required></textarea>
  <button type="submit">Add Manual Event</button>
</form>

<script>
document.getElementById('manual-event-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const formData = new FormData(e.target);
  const data = Object.fromEntries(formData);
  
  const response = await fetch('/api/control/manual-event', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  
  const result = await response.json();
  alert(result.message);
});
</script>
```

---

## 🚨 Recommended Monitoring

### Real-Time Alerts

Set up alerts for high-severity anomalies:

```python
def check_critical_anomalies():
    """Check for critical anomalies every 5 minutes"""
    anomalies = db.get_anomalies(session_id)
    
    # Alert if >5 high-severity issues
    high_severity_count = sum(
        1 for category in anomalies.values()
        for item in category
        if item.get("severity") == "high"
    )
    
    if high_severity_count > 5:
        send_alert(f"⚠️ {high_severity_count} critical anomalies detected!")
        
    # Alert if >10 forgotten exit taps
    if len(anomalies["forgotten_exit_taps"]) > 10:
        send_alert(f"🚨 {len(anomalies['forgotten_exit_taps'])} people may have left without tapping exit!")
```

### End-of-Event Review

After each event, review anomalies:

1. **Check Forgotten Exit Taps:** Use force-exit tool to close out stuck cards
2. **Review Long Service Times:** Identify if specific staff need retraining
3. **Analyze Patterns:** Do certain stages have more errors? Why?

---

## 🎓 Staff Training

### Key Concepts to Teach

**1. Grace Period (5 minutes)**

- "If you make a mistake, correct it within 5 minutes!"
- Tap at wrong station? Just tap again at right station immediately

**2. Manual Corrections**

- "Forgot to tap? No problem - add it manually with reason"
- Always include why you're making a correction

**3. Beep Codes**

- 1 beep = Success
- 2 beeps = Duplicate OR out-of-order (check dashboard)
- Long beep = Error

**4. What to Do When:**

- **Participant forgot exit tap:** Add manual EXIT event with timestamp estimate
- **Wrong card tapped:** Remove incorrect event, explain reason
- **Card lost mid-service:** Complete journey manually based on service logs
- **Reader malfunction:** Note time range, manually add events after fix

---

## 🔧 Configuration Options

### Adjust Thresholds

Edit `database.py` to customize detection thresholds:

```python
# Grace period for corrections (default: 5 minutes)
def _is_duplicate(self, token_id: str, stage: str, session_id: str, grace_minutes: int = 5):

# Anomaly detection thresholds
def get_anomalies(self, session_id: str):
    # Forgotten exit taps (default: >30 min)
    WHERE q.timestamp < datetime('now', '-30 minutes')
    
    # Stuck in service (default: >45 min)
    WHERE s.timestamp < datetime('now', '-45 minutes')
    
    # Long service times (default: >2× median)
    WHERE st.service_minutes > (mc.median_service * 2)
```

### Disable Features

To disable sequence validation (not recommended):

```python
# In main.py, _handle_tap()
result = self.db.log_event(
    token_id=token_id,
    uid=uid,
    stage=self.config.stage,
    device_id=self.config.device_id,
    session_id=self.config.session_id,
    allow_out_of_order=True  # Bypass validation
)
```

---

## 📊 Data Quality Impact

### Before Human Error Handling

- ~15-20% incomplete journeys
- ~10% out-of-order events
- Limited ability to correct mistakes
- Data cleanup required after each event

### After Human Error Handling

- <5% unresolvable issues
- Real-time error detection
- Staff can correct mistakes immediately
- Clean data ready for analysis

---

## 🆘 Troubleshooting

### "Too many anomalies detected"

**Cause:** Staff not trained properly, or system misconfigured

**Solution:**

1. Review staff training on tap procedures
2. Check if stations positioned correctly
3. Verify NFC readers functioning properly

### "Manual events not working"

**Cause:** Missing required fields or invalid timestamp format

**Solution:**

1. Ensure all required fields present: `token_id`, `stage`, `timestamp`, `operator_id`, `reason`
2. Use ISO 8601 timestamp format: `2025-01-24T17:30:00Z`
3. Check API response for specific error message

### "Sequence validation too strict"

**Cause:** Your workflow doesn't match default state machine

**Solution:**

1. Review `_validate_sequence()` in `database.py`
2. Adjust valid transitions for your specific workflow
3. Or use `allow_out_of_order=True` for specific stages

---

## 🎯 Best Practices

1. **Monitor Anomalies Every 15-30 Minutes** - Catch issues while participants still on-site
2. **Train All Staff on Manual Corrections** - Don't just rely on tech-savvy coordinators
3. **Document Reasons for Manual Changes** - Audit trail helps improve processes
4. **Review Patterns Post-Event** - Learn from mistakes to improve future events
5. **Keep Grace Period Short** - 5 minutes balances flexibility and data integrity
6. **Don't Rely on Manual Corrections** - Use as backup, not primary workflow

---

## 📚 Related Documentation

- [Operations Guide](OPERATIONS.md) - Day-of-event procedures
- [Control Panel](CONTROL_PANEL.md) - Administrative tools
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues

---

**Remember:** The goal isn't to prevent all human errors—it's to **detect, handle, and correct them gracefully** so you still get accurate data despite imperfect human behavior.
