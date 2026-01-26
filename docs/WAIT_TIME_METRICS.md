# Understanding Wait Time Metrics

## Overview

The NFC Tap Logger tracks two distinct time periods during a participant's journey through your service:

1. **Queue Wait Time** - Time spent waiting to be served
2. **Service Time** - Time spent actively being served

This distinction is important because these metrics serve different purposes and vary differently across events.

## The Two Time Periods

### 1. Queue Wait Time (QUEUE_JOIN → SERVICE_START)

**What it measures:** Time a participant spends waiting in the queue before a staff member begins serving them.

**Characteristics:**

- **Highly variable**: Can range from 0 minutes to 3+ hours
- **Event-dependent**: Changes based on demand, staffing, and time of day
- **Dynamic**: Fluctuates throughout the event (peak hours vs. quiet periods)
- **Unpredictable**: Hard to estimate in advance

**Used for:**

- Telling new arrivals how long they'll wait
- Identifying queue bottlenecks
- Making staffing decisions
- Real-time operational adjustments

**Example values:**

- Quiet period: 5-10 minutes
- Moderate demand: 20-45 minutes
- Peak demand: 60-180 minutes

### 2. Service Time (SERVICE_START → EXIT)

**What it measures:** Time from when a staff member starts serving a participant until they complete and exit.

**Characteristics:**

- **Relatively consistent**: Usually stays within a narrow range
- **Service-dependent**: Varies by service type but stable within a service
- **Predictable**: Can be estimated based on past events
- **Staff-controlled**: Depends on process efficiency, not demand

**Used for:**

- Capacity planning (how many people can you serve per hour?)
- Process optimization
- Staffing calculations
- Comparing service efficiency across events

**Example values:**

- Quick drug check: 3-8 minutes
- Standard consultation: 10-15 minutes
- Comprehensive testing: 15-25 minutes

### 3. Total Time (QUEUE_JOIN → EXIT)

**What it measures:** Complete journey from arrival to departure.

**Formula:** Queue Wait Time + Service Time

**Used for:**

- Overall participant experience assessment
- Event retrospectives
- Funder reports showing complete service time

## How the System Tracks These Metrics

### 3-Stage Tracking

To separate queue wait from service time, use the 3-stage workflow:

```yaml
# service_config.yaml
workflow:
  stages:
    - id: "QUEUE_JOIN"
      label: "Joined Queue"
      order: 1
      
    - id: "SERVICE_START"
      label: "Service Started"
      order: 2
      
    - id: "EXIT"
      label: "Service Complete"
      order: 3
```

**Stage purposes:**

- **QUEUE_JOIN**: Participant taps when entering the queue
- **SERVICE_START**: Staff taps participant's card when beginning service
- **EXIT**: Participant taps when leaving

### 2-Stage Tracking (Simple Mode)

If you only use QUEUE_JOIN and EXIT (no SERVICE_START):

- The system tracks total time only
- Queue wait and service time cannot be separated
- Less data granularity but simpler operations

## Dashboard Display

The dashboard shows different metrics depending on your setup:

### With 3-Stage Data Available

```
Queue Metrics:
  Average Queue Wait: 32 minutes
  Average Service Time: 12 minutes
  Average Total Time: 44 minutes
  
Current Status:
  Estimated Wait for New Arrivals: 45 minutes
  Longest Current Wait: 58 minutes (Token 042)
  People in Queue: 15
  People Being Served: 3
```

### With 2-Stage Data Only

```
Queue Metrics:
  Average Total Time: 44 minutes
  
Current Status:
  Estimated Wait for New Arrivals: 45 minutes
  Longest Current Wait: 58 minutes
  People in Queue: 15
```

## Configuration

### Service Capacity Configuration

```yaml
# service_config.yaml
capacity:
  # Throughput capacity (people per hour)
  people_per_hour: 12

  # Average service time (SERVICE_START → EXIT)
  # NOT the total time including queue wait
  avg_service_minutes: 5

  # Default queue wait estimate when no data available
  default_wait_estimate: 20

  # Queue multiplier: how much each person ahead adds to wait
  queue_multiplier: 2
```

### Wait Time Estimation

The system estimates wait time for new arrivals using:

```python
estimated_wait = avg_recent_queue_wait + (people_in_queue * queue_multiplier)
```

**Example:**

- Recent average queue wait: 30 minutes
- People currently in queue: 5
- Queue multiplier: 2

Estimated wait = 30 + (5 × 2) = **40 minutes**

## Operational Use Cases

### Scenario 1: Quiet Period

```
Current Status:
  Queue Wait: 5 minutes
  Service Time: 8 minutes
  People in Queue: 2
  Estimated Wait: 9 minutes
```

**Action:** Normal operations, no changes needed.

### Scenario 2: Building Queue

```
Current Status:
  Queue Wait: 25 minutes
  Service Time: 8 minutes
  People in Queue: 12
  Estimated Wait: 49 minutes
```

**Action:** Monitor closely. Consider calling backup staff if wait continues to grow.

### Scenario 3: Critical Queue

```
Current Status:
  Queue Wait: 65 minutes
  Service Time: 8 minutes
  People in Queue: 24
  Estimated Wait: 113 minutes
```

**Action:** 🚨 Add resources immediately. Prioritize longest waiting participants.

### Scenario 4: Service Bottleneck

```
Current Status:
  Queue Wait: 10 minutes
  Service Time: 45 minutes (usually 12)
  People in Queue: 8
  Estimated Wait: 26 minutes
```

**Action:** Service time is unusually high. Check if:

- Complex cases requiring extra time
- New staff member learning process
- Technical issues (equipment malfunction)

## Why This Matters

### For Operations

**Queue Wait Time helps you:**

- Set accurate expectations for participants
- Make real-time staffing decisions
- Identify when demand exceeds capacity
- Adjust strategy during the event

**Service Time helps you:**

- Plan staffing levels before the event
- Calculate theoretical capacity
- Optimize your service process
- Compare efficiency across events

### For Reporting

**To funders/stakeholders:**

- Queue wait shows demand and accessibility
- Service time shows operational efficiency
- Total time shows complete participant experience

**Example report:**
> "During peak hours (8-10pm), participants experienced an average 45-minute queue wait before being seen. Once service began, the average consultation time was 12 minutes. Total time from arrival to departure averaged 57 minutes. We served 186 participants over 8 hours (23 per hour)."

## Common Misconceptions

### ❌ Misconception: "Average wait time is the service time"

**Reality:** Wait time includes both queue wait AND service time. When people ask "how long is the wait?", they mean queue wait time (how long until they're served), not service time.

### ❌ Misconception: "Service time varies as much as queue wait"

**Reality:** Service time is usually consistent (±20% variation). Queue wait is highly variable (can be 10× different between quiet and peak).

### ❌ Misconception: "Total time = wait time"

**Reality:** Total time = queue wait + service time. The "wait" ends when service starts, even though the participant hasn't exited yet.

## Best Practices

### 1. Use 3-Stage Tracking for Better Data

Enable SERVICE_START stage:

```yaml
workflow:
  stages:
    - {id: "QUEUE_JOIN", order: 1}
    - {id: "SERVICE_START", order: 2}
    - {id: "EXIT", order: 3}
```

### 2. Train Staff on SERVICE_START

**When to tap SERVICE_START:**

- ✅ When you begin talking to the participant
- ✅ When you accept their substance for testing
- ✅ When they sit down for consultation

**When NOT to tap:**

- ❌ When you're still helping someone else
- ❌ When setting up equipment between participants
- ❌ During your break

### 3. Communicate Queue Wait, Not Total Time

**To participants:**

- ✅ "Current wait time is about 30 minutes"
- ❌ "You'll be here for 40 minutes total"

Why? People care about how long until they're helped, not how long the service takes once it starts.

### 4. Set Alert Thresholds Based on Queue Wait

```yaml
# service_config.yaml
alerts:
  wait_time:
    warning_minutes: 45   # Queue wait approaching high
    critical_minutes: 90  # Queue wait critically high
```

### 5. Review Both Metrics After Events

**Questions to ask:**

- How did queue wait vary throughout the event?
- Was service time consistent or variable?
- What was our peak capacity utilization?
- Did we have enough staff during peak queue times?

## Troubleshooting

### Problem: Service time seems too long

**Check:**

- Are staff members tapping SERVICE_START at the right time?
- Are there technical issues slowing the process?
- Is training needed for new staff?

### Problem: Queue wait estimates are inaccurate

**Check:**

- Is the queue multiplier appropriate? (adjust in config)
- Are there enough recent completions to calculate averages?
- Is the service capacity setting correct?

### Problem: Dashboard shows 0 for queue wait and service time

**Cause:** No SERVICE_START events in recent completions.

**Solution:** Either:

1. Start using SERVICE_START stage (recommended)
2. Accept that only total time is available (2-stage mode)

## Example Event Analysis

### Event: Summer Festival Drug Checking

**Configuration:**

```yaml
capacity:
  people_per_hour: 15
  avg_service_minutes: 8
  queue_multiplier: 2
```

**Results:**

| Time Period | Queue Wait | Service Time | Total Time | People Served |
|-------------|-----------|--------------|------------|---------------|
| 12pm-2pm    | 8 min     | 7 min        | 15 min     | 28            |
| 2pm-4pm     | 15 min    | 8 min        | 23 min     | 31            |
| 4pm-6pm     | 28 min    | 9 min        | 37 min     | 29            |
| 6pm-8pm     | 52 min    | 8 min        | 60 min     | 26            |
| 8pm-10pm    | 78 min    | 8 min        | 86 min     | 22            |
| 10pm-11pm   | 35 min    | 9 min        | 44 min     | 18            |

**Insights:**

- Service time remained consistent (7-9 min) ✅
- Queue wait varied dramatically (8-78 min)
- Peak demand 6-10pm exceeded capacity
- Service efficiency maintained despite high demand
- Consider 2 additional staff during 6-10pm peak

## See Also

- [3_STAGE_TRACKING.md](3_STAGE_TRACKING.md) - How to configure 3-stage tracking
- [SERVICE_CONFIGURATION.md](SERVICE_CONFIGURATION.md) - Configuring capacity and thresholds
- [OPERATIONS.md](OPERATIONS.md) - Day-of-event operations guide
