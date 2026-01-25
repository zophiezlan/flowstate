# 🎪 NSW Health Drug Checking Demo

**Live, interactive demo site for NSW Health stakeholder presentations**

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements-web.txt

# Start the demo
python demo_server.py
```

Visit **http://localhost:8080** - the demo landing page will guide you through all features.

## ✨ What's Included

- **Live Data Simulation** - Realistic participant flow automatically generated
- **Multiple View Modes** - Public displays, staff dashboards, control panels
- **NSW Health Branding** - Customized for drug checking services
- **No Hardware Required** - Runs in mock mode without NFC readers

## 📺 Key Demo Pages

| Page | Best For | URL |
|------|----------|-----|
| **Landing Page** | Overview & navigation | / |
| **Public Display** | What participants see | /public |
| **Staff Dashboard** | Operational metrics | /dashboard |
| **Control Panel** | Admin functions | /control |

## ☁️ Deploy to Cloud

### Render.com (Recommended)

1. Push code to GitHub
2. Create account at https://render.com
3. New Web Service → Connect GitHub repo
4. Configure:
   - **Build Command**: `pip install -r requirements-web.txt`
   - **Start Command**: `python demo_server.py`
   - **Branch**: `main`

**See [DEMO_DEPLOYMENT.md](DEMO_DEPLOYMENT.md) for detailed deployment guides.**

## 🎯 For NSW Health

This demo simulates a complete drug checking workflow:

1. **QUEUE_JOIN** - Participant taps in to join queue
2. **SERVICE_START** - Staff begins substance testing
3. **SUBSTANCE_RETURNED** - Results delivered
4. **EXIT** - Service complete

All features are **fully configurable** to match your specific workflow and requirements.

## 💡 Next Steps

1. **Explore the demo** - Try all the different view modes
2. **Workshop feedback** - What works? What doesn't?
3. **Customize workflow** - We can adapt to your exact process
4. **Plan pilot** - Same code deploys to Raspberry Pi hardware

## 📖 Documentation

- [Full Deployment Guide](DEMO_DEPLOYMENT.md) - Cloud deployment options
- [Service Configuration](docs/SERVICE_CONFIGURATION.md) - Customization guide
- [Main README](README.md) - Complete project documentation

## 🤝 Feedback

During your evaluation, consider:

- Is the public display clear for participants?
- Does the staff dashboard show the right metrics?
- Does the workflow match your service flow?
- What additional features would be valuable?

---

**Questions?** Open an issue or request a workshop session to discuss specific requirements.
