# Requirements

## Functional Requirements

### Must Have (v1.0)

**NFC Card Reading:**
- Read NTAG215 UID via PN532 I2C
- Handle read failures gracefully (retry, then skip with error feedback)
- Debounce (don't log same card twice within 1 second)

**Data Logging:**
- Log to SQLite: token_id, stage, timestamp (ISO 8601 UTC), station_id, session_id
- Prevent duplicate stage logs (same card can't log QUEUE_JOIN twice in one session)
- Database survives power loss (WAL mode)

**User Feedback:**
- Success: beep (or LED if no buzzer)
- Error: different beep pattern
- Duplicate tap: different pattern again
- Feedback happens within 1 second of tap

**Configuration:**
- YAML config file defines which stage this Pi logs (QUEUE_JOIN, EXIT, etc.)
- Each Pi has unique device_id
- Can configure GPIO pins (or disable buzzer/LEDs)

**Data Export:**
- Export SQLite to CSV
- Filename includes timestamp

**Card Initialization:**
- Separate script to write sequential token IDs (001-100) to cards
- Show progress as cards are tapped

### Nice to Have (if time allows)

- Visual feedback (LEDs in addition to buzzer)
- Ability to add notes to log entries (peer can flag issues)
- Database backup on shutdown
- Log file rotation
- Read NDEF data from cards (not just UID)

### Explicitly Out of Scope (v1.0)

- Real-time dashboard
- Network sync between Pis
- Web interface
- Participant-facing features
- Complex queueing logic (we just log taps, analysis happens later)

## Non-Functional Requirements

**Reliability:**
- Run for 8+ hours on battery without crashing
- Auto-restart on failure (systemd)
- Work without network

**Performance:**
- Tap to confirmation: <2 seconds
- Database writes: <100ms
- Memory usage: <100MB (Pi Zero has 512MB)

**Usability:**
- Peer training time: <5 minutes
- Clear error states (different beep = different problem)
- Physical setup time: <30 minutes

**Data Quality:**
- >90% of cards should have complete timestamp pairs (queue + exit minimum)
- No data corruption from power loss

**Maintainability:**
- Code is readable (we're not Python experts)
- Easy to change GPIO pins or stage names
- Can run tests without hardware (mock NFC reader)

## Constraints

**Hardware:**
- Must use I2C mode for PN532 (that's how modules are configured)
- Pi Zero 2 W only (512MB RAM, 4-core ARM)
- NTAG215 cards specifically (don't assume other NFC types work)

**Software:**
- Python 3.9+ (Raspberry Pi OS default)
- SQLite only (no postgres/mysql)
- No paid dependencies
- Must work offline (no internet APIs)

**Operational:**
- Peers are not developers (error messages need to be actionable)
- Festival noise (visual feedback helpful)
- Battery powered (low-power mode if idle)

## Success Metrics

**During Development:**
- Can we tap 50 cards in sequence without errors?
- Does it run for 8 hours without crashing?
- Can a non-technical peer operate it after 5 min training?

**Post-Event:**
- Data completeness: % of cards with both queue join and exit timestamps
- System uptime: hours operational / hours deployed
- Usability: peer feedback ("this was easy/hard")
- Value: could we calculate median wait time from the data?
- 
