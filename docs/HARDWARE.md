# Hardware Details

## What We Have

### Confirmed Inventory
- 2× Raspberry Pi Zero 2 WH (512MB RAM, 4-core ARM, WiFi/BT)
- 2× PN532 NFC modules (blue PCB, I2C capable, working)
- 100× NTAG215 NFC cards (rewritable, 540 bytes each)
- 2× USB-C power banks (~10,000mAh each)

### To Acquire (Optional)
- Piezo buzzers (5V, for audio feedback)
- LEDs + resistors (for visual feedback)
- Small weatherproof boxes (housing)
- MicroSD cards (if not already have)

## PN532 Configuration

**Communication Mode:** I2C (already configured)  
**I2C Address:** 0x24 (standard for PN532)  
**Wiring:**
```
PN532        Pi GPIO
VCC    →     3.3V (Pin 1)
GND    →     GND (Pin 6)  
SDA    →     GPIO 2 (Pin 3)
SCL    →     GPIO 3 (Pin 5)
```

**Verification:**
```bash
sudo i2cdetect -y 1
# Should show device at 0x24
```

**Library:** Use `py532lib` (works well with I2C mode)

## NTAG215 Cards

**Specs:**
- Total memory: 540 bytes
- Writable: ~500 bytes (after header)
- UID: 7 bytes (read-only, unique per card)

**What We'll Use:**
- UID as primary identifier (auto-unique)
- Optional: Write token_id + session_id to NDEF data
- Don't store personal info or sample data on cards

**Example UID:** `04:A3:2F:B2:C1:50:80` (hex format)

## Power

**Power Banks:**
- Capacity: 10,000mAh @ 5V = ~50Wh
- Pi Zero 2 W draws: ~200-300mA average (~1.5W)
- Expected runtime: 20-30 hours (plenty for festival day)

**Battery Management:**
- Monitor: `vcgencmd get_throttled` (should be 0x0)
- If under-voltage (0x50000): battery dying, swap power bank

**Power Saving (if needed):**
- Disable WiFi: `sudo rfkill block wifi`
- Disable Bluetooth: `sudo rfkill block bluetooth`
- Lower CPU frequency (not usually necessary)

## GPIO Pins (Optional Feedback)

**If using buzzer:**
- Buzzer+ → GPIO 17 (Pin 11)
- Buzzer- → GND

**If using LEDs:**
- Green LED (success): GPIO 27 (Pin 13) → 220Ω resistor → GND
- Red LED (error): GPIO 22 (Pin 15) → 220Ω resistor → GND

**Note:** These GPIO pins are just suggestions. Make them configurable in `config.yaml`.

## Physical Setup

**Minimal (no housing):**
- Tape PN532 to cardboard/clipboard
- Pi sits underneath
- Ziplock bag for moisture protection
- "TAP HERE" label

**Better (weatherproof box):**
- Mount PN532 on lid (accessible)
- Pi inside box
- Cable gland for power cable
- Clear window over PN532 if needed

## Known Issues

**PN532 read range:** ~3-5cm (need good contact)
- Solution: Flat surface, clear "tap here" marking
- Cards must be placed centered on antenna

**I2C timeout:** Sometimes happens if card removed too quickly
- Solution: Retry logic (3 attempts), then give up gracefully

**Power fluctuations:** Can cause Pi to reboot
- Solution: Good quality power bank, decent USB cable

## Pre-Flight Checks

Before each deployment:

1. **I2C Detection:**
```bash
   sudo i2cdetect -y 1
   # Should show 0x24
```

2. **Card Read Test:**
```python
   # Quick test script
   from py532lib.i2c import Pn532_i2c
   pn532 = Pn532_i2c(address=0x24)
   uid = pn532.read_mifare().get_data()
   print(f"UID: {uid.hex()}")
```

3. **Battery Check:**
```bash
   vcgencmd get_throttled
   # Should return: throttled=0x0
```

4. **GPIO Test (if using):**
   - Test buzzer/LEDs manually with GPIO script

## Troubleshooting Quick Ref

**PN532 not detected:**
- Check I2C jumpers/switches (should be I2C mode)
- Verify wiring (VCC to 3.3V NOT 5V)
- Try `sudo i2cdetect -y 0` (some Pis use bus 0)

**Card read fails:**
- Check card is NTAG215 (not other NFC type)
- Hold card flat against antenna for 2-3 seconds
- Try different card (could be faulty)

**Random reboots:**
- Check power bank capacity
- Try different USB cable
- Monitor with `vcgencmd get_throttled` during operation
