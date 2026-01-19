# NFC Tap Logger

**A simple, reliable system for tracking wait times at festival harm reduction services using NFC tap stations.**

Two tap stations measure queue flow: participants tap their NFC card when joining the queue and again when exiting. The system logs timestamps to calculate wait times, throughput, and service metrics.

**Designed for:** Festival peer workers who need a dead-simple, network-free system that runs all day on battery power.

## Why This Exists

Drug checking services at festivals need data to optimize flow, measure impact, and report to funders—but currently rely on manual estimates. This system provides accurate metrics with minimal technical burden on peer workers operating in chaotic, outdoor environments.

**Key metrics:**

- Median & 90th percentile wait times
- Hourly throughput
- Abandonment rate (joined but didn't complete)

## Quick Links

- **🚀 [Setup Guide](docs/SETUP.md)** - Hardware wiring & software installation
- **⚙️ [Service Configuration Guide](docs/SERVICE_CONFIGURATION.md)** - **NEW!** Customize for your festival service
- **🆔 [Auto-Initialize Cards](docs/AUTO_INIT_CARDS.md)** - **NEW!** Use fresh cards without pre-initialization
- **⏱️ [Wait Time Metrics Guide](docs/WAIT_TIME_METRICS.md)** - **NEW!** Understanding queue wait vs. service time
- **🤝 [Substance Return Confirmation](docs/SUBSTANCE_RETURN_CONFIRMATION.md)** - **NEW!** Accountability for substance handback
- **📱 [Mobile App Guide](docs/MOBILE.md)** - Use Android phones instead of Raspberry Pis
- **📋 [Operations Guide](docs/OPERATIONS.md)** - Day-of-event workflow, live monitoring & decision-making
- **✅ [Pre-Deployment Checklist](docs/PRE_DEPLOYMENT_CHECKLIST.md)** - Ensure you're ready before your event
- **📊 [Live Dashboard](#live-monitoring)** - Real-time queue tracking & operational metrics
- **🔥 [New Features Guide](docs/NEW_FEATURES.md)** - Public display, enhanced alerts, shift summaries
- **🎛️ [Control Panel](docs/CONTROL_PANEL.md)** - Web-based system administration
- **🔧 [Troubleshooting](docs/TROUBLESHOOTING.md)** - Fix common issues
- **💻 [Contributing](CONTRIBUTING.md)** - For developers

## What's New (v2.4)

**🆔 Auto-Initialize Cards on First Tap:**

- **Dynamic Card Initialization** - No need to pre-initialize cards before events
- **Sequential Assignment** - System automatically assigns next available token ID
- **Saves Setup Time** - Just hand out blank cards and let the system handle numbering
- **Lost Card Recovery** - When cards are stolen/lost, numbering stays sequential without gaps
- **Optional Feature** - Enable/disable per event via configuration

**⏱️ Enhanced Wait Time Metrics:**

- **Separate Queue Wait & Service Time** - Distinguish between waiting and being served
- **Better Estimates** - Queue wait time (highly variable) vs. service time (consistent)
- **Improved Dashboard** - Clear display of both metrics with explanations
- **Documentation** - Comprehensive guide on understanding and using wait time data

See [Auto-Initialize Cards Guide](docs/AUTO_INIT_CARDS.md) and [Wait Time Metrics Guide](docs/WAIT_TIME_METRICS.md) for details.

**v2.3 - Substance Return Confirmation:**

- **Substance Return Tracking** - Track when participants' substances are returned after testing
- **Accountability & Trust** - Prevent "left behind" incidents with formal confirmation system
- **Unreturned Substance Alerts** - Proactive alerts when substances not returned within threshold
- **Audit Trail** - Complete timestamped record of substance custody and handback
- **Configurable Workflow** - Add SUBSTANCE_RETURNED stage to any service workflow

See [Substance Return Confirmation Guide](docs/SUBSTANCE_RETURN_CONFIRMATION.md) for setup and best practices.

**v2.2.1 - Quick Wins for Event Operations:**

- **Force-Exit Tool** - Mark stuck cards as exited in bulk at end of events (Control Panel)
- **Real-Time Export** - One-click CSV downloads directly from dashboard (no SSH needed)

**v2.2 - 3-Stage Tracking:**

- **3-Stage Service Tracking** - Separate queue wait from service time (QUEUE_JOIN → SERVICE_START → EXIT)

**v2.1 - Enhanced Operational Intelligence:**

- **Public Queue Display** (`/public`) - Large, simple display showing current wait times for participants
- **Enhanced Staff Alerts** - Proactive monitoring for station failures, long waits, and operational issues
- **Shift Summary** (`/shift`) - Quick handoff information for shift changes
- **Activity Monitoring** - Automatic detection of stuck cards, service anomalies, and capacity issues

See [Force-Exit & Export Guide](docs/FORCE_EXIT_AND_EXPORT.md), [3-Stage Tracking Guide](docs/3_STAGE_TRACKING.md), and [New Features Guide](docs/NEW_FEATURES.md) for details.

## ⚙️ Configurable for Any Festival Service

**NEW:** The system is now fully configurable for different festival-based community drug checking services!

Different services have different needs:
- **Workflow**: Simple queue (join→exit) vs. comprehensive (intake→test→results→exit)
- **Capacity**: 5 people/hour vs. 20 people/hour
- **Staffing**: Single peer worker vs. specialized roles (intake, testing, counseling)
- **Locations**: Single tent vs. multiple service points across festival
- **Alerts**: Different thresholds based on your capacity and goals

**Customize everything** via `service_config.yaml`:
- Service name, hours, and branding
- Custom workflow stages matching your process
- Alert thresholds for your service capacity
- UI labels and terminology
- Multi-location support
- Staffing roles and permissions

**Example configurations provided:**
- Simple queue service (popup/small festivals)
- Comprehensive testing service (large festivals)
- Multi-location festival service

👉 **[Service Configuration Guide](docs/SERVICE_CONFIGURATION.md)** - Complete customization guide with examples

## System Overview

### Hardware (Raspberry Pi version)

- 2× Raspberry Pi Zero 2 W
- 2× PN532 NFC readers (I2C)
- 100× NTAG215 NFC cards
- 2× USB-C power banks
- Optional: Buzzers for audio feedback

### Hardware (Mobile version)

- 2× Android phones with NFC (Chrome/Edge browser)
- NTAG215 NFC cards
- Laptop for data export/analysis

### Software Architecture

- Python 3.9+ with `pn532pi` library
- SQLite database (WAL mode for crash resistance)
- Flask web server for live dashboard & status checks
- systemd service for auto-start/restart
- Real-time operational analytics

## Quick Start (Raspberry Pi)

**1. Wire the hardware**

```
PN532 → Pi GPIO
VCC   → Pin 1 (3.3V)
GND   → Pin 6 (GND)
SDA   → Pin 3 (GPIO 2)
SCL   → Pin 5 (GPIO 3)
```

**2. Install software**

```bash
git clone https://github.com/zophiezlan/nfc-tap-logger.git
cd nfc-tap-logger
bash scripts/install.sh
sudo reboot
```

**3. Configure station**
Edit `config.yaml`:

```yaml
station:
  device_id: "station1" # station1 or station2
  stage: "QUEUE_JOIN" # QUEUE_JOIN or EXIT
  session_id: "festival-2026-01"
```

**4. Verify & run**

```bash
bash scripts/verify_deployment.sh
sudo systemctl start tap-station
```

**5. Initialize cards**

```bash
source venv/bin/activate
python scripts/init_cards.py --start 1 --end 100
```

The script automatically handles conflicts with running services - no manual cleanup needed!

**6. Manual reset (if needed)**

In rare cases where automatic cleanup fails:

```bash
# Quick reset (no sudo)
python3 scripts/dev_reset.py

# Full reset with I2C bus reset (needs sudo)
sudo bash scripts/dev_reset.sh
```

**Need detailed instructions?** See the [Setup Guide](docs/SETUP.md).

## Quick Start (Mobile App)

**1. Serve the app**

```bash
python -m http.server 8000 --directory mobile_app
```

**2. Open on Android phone**

- Navigate to `http://<laptop-ip>:8000`
- Add to home screen for offline use

**3. Configure & scan**

- Set session ID, stage (QUEUE_JOIN/EXIT), device ID
- Tap "Start NFC scanning"
- Present NFC cards to log taps

**4. Export & ingest data**

```bash
# On phone: Download JSONL
# On laptop:
python scripts/ingest_mobile_batch.py --input mobile-export.jsonl
```

**Need detailed instructions?** See the [Mobile Guide](docs/MOBILE.md).

---

## Live Monitoring

The system includes powerful real-time dashboards for operational management during your event.

### Access Dashboards

Once the system is running, access dashboards from any device on the same network:

```
# Full analytics dashboard (for coordinators)
http://<pi-ip-address>:8080/dashboard

# Simplified monitor (for peer workers)
http://<pi-ip-address>:8080/monitor

# Control panel (for administrators)
http://<pi-ip-address>:8080/control
```

**Find your Pi's IP address:**

```bash
hostname -I
```

**Security Note:** The control panel provides system administration capabilities. Keep your Pi on a private network and only share the control panel URL with trusted administrators.

### Dashboard Features

#### 📊 Full Dashboard (`/dashboard`)

**For coordinators and decision-makers**

- **Real-time metrics:**
  - People in queue right now
  - Estimated wait time for new arrivals
  - Longest current wait (time in service)
  - Capacity utilization
  - Throughput per hour

- **Operational alerts:**
  - 🟢 Green: All systems normal
  - 🟡 Yellow: Queue getting busy (>10 people or >45min wait)
  - 🔴 Red: Critical conditions (>20 people or >90min wait)

- **Queue details:**
  - Position in queue (#1, #2, etc.)
  - Time each person has been waiting
  - Real-time updates every 5 seconds

- **Activity visualization:**
  - 12-hour activity chart
  - Recent completions with wait times
  - Live event feed showing all taps

#### 📱 Simplified Monitor (`/monitor`)

**For peer workers and quick status checks**

- Large, easy-to-read display optimized for mobile/tablet
- Critical metrics only:
  - People waiting
  - Estimated wait time
  - Simple status indicators
- Color-coded alerts (green/yellow/red)
- No clutter - just what you need to know

### Using Live Data Operationally

**At Queue Entry:**

- Communicate current wait time to arrivals
- Adjust staffing based on queue length alerts

**During Service:**

- Monitor longest wait to prioritize people
- Track throughput to identify bottlenecks
- Use alerts to make staffing decisions

**Example scenarios:**

```
🟢 Queue: 3 people, Est. wait: 15min
→ All good, normal operations

🟡 Queue: 12 people, Est. wait: 35min, Longest wait: 47min
→ Monitor closely, consider calling extra volunteer

🔴 Queue: 24 people, Est. wait: 65min, Longest wait: 95min
→ URGENT: Add resources, prioritize longest waiters
```

See the [Operations Guide](docs/OPERATIONS.md) for detailed guidance on interpreting metrics and making operational decisions.

### Control Panel (`/control`)

**Administrative interface for system management** - No SSH required!

Execute common tasks through a web interface:

- **Service Management:** Start/stop/restart tap-station service
- **Diagnostics:** Verify hardware, run health checks, scan I2C devices
- **Data Operations:** Export data, backup database, view recent events
- **System Control:** Reboot, shutdown, view logs, check disk space
- **Development:** Reset I2C, test card reading, run tests

**Key Benefits:**

- Execute commands without SSH access
- Real-time command output display
- Safety confirmations for destructive operations
- Quick troubleshooting during events
- One-click data export and backup

**Security:** Keep your Pi on a private network. Only share control panel URL with trusted administrators.

---

## Project Features

### Core Functionality

- **Dual-stage logging:** Track entry and exit timestamps
- **Offline operation:** No network required
- **Crash-resistant:** SQLite WAL mode, auto-restart service
- **Debouncing:** Prevents duplicate taps within configurable window
- **Audio/visual feedback:** Buzzer beeps and LEDs for user confirmation

### Data Management

- **SQLite database:** Reliable storage with automatic backups
- **CSV export:** Compatible with R, Python, Excel
- **Card mapping:** Track which physical card corresponds to which participant
- **Session support:** Multiple events/sessions in same database

### Monitoring

- **Web status server:** HTTP endpoints for health checks
- **Live statistics:** View tap counts and recent events
- **Detailed logging:** Rotating log files for troubleshooting
- **Power monitoring:** Detect under-voltage conditions

### Mobile Support

- **Progressive Web App:** Run on Android phones with NFC
- **Offline-first:** Works without network after initial load
- **JSONL/CSV export:** Same data format as Pi version
- **Hybrid deployments:** Mix Pi and mobile stations

---

## Usage Examples

### View Station Statistics

```bash
python -m tap_station.main --stats
```

### Monitor Service

```bash
# Check status
sudo systemctl status tap-station

# View live logs
tail -f logs/tap-station.log

# Check power
vcgencmd get_throttled
```

### Export & Analyze Data

```bash
# Export to CSV
python scripts/export_data.py

# Analyze in Python
import pandas as pd

df = pd.read_csv('export_20260116_143000.csv')

# Calculate wait times
pivoted = df.pivot_table(
    values='timestamp',
    index='token_id',
    columns='stage'
)
pivoted['wait_time'] = (
    pd.to_datetime(pivoted['EXIT']) -
    pd.to_datetime(pivoted['QUEUE_JOIN'])
)

print(f"Median wait: {pivoted['wait_time'].median()}")
print(f"90th percentile: {pivoted['wait_time'].quantile(0.9)}")
```

---

## Project Structure

```
nfc-tap-logger/
├── tap_station/              # Main application
│   ├── main.py              # Service entry point
│   ├── config.py            # Configuration management
│   ├── database.py          # SQLite operations
│   ├── nfc_reader.py        # PN532 NFC interface
│   ├── feedback.py          # Buzzer/LED control
│   ├── web_server.py        # Flask server (dashboards + control panel)
│   ├── ndef_writer.py       # NDEF writing (NFC Tools)
│   └── templates/           # Web interface templates
│       ├── dashboard.html   # Full analytics dashboard
│       ├── monitor.html     # Simplified peer worker view
│       ├── control.html     # System administration panel
│       ├── index.html       # Landing page
│       ├── status.html      # Participant status check
│       └── error.html       # Error display
├── scripts/                  # Utility scripts
│   ├── install.sh           # Automated installation
│   ├── verify_hardware.py   # Hardware diagnostics
│   ├── verify_deployment.sh # Full system verification
│   ├── init_cards.py        # Card initialization
│   ├── init_cards_with_ndef.py # NDEF card programming
│   ├── export_data.py       # Data export
│   ├── ingest_mobile_batch.py  # Mobile data import
│   ├── health_check.py      # Remote health monitoring
│   ├── service_manager.py   # Service control utility
│   ├── dev_reset.py         # Development reset tool
│   ├── setup_wizard.py      # Interactive configuration
│   └── enable_i2c.sh        # I2C setup automation
├── mobile_app/              # Progressive Web App
│   ├── index.html           # App interface
│   ├── app.js               # NFC scanning logic
│   ├── service-worker.js    # Offline support
│   ├── style.css            # Styling
│   └── manifest.webmanifest # PWA manifest
├── tests/                   # Test suite
│   ├── test_config.py       # Configuration tests
│   ├── test_database.py     # Database tests
│   ├── test_nfc_reader.py   # NFC reader tests
│   ├── test_web_server.py   # Web server tests
│   ├── test_integration.py  # End-to-end tests
│   └── test_mobile_ingest.py # Mobile ingest tests
├── docs/                    # Documentation
│   ├── SETUP.md            # Installation & setup
│   ├── OPERATIONS.md       # Day-of-event operations
│   ├── PRE_DEPLOYMENT_CHECKLIST.md # Pre-event verification
│   ├── CONTROL_PANEL.md    # Control panel reference
│   ├── TROUBLESHOOTING.md  # Problem solving
│   ├── MOBILE.md           # Mobile app guide
│   └── ROADMAP.md          # Future plans
├── data/                    # Database & mappings
│   ├── events.db           # Main event database
│   └── card_mapping.csv    # Card UID → Token ID
├── logs/                    # Application logs
│   └── tap-station.log     # Rotating logs
├── backups/                 # Database backups
├── config.yaml              # Configuration file
├── config.yaml.example      # Configuration template
├── requirements.txt         # Python dependencies
├── tap-station.service      # systemd service file
├── CONTRIBUTING.md          # Developer guide
├── PRODUCTION_READINESS.md  # Production status report
└── README.md               # This file
```

│ ├── web_server.py # Flask status server
│ └── ndef_writer.py # NDEF writing (NFC Tools)
├── scripts/ # Utility scripts
│ ├── install.sh # Automated installation
│ ├── verify_hardware.py # Hardware diagnostics
│ ├── init_cards.py # Card initialization
│ ├── export_data.py # Data export
│ ├── ingest_mobile_batch.py # Mobile data import
│ └── health_check.py # Remote health monitoring
├── mobile_app/ # Progressive Web App
│ ├── index.html # App interface
│ ├── app.js # NFC scanning logic
│ ├── service-worker.js # Offline support
│ └── manifest.webmanifest # PWA manifest
├── tests/ # Test suite
├── docs/ # Documentation
│ ├── SETUP.md # Installation & setup
│ ├── OPERATIONS.md # Day-of-event guide
│ ├── TROUBLESHOOTING.md # Problem solving
│ ├── MOBILE.md # Mobile app guide
│ └── CONTRIBUTING.md # Developer guide
├── data/ # Database & mappings
│ ├── events.db # Main event database
│ └── card_mapping.csv # Card UID → Token ID
└── logs/ # Application logs
└── tap-station.log # Rotating logs
├── backups/ # Database backups
├── config.yaml # Configuration file
├── requirements.txt # Python dependencies
└── README.md # This file

````

## Configuration

### Station Configuration

Each Pi needs unique `device_id` and appropriate `stage`:

**Station 1 (Queue Join):**

```yaml
station:
  device_id: "station1"
  stage: "QUEUE_JOIN"
  session_id: "festival-2025-summer"
````

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
  beep_success: [0.1] # Short beep
  beep_duplicate: [0.1, 0.05, 0.1] # Double beep
  beep_error: [0.3] # Long beep
```

## Testing

Run tests without hardware:

```bash
source venv/bin/activate
pytest tests/ -v
```

Tests use mock NFC reader, so they work on any machine.

---

## Common Issues

**See the [Troubleshooting Guide](docs/TROUBLESHOOTING.md) for comprehensive problem-solving.**

Quick fixes:

**I2C not working:**

```bash
bash scripts/enable_i2c.sh
sudo reboot
```

**PN532 not detected:**

```bash
sudo i2cdetect -y 1  # Should show device at 0x24
```

**Service won't start:**

```bash
sudo journalctl -u tap-station -n 50
```

**Card read fails:**

- Use NTAG215 cards
- Hold flat for 2+ seconds
- Check logs: `tail -f logs/tap-station.log`

---

## License & Credits

**License:** MIT - See LICENSE file

**Built for:** Festival drug checking services

**Key dependencies:**

- [pn532pi](https://pypi.org/project/pn532pi/) - PN532 NFC library
- [RPi.GPIO](https://pypi.org/project/RPi.GPIO/) - GPIO control
- [Flask](https://flask.palletsprojects.com/) - Web status server
- [ndeflib](https://ndeflib.readthedocs.io/) - NDEF writing

---

## Version History

**v1.1 (Current)**

- Mobile Progressive Web App support
- Web status server with health endpoints
- NDEF writing for NFC Tools integration
- Improved hardware verification
- Mobile data ingest script

**v1.0**

- Initial release
- Dual-station tap logging
- SQLite with WAL mode
- Buzzer/LED feedback
- systemd service with auto-restart

---

**Questions?** Check the docs or open a GitHub issue. Happy logging! 🎉
