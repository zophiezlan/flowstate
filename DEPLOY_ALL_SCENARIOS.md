# Deploy All 3 Scenarios to Render.com

This guide shows how to deploy all three festival scenarios so NSW Health can click between them.

## 🎯 Why Deploy All Three?

- **Side-by-side comparison** - Open all 3 URLs in different tabs
- **Instant switching** - No need to restart servers
- **Always running** - Live demos 24/7 for stakeholders
- **Free tier** - Render.com free tier for all 3

## 🚀 Quick Deploy (15 minutes total)

### Step 1: Get Render.com Account

1. Go to https://render.com
2. Sign up with GitHub
3. Connect your `zophiezlan/nfc-tap-logger` repository

### Step 2: Deploy Scenario 1 - HTID ✅

1. **New Web Service** → Select your repo
2. **Settings:**
   - **Name:** `nfc-demo-htid`
   - **Branch:** `main`
   - **Build Command:** `pip install -r requirements-web.txt`
   - **Start Command:** `python demo_server.py --scenario htid`
   - **Instance Type:** Free

3. **Environment Variables:**
   ```
   DEMO_SCENARIO=htid
   PYTHON_VERSION=3.9.0
   ```

4. **Deploy** (takes ~3 minutes)

5. **Your URL:** `https://nfc-demo-htid.onrender.com`

### Step 3: Deploy Scenario 2 - Lost Paradise (Actual) 🔴

1. **New Web Service** → Same repo
2. **Settings:**
   - **Name:** `nfc-demo-lost-paradise-actual`
   - **Branch:** `main`
   - **Build Command:** `pip install -r requirements-web.txt`
   - **Start Command:** `python demo_server.py --scenario lost_paradise_actual`
   - **Instance Type:** Free

3. **Environment Variables:**
   ```
   DEMO_SCENARIO=lost_paradise_actual
   PYTHON_VERSION=3.9.0
   ```

4. **Deploy**

5. **Your URL:** `https://nfc-demo-lost-paradise-actual.onrender.com`

### Step 4: Deploy Scenario 3 - Lost Paradise (Ideal) ⭐

1. **New Web Service** → Same repo
2. **Settings:**
   - **Name:** `nfc-demo-lost-paradise-ideal`
   - **Branch:** `main`
   - **Build Command:** `pip install -r requirements-web.txt`
   - **Start Command:** `python demo_server.py --scenario lost_paradise_ideal`
   - **Instance Type:** Free

3. **Environment Variables:**
   ```
   DEMO_SCENARIO=lost_paradise_ideal
   PYTHON_VERSION=3.9.0
   ```

4. **Deploy**

5. **Your URL:** `https://nfc-demo-lost-paradise-ideal.onrender.com`

---

## 📧 Share With NSW Health

Once all 3 are deployed, send this email:

```
Subject: NSW Drug Checking Demo - Live Festival Scenarios

Hi [Name],

I've set up three live demos of the queue management system showing different
real-world festival scenarios. Each runs 24/7 with realistic participant flow.

🎵 HTID (Success Case)
https://nfc-demo-htid.onrender.com
- What works for single-day festivals
- 6 peers, 6 chemists | 70 groups | 30 min max wait

🌴 Lost Paradise (What Happened - Crisis)
https://nfc-demo-lost-paradise-actual.onrender.com
- Same 6+6 staffing with multi-day demand
- Queue hits 60+ people | 3 HOUR waits | 25% turned away

🌟 Lost Paradise (What's Possible - Solution)
https://nfc-demo-lost-paradise-ideal.onrender.com
- Doubled staffing (12+12)
- Queue stays under 20 | <45 min waits | Everyone served

Suggested viewing:
1. Open all 3 in separate browser tabs
2. Compare the dashboards side-by-side
3. Watch the queue lengths and wait times

Each scenario runs independently. The data you see is generated in real-time
based on actual NSW festival deployments.

Try these views:
- Dashboard: Real-time metrics and alerts
- Public Display: What participants see on TVs
- Control Panel: Admin tools and reporting

Happy to schedule a walkthrough or answer questions!

[Your name]
```

---

## 🎭 Pro Tips

### For Presentations

Open all 3 dashboards in browser tabs:

**Tab 1:** HTID - "This is manageable"
- Point out the steady queue
- Show the ~30 min waits
- Green metrics

**Tab 2:** Lost Paradise Actual - "This is the problem"
- Queue exploding to 60+
- Red critical alerts
- 180+ minute waits
- Abandonment warnings

**Tab 3:** Lost Paradise Ideal - "This is the solution"
- Manageable queue
- Double the throughput
- Everyone served

### Auto-Refresh

Render free tier instances spin down after 15 mins of inactivity.

**Before a presentation:**
- Visit all 3 URLs to wake them up
- Wait 30 seconds for simulation to start
- Refresh to see live data flowing

### Screenshots

If you need static screenshots:
1. Let each demo run for 5+ minutes
2. Screenshot the dashboard
3. Use in presentations

---

## 💰 Cost

**FREE!** 🎉

Render.com free tier includes:
- 750 hours/month per service
- All 3 scenarios = 2250 hours available
- More than enough for continuous demo

Only limits:
- Spins down after 15 min idle (wakes up in ~30 sec)
- Good enough for demos and presentations

---

## 🔧 Troubleshooting

**Demo not showing data?**
- Wait 30 seconds after first visit
- Background simulator needs to start
- Refresh the page

**"Service Unavailable"?**
- Instance is spinning up (free tier)
- Wait 30 seconds and refresh
- Visit URL 5 min before presentation to pre-warm

**Want to update?**
- Just push to GitHub
- Render auto-redeploys
- Takes ~3 min to rebuild

---

## 📊 What NSW Health Will See

**HTID Dashboard:**
```
Active Now: 8
In Queue: 12
Total Served: 47
Est Wait: 28 min

✅ All systems normal
```

**Lost Paradise Actual Dashboard:**
```
Active Now: 6
In Queue: 54
Total Served: 89
Est Wait: 167 min

🔴 CRITICAL: Queue length 54 (threshold: 50)
🔴 CRITICAL: Wait time 167 min (threshold: 150)
⚠️  Many participants abandoning queue
```

**Lost Paradise Ideal Dashboard:**
```
Active Now: 18
In Queue: 14
Total Served: 178
Est Wait: 32 min

✅ All systems normal
✅ Meeting demand effectively
```

**The contrast is stark and undeniable.**

---

## 🎯 Next Steps

1. Deploy all 3 scenarios (15 min)
2. Test each URL yourself
3. Share URLs with NSW Health
4. Let them explore independently
5. Schedule workshop to discuss

This makes the resource argument for you - they can SEE the difference between
understaffed (3hr waits) and properly staffed (<45min waits).
