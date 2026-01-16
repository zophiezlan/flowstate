# NFC Tap Logger

A simple, reliable system for tracking wait times at festival drug checking services using NFC tap stations.

## Overview

This system logs NFC card taps at two stations (queue join and exit) to measure wait times and throughput at harm reduction events. It's designed to be:

- **Reliable**: Runs for 8+ hours on battery, auto-restarts on failure, crash-resistant database
- **Simple**: Dead simple peer workflow, no network required, quick setup
- **Maintainable**: Clean Python code, well-documented, easy to modify

## 🆕 What's New (v1.1)

Three new features make deployment even easier:

1. **Visual Setup Guide** (`docs/VISUAL_SETUP_GUIDE.md`) - Detailed wiring diagrams and photo placeholders
2. **NFC Tools App Integration** - Participants can check status with their phones
3. **Health Check & Web Status** - Monitor stations remotely, show live status

See `docs/NEW_FEATURES.md` for full details!

## Quick Start

### Prefer phones over Raspberry Pis?

You can now run the tap stations entirely on NFC-capable Android phones:

- Launch the PWA in `mobile_app/` with `python -m http.server 8000 --directory mobile_app`
- Open the URL on an Android phone (Chrome/Edge) and tap **Start NFC scanning**
- Export JSONL/CSV and ingest with `python scripts/ingest_mobile_batch.py --input mobile-export.jsonl`

See `docs/MOBILE_APP_SETUP.md` and `docs/MOBILE_ONLY_VERSION.md` for the full mobile workflow.

### 1. Hardware Setup

**You need:**
- Raspberry Pi Zero 2 WH
- PN532 NFC module (I2C mode)
- NTAG215 NFC cards
- USB-C power bank
- Optional: Piezo buzzer, LEDs

**Wiring:**
```
PN532        Pi GPIO
VCC    →     3.3V (Pin 1)
GND    →     GND (Pin 6)
SDA    →     GPIO 2 (Pin 3)
SCL    →     GPIO 3 (Pin 5)

Buzzer (optional):
Buzzer+ →    GPIO 17 (Pin 11)
Buzzer- →    GND
```

### 2. Installation

Clone this repository on your Raspberry Pi:

```bash
git clone https://github.com/yourusername/nfc-tap-logger.git
cd nfc-tap-logger
```

Run the installation script:

```bash
bash scripts/install.sh
```

This will:
- Install system dependencies (Python, I2C tools)
- Enable I2C interface
- Create virtual environment
- Install Python packages
- Configure systemd service
- Set up directories

**Important:** Reboot after installation if I2C was just enabled:
```bash
sudo reboot
```

**Troubleshooting I2C:** If you encounter I2C issues, see [I2C Setup Guide](docs/I2C_SETUP.md) or run:
```bash
bash scripts/enable_i2c.sh
```

### 3. Verify Hardware

After reboot, verify everything is working:

```bash
source venv/bin/activate
python scripts/verify_hardware.py
```

This checks:
- I2C bus
- PN532 reader
- GPIO/buzzer
- Power/battery
- Database

### 4. Configure Station

Edit `config.yaml` for each Pi:

```yaml
station:
  device_id: "station1"        # Unique per Pi: station1, station2
  stage: "QUEUE_JOIN"          # QUEUE_JOIN or EXIT
  session_id: "festival-2025"  # Same for all stations at event
```

### 5. Initialize Cards

Initialize 100 NFC cards with sequential token IDs:

```bash
source venv/bin/activate
python scripts/init_cards.py --start 1 --end 100
```

Tap each card when prompted. This creates a card mapping file in `data/card_mapping.csv`.

### 6. Deploy

Start the tap station service:

```bash
sudo systemctl start tap-station
```

Monitor logs:

```bash
tail -f logs/tap-station.log
```

The service will:
- Auto-start on boot
- Auto-restart if it crashes
- Log all activity to `logs/tap-station.log`
- Store events in `data/events.db`

### 7. Export Data

After the event, export data to CSV:

```bash
source venv/bin/activate
python scripts/export_data.py
```

This creates `export_YYYYMMDD_HHMMSS.csv` with all event data.

## Usage

### During Event

**Peer workflow:**
1. Hand participant a card: "Tap this at each station"
2. Person taps at Station 1 (queue join) → **BEEP**
3. Person waits for service
4. Person taps at Station 2 (exit) → **BEEP**
5. Done!

**Feedback signals:**
- 1 beep = Success
- 2 quick beeps = Duplicate tap (already logged here)
- 1 long beep = Error (retry)

### Monitoring

Check service status:
```bash
sudo systemctl status tap-station
```

View recent events:
```bash
python -m tap_station.main --stats
```

Check battery:
```bash
vcgencmd get_throttled
# Should return: throttled=0x0
```

### Data Analysis

Load exported CSV in R:

```r
library(tidyverse)

events <- read_csv("export.csv")

# Calculate wait times
flow <- events %>%
  pivot_wider(names_from = stage, values_from = timestamp) %>%
  mutate(
    wait_time = difftime(EXIT, QUEUE_JOIN, units = "mins"),
    total_time = as.numeric(wait_time)
  )

# Median wait time
median(flow$total_time, na.rm = TRUE)

# 90th percentile
quantile(flow$total_time, 0.9, na.rm = TRUE)

# Hourly throughput
events %>%
  filter(stage == "EXIT") %>%
  mutate(hour = floor_date(timestamp, "hour")) %>%
  count(hour)
```

## Project Structure

```
nfc-tap-logger/
├── tap_station/           # Main service code
│   ├── __init__.py
│   ├── main.py           # Entry point
│   ├── config.py         # Configuration loader
│   ├── database.py       # SQLite operations
│   ├── nfc_reader.py     # PN532 wrapper
│   └── feedback.py       # Buzzer/LED control
├── scripts/
│   ├── init_cards.py     # Card initialization
│   ├── export_data.py    # CSV export
│   ├── install.sh        # Installation script
│   └── verify_hardware.py # Hardware verification
├── tests/                # Unit and integration tests
├── docs/                 # Documentation
│   ├── CONTEXT.md        # Project background
│   ├── REQUIREMENTS.md   # Detailed requirements
│   ├── HARDWARE.md       # Hardware details
│   └── WORKFLOWS.md      # User workflows
├── data/                 # Database and card mapping
├── logs/                 # Application logs
├── backups/              # Database backups
├── config.yaml           # Configuration file
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Configuration

### Station Configuration

Each Pi needs unique `device_id` and appropriate `stage`:

**Station 1 (Queue Join):**
```yaml
station:
  device_id: "station1"
  stage: "QUEUE_JOIN"
  session_id: "festival-2025-summer"
```

**Station 2 (Exit):**
```yaml
station:
  device_id: "station2"
  stage: "EXIT"
  session_id: "festival-2025-summer"
```

### GPIO Configuration

Customize GPIO pins in `config.yaml`:

```yaml
feedback:
  buzzer_enabled: true
  led_enabled: true
  gpio:
    buzzer: 17
    led_green: 27
    led_red: 22
```

### Beep Patterns

Customize beep patterns (on/off times in seconds):

```yaml
feedback:
  beep_success: [0.1]              # Short beep
  beep_duplicate: [0.1, 0.05, 0.1] # Double beep
  beep_error: [0.3]                # Long beep
```

## Testing

Run tests without hardware:

```bash
source venv/bin/activate
pytest tests/ -v
```

Tests use mock NFC reader, so they work on any machine.

Run integration tests:

```bash
pytest tests/test_integration.py -v
```

## Troubleshooting

### I2C Not Working / /dev/i2c-1 Not Found

If you see errors like `No such file or directory: '/dev/i2c-1'`:

```bash
# Run the I2C setup script
bash scripts/enable_i2c.sh
```

This script will:
- Check if I2C is enabled
- Enable I2C if needed
- Verify the I2C device exists
- Scan for the PN532 reader
- Provide detailed troubleshooting if issues are found

**Important:** After enabling I2C, you MUST reboot:
```bash
sudo reboot
```

### PN532 Not Detected

```bash
sudo i2cdetect -y 1
```

Should show device at `0x24`. If not:

- Check wiring (VCC to 3.3V, NOT 5V)
- Verify PN532 is in I2C mode (check jumpers)
- Try `sudo i2cdetect -y 0` (some Pis use bus 0)
- Run `bash scripts/enable_i2c.sh` for detailed troubleshooting

### Card Read Fails

- Check card is NTAG215 (not other NFC type)
- Hold card flat against reader for 2-3 seconds
- Try different card (could be faulty)
- Check logs: `tail -f logs/tap-station.log`

### Service Won't Start

```bash
sudo systemctl status tap-station
sudo journalctl -u tap-station -n 50
```

Common issues:
- Config file missing or invalid
- Database directory doesn't exist
- py532lib not installed in venv

### Random Reboots

```bash
vcgencmd get_throttled
```

If not `0x0`:
- Check power bank capacity
- Use better USB cable
- Ensure 5V 2A minimum power supply

### Database Locked

If you see "database is locked" errors:

```bash
# Stop service
sudo systemctl stop tap-station

# Check for lingering processes
ps aux | grep python

# Kill if needed
killall python3

# Restart
sudo systemctl start tap-station
```

## Development

### Running Locally

Test on your laptop without hardware:

```bash
python -m tap_station.main --config config.yaml --mock-nfc
```

This uses mock NFC reader for testing.

### Adding New Features

The code is modular:

- **New stages**: Just add to `config.yaml`, no code changes needed
- **New feedback patterns**: Update `config.yaml`
- **New GPIO pins**: Update `config.yaml`
- **Custom database schema**: Modify `database.py`
- **NDEF writing**: Enhance `nfc_reader.py`

### Code Style

```bash
# Format code
black tap_station/ tests/ scripts/

# Lint
flake8 tap_station/ tests/ scripts/
```

## Advanced Usage

### Multiple Stages

Track more than 2 stages by adding more stations:

```yaml
# Station 3: Consult start
station:
  device_id: "station3"
  stage: "CONSULT_START"

# Station 4: Sample registered
station:
  device_id: "station4"
  stage: "SAMPLE_REGISTERED"
```

### Remote Monitoring

If on same WiFi network:

```bash
ssh pi@raspberrypi.local
tail -f ~/nfc-tap-logger/logs/tap-station.log
```

### Database Backup

Automatic backup on shutdown:

```bash
sudo systemctl stop tap-station
cp data/events.db backups/events_$(date +%Y%m%d).db
```

Or set up periodic backups with cron:

```bash
crontab -e

# Backup every hour
0 * * * * cp ~/nfc-tap-logger/data/events.db ~/nfc-tap-logger/backups/events_$(date +\%Y\%m\%d_\%H).db
```

## Hardware Notes

### Power Consumption

- Pi Zero 2 W: ~200-300mA average (~1.5W)
- 10,000mAh power bank = ~20-30 hours runtime
- More than enough for 8-hour festival day

### Battery Life Tips

Disable WiFi/Bluetooth to save power:

```bash
sudo rfkill block wifi
sudo rfkill block bluetooth
```

Add to `/etc/rc.local` for auto-disable on boot.

### Weatherproofing

Minimal setup:
- Ziplock bag over Pi/reader
- "TAP HERE" label on bag

Better setup:
- Small weatherproof box
- Mount PN532 on lid (accessible)
- Cable gland for power

## Support & Contributing

### Documentation

See `docs/` folder for detailed information:
- `CONTEXT.md`: Why this exists
- `REQUIREMENTS.md`: What it needs to do
- `HARDWARE.md`: Hardware specs and wiring
- `I2C_SETUP.md`: I2C setup and troubleshooting guide
- `TROUBLESHOOTING_FLOWCHART.md`: Step-by-step problem solving
- `WORKFLOWS.md`: How people use it

### Issues

For bugs or feature requests, open an issue on GitHub.

### Contributing

Pull requests welcome! Please:
- Follow existing code style
- Add tests for new features
- Update documentation

## License

MIT License - see LICENSE file for details.

## Credits

Built for NUAA drug checking services.

Uses:
- [py532lib](https://github.com/HubertD/py532lib) - PN532 NFC library
- [RPi.GPIO](https://pypi.org/project/RPi.GPIO/) - Raspberry Pi GPIO

## Changelog

### v1.0.0 (2025-06-15)

Initial release:
- Two-station tap logging (queue join + exit)
- SQLite database with WAL mode
- Buzzer/LED feedback
- Card initialization script
- CSV export
- systemd service
- Hardware verification
- Comprehensive tests
