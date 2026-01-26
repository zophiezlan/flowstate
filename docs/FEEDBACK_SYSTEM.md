# Feedback System - LED and Buzzer Patterns

## Overview

The NFC Tap Logger uses a comprehensive feedback system combining LEDs and buzzer to provide clear visual and audio feedback for all system events. The system is designed to minimize confusion by using **solid states** for system status and **flashing patterns** for events.

## Core Design Philosophy

### Base States (Solid LEDs)

- **Solid Green**: System ready and idle - waiting for card taps
- **Solid Red**: System error state - requires attention
- **Solid Yellow**: Warning or failover mode - system operational but flagged

### Event Feedback (Flashing LEDs)

- Events trigger brief flashing patterns that automatically return to the base state
- Different flash durations and counts distinguish event types
- Combined with distinctive beep patterns for multi-sensory confirmation

## LED Feedback Patterns

### Ready State (Default)

- **LED**: Solid Green
- **Meaning**: System is ready and waiting for card taps
- **Duration**: Continuous until an event occurs

### Success Event

- **LED**: Green flashes 3 times (0.08s on/off)
- **Buzzer**: 1 short beep (0.1s)
- **Meaning**: Card tap logged successfully
- **Returns to**: Solid green (ready state)

### Duplicate Event

- **LED**: Yellow flashes 2 times (0.15s on/off)
- **Buzzer**: 2 quick beeps (0.1s, 0.05s, 0.1s)
- **Meaning**: Card tap ignored due to debounce (duplicate within time window)
- **Returns to**: Solid green (ready state)

### Warning Event

- **LED**: Yellow flashes 2 times (0.15s on/off), then solid yellow briefly (0.5s)
- **Buzzer**: 3 medium beeps (0.15s, 0.1s, 0.15s)
- **Meaning**: Event logged but with warnings (e.g., out-of-order, failover mode)
- **Returns to**: Solid green (ready state)

### Error Event

- **LED**: Red flashes 3 times (0.12s on/off), then solid red for 1 second
- **Buzzer**: 1 long beep (0.3s)
- **Meaning**: Event failed to log or system error occurred
- **Returns to**: Solid green (ready state)

### Startup Sequence

- **LED**: Alternating green/red 3 times (0.1s each)
- **Buzzer**: Ascending pattern (0.05s, 0.05s, 0.05s, 0.05s, 0.1s)
- **Meaning**: System initializing
- **Ends with**: Solid green (ready state)

## Button Feedback

### Button Press

- **Buzzer**: Very short beep (0.05s)
- **Meaning**: Button press detected

### Button Hold Confirmation (Shutdown Triggered)

- **Buzzer**: Confirmation pattern (0.05s, 0.05s, 0.15s)
- **LED**: Red flashes 3 times
- **Meaning**: Shutdown button held long enough - shutdown initiated

## Special Modes

### Failover Mode

- **Event feedback**: Uses warning pattern (yellow flash) instead of success pattern
- **Base state**: Solid green (same as normal operation)
- **Purpose**: Distinguishes failover events from normal single-station events

### Error State (Persistent)

- **LED**: Solid red (continuous)
- **Triggered by**: Critical system errors requiring intervention
- **Cleared by**: System restart or error resolution

## Hardware Configuration

### GPIO Pins (Default)

```yaml
feedback:
  buzzer_enabled: true
  led_enabled: true
  gpio:
    buzzer: 17
    led_green: 27
    led_red: 22
```

### Beep Pattern Customization

```yaml
feedback:
  beep_success: [0.1]                 # Short beep
  beep_duplicate: [0.1, 0.05, 0.1]    # Double beep  
  beep_error: [0.3]                   # Long beep
```

## Visual Reference

### LED State Timeline

```
STARTUP:
Green/Red alternate → Solid Green (ready)

SUCCESSFUL TAP:
Solid Green → Flash Green (3x) → Solid Green

DUPLICATE TAP:
Solid Green → Flash Yellow (2x) → Solid Green

WARNING/OUT-OF-ORDER:
Solid Green → Flash Yellow (2x) → Solid Yellow (0.5s) → Solid Green

ERROR:
Solid Green → Flash Red (3x) → Solid Red (1s) → Solid Green

BUTTON PRESS:
(No visual change, audio only)

BUTTON HOLD:
Solid Green → Flash Red (3x) → (System shuts down)
```

## Benefits of the New System

### 1. **Clear Idle State**

- Solid green LED clearly indicates "ready to scan"
- No confusing flashing when system is idle
- Staff can see at a glance if station is operational

### 2. **Distinctive Event Feedback**

- Different patterns for success/warning/error prevent confusion
- Flash duration and count provide quick visual distinction
- Combined audio/visual feedback for all event types

### 3. **Automatic State Return**

- All events automatically return to ready state
- Prevents "stuck" LEDs that cause confusion
- Thread-safe state management prevents conflicts

### 4. **Button Feedback**

- Immediate audio confirmation of button press
- Distinctive shutdown confirmation pattern
- Prevents accidental shutdowns

### 5. **Failover Visibility**

- Yellow warning pattern during failover mode
- Distinguishes from normal single-station operation
- Maintains operational flow while flagging mode

## Technical Implementation

### Thread-Safe State Management

- LED patterns run in background threads
- Mutex locks prevent race conditions
- Patterns can be interrupted and replaced seamlessly

### Automatic Pattern Completion

- Flashing patterns complete their cycle before returning to base state
- Background thread management ensures clean transitions
- No manual state restoration required

### GPIO Cleanup

- Proper cleanup on shutdown prevents GPIO warnings
- Thread termination with timeouts prevents hangs
- LEDs turned off gracefully

## Troubleshooting

### LEDs Not Lighting

1. Check `led_enabled: true` in config
2. Verify GPIO pins match wiring
3. Test with `scripts/verify_hardware.py`
4. Check for GPIO conflicts with StatusLEDManager

### Buzzer Not Beeping

1. Check `buzzer_enabled: true` in config
2. Verify buzzer polarity (+ to GPIO, - to GND)
3. Check GPIO 17 is not used by other services
4. Test with `scripts/verify_hardware.py`

### Confusing Flash Patterns

- Ensure only FeedbackController manages the feedback LEDs
- StatusLEDManager should use separate LEDs if enabled
- Check logs for LED state transitions

## Future Enhancements

### Potential Additions

- **PWM buzzer control**: Variable pitch/tone for different events
- **RGB LED support**: More color options beyond red/green/yellow
- **Brightness control**: PWM dimming for low-light environments
- **Custom patterns**: User-definable flash patterns in config
- **Status LED integration**: Seamless coordination with StatusLEDManager

### Considerations

- Keep patterns simple and distinctive
- Avoid overly complex sequences
- Balance feedback richness with clarity
- Test with actual users for effectiveness
