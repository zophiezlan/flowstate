# Operations Guide

Day-of-event guide for peer workers and operators running FlowState stations.

**Audience:** Festival volunteers and peer workers who need a simple, reliable workflow.

---

## Quick Reference Card

### Your Job: Help People Tap

1. Hand participant a card: _"Tap this at each station to track wait times"_
2. Point to tap zone (where NFC reader is)
3. Wait for beep
4. Done!

### Beep Codes

| Sound                        | Meaning                | What to Say               |
| ---------------------------- | ---------------------- | ------------------------- |
| 🔊 **BEEP** (1 short)        | ✅ Success             | "You're all set!"         |
| 🔊🔊 **BEEP-BEEP** (2 short) | ⚠️ Already tapped here | "Already checked in!"     |
| 🔊━━━ **BEEEEEP** (1 long)   | ❌ Error               | "Try again, hold it flat" |

### If Something Goes Wrong

1. Ask them to try again (hold flat for 2 seconds)
2. Try a different card
3. Write it down manually (name or number)
4. Find the tech person if it keeps happening

---

## Pre-Event Setup (30 minutes)

### Equipment Checklist

- [ ] 2× Raspberry Pis (Station 1 and 2)
- [ ] 2× PN532 NFC readers
- [ ] 100× NFC cards (initialized)
- [ ] 2× Power banks (fully charged)
- [ ] 2× USB-C cables
- [ ] "TAP HERE" signs
- [ ] Tape/velcro for mounting
- [ ] This operations guide (printed)
- [ ] Backup: paper log sheets + pens
- [ ] Optional: weatherproof bags/cases

### Station 1 Setup (Queue Entry) - 10 min

**Location:** Registration desk or queue entry point

1. **Power on the Pi**
   - Connect power bank
   - Wait 30 seconds for boot
   - Look for flashing activity LED

2. **Verify it's working**
   - Tap a test card on reader
   - Listen for beep
   - If no beep, see troubleshooting section

3. **Position the hardware**
   - Place reader where participants can reach
   - Mount "TAP HERE" sign above reader
   - Secure with velcro/tape
   - Keep power bank accessible (for checking charge)

4. **Test again**
   - Tap card: should beep once
   - Tap same card immediately: should double-beep (duplicate)
   - ✅ Station 1 ready!

### Station 2 Setup (Exit) - 10 min

**Location:** Exit point after service complete

Repeat same process as Station 1:

1. Power on Pi (wait 30 seconds)
2. Test with card (listen for beep)
3. Position hardware at exit
4. Mount "TAP HERE" sign
5. ✅ Station 2 ready!

### Final Checks - 5 min

- [ ] Both stations powered and beeping
- [ ] "TAP HERE" signs visible
- [ ] Cards readily available at Station 1
- [ ] Peer workers briefed on workflow
- [ ] Backup log sheets ready
- [ ] Tech person identified and available

---

## During Event: Peer Workflow

### Station 1 (Queue Entry): Registration Desk

**When someone arrives for service:**

1. **Greet and hand card**
   - "Welcome! Here's a card - tap it at each station"
   - "It helps us track wait times"

2. **Guide them to tap**
   - "Hold it flat on this reader for a second"
   - Point to tap zone

3. **Wait for beep**
   - 1 beep = ✅ Success: "You're all set!"
   - 2 beeps = ⚠️ Duplicate: "Already checked in - you're good!"
   - Long beep = ❌ Error: "Try again, hold it flat"

4. **If tap fails after 2-3 attempts**
   - Try different card
   - Write name/number on backup sheet
   - Keep going (don't hold up the queue)

5. **Direct to service**
   - "Head inside for your service"
   - "Tap your card again when you exit"

### Station 2 (Exit): After Service

**When someone exits service:**

1. **Remind them to tap**
   - "Don't forget to tap out!"
   - Point to reader

2. **Wait for beep**
   - Same beep codes as Station 1

3. **Thank them**
   - "Thanks! Have a great festival!"
   - They can keep or return the card

### Optional: Station 3 (Substance Return Confirmation)

**If your service uses substance return tracking:**

This station provides accountability when returning substances to participants after testing/analysis.

**When returning a participant's substance:**

1. **Complete testing/analysis**
   - Finish service interaction
   - Prepare substance for return

2. **Physically hand substance to participant**
   - "Here's your substance back"
   - Make eye contact, clear handoff

3. **Immediately tap their card on Station 3**
   - This confirms the return happened
   - Creates timestamped proof
   - Prevents "left behind" incidents

4. **Wait for beep**
   - 1 beep = ✅ Return confirmed
   - Participant can proceed to exit

**Why this matters:**

- Builds trust with participants
- Prevents substances from being forgotten
- Protects staff from disputes
- Creates audit trail
- Dashboard alerts if return delayed

**Training tip:** Make it a habit - "Hand back + Tap = Complete"

See [Substance Return Confirmation Guide](SUBSTANCE_RETURN_CONFIRMATION.md) for full details.

### Managing Cards

**Handing out cards:**

- Keep stack accessible at Station 1
- Hand one card per person
- No need to track which person gets which card

**Collecting cards (optional):**

- Set up collection box at Station 2
- "You can keep it or return it here"
- Cards can be reused at future events

**Running low on cards:**

- Collect cards from return box
- Cards can be tapped multiple times (different sessions)
- Have backup manual log if cards run out

---

## Monitoring During Event

### Live Dashboard (Recommended)

Access dashboards on any phone, tablet, or laptop connected to the same network:

```
# Full analytics dashboard (for coordinators)
http://<pi-ip-address>:8080/dashboard

# Simplified monitor (for peer workers)
http://<pi-ip-address>:8080/monitor

# Control panel (for administrators)
http://<pi-ip-address>:8080/control
```

**Find your Pi's IP:** Run `hostname -I` on the Pi

**Security Note:** The control panel provides administrative access. In production:

- Keep the Pi on a private network
- Use firewall rules to restrict access
- Only share control panel URL with trusted administrators

**What you'll see:**

#### Key Metrics (Top Cards)

| Metric              | What It Means                                       | Action Needed                                                                         |
| ------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------- |
| **In Queue Now**    | People currently waiting for service                | 🟢 <5: Good<br>🟡 5-10: Moderate<br>🟠 10-20: Busy<br>🔴 >20: Critical                |
| **Est. Wait (New)** | Expected wait time for someone joining now          | Communicate this to new arrivals                                                      |
| **Longest Wait**    | How long the first person has been waiting          | 🟢 <30min: Good<br>🟡 30-45min: Watch<br>🟠 45-90min: Concerning<br>🔴 >90min: Urgent |
| **Avg Wait Time**   | Average time from entry to exit (recent)            | Baseline for service speed                                                            |
| **Completed Today** | Total people served                                 | Celebrate milestones! 🎉                                                              |
| **Capacity**        | How efficiently you're operating (% of theoretical) | 🟢 <80%: Good buffer<br>🟡 80-90%: Busy<br>🔴 >90%: At capacity                       |
| **Time in Service** | How long you've been operating today                | Track for shift management                                                            |
| **Throughput**      | People served per hour                              | Monitor service rate trends                                                           |

#### Alerts Section

Dashboard will show color-coded alerts:

- **🔵 Blue (Info):** Operating near capacity - good to know
- **🟡 Yellow (Warning):** Queue getting long (>10) or wait times elevated (>45min)
- **🔴 Red (Critical):** Queue critical (>20) or dangerous wait times (>90min)

**When you see critical alerts:**

1. Consider calling additional volunteers
2. Check if service process can be streamlined
3. Communicate wait times to people in queue
4. Consider limiting new entries temporarily

#### Queue Status Section

Shows everyone currently waiting:

- **Position** in queue (#1, #2, etc.)
- **Token ID** to identify specific person
- **Join Time** when they entered queue
- **Time in Service** how long they've been waiting

**Use this to:**

- Track specific individuals if needed
- Identify anyone waiting unusually long
- Estimate position for people asking "how much longer?"

#### Activity Chart

Visual graph showing tap activity over last 12 hours:

- **Peaks** = busy times
- **Valleys** = slower periods
- **Trends** = help predict upcoming demand

**Use this to:**

- Plan break times during valleys
- Prepare for known busy patterns
- Staff appropriately for anticipated demand

#### Recent Completions

Shows last 10 people who finished service:

- Token ID
- Exit time
- Wait time (color-coded: 🟢 <15min, 🟡 15-30min, 🔴 >30min)

**Use this to:**

- See actual service times
- Verify system is capturing exits
- Communicate realistic wait times

#### Live Event Feed

Real-time stream of all taps:

- Shows each tap as it happens
- Green = Queue Join (entry)
- Red = Exit
- Device ID shows which station

**Use this to:**

- Verify both stations working
- Monitor activity in real-time
- Troubleshoot specific events

### Visual Checks Every Hour

- [ ] Green activity LED flashing on both Pis (shows running)
- [ ] Power banks still charged (check indicator lights)
- [ ] No loose wires
- [ ] Reader accessible and visible
- [ ] Adequate card supply

### Audio Checks

- **Constant beeping** = Good! System is working
- **No beeps for 10+ minutes** = Check if reader is working
- **Long beeps frequently** = Cards may not be initialized properly

### Quick Status Check (Optional)

If web server is enabled:

```
# On phone/laptop connected to same network
http://<pi-ip-address>:8080/health
```

Shows:

- Station ID
- Stage
- Total taps logged
- Status: OK or Error

### Making Operational Decisions

#### Scenario: Queue Length Growing

**Dashboard shows:** In Queue = 12 (🟡 Warning)

**Actions:**

1. ✅ Check avg wait time - is service slowing down?
2. ✅ Review recent completions - are people exiting normally?
3. ✅ Consider: Do we need another peer worker?
4. ✅ Communicate wait times to new arrivals
5. ✅ Monitor for next 15 minutes

#### Scenario: Wait Times Elevated

**Dashboard shows:** Longest Wait = 50min (🟠), Avg Wait = 35min

**Actions:**

1. ✅ Check capacity utilization - are we operating efficiently?
2. ✅ Review service process - any bottlenecks?
3. ✅ Find the person who's been waiting longest (check Queue Status)
4. ✅ Consider priority service for longest waiters
5. ✅ Communicate realistic wait times to new arrivals

#### Scenario: Critical Queue

**Dashboard shows:** In Queue = 23 (🔴 Critical), Est. Wait = 65min

**Actions:**

1. 🚨 **Immediate:** Check both stations functioning
2. 🚨 Call for additional volunteers/resources
3. 🚨 Communicate honestly: "Wait time currently ~1 hour"
4. 🚨 Consider: Can service be expedited without compromising safety?
5. 🚨 May need to temporarily stop accepting new entries
6. 🚨 Prioritize people who've been waiting longest

#### Scenario: Low Activity

**Dashboard shows:** In Queue = 0-2, Throughput dropping

**Actions:**

1. ✅ Good time for peer worker breaks
2. ✅ Restock supplies
3. ✅ Check equipment (while not busy)
4. ✅ Prepare for next rush (monitor activity chart for patterns)

#### Scenario: System Issues

**Dashboard shows:** No new events for 10+ minutes (but people are around)

**Actions:**

1. ⚠️ Check both stations visually
2. ⚠️ Test tap a card at each station
3. ⚠️ Check power banks (lights still on?)
4. ⚠️ If one station down: redistribute workflow
5. ⚠️ If both down: Switch to manual logging immediately
6. ⚠️ Don't troubleshoot during event - document for later

### Dashboard Best Practices

**🔄 Refresh Rate:** Dashboard auto-refreshes every 5 seconds

**📱 Access:** Anyone can view, use tablet/phone mounted in visible location

**👥 Who Should Monitor:**

- Lead coordinator: Watch full dashboard
- Peer workers: Don't need constant monitoring, check periodically
- Tech support: Monitor for system health issues

**⏰ Check Frequency:**

- 🟢 Quiet times: Every 15-20 minutes
- 🟡 Moderate: Every 10 minutes
- 🟠 Busy: Every 5 minutes or keep visible
- 🔴 Critical: Continuous monitoring

**📊 Key Indicators for Quick Glance:**

1. **Queue card color:**
   - Green = All good
   - Yellow/Orange = Pay attention
   - Red = Take action
2. **Alerts section:** Any red alerts = immediate attention
3. **Activity chart:** Trending up or down?

### Communicating With Participants

Use dashboard data to set expectations:

**At Entry (Station 1):**

- "Current wait time is approximately [EST. WAIT] minutes"
- "We're serving about [THROUGHPUT] people per hour"
- If queue is long: "Queue is longer than usual, estimated [EST. WAIT] min wait"

**During Wait:**

- If someone asks: Check their position in Queue Status
- "You're #[POSITION] in queue, should be another [ESTIMATE] minutes"

**Managing Expectations:**

- ✅ Be honest about wait times
- ✅ Under-promise, over-deliver
- ✅ Update if situation changes
- ❌ Don't guarantee specific times
- ❌ Don't blame technology

### Control Panel (Administrators Only)

The control panel (`/control`) provides a web-based interface for all system management tasks. **This is for tech leads and administrators only.**

**📘 For complete control panel reference**, see [Control Panel Documentation](CONTROL_PANEL.md)

#### What It Provides

**System Status:**

- Real-time service status (running/stopped)
- Total events logged
- System uptime
- Database size

**Service Management:**

- Start/stop/restart the tap-station service
- View detailed service status and logs
- No SSH required for basic operations

**Diagnostics & Verification:**

- **Verify Hardware** - Test NFC reader connection
- **Verify Deployment** - Run full system checks
- **Health Check** - Check system health
- **I2C Devices** - Scan for connected I2C devices

**Data Operations:**

- **Export Data** - Export events to CSV
- **Backup Database** - Create timestamped backup
- **View Recent Events** - See last 20 events
- **Database Stats** - View statistics

**System Control (Use with Caution!):**

- **Reboot System** - Restart the Raspberry Pi
- **Shutdown System** - Power off (requires physical restart)
- **View Logs** - Show recent system logs
- **Disk Usage** - Check storage space

**Development Tools:**

- **Dev Reset** - Reset I2C and NFC reader
- **Test Card Read** - Test reading an NFC card
- **Run Tests** - Execute test suite
- **Git Status** - Check repository status

#### When to Use Control Panel

**Pre-Event:**

- Verify hardware before deployment
- Run full system checks
- Test card reading

**During Event:**

- Monitor service status
- Restart service if issues occur
- View recent events to verify logging
- Export data for interim analysis

**Post-Event:**

- Export final data
- Create database backup
- View logs for troubleshooting
- Shutdown system safely

#### Best Practices

✅ **Do:**

- Bookmark control panel URL for quick access
- Test commands in pre-event setup
- Export data regularly
- Use during downtime, not during active service

❌ **Don't:**

- Restart system during active service hours
- Share control panel URL with untrained volunteers
- Shutdown system without ensuring data is saved
- Make changes during critical queue situations

**If Something Goes Wrong:**

- Use control panel to view logs
- Check service status
- Restart service if needed
- Fall back to manual logging if issues persist

### Power Management

**Power bank indicators:**

- 4 LEDs = 75-100% (good for full event)
- 3 LEDs = 50-75% (still good)
- 2 LEDs = 25-50% (consider swapping)
- 1 LED = <25% (swap power bank)

**Swapping power bank:**

1. Have replacement ready
2. Plug in new power bank first
3. Quickly disconnect old one
4. Pi should stay running (brief power dip OK)
5. Or let it reboot (takes 30 seconds)

---

## Common Situations

### "Did my tap work?"

**How to tell:**

- You heard a beep = YES
- No beep = NO, try again

**If unsure:**

- Have them tap again
- Duplicate tap = 2 beeps = confirms first tap worked

### "I lost my card"

**No problem:**

- Give them a new card
- System tracks by card UID, not person
- Multiple taps are fine for statistics

### "Can I use my phone?"

**Current answer:**

- Not for logging taps (Raspberry Pi version requires NFC cards)
- Maybe yes if mobile app version is deployed (see [Mobile Guide](MOBILE.md))

**If NFC Tools integration enabled:**

- They can tap phone to card to check status
- But still need to tap card at station

### "The station isn't beeping"

**Quick fixes:**

1. Check power bank is on and charged
2. Check USB cable is plugged in
3. Wait 30 seconds (may be booting)
4. Try tapping a card you know works
5. If still fails, switch to manual logging

**Don't:**

- Try to restart or troubleshoot during event
- Delay participants
- Panic - manual logging works fine

### "Someone tapped the wrong station"

**No problem:**

- System logs all taps
- Can be filtered during analysis
- Not a critical error

### "Cards aren't working"

**Possible causes:**

- Cards not initialized (should be done before event)
- Wrong type of cards (need NTAG215)
- Reader malfunction

**Solution:**

- Switch to manual logging
- Record: time, approximate participant ID
- Continue event, troubleshoot later

---

## Manual Backup Logging

If technology fails, use paper:

**Log sheet template:**

```
Event: _______________  Station: ___  Date: ________

Time    | Participant ID / Description | Stage
--------|------------------------------|-------------
2:15pm  | Blue shirt, ~30yo            | QUEUE_JOIN
2:17pm  | Green hat, "Alex"            | QUEUE_JOIN
2:32pm  | Blue shirt                   | EXIT
```

**Tips:**

- Note distinctive features or names
- Record times (even approximate)
- Don't delay participants for logging
- Can be entered into system later

---

## End of Event (15 minutes)

### Station Shutdown

**Don't immediately power off!** Give system time to finish writes.

1. **Stop accepting new taps**
   - Remove "TAP HERE" signs
   - Collect remaining cards

2. **Wait 2-3 minutes**
   - Let any pending writes complete

3. **Graceful shutdown**

   ```bash
   ssh pi@<station-ip>
   sudo systemctl stop tap-station
   sudo shutdown -h now
   ```

   **Or:** Just unplug power (system is crash-resistant)

4. **Pack hardware**
   - Disconnect NFC reader
   - Store in protective case
   - Note any damage or issues

### Data Export

**On-site quick export:**

```bash
ssh pi@<station-ip>
cd ~/flowstate
source venv/bin/activate
python scripts/export_data.py
```

Creates `export_YYYYMMDD_HHMMSS.csv` in current directory.

**Retrieve via:**

- SCP: `scp pi@<station-ip>:~/flowstate/export_*.csv .`
- USB drive: Copy file to mounted drive
- Email: Use `mail` command if configured

**Or:** Remove SD card and read directly on laptop

### Post-Event Checklist

- [ ] Data exported from both stations
- [ ] Hardware packed safely
- [ ] Damage/issues noted
- [ ] Cards collected (if reusing)
- [ ] Power banks plugged in to recharge
- [ ] Backup logs collected (if any)
- [ ] Feedback from peer workers noted

---

## Troubleshooting Quick Reference

### No Beep

| Check    | Action                                           |
| -------- | ------------------------------------------------ |
| Power    | Check power bank charged and LED lit             |
| Boot     | Wait 30 seconds after powering on                |
| Card     | Try different card                               |
| Position | Hold card flat, centered on reader for 2 seconds |

### Wrong Beep Pattern

| Pattern       | Meaning        | Action                              |
| ------------- | -------------- | ----------------------------------- |
| 2 short beeps | Duplicate tap  | Normal - person already tapped here |
| Long beep     | Read error     | Try again, hold card flat           |
| No sound      | Reader offline | Check power, see troubleshooting    |

### Station Dead

1. ✅ Check power bank charged
2. ✅ Check USB cable connected
3. ✅ Check activity LED on Pi
4. ✅ Wait 30 seconds (may be booting)
5. ✅ Try power cycle (disconnect/reconnect)
6. ✅ Switch to manual logging if needed

### Frequent Read Errors

- Cards may not be initialized
- Reader may be loose (check wiring)
- Power issue (check `vcgencmd get_throttled`)
- Continue with manual logging

**For detailed troubleshooting**, see [Troubleshooting Guide](TROUBLESHOOTING.md).

---

## Tips for Success

### For Peer Workers

- **Keep it simple:** "Tap card, wait for beep, you're done"
- **Don't over-explain:** People don't need to know how it works
- **Stay positive:** If tech fails, manual logging works fine
- **Don't troubleshoot:** Focus on participant experience, flag tech issues for later

### For Tech Support

- **Test early:** Boot stations 30 min before event start
- **Have spares:** Extra cards, power banks, cables
- **Stay available:** Check stations hourly
- **Document issues:** Note problems for post-event review
- **Prioritize people:** If tech is blocking participants, switch to manual

### For Smooth Operation

- **Position matters:** Reader should be at comfortable height, well-lit
- **Signs help:** Clear "TAP HERE" visual indicator
- **Card management:** Keep cards organized and accessible
- **Backup plan:** Always have manual log sheets ready
- **Test workflow:** Do a full rehearsal before event

---

## FAQ

**Q: What if someone taps multiple times?**
A: System deduplicates within same stage. Multiple taps = one log entry.

**Q: Can cards be reused at different events?**
A: Yes! Just change the `session_id` in config.

**Q: What if they forget to tap at exit?**
A: Shows as "abandoned queue" - valuable data about flow.

**Q: How do we analyze the data later?**
A: Export CSV and use spreadsheet or provided analysis scripts.

**Q: Can we see live statistics during event?**
A: Yes, if web server enabled: `http://<pi-ip>:8080` shows stats.

**Q: What if it rains?**
A: Use weatherproof cases or ziplock bags with opening for reader.

**Q: Do we need WiFi?**
A: No! System works completely offline.

**Q: Can we use this for other workflows?**
A: Yes! System supports custom stages - configure as needed.

---

## Contact & Support

**During event issues:**

- Don't delay participants
- Switch to manual logging if needed
- Document issues for post-event review

**Post-event support:**

- Check [Troubleshooting Guide](TROUBLESHOOTING.md)
- Review logs: `logs/tap-station.log`
- GitHub issues: [Project Repository](https://github.com/zophiezlan/flowstate)

---

## One-Page Quick Reference

**Print this section and laminate for each station!**

### Peer Worker Card

#### Your Job

Help people tap their card. That's it!

#### The Process

1. Hand them a card → "Tap this at each station"
2. Point to reader → "Hold it flat here"
3. Listen for beep → Tell them they're done
4. If no beep → Try again or use backup log

#### Beep Codes

- **1 beep** = Success!
- **2 beeps** = Already tapped (also good!)
- **Long beep** = Error, try again

#### If Problems

1. Try different card
2. Write name on paper
3. Find tech support
4. **Don't stop the flow!**

#### You Don't Need To

❌ Troubleshoot hardware  
❌ Check logs  
❌ Restart anything  
❌ Worry about occasional failures

**Your job: Keep people moving through smoothly** 🎉

---

**Ready to run the event?** You got this! 💚
