# NFC Tap Logger Upgrade – Wiring Schematics and Pin Mapping

All I2C devices (PN532, DS3231 RTC, SSD1306 OLED) share the same bus lines (SDA/SCL) and 3.3V/GND. Feedback devices (LEDs, buzzer) use individual GPIO pins as defined in the project’s `config.yaml`.

## Raspberry Pi Zero 2 W – Pin References (BCM)

- 3.3V: Pin 1
- GND: Pin 6 (also available on pins 9, 14, 20, 25, 30, 34, 39)
- SDA (GPIO 2): Pin 3
- SCL (GPIO 3): Pin 5
- GPIO 17: Pin 11 (Buzzer)
- GPIO 27: Pin 13 (Green LED)
- GPIO 22: Pin 15 (Red LED)
- GPIO 26: Pin 37 (Optional shutdown button)

## I2C Bus – Daisy Chain (Parallel Wiring)

Connect each I2C module’s 4 pins to the Pi’s I2C and power pins. You can “fan-out” using a small breadboard or by bundling/joining wires.

Pi Pin → Every I2C Module Pin:

- Pin 1 (3.3V) → VCC
- Pin 6 (GND) → GND
- Pin 3 (GPIO2/SDA) → SDA
- Pin 5 (GPIO3/SCL) → SCL

Expected addresses:

- PN532: 0x24 (typical for I2C mode)
- DS3231: 0x68
- SSD1306 OLED: 0x3C

### PN532 (I2C Mode)

- Verify DIP switch/jumper settings for I2C:
  - Often “I2C: ON” and “HSU/SPI: OFF” (check your board’s silk screen or manual)
- Connect:
  - VCC → Pin 1 (3.3V)
  - GND → Pin 6 (GND)
  - SDA → Pin 3 (GPIO2/SDA)
  - SCL → Pin 5 (GPIO3/SCL)

### DS3231 RTC

- Install CR1220 backup battery
- Connect:
  - VCC → Pin 1 (3.3V)
  - GND → Pin 6 (GND)
  - SDA → Pin 3 (GPIO2/SDA)
  - SCL → Pin 5 (GPIO3/SCL)

### SSD1306 OLED (0.96", 128×64)

- Connect:
  - VCC → Pin 1 (3.3V)
  - GND → Pin 6 (GND)
  - SDA → Pin 3 (GPIO2/SDA)
  - SCL → Pin 5 (GPIO3/SCL)

## Feedback Devices

### Green LED (GPIO 27) with 220Ω resistor

- Series resistor required to limit current
- Wiring (series):
  - GPIO 27 (Pin 13) → 220Ω resistor → LED anode (long leg)
  - LED cathode (short leg) → GND (e.g., Pin 14/20/6)

### Red LED (GPIO 22) with 220Ω resistor

- Wiring (series):
  - GPIO 22 (Pin 15) → 220Ω resistor → LED anode (long leg)
  - LED cathode (short leg) → GND

### Buzzer (Active, polarized)

- Wiring:
  - Buzzer (+) → GPIO 17 (Pin 11)
  - Buzzer (−) → GND (e.g., Pin 9/6/14)
- Note: Active buzzers don’t need a series resistor

### Optional Shutdown Button (GPIO 26)

- Wiring:
  - One leg → GPIO 26 (Pin 37)
  - Other leg → GND (Pin 39)
- Software: Configure a GPIO input with an internal pull-up and catch presses to trigger a clean shutdown

## External NFC Antenna (Optional, Module-Dependent)

- Only applicable if your PN532 breakout includes an **external antenna connector** (e.g., U.FL or dedicated antenna pads)
- Connection:
  - Match connector type exactly (U.FL pigtail to the antenna)
  - Route antenna to be flush against the enclosure’s lid for best coupling
- If your PN532 has an integrated coil and no connector, adding an external antenna is not supported—mount the board firmly near the lid (use nylon standoffs) to minimize air gap

## Breadboard-Based Wiring Guide

Using an 830-point breadboard simplifies connections and reduces wiring complexity. This guide shows how to organize all components on the breadboard.

### Breadboard Power Rails Setup

1. **Connect power rails to Raspberry Pi:**
   - Pi Pin 1 (3.3V) → Breadboard positive rail (red)
   - Pi Pin 6 (GND) → Breadboard negative rail (blue/black)
   - Optional: Bridge both power rails on breadboard for easier access

### Component Placement on Breadboard

#### I2C Devices (PN532, DS3231 RTC, SSD1306 OLED)

All I2C devices share the same 4 connections. Use breadboard rows to fan out:

```
Breadboard Layout (I2C Bus):
Row A: 3.3V rail → All VCC pins
Row B: GND rail → All GND pins  
Row C: SDA (Pi Pin 3/GPIO2) → All SDA pins
Row D: SCL (Pi Pin 5/GPIO3) → All SCL pins

Connect each I2C module:
- PN532: VCC to Row A, GND to Row B, SDA to Row C, SCL to Row D
- DS3231 RTC: VCC to Row A, GND to Row B, SDA to Row C, SCL to Row D
- SSD1306 OLED: VCC to Row A, GND to Row B, SDA to Row C, SCL to Row D
```

#### Green LED Circuit (GPIO 27)

```
Pi Pin 13 (GPIO27) → 220Ω resistor → LED anode (long leg) → LED cathode (short leg) → GND rail
```

Place on breadboard:

- Row E: Connect GPIO27 wire
- Row E: Insert 220Ω resistor (one leg)
- Row F: Resistor other leg + LED anode (long leg)
- Row G: LED cathode (short leg) → jumper to GND rail

#### Red LED Circuit (GPIO 22)

```
Pi Pin 15 (GPIO22) → 220Ω resistor → LED anode (long leg) → LED cathode (short leg) → GND rail
```

Place on breadboard:

- Row H: Connect GPIO22 wire
- Row H: Insert 220Ω resistor (one leg)
- Row I: Resistor other leg + LED anode (long leg)
- Row J: LED cathode (short leg) → jumper to GND rail

#### Buzzer Connection

```
Pi Pin 11 (GPIO17) → Buzzer positive (+)
Buzzer negative (−) → GND rail
```

Place on breadboard:

- Row K: Connect GPIO17 wire and buzzer positive pin
- Row L: Connect buzzer negative pin → jumper to GND rail

#### Shutdown Button (Momentary Push Button)

```
Pi Pin 37 (GPIO26) → Button leg 1
Button leg 2 → GND rail
```

Place on breadboard:

- Row M: Connect GPIO26 wire and one button leg
- Row N: Connect other button leg → jumper to GND rail
- Software will enable internal pull-up resistor (no external resistor needed)

### Complete Breadboard Connection Summary

```
Raspberry Pi → Breadboard Connections:
Pin 1  (3.3V)    → Positive rail (red)
Pin 3  (GPIO2/SDA) → I2C SDA row
Pin 5  (GPIO3/SCL) → I2C SCL row
Pin 6  (GND)     → Negative rail (blue/black)
Pin 11 (GPIO17)  → Buzzer positive row
Pin 13 (GPIO27)  → Green LED resistor row
Pin 15 (GPIO22)  → Red LED resistor row
Pin 37 (GPIO26)  → Button row
Pin 39 (GND)     → Negative rail (optional, for shorter runs)
```

## ASCII Wiring Diagram (Simplified)

```
Raspberry Pi Zero 2 W (Top view, pin numbers)

(1)3V3  (2)5V
(3)SDA  (4)5V
(5)SCL  (6)GND
(7)GPIO4(8)TXD
(9)GND  (10)RXD
(11)GPIO17 [Buzzer +]
(12)GPIO18
(13)GPIO27 [Green LED +]
(14)GND   [Green LED −]
(15)GPIO22 [Red LED +]
(16)GPIO23
...
(37)GPIO26 [Shutdown button]
(39)GND   [Shutdown button]

I2C BUS (shared via breadboard):
 Pin 1 (3V3) → VCC on PN532, RTC, OLED
 Pin 6 (GND) → GND on PN532, RTC, OLED
 Pin 3 (SDA) → SDA on PN532, RTC, OLED
 Pin 5 (SCL) → SCL on PN532, RTC, OLED

LEDs (with 220Ω resistors):
 GPIO27 (Pin 13) → 220Ω → LED(GREEN anode) → LED cathode → GND
 GPIO22 (Pin 15) → 220Ω → LED(RED anode) → LED cathode → GND

Buzzer (Active):
 GPIO17 (Pin 11) → Buzzer +
 Buzzer − → GND

Shutdown Button (Momentary):
 GPIO26 (Pin 37) → Button leg 1
 Button leg 2 → GND
 (Internal pull-up enabled in software)
```

## Software/Config Notes

- Ensure I2C is enabled:
  - `sudo raspi-config` → Interface Options → I2C → Enable
- Verify devices with:
  - `sudo apt install -y i2c-tools`
  - `i2cdetect -y 1` → should show `0x24` (PN532), `0x68` (RTC), `0x3C` (OLED)
- RTC overlay (if using DS3231):
  - Add to `/boot/config.txt`: `dtoverlay=i2c-rtc,ds3231`
  - On first boot, sync time with network or manually, then RTC will maintain time offline
- The project’s default pins (from `config.yaml`):
  - Buzzer: GPIO 17
  - LED green: GPIO 27
  - LED red: GPIO 22
  - I2C bus: 1 (SDA=GPIO2, SCL=GPIO3)
  - Shutdown button: GPIO 26 (with internal pull-up)
- Shutdown button configuration:
  - The shutdown button uses GPIO 26 with an internal pull-up resistor
  - Press and hold for 3 seconds to trigger a clean shutdown
  - Enable in `config.yaml`: `shutdown_button_enabled: true`
- RTC time synchronization:
  - After enabling RTC overlay, disable fake-hwclock: `sudo apt-get -y remove fake-hwclock && sudo update-rc.d -f fake-hwclock remove`
  - Set system time from RTC on boot: `sudo hwclock -s`
  - Set RTC from system time: `sudo hwclock -w`
