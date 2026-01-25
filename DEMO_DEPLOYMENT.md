# NSW Health Demo Deployment Guide

This guide explains how to deploy and use the live demo site for NSW Health stakeholder presentations.

## 🎯 Overview

The demo site provides a **live, interactive environment** for NSW Health to evaluate the NFC tap logging system for festival drug checking services. It includes:

- **Live data simulation** - Realistic participant flow automatically generated in the background
- **Multiple view modes** - Public displays, staff dashboards, control panels
- **No hardware required** - Runs in mock mode without NFC readers
- **Production-ready** - Same codebase used for actual deployments

## 🚀 Quick Start (Local Testing)

### Prerequisites

- Python 3.9 or higher
- pip package manager

### Run Locally

```bash
# 1. Install dependencies
pip install -r requirements-web.txt

# 2. Start the demo server
python demo_server.py
```

The server will start on `http://localhost:8080` with:
- ✅ Live data simulation running in background
- ✅ All UI pages accessible
- ✅ Realistic festival activity

### Available Pages

Once running, visit:

| Page | URL | Description |
|------|-----|-------------|
| **Demo Landing** | http://localhost:8080/ | NSW Health demo homepage with navigation |
| **Public Display** | http://localhost:8080/public | Large-format queue display for participants |
| **Staff Dashboard** | http://localhost:8080/dashboard | Real-time metrics and analytics |
| **Activity Monitor** | http://localhost:8080/monitor | Live feed of all taps and events |
| **Control Panel** | http://localhost:8080/control | Admin tools and manual corrections |
| **Shift Summary** | http://localhost:8080/shift | Handoff report for shift changes |
| **Status Check** | http://localhost:8080/check?token=001 | Individual participant status |

## 🎪 Festival Scenario Comparison

The demo includes **three real-world scenarios** based on actual NSW festival deployments. This directly answers: *"How much resources do we need?"*

### Scenario 1: HTID - Success Case ✅

**Single day hardstyle festival** - Manageable demand, service met expectations

```bash
python demo_server.py --scenario htid
```

- **Duration**: 1 day, 6 hours
- **Staffing**: 6 peers, 6 chemists
- **Volume**: 70 groups, 110 samples
- **Queue**: Peak ~15 groups
- **Wait Time**: Max 30 minutes
- **Abandonment**: 2% (very low)
- **Outcome**: ✅ **SUCCESS** - Everyone served, quality conversations, happy participants
- **Lesson**: This staffing level works for moderate-demand single-day festivals

### Scenario 2: Lost Paradise (Actual) - Capacity Crisis ⚠️

**Multi-day festival - OVERWHELMED** - Same staffing, way more demand

```bash
python demo_server.py --scenario lost_paradise_actual
```

- **Duration**: 2 days, 6 hours/day
- **Staffing**: 6 peers, 6 chemists (SAME AS HTID!)
- **Volume**: 150 groups, 300 samples (over 2 days)
- **Queue**: Peak **60+ groups** (line out the door!)
- **Wait Time**: Max **3 HOURS**
- **Abandonment**: **25%** (many turned away)
- **Outcome**: ❌ **CRITICAL FAILURE** - Severe understaffing, staff burnout, many participants couldn't access service
- **Lesson**: Multi-day festivals need scaled resources - current model doesn't work

### Scenario 3: Lost Paradise (Ideal) - Proper Resourcing ⭐

**Same festival, DOUBLED staff** - Shows ROI of proper investment

```bash
python demo_server.py --scenario lost_paradise_ideal
```

- **Duration**: 2 days, 6 hours/day
- **Staffing**: **12 peers, 12 chemists** (DOUBLED!)
- **Capacity**: 250+ groups, 500+ samples
- **Queue**: Peak ~20 groups (manageable)
- **Wait Time**: Max 45 minutes
- **Abandonment**: 3% (minimal)
- **Outcome**: ✅ **SUCCESS** - Demand met, quality harm reduction, sustainable staffing
- **Lesson**: Proper resourcing enables quality service at scale

### Interactive Scenario Switcher

The demo landing page includes an **interactive scenario selector**:
- Click any scenario card to switch
- Visual comparison of staffing vs outcomes
- Color-coded: Green (success), Red (crisis)
- Real-time stats update for each scenario

This makes it easy to show stakeholders:
1. What you're currently achieving (HTID)
2. What happens when you're understaffed (Lost Paradise actual - 3hr waits!)
3. What's possible with proper investment (Lost Paradise ideal)

## ☁️ Cloud Deployment Options

### Option 1: Render.com (Recommended - Free Tier Available)

Render provides automatic deployments from GitHub with a free tier perfect for demos.

#### Setup Steps:

1. **Push code to GitHub**
   ```bash
   git push origin main
   ```

2. **Create Render account**
   - Go to https://render.com
   - Sign up with GitHub

3. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository: `zophiezlan/nfc-tap-logger`
   - Select branch: `main`

4. **Configure Service**
   - **Name**: `nfc-tap-logger-demo` (or choose your own)
   - **Region**: Oregon (or closest to Australia)
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements-web.txt`
   - **Start Command**: `python demo_server.py`
   - **Plan**: Free

5. **Environment Variables** (optional)
   - `PYTHON_VERSION`: `3.9.0`
   - `DEMO_MODE`: `true`

6. **Deploy**
   - Click "Create Web Service"
   - Render will build and deploy automatically
   - You'll get a URL like: `https://nfc-tap-logger-demo.onrender.com`

#### Auto-Deploy

Once set up, Render will automatically redeploy whenever you push to the branch!

### Option 2: Railway.app (Alternative)

Railway offers similar features with a generous free tier.

1. **Sign up**: https://railway.app
2. **New Project** → Deploy from GitHub
3. **Settings**:
   - Build Command: `pip install -r requirements-web.txt`
   - Start Command: `python demo_server.py`
   - Add Port: 8080

### Option 3: Fly.io (For Australian Hosting)

Fly.io lets you deploy to Sydney region for lower latency.

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
flyctl auth login

# Deploy
flyctl launch
```

When prompted:
- App name: `nfc-tap-logger-demo`
- Region: `Sydney, Australia (syd)`
- Postgres: No
- Redis: No

Create `fly.toml`:
```toml
app = "nfc-tap-logger-demo"
primary_region = "syd"

[build]
  builder = "paketobuildpacks/builder:base"

[env]
  PORT = "8080"
  DEMO_MODE = "true"

[[services]]
  internal_port = 8080
  protocol = "tcp"

  [[services.ports]]
    handlers = ["http"]
    port = 80

  [[services.ports]]
    handlers = ["tls", "http"]
    port = 443
```

Then deploy:
```bash
flyctl deploy
```

## 🎭 Demo Features

### Live Data Simulation

The demo automatically generates realistic festival activity:

- **Arrival Rate**: ~2-3 participants per minute
- **Service Time**: 5-12 minutes average (realistic variation)
- **Queue Dynamics**: Some participants abandon queue (~5%)
- **Multi-stage Flow**: Queue → Testing → Results → Exit

### Service Workflow

The demo simulates a drug checking service with 4 stages:

1. **QUEUE_JOIN** - Participant taps in to join queue
2. **SERVICE_START** - Staff begins testing substance
3. **SUBSTANCE_RETURNED** - Results delivered, substance returned
4. **EXIT** - Service complete, participant exits

### Configurable Settings

All aspects can be customized via configuration files:

- `service_config.yaml` - Workflow, alerts, UI messages
- Capacity metrics (throughput, service times)
- Alert thresholds (queue length, wait times)
- Display settings and branding

## 📊 What NSW Health Can Explore

### For Decision Makers

- **Public Display** (`/public`) - See what participants see on tablets/TVs
- **Dashboard** (`/dashboard`) - Operational metrics and real-time monitoring
- **Shift Summary** (`/shift`) - Volunteer handoff reports

### For Operations Staff

- **Activity Monitor** (`/monitor`) - Live event feed and anomaly detection
- **Control Panel** (`/control`) - Administrative tools and manual corrections
- **Individual Status** (`/check?token=XXX`) - Participant journey tracking

### For Technical Teams

- **API Endpoints** - All data available via JSON APIs
  - `/api/stats` - General statistics
  - `/api/dashboard` - Dashboard data
  - `/api/public` - Public display data
  - `/api/control/status` - System status
  - `/api/export` - CSV data export

- **Database Access** - SQLite database at `data/demo_events.db`
- **Source Code** - Full codebase available for review

## 🔧 Customization for NSW Health

### Branding

Edit `demo_server.py` to customize:

```python
'service': {
    'name': 'NSW Festival Drug Checking Service',
    'organization': 'NSW Health - Harm Reduction',
    'description': 'Free, confidential substance testing service',
    'branding': {
        'primary_color': '#0066cc',  # NSW Health blue
        'secondary_color': '#00cc66'
    }
}
```

### Workflow Stages

Modify the workflow stages to match your process:

```python
'workflow': {
    'stages': [
        {
            'id': 'QUEUE_JOIN',
            'name': 'Join Queue',
            'action_label': 'Tap to Join Queue',
            'success_message': 'You\'re in the queue!'
        },
        # Add or modify stages as needed
    ]
}
```

### Capacity Planning

Adjust expected throughput and alert thresholds:

```python
'capacity': {
    'expected_throughput_per_hour': 20,  # How many people/hour
    'average_service_time_minutes': 10,  # Avg service duration
    'max_queue_length': 50
},
'alerts': {
    'queue_length_warning': 15,  # Yellow alert
    'queue_length_critical': 25,  # Red alert
    'wait_time_warning_minutes': 30,
    'wait_time_critical_minutes': 60
}
```

## 🐛 Troubleshooting

### Demo not showing live data?

Check that the background simulator started:
```
✅ Background simulator started
```

If not, check Python version (needs 3.9+) and dependencies.

### Port already in use?

Change the port in `demo_server.py`:
```python
'port': int(os.environ.get('PORT', 8080))  # Try 8081, 8082, etc.
```

### Database errors?

The demo creates its own database. If issues occur:
```bash
rm -rf data/demo_events.db
python demo_server.py  # Will recreate database
```

## 📝 Next Steps After Demo

### Feedback Collection

Use the demo to workshop:
- **UI/UX preferences** - What works, what doesn't?
- **Workflow customization** - Does the 4-stage flow match your process?
- **Alert thresholds** - What queue lengths/wait times trigger concerns?
- **Display preferences** - Public display size, refresh rates, information shown
- **Integration needs** - Reporting, data export, third-party systems

### Pilot Deployment

Once approved, the same codebase deploys to:
- **Raspberry Pi Zero 2 W** - Low cost (~$50 AUD per station)
- **PN532 NFC Reader** - Reliable, tested hardware (~$15 AUD)
- **NFC Cards/Tags** - Reusable, washable (~$0.50-1 each)

### Training Materials

The demo can be used to:
- Train staff on the interface
- Create volunteer orientation materials
- Document standard operating procedures
- Test workflow modifications before events

## 🔗 Resources

- **GitHub Repository**: https://github.com/zophiezlan/nfc-tap-logger
- **Documentation**: See `/docs` folder for technical details
- **Service Configuration Guide**: `docs/SERVICE_CONFIGURATION.md`
- **Hardware Setup**: `docs/HARDWARE_SETUP.md` (for future pilot)

## 💬 Support

For questions or customization requests during the demo review:
- Open a GitHub issue
- Contact the development team
- Request a workshop session to discuss specific requirements

---

**NSW Health Drug Checking Service Demo** | 2026
