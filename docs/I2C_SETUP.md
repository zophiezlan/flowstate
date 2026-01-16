# I2C Setup Guide for NFC Tap Logger

This guide helps you set up and troubleshoot I2C communication for the PN532 NFC reader on Raspberry Pi.

## Quick Start

If you're getting I2C errors, run this automated setup script:

```bash
bash scripts/enable_i2c.sh
```

This script will:
- Check if I2C is enabled in the config
- Enable I2C if needed
- Verify the I2C device exists
- Scan for the PN532 reader
- Provide troubleshooting guidance

## Understanding I2C on Raspberry Pi

### What is I2C?

I2C (Inter-Integrated Circuit) is a communication protocol that allows the Raspberry Pi to talk to the PN532 NFC reader. It uses two wires:
- **SDA** (Serial Data) - for data transfer
- **SCL** (Serial Clock) - for timing

### I2C Device Files

When I2C is enabled, Linux creates a device file:
- `/dev/i2c-1` on most Raspberry Pi models (Pi Zero 2, Pi 3, Pi 4)
- `/dev/i2c-0` on some older models (original Pi, Pi Zero)

If these files don't exist, I2C is not enabled.

## Manual I2C Setup

### Step 1: Enable I2C in Config

I2C must be enabled in the Raspberry Pi boot configuration:

1. Find your config file:
   ```bash
   # On newer Raspberry Pi OS (Bookworm and later)
   ls /boot/firmware/config.txt

   # On older Raspberry Pi OS
   ls /boot/config.txt
   ```

2. Edit the config file:
   ```bash
   # For newer OS
   sudo nano /boot/firmware/config.txt

   # For older OS
   sudo nano /boot/config.txt
   ```

3. Add this line (if not already present):
   ```
   dtparam=i2c_arm=on
   ```

4. Save and exit (Ctrl+X, then Y, then Enter)

### Step 2: Load I2C Kernel Module

1. Load the module immediately:
   ```bash
   sudo modprobe i2c_dev
   ```

2. Make it load automatically on boot:
   ```bash
   echo "i2c-dev" | sudo tee -a /etc/modules
   ```

### Step 3: Add User to i2c Group

To access I2C without sudo:

```bash
sudo usermod -a -G i2c $USER
```

**Important:** You must log out and back in for group changes to take effect.

### Step 4: Reboot (Required!)

```bash
sudo reboot
```

**This is mandatory!** I2C will not work until you reboot.

## Verification

After rebooting, verify I2C is working:

### 1. Check I2C Device Exists

```bash
ls -la /dev/i2c*
```

Should show:
```
crw-rw---- 1 root i2c 89, 1 Jan 16 10:00 /dev/i2c-1
```

If you don't see this, I2C is not enabled. Go back to Step 1.

### 2. Check Permissions

```bash
groups
```

Should include `i2c` in the list. If not:
- Run: `sudo usermod -a -G i2c $USER`
- Log out and back in
- Check again

### 3. Install i2c-tools

```bash
sudo apt-get install i2c-tools
```

### 4. Scan for Devices

```bash
sudo i2cdetect -y 1
```

Should show output like:
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

The `24` indicates the PN532 is detected at address 0x24. **This is what you want to see!**

### 5. Run Hardware Verification

```bash
source venv/bin/activate
python scripts/verify_hardware.py
```

All I2C checks should pass.

## Troubleshooting

### Problem: /dev/i2c-1 doesn't exist after reboot

**Possible causes:**
1. I2C not enabled in config.txt
2. Wrong config file edited
3. Typo in config file

**Solutions:**
1. Run `bash scripts/enable_i2c.sh` - it will check and fix
2. Verify the config line exactly: `dtparam=i2c_arm=on` (no spaces around =)
3. Check you edited the correct config file for your OS version

### Problem: Permission denied when accessing I2C

**Cause:** User not in i2c group

**Solution:**
```bash
sudo usermod -a -G i2c $USER
# Then log out and back in (required!)
```

Verify:
```bash
groups | grep i2c
```

### Problem: PN532 not detected (no 24 in i2cdetect)

**Possible causes:**
1. Wiring incorrect
2. PN532 not in I2C mode
3. Loose connections
4. Using wrong I2C bus

**Solutions:**

1. **Check wiring:**
   ```
   PN532 Pin    →    Raspberry Pi Pin
   VCC          →    Pin 1 (3.3V) - NOT 5V!
   GND          →    Pin 6 (GND)
   SDA          →    Pin 3 (GPIO 2)
   SCL          →    Pin 5 (GPIO 3)
   ```

2. **Check PN532 mode:**
   - Look for jumpers or switches on the PN532 board
   - Must be set to I2C mode (not SPI or UART)
   - Consult your PN532 module documentation

3. **Try alternate I2C bus:**
   ```bash
   sudo i2cdetect -y 0
   ```

   If you see `24` on bus 0, update your configuration:
   - Edit `config.yaml`: set `i2c_bus: 0`
   - Or update code to use bus 0

4. **Check connections:**
   - Ensure wires are firmly connected
   - Check for broken solder joints
   - Try different jumper wires

### Problem: I2C works but NFC reader fails

**Error:** "Failed to communicate with PN532"

**Possible causes:**
1. PN532 detected but not responding
2. Faulty PN532 module
3. Power issues

**Solutions:**

1. **Check power:**
   ```bash
   vcgencmd get_throttled
   ```

   Should return `throttled=0x0`. If not, power supply issue.

2. **Check PN532 power LED:**
   - Most PN532 modules have a power indicator LED
   - If not lit, check VCC/GND connections

3. **Try a different PN532 module** (if available)

### Problem: i2cdetect shows -- -- -- -- everywhere

**Cause:** I2C enabled but no devices connected or wrong bus

**Solutions:**
1. Try the other bus: `sudo i2cdetect -y 0`
2. Check all wiring connections
3. Verify PN532 is powered (check LED if present)

## Technical Details

### I2C on Raspberry Pi

- **I2C Bus 0:** Usually used for HAT EEPROM
- **I2C Bus 1:** Standard bus for peripherals (our PN532)
- **Speed:** Default is 100 kHz, can be increased if needed
- **Address:** PN532 uses 0x24 by default (hardware fixed)

### Pin Mapping

Physical pins on the Raspberry Pi 40-pin header:

```
        3.3V (1)  (2)  5V
   I2C1 SDA (3)  (4)  5V
   I2C1 SCL (5)  (6)  GND
       GPIO4 (7)  (8)  GPIO14
         GND (9) (10)  GPIO15
            ...
```

- Pin 1: 3.3V Power (VCC for PN532)
- Pin 3: GPIO 2 / I2C1 SDA (data)
- Pin 5: GPIO 3 / I2C1 SCL (clock)
- Pin 6: Ground (GND)

### I2C Configuration Parameters

In `/boot/config.txt` or `/boot/firmware/config.txt`:

```
# Enable I2C (required)
dtparam=i2c_arm=on

# Optional: Change I2C speed (if needed)
# dtparam=i2c_arm_baudrate=400000  # 400 kHz (faster)
# dtparam=i2c_arm_baudrate=100000  # 100 kHz (default)
```

## Common Scenarios

### First-time Setup

1. Run installation script: `bash scripts/install.sh`
2. Reboot: `sudo reboot`
3. Verify: `bash scripts/enable_i2c.sh`
4. Test: `python scripts/verify_hardware.py`

### After Fresh OS Install

1. Enable I2C: `bash scripts/enable_i2c.sh`
2. Reboot when prompted
3. Run again to verify: `bash scripts/enable_i2c.sh`

### Moving to a New Raspberry Pi

1. Ensure I2C enabled on new Pi: `bash scripts/enable_i2c.sh`
2. Check same I2C bus: compare `ls /dev/i2c*` output
3. Update config.yaml if different bus (i2c_bus: 0 or 1)
4. Verify wiring matches pin numbers, not GPIO numbers

### Debugging Connection Issues

1. **Physical Layer:** Wiring and power
   ```bash
   # Check device exists
   ls /dev/i2c*

   # Check permissions
   groups | grep i2c
   ```

2. **Bus Layer:** I2C communication
   ```bash
   # Scan for devices
   sudo i2cdetect -y 1

   # Should see 24
   ```

3. **Device Layer:** PN532 firmware
   ```bash
   # Test with Python
   source venv/bin/activate
   python scripts/verify_hardware.py
   ```

Work through each layer systematically.

## Need More Help?

1. **Run the troubleshooting script:**
   ```bash
   bash scripts/enable_i2c.sh
   ```

2. **Check other documentation:**
   - [Hardware Guide](HARDWARE.md) - Wiring details
   - [Troubleshooting Flowchart](TROUBLESHOOTING_FLOWCHART.md) - Step-by-step debugging
   - [README](../README.md) - General setup

3. **Collect diagnostic information:**
   ```bash
   # System info
   cat /proc/device-tree/model

   # I2C status
   ls -la /dev/i2c*
   lsmod | grep i2c
   groups

   # I2C scan
   sudo i2cdetect -y 1

   # Power status
   vcgencmd get_throttled
   ```

## Quick Reference

| Command | Purpose |
|---------|---------|
| `bash scripts/enable_i2c.sh` | Automated I2C setup and troubleshooting |
| `ls /dev/i2c*` | Check if I2C device exists |
| `lsmod \| grep i2c` | Check if I2C kernel module loaded |
| `groups` | Check if user is in i2c group |
| `sudo i2cdetect -y 1` | Scan I2C bus 1 for devices |
| `sudo i2cdetect -y 0` | Scan I2C bus 0 for devices |
| `vcgencmd get_throttled` | Check for power issues |
| `python scripts/verify_hardware.py` | Full hardware verification |

---

**Remember:** After any config changes, you MUST reboot! 🔄
