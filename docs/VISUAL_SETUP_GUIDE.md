# Visual Setup Guide
## Hardware Assembly with Diagrams

> **Note:** This guide includes detailed diagrams. For best results, add photos of your actual hardware setup where indicated with `[PHOTO NEEDED]`.

---

## 📦 Parts Inventory

Before starting, verify you have:

```
☐ 1× Raspberry Pi Zero 2 W (with headers)
☐ 1× PN532 NFC Module (blue PCB, I2C mode)
☐ 1× MicroSD card (8GB+, with Raspberry Pi OS)
☐ 1× USB-C power bank (10,000mAh recommended)
☐ 1× USB-C cable (Pi Zero 2 W uses USB-C)
☐ 4× Female-to-female jumper wires (for PN532)
☐ 1× Piezo buzzer 5V (optional)
☐ 2× Female-to-male jumper wires (for buzzer, optional)
☐ 100× NTAG215 NFC cards
☐ Tape or velcro (for mounting)
```

`[PHOTO NEEDED: All parts laid out on table]`

---

## 🔌 Wiring Diagrams

### Overview: Raspberry Pi Zero 2 W Pinout

```
        3.3V  ●  1     2  ●  5V
  (SDA) GPIO2 ●  3     4  ●  5V
  (SCL) GPIO3 ●  5     6  ●  GND
        GPIO4 ●  7     8  ●  GPIO14
          GND ●  9    10  ●  GPIO15
       GPIO17 ● 11    12  ●  GPIO18
       GPIO27 ● 13    14  ●  GND
       GPIO22 ● 15    16  ●  GPIO23
        3.3V  ● 17    18  ●  GPIO24
       GPIO10 ● 19    20  ●  GND
        GPIO9 ● 21    22  ●  GPIO25
       GPIO11 ● 23    24  ●  GPIO8
          GND ● 25    26  ●  GPIO7
          ...            ...
```

### PN532 to Pi Wiring (I2C Mode)

```
PN532 Module                    Raspberry Pi Zero 2 W
┌─────────────┐                ┌──────────────────────┐
│             │                │                      │
│  [PN532]    │                │   Raspberry Pi       │
│             │                │   Zero 2 W           │
│  VCC ●──────┼────────────────┼──● Pin 1 (3.3V)     │  RED wire
│  GND ●──────┼────────────────┼──● Pin 6 (GND)      │  BLACK wire
│  SDA ●──────┼────────────────┼──● Pin 3 (GPIO2)    │  BLUE wire
│  SCL ●──────┼────────────────┼──● Pin 5 (GPIO3)    │  YELLOW wire
│             │                │                      │
│  IRQ ● (not connected)       │                      │
│  RSTO● (not connected)       │                      │
└─────────────┘                └──────────────────────┘
```

**⚠️ CRITICAL WARNINGS:**

1. **Use 3.3V, NOT 5V!** PN532 modules can be damaged by 5V
2. **Double-check pin numbers** before powering on
3. **Color coding helps** - use consistent wire colors

`[PHOTO NEEDED: Close-up of PN532 to Pi wiring, showing each connection clearly]`

---

### Buzzer Wiring (Optional)

```
Buzzer                         Raspberry Pi Zero 2 W
┌──────┐                      ┌──────────────────────┐
│  +   ●──────────────────────┼──● Pin 11 (GPIO17)   │  RED wire
│  -   ●──────────────────────┼──● Pin 9 or 6 (GND)  │  BLACK wire
└──────┘                      └──────────────────────┘
```

**Notes:**
- Buzzer polarity matters: + to GPIO17, - to GND
- If buzzer is too quiet, use a transistor circuit
- Can use any GPIO pin, just update config.yaml

`[PHOTO NEEDED: Buzzer connections]`

---

### LED Wiring (Optional)

```
Green LED (Success)            Raspberry Pi Zero 2 W
┌─────────────┐               ┌──────────────────────┐
│  Anode (+)  ●─┬─────────────┼──● Pin 13 (GPIO27)   │  GREEN wire
│             │ │             │                      │
│          220Ω ├─┤           │                      │
│          Resistor           │                      │
│             │               │                      │
│ Cathode (-) ●─┴─────────────┼──● GND               │  BLACK wire
└─────────────┘               └──────────────────────┘

Red LED (Error)
┌─────────────┐               ┌──────────────────────┐
│  Anode (+)  ●─┬─────────────┼──● Pin 15 (GPIO22)   │  RED wire
│             │ │             │                      │
│          220Ω ├─┤           │                      │
│          Resistor           │                      │
│             │               │                      │
│ Cathode (-) ●─┴─────────────┼──● GND               │  BLACK wire
└─────────────┘               └──────────────────────┘
```

**Notes:**
- Always use resistors with LEDs (220Ω or 330Ω)
- Longer LED leg is + (anode)
- Shorter LED leg is - (cathode)

`[PHOTO NEEDED: LED setup with resistors]`

---

## 🔧 Step-by-Step Assembly

### Step 1: Prepare the Pi (5 min)

1. **Insert MicroSD card** with Raspberry Pi OS
   - Already flashed and ready to boot
   - Should have SSH enabled

2. **Identify pin 1 on Pi**
   - Pin 1 is closest to SD card slot
   - Square pad on underside of board

`[PHOTO NEEDED: Pi with SD card inserted, pin 1 indicated]`

### Step 2: Connect PN532 (5 min)

**Before connecting, verify PN532 is in I2C mode:**

```
PN532 has two small switches/jumpers:
- Switch 1: OFF (or jumper open)
- Switch 2: ON  (or jumper closed)

This sets I2C mode. SPI mode is different!
```

`[PHOTO NEEDED: PN532 switches showing I2C configuration]`

**Now connect wires in this order:**

1. **GND (Black wire):** PN532 GND → Pi Pin 6
   - Connect ground first (safety)

2. **VCC (Red wire):** PN532 VCC → Pi Pin 1 (3.3V)
   - NOT 5V! Use pin 1 (3.3V)

3. **SDA (Blue wire):** PN532 SDA → Pi Pin 3 (GPIO2)
   - Data line

4. **SCL (Yellow wire):** PN532 SCL → Pi Pin 5 (GPIO3)
   - Clock line

`[PHOTO NEEDED: Each wire being connected, shown in sequence]`

**Final check before power:**
- [ ] VCC → 3.3V (Pin 1) ✓
- [ ] GND → GND (Pin 6) ✓
- [ ] SDA → GPIO2 (Pin 3) ✓
- [ ] SCL → GPIO3 (Pin 5) ✓

`[PHOTO NEEDED: Completed PN532 wiring, all four wires visible]`

### Step 3: Connect Buzzer (2 min, optional)

1. **Red wire:** Buzzer + → Pi Pin 11 (GPIO17)
2. **Black wire:** Buzzer - → Pi Pin 9 (GND)

`[PHOTO NEEDED: Buzzer connected to Pi]`

### Step 4: Physical Mounting (5 min)

**Option A: Desktop Setup (Quick)**
- Tape PN532 to clipboard or cardboard
- Label "TAP HERE" clearly
- Pi sits underneath or beside

`[PHOTO NEEDED: Desktop setup with tape mounting]`

**Option B: Weatherproof Box (Better)**
- Small plastic box (tupperware works)
- PN532 mounted on lid (accessible from outside)
- Pi inside box
- Power cable through small hole or cable gland
- Clear window over PN532 if needed

`[PHOTO NEEDED: Weatherproof box assembly]`

**Option C: Minimal (Festival Tested)**
- Ziplock bag over entire setup
- "TAP HERE" label on bag
- Surprisingly effective!

`[PHOTO NEEDED: Ziplock bag setup]`

### Step 5: Power Connection (1 min)

1. Connect USB-C cable to Pi
2. Connect other end to power bank
3. Turn on power bank
4. Pi should boot (green LED flashes)
5. Wait 30 seconds for full boot

`[PHOTO NEEDED: Power bank connected, Pi booting]`

---

## ✅ Verification Steps

### 1. Check Pi is Booting

**Look for:**
- Green LED on Pi flashing (disk activity)
- After 30 seconds, LED should settle to occasional flashes
- If red LED only (no green), check SD card

`[PHOTO NEEDED: Pi LEDs during boot]`

### 2. SSH into Pi

```bash
# From your laptop
ssh pi@raspberrypi.local
# Default password: raspberry (change this!)
```

### 3. Check I2C Bus

```bash
sudo i2cdetect -y 1
```

**Expected output:**
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- 24 -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```

See `24` at address 0x24? **PN532 detected! ✓**

`[PHOTO NEEDED: Terminal showing i2cdetect output]`

### 4. Test NFC Reader

```bash
cd ~/nfc-tap-logger
source venv/bin/activate
python scripts/verify_hardware.py
```

When prompted, tap an NFC card. Should see:
```
✓ Card read: UID=04A32FB2C15080, Token=04A32FB2
```

`[PHOTO NEEDED: Card being held over PN532 reader]`

### 5. Test Buzzer (if installed)

```bash
python -c "
import RPi.GPIO as GPIO
import time
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.OUT)
GPIO.output(17, True)
time.sleep(0.2)
GPIO.output(17, False)
GPIO.cleanup()
"
```

Should hear a short beep.

---

## 🚫 Common Mistakes (What NOT to Do)

### ❌ Mistake #1: Using 5V Instead of 3.3V

```
WRONG:
PN532 VCC → Pi Pin 2 (5V)  ❌ TOO HIGH! Can damage PN532

CORRECT:
PN532 VCC → Pi Pin 1 (3.3V) ✓
```

`[PHOTO NEEDED: Pin 1 vs Pin 2 comparison, labeled clearly]`

### ❌ Mistake #2: Wrong I2C Pins

```
WRONG:
PN532 SDA → Any random GPIO  ❌
PN532 SCL → Any random GPIO  ❌

CORRECT:
PN532 SDA → GPIO2 (Pin 3)  ✓ I2C SDA
PN532 SCL → GPIO3 (Pin 5)  ✓ I2C SCL
```

Only GPIO2 and GPIO3 are I2C by default!

### ❌ Mistake #3: PN532 in SPI Mode

```
If i2cdetect shows nothing, check PN532 switches:
- Should be in I2C mode, not SPI or UART
- Check module documentation for switch positions
```

`[PHOTO NEEDED: PN532 switches in wrong position vs correct position]`

### ❌ Mistake #4: Loose Connections

```
Jumper wires can work loose!
- Press firmly onto pins
- Test by gently tugging
- Use tape if needed
```

`[PHOTO NEEDED: Secure vs loose jumper wire connection]`

### ❌ Mistake #5: Wrong Card Type

```
WRONG: Random NFC tag from keychain  ❌
WRONG: Mifare Classic 1K              ❌
WRONG: Credit card (RFID, not NFC)    ❌

CORRECT: NTAG215 card                 ✓
```

NTAG215 cards typically say "NTAG215" or "504 bytes" on packaging.

---

## 📏 Card Placement Guide

### Optimal Card Position

```
        ┌─────────────────┐
        │   PN532 Module  │
        │                 │
        │  ┌───────────┐  │
        │  │  Antenna  │  │ ← PN532 antenna (square coil)
        │  │           │  │
        │  │     ●     │  │ ← Sweet spot (center)
        │  │           │  │
        │  └───────────┘  │
        │                 │
        └─────────────────┘
```

**Hold card:**
- Flat against PN532 antenna
- Centered over sweet spot
- 1-2 seconds for read
- Distance: 0-5cm works, closer is better

`[PHOTO NEEDED: Correct card placement, hand holding card flat]`

### Poor Card Placement

```
❌ Card at angle (not flat)
❌ Card too far away (>5cm)
❌ Card moving while reading
❌ Metal objects nearby (interferes with NFC)
```

`[PHOTO NEEDED: Examples of bad card placement]`

---

## 🔋 Power Best Practices

### Good Power Bank Choice

**Look for:**
- ✓ 10,000mAh or higher
- ✓ 5V 2A output minimum
- ✓ Quality brand (Anker, RAVPower, etc.)
- ✓ Short, thick USB cable (lower resistance)

`[PHOTO NEEDED: Recommended power bank connected to Pi]`

### Poor Power Setup

**Avoid:**
- ❌ Cheap, thin USB cables (causes voltage drop)
- ❌ Long USB cables (>1 meter)
- ❌ Old/worn power banks
- ❌ Phone chargers <2A

### Check for Under-Voltage

```bash
vcgencmd get_throttled
```

**Good:** `throttled=0x0` (no problems)
**Bad:** `throttled=0x50000` (under-voltage detected!)

If under-voltage:
1. Try different USB cable (thicker)
2. Try different power bank
3. Check power bank is fully charged

`[PHOTO NEEDED: Terminal showing throttled status]`

---

## 📦 Complete Assembly Photos

### Station 1 (Queue Join) - Example Setup

`[PHOTO NEEDED: Full station 1 setup - overview]`
`[PHOTO NEEDED: Close-up of PN532 with "TAP HERE" sign]`
`[PHOTO NEEDED: Pi and power bank placement]`
`[PHOTO NEEDED: Cable management]`

### Station 2 (Exit) - Example Setup

`[PHOTO NEEDED: Full station 2 setup - overview]`

### Portable Kit in Storage

`[PHOTO NEEDED: All components packed in case]`
`[PHOTO NEEDED: Labeled cables and bags]`

---

## 🎨 Labeling & Organization

### Cable Labels

Use tape and sharpie to label:
- "Station 1 - PN532"
- "Station 1 - Power"
- "Station 2 - PN532"
- "Station 2 - Power"

Prevents mix-ups during setup!

`[PHOTO NEEDED: Labeled cables]`

### Station Labels

Print and laminate:
- "STATION 1 - QUEUE JOIN - TAP HERE"
- "STATION 2 - EXIT - TAP HERE"

Make it obvious where to tap!

`[PHOTO NEEDED: Example station label]`

---

## ⏱️ Setup Time Expectations

**First time:** 30-45 minutes
- Learning where everything goes
- Double-checking connections
- Verifying it works

**Second time:** 15-20 minutes
- Familiar with layout
- Labeled cables help

**Experienced:** 10 minutes
- Muscle memory
- Quick verification

---

## 🧪 Pre-Event Testing

### Full System Test (15 min)

1. **Assemble both stations** (10 min)
2. **Boot and verify I2C** (2 min each)
3. **Test card tap** (1 min each)
4. **Check database logs** (1 min)

```bash
# After testing both stations
python -m tap_station.main --stats

Expected:
  Total Events: 2 (one from each station)
```

5. **Let run for 1 hour** (verify stability)
   - Check for crashes
   - Check battery level
   - Check temperature

`[PHOTO NEEDED: Both stations running side-by-side during test]`

---

## 🎓 Training New Users

### Show Them This Guide

1. **Parts inventory** - verify they have everything
2. **Wiring diagram** - follow color codes
3. **Step-by-step assembly** - go slow first time
4. **Verification steps** - confirm it works
5. **Common mistakes** - learn from others

### Hands-On Practice

- Let them assemble one station
- Guide but don't do it for them
- Check their work
- Have them test it

After building one station, they can build the second in 10 min!

---

## 📞 Quick Reference

**PN532 Wiring:**
```
VCC → Pin 1 (3.3V)   RED
GND → Pin 6 (GND)    BLACK
SDA → Pin 3 (GPIO2)  BLUE
SCL → Pin 5 (GPIO3)  YELLOW
```

**Verify I2C:**
```bash
sudo i2cdetect -y 1  # Should show 24
```

**Test Tap:**
```bash
python scripts/verify_hardware.py
```

---

## 🎉 Success!

If you've followed this guide, you should now have:
- ✅ Properly wired PN532 to Pi
- ✅ I2C detection working
- ✅ Cards reading successfully
- ✅ Buzzer beeping (if installed)
- ✅ Understanding of common mistakes
- ✅ Confidence to deploy at event

**Next steps:** See DEPLOYMENT_CHECKLIST.md for event operations.

---

## 📸 Photo Checklist

To complete this visual guide, add photos for:

- [ ] All parts inventory
- [ ] PN532 I2C mode switches
- [ ] Each wire connection (4 close-ups)
- [ ] Complete PN532 wiring
- [ ] Buzzer connection
- [ ] LED setup with resistors
- [ ] Desktop mounting option
- [ ] Weatherproof box option
- [ ] Ziplock bag option
- [ ] Pi LEDs during boot
- [ ] i2cdetect terminal output
- [ ] Correct card placement
- [ ] Bad card placement examples
- [ ] Power bank setup
- [ ] Complete station 1 setup
- [ ] Complete station 2 setup
- [ ] Labeled cables
- [ ] Station labels
- [ ] Both stations during test

**Pro tip:** Take photos during your next assembly and update this guide!
