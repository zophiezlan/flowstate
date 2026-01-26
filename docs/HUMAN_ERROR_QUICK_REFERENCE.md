# Quick Reference: Handling Human Errors

**For festival staff operating FlowState stations**

---

## Common Mistakes & How System Adapts

### ❌ Forgot to Tap Exit

**What happens:**

- System flags card as "stuck" after 30+ minutes
- Dashboard shows warning with token ID
- You can add missed tap manually

**How to fix:**

1. Check dashboard for stuck cards
2. Confirm participant left
3. Add manual EXIT event with estimated time
4. Document reason

---

### ❌ Tapped at Wrong Station

**What happens:**

- If within 5 minutes: System allows correction
- Participant can tap again at correct station
- System treats second tap as correction, not duplicate

**How to fix:**

- Just tap again at correct station within 5 min
- Beyond 5 min: Need manual correction

---

### ❌ Tapped Out of Order (e.g., EXIT before QUEUE_JOIN)

**What happens:**

- System logs event anyway
- Double-beep warns something wrong
- Warning appears in dashboard

**How to fix:**

- Check dashboard for details
- Add missing events manually if needed
- System still has complete data

---

### ❌ Lost Card Mid-Service

**What happens:**

- Journey incomplete in database
- Participant can't tap exit

**How to fix:**

1. Note approximate entry/service times
2. Add manual events for complete journey
3. Document: "Card lost, manually completed based on service log"

---

### ❌ NFC Reader Malfunction

**What happens:**

- No taps recorded during downtime
- Multiple incomplete journeys

**How to fix:**

1. Note time range of malfunction
2. Use paper backup log during downtime
3. Manually add events after fix
4. Document: "Added events from paper backup during reader failure 2-2:15pm"

---

## System Beeps

| Beeps                        | Meaning                      | Action          |
| ---------------------------- | ---------------------------- | --------------- |
| 🔊 **BEEP** (1 short)        | ✅ Success                   | Continue        |
| 🔊🔊 **BEEP-BEEP** (2 short) | ⚠️ Duplicate or out-of-order | Check dashboard |
| 🔊━━━ **BEEEEEP** (1 long)   | ❌ Error                     | Try again       |

---

## Manual Corrections

### Add Missed Tap

**When:** Forgot to tap, reader malfunction, card lost

**Steps:**

1. Go to Control Panel
2. Click "Add Manual Event"
3. Enter:
   - Token ID
   - Stage (QUEUE_JOIN, SERVICE_START, EXIT)
   - Estimated time
   - Your name/ID
   - Reason (be specific!)
4. Submit

**Example Reason:**

> "Participant confirmed left at ~2:45pm, forgot to tap exit. Card reader working normally."

---

### Remove Wrong Tap

**When:** Wrong card used, accidental tap, test during live event

**Steps:**

1. Go to Control Panel
2. Find event in recent events
3. Click "Remove Event"
4. Enter:
   - Your name/ID
   - Reason (be specific!)
5. Confirm

**Example Reason:**

> "Participant grabbed wrong card from table, used neighbor's card by mistake. Correct card tapped 2 minutes later."

---

## Dashboard Anomaly Warnings

### High-Severity (Red)

- **Stuck >120 min:** Participant forgot exit, or data error
- **Multiple anomalies:** Pattern suggests systemic issue

**Action:** Review immediately, add corrections as needed

### Medium-Severity (Yellow)

- **Stuck 30-120 min:** May have forgotten exit
- **Long service times:** Genuine or data issue?

**Action:** Check when time permits

### Low-Severity (Blue)

- **Rapid duplicate taps:** Participant testing
- **Slightly long service:** Within normal range

**Action:** Monitor but usually okay

---

## 5-Minute Grace Period

**What it is:** Window to self-correct mistakes

**Example:**

```
2:00:00 PM - Tap at SERVICE_START (wrong!)
2:00:30 PM - Realize mistake
2:00:45 PM - Tap at QUEUE_JOIN (correct!)
           ✅ System accepts as correction
```

**After 5 minutes:**

```
2:00:00 PM - Tap at QUEUE_JOIN
2:06:00 PM - Try to tap again
           ❌ System rejects as duplicate
           Need manual correction
```

---

## Best Practices

✅ **Do:**

- Check dashboard for anomalies every 15-30 min
- Add manual corrections immediately when noticed
- Always document reason for corrections
- Keep paper backup during technical issues

❌ **Don't:**

- Ignore stuck card warnings
- Make corrections without documenting reason
- Over-rely on manual corrections (fix root cause)
- Delete events without understanding why they're wrong

---

## API Endpoints (For Developers)

```bash
# Get anomalies
GET /api/control/anomalies

# Add manual event
POST /api/control/manual-event
{
  "token_id": "042",
  "stage": "EXIT",
  "timestamp": "2025-01-24T17:30:00Z",
  "operator_id": "staff_sarah",
  "reason": "Participant confirmed left, forgot to tap"
}

# Remove event
POST /api/control/remove-event
{
  "event_id": 1234,
  "operator_id": "staff_mike",
  "reason": "Wrong card tapped"
}
```

---

## Troubleshooting

**"Too many anomalies"**
→ Staff training issue or reader positioning problem

**"Can't add manual event"**
→ Check timestamp format (YYYY-MM-DDTHH:MM:SSZ)

**"Sequence validation too strict"**
→ Your workflow may not match default - check with tech lead

---

## Full Documentation

- 📖 [Complete Guide](HUMAN_ERROR_HANDLING.md)
- 📊 [Summary](HUMAN_ERROR_ADAPTATION_SUMMARY.md)
- 📋 [Operations Guide](OPERATIONS.md)

---

**Remember:** The system is designed to adapt to human errors. Your job is to detect, correct, and document - the system handles the rest!
