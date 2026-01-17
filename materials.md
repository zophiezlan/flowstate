# NFC Tap Logger Upgrade – Bill of Materials (BOM)

This list covers the proposed upgrades and all supporting hardware to make the Pi-based station robust for field use. Quantities are for one station.

## Core Upgrades

- 1× PN532 NFC Reader (I2C mode)
  - Interface: I2C
  - Typical I2C address: 0x24
  - Notes: Ensure board has I2C DIP switch/jumpers; integrated 13.56 MHz antenna or external connector depending on model
- 1× DS3231 Real-Time Clock (RTC) Module
  - Interface: I2C (address 0x68)
  - Battery: 1× CR1220 coin cell (backup, often included)
  - Operating voltage: 3.3V–5V (use 3.3V on Pi)
  - Connector: 4-pin header (VCC, GND, SDA, SCL)
- 1× 0.96" SSD1306 OLED Display (128×64, I2C)
  - Interface: I2C (address typically 0x3C)
  - Operating voltage: 3.3V–5V (use 3.3V on Pi)
  - Connector: 4-pin header (VCC, GND, SDA, SCL)
- 1× Micro-USB OTG Adapter/Cable
  - Type: Micro-USB male to USB-A female (for Pi Zero 2 W OTG)
  - Use: Connect keyboard/mouse or USB devices when needed
- 1× External NFC Antenna (optional, module-dependent)
  - Type: 13.56 MHz coil antenna with compatible connector (e.g., U.FL) for PN532 boards that support external antennas
  - Notes: Many PN532 boards have an integrated antenna and no external connector; verify your board before purchase

## Feedback and Controls

- 1× Active buzzer (3.3V–5V compatible)
  - Polarity: (+) and (−) pins
- 2× 5mm LEDs (1× green, 1× red)
- 2× Resistors, 220Ω (for LEDs)
- 1× Momentary push button (SPST)
  - Use: Safe shutdown or mode toggle

## Mounting and Enclosure

- 1× ABS project box (approx. 115×65×40 mm or larger)
- 1× Nylon standoff kit (M3) for mounting Pi and PN532
- 1× 830-point breadboard (for organizing all connections - highly recommended)
  - Alternative: Small distribution block for I2C bus splitting only
- 1× Clear acrylic window or protective film (optional, to protect OLED)

## Cabling and Connectors

- 1× 40-pin male header for Raspberry Pi Zero 2 W (if not already soldered)
- 1× High-quality power cable (USB to Micro-USB, short and thick to reduce voltage drop)
- Assorted jumper leads:
  - Female–female leads (for Pi header to module headers)
  - Optional: male–female leads and dupont housings, depending on module connectors

## Consumables and Tools

- Electrical tape or heatshrink tubing
- Hot glue or Blu-Tack (strain relief and fixing LEDs in the box)
- Soldering iron and solder (if header/module pins need to be soldered)
- Small screws/nuts (M3) for standoffs and mounting

## Optional Electrical (for long I2C runs)

- 2× 4.7kΩ resistors (SDA/SCL pull-ups to 3.3V) if your combined I2C bus or module set lacks adequate pull-ups (most modules already include them)
