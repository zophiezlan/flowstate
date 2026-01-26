# Auto-Initialize Cards on First Tap

## Overview

The auto-initialization feature allows you to use fresh, unprogrammed NFC cards at events without pre-initializing them. When an unprogrammed card is tapped for the first time, the system automatically assigns it the next sequential token ID.

## Benefits

- **Saves time before events**: No need to pre-initialize hundreds of cards
- **Flexibility**: Use any NTAG215 card on-the-fly
- **No card-number sync issues**: When cards are lost or stolen, the numbering stays sequential without gaps
- **Simplifies setup**: Just hand out blank cards and let the system handle the rest

## How It Works

1. Participant receives a blank NFC card
2. They tap it at the QUEUE_JOIN station
3. The system detects it's uninitialized (no token ID programmed)
4. The system automatically assigns the next available token ID (e.g., "001", "002", "003")
5. The token ID is written to the card (if possible) and logged in the database
6. Subsequent taps use the assigned token ID

## Configuration

### Enable Auto-Initialization

Edit `config.yaml`:

```yaml
nfc:
  # Auto-initialize cards on first tap (assigns next available token ID)
  auto_init_cards: true
  
  # Starting token ID for auto-initialization (default: 1)
  auto_init_start_id: 1
```

### Configuration Options

- **`auto_init_cards`** (boolean, default: `false`)
  - Set to `true` to enable auto-initialization
  - Set to `false` to require pre-initialized cards (traditional mode)

- **`auto_init_start_id`** (integer, default: `1`)
  - The first token ID to assign
  - Subsequent cards get incrementing numbers (1, 2, 3, ...)
  - Can be set higher if you want to start from a specific number

## Usage Examples

### Example 1: Fresh Event with Auto-Init

```yaml
# config.yaml
station:
  device_id: "station1"
  stage: "QUEUE_JOIN"
  session_id: "summer-fest-2026"

nfc:
  auto_init_cards: true
  auto_init_start_id: 1
```

**What happens:**

- First participant taps blank card → assigned "001"
- Second participant taps blank card → assigned "002"
- Third participant taps pre-initialized card "050" → uses "050" (not changed)
- Fourth participant taps blank card → assigned "003"

### Example 2: Mixed Cards (Pre-initialized + Auto-init)

You can use a mix of pre-initialized and blank cards:

```yaml
nfc:
  auto_init_cards: true
  auto_init_start_id: 100
```

- Pre-initialized cards (001-099) work normally
- Blank cards get assigned starting from 100
- No collisions between pre-initialized and auto-assigned IDs

### Example 3: Traditional Mode (No Auto-Init)

```yaml
nfc:
  auto_init_cards: false
```

- All cards must be pre-initialized using `scripts/init_cards.py`
- Blank cards will be treated as having a UID-based token ID
- Recommended if you want tight control over card numbering

## Technical Details

### How the System Detects Uninitialized Cards

The system identifies uninitialized cards by checking if the token ID looks like a UID:

- Token IDs that are 8+ hexadecimal characters are considered UIDs
- UIDs are typically 7-14 hex digits (e.g., "04A32FB2C15080")
- Token IDs are typically 3-4 digits (e.g., "001", "002")

### Token ID Assignment

1. The system maintains a counter in the database (`auto_init_counter` table)
2. Each session has its own counter
3. When a blank card is detected:
   - Get the next token ID from the counter
   - Increment the counter
   - Attempt to write the token ID to the card
   - Log the event with the assigned token ID

### Writing to Cards

The system attempts to write the assigned token ID to the card so it can be read on subsequent taps. However:

- If writing fails (card removed too quickly, card is read-only, etc.), the system still logs the event
- The token ID is permanently associated with that card's UID in the database
- Future taps will still work because the system remembers the UID → token ID mapping

### Database Storage

Token ID assignments are stored in:

1. **`auto_init_counter` table**: Tracks next available ID per session
2. **`events` table**: Records all taps with token_id and uid
3. The system uses UID as the primary identifier internally

## Operational Considerations

### When to Use Auto-Init

**✅ Good for:**

- Popup events with limited setup time
- Events where cards might be lost or stolen frequently
- Situations where exact numbering doesn't matter
- Events using mixed pre-initialized and blank cards

**❌ Not recommended for:**

- Events requiring specific card numbers for participants
- Situations where cards must be pre-assigned to individuals
- Events where you need to audit card inventory beforehand

### Pre-Event Checklist

1. Enable `auto_init_cards: true` in `config.yaml`
2. Set `auto_init_start_id` appropriately
3. Ensure stations are synced to the same session ID
4. Test with a few blank cards before the event
5. Have spare blank cards available

### Troubleshooting

**Q: Cards are getting sequential IDs but not remembering them on subsequent taps**

A: This is normal if card writing fails. The system still tracks the UID → token ID mapping in the database. As long as the card has a consistent UID, it will work correctly.

**Q: Token IDs are jumping (001, 002, 005, 006)**

A: This can happen if:

- Some participants received pre-initialized cards with IDs 003-004
- The database counter was manually adjusted
- Cards were tapped but never completed the journey (still counts as assigned)

**Q: Can I use auto-init on the EXIT station?**

A: While technically possible, it's not recommended. Cards should be initialized at QUEUE_JOIN so they have a consistent token ID throughout their journey. If EXIT also auto-initializes, you could end up with different token IDs for the same physical card.

**Q: What happens if two stations auto-initialize at the same time?**

A: The database uses transactions to ensure each token ID is assigned only once. Even with concurrent taps, each card gets a unique ID.

## Migration from Pre-Initialized Cards

If you want to switch from pre-initialized to auto-init:

1. **Gradual migration**: Enable auto-init with `auto_init_start_id` set above your highest pre-initialized ID

   ```yaml
   auto_init_cards: true
   auto_init_start_id: 501  # If pre-init cards are 001-500
   ```

2. **Fresh start**: Begin a new session with auto-init from ID 1

   ```yaml
   session_id: "new-event-2026"
   auto_init_cards: true
   auto_init_start_id: 1
   ```

3. **Hybrid approach**: Keep using pre-init for VIP/staff cards, use auto-init for general participants
   - Pre-init cards 001-099 for staff
   - Auto-init starting at 100 for participants

## Performance Impact

Auto-initialization adds minimal overhead:

- **Detection**: < 1ms (checks if token ID looks like UID)
- **Database lookup/update**: 5-10ms (get next ID, increment counter)
- **Card writing**: 100-300ms (optional, doesn't block if it fails)
- **Total impact**: < 20ms added to tap processing time

The system provides audio feedback when auto-initializing, so participants know their card is being set up.

## Security Considerations

- Token IDs are sequential and predictable (by design)
- This is acceptable for queue management where anonymity is key
- UIDs are stored in the database but not displayed to participants
- If you need non-predictable IDs, consider pre-initializing with random IDs

## Examples in Practice

### Scenario: Festival Drug Checking Service

**Setup:**

```yaml
nfc:
  auto_init_cards: true
  auto_init_start_id: 1
```

**Event day:**

- Hour 1: 50 participants tap blank cards, assigned IDs 001-050
- Hour 2: 75 more participants, assigned IDs 051-125
- Hour 3: Someone loses their card (ID 037), receives a new blank card, assigned ID 126
- End of day: 250 cards used, IDs 001-250 assigned

**No gaps from lost cards!** The numbering continues sequentially.

---

## See Also

- [OPERATIONS.md](OPERATIONS.md) - Day-of-event operations guide
- [3_STAGE_TRACKING.md](3_STAGE_TRACKING.md) - Understanding queue stages
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common issues and solutions
