"""
Contextual Help and Tooltips

This module provides help text and tooltips for UI elements across
the application, improving UX for all stakeholder groups.
"""

from typing import Dict


# Mobile App Help Text
MOBILE_HELP = {
    "session_id": {
        "title": "Session ID",
        "tooltip": "The event name or date (e.g., 'festival-2026-summer'). This groups all taps from the same event together.",
        "example": "festival-2026-summer",
    },
    "device_id": {
        "title": "Device ID",
        "tooltip": "Unique name for this phone/device (e.g., 'phone1', 'mobile-entry'). Helps identify which station recorded each tap.",
        "example": "phone1",
    },
    "stage": {
        "title": "Stage",
        "tooltip": "Which checkpoint this station represents. QUEUE_JOIN = entry, SERVICE_START = beginning service, EXIT = leaving.",
        "options": {
            "QUEUE_JOIN": "Entry - people joining the queue",
            "SERVICE_START": "Service began - starting consultation",
            "SUBSTANCE_RETURNED": "Substance returned after testing",
            "EXIT": "Leaving - service complete",
        },
    },
    "sync_status": {
        "title": "Sync Status",
        "tooltip": "Shows how many taps are waiting to sync to the main server. Taps are saved locally and will sync automatically when online.",
        "icons": {
            "synced": "✓ All synced",
            "pending": "⏱ Waiting to sync",
            "syncing": "🔄 Syncing now...",
        },
    },
}


# Dashboard/Monitor Help Text
DASHBOARD_HELP = {
    "queue_length": {
        "title": "People in Queue",
        "tooltip": "Number of people currently waiting or being served (tapped QUEUE_JOIN but not yet EXIT).",
        "calculation": "Counted from: QUEUE_JOIN taps minus EXIT taps",
    },
    "estimated_wait": {
        "title": "Estimated Wait Time",
        "tooltip": "Predicted wait time for someone joining the queue now, based on recent service times.",
        "calculation": "Average of last 20 completed service times × current queue position",
    },
    "longest_wait": {
        "title": "Longest Current Wait",
        "tooltip": "How long the person who's been waiting the longest has been in the system.",
        "action": "If this exceeds 90 minutes, consider prioritizing this person or investigating if they forgot to tap exit.",
    },
    "throughput": {
        "title": "Throughput (per hour)",
        "tooltip": "Number of people served per hour, averaged over the last hour.",
        "calculation": "Completed services in last 60 minutes",
    },
    "capacity_utilization": {
        "title": "Capacity Utilization",
        "tooltip": "How busy the service is compared to maximum capacity.",
        "calculation": "Current queue length / estimated max capacity × 100%",
    },
    "health_status": {
        "title": "Queue Health",
        "tooltip": "Overall system status based on queue length, wait times, and alerts.",
        "levels": {
            "good": "✅ Normal operations - queue under control",
            "moderate": "⚠️ Getting busy - monitor closely",
            "warning": "⚠️ High queue - consider adding resources",
            "critical": "🚨 Overloaded - immediate action needed",
        },
    },
}


# Control Panel Help Text
CONTROL_PANEL_HELP = {
    "service_status": {
        "title": "Service Status",
        "tooltip": "Whether the tap-station background service is running.",
        "actions": {
            "start": "Start the NFC reader and event logging",
            "stop": "Stop all tap logging (use during breaks)",
            "restart": "Restart after config changes",
        },
    },
    "stuck_cards": {
        "title": "Stuck Cards",
        "tooltip": "People who tapped in but haven't tapped out after 30+ minutes. May indicate lost cards or forgotten exit taps.",
        "actions": "Use 'Force Exit' to mark them as complete if you know they've left.",
    },
    "backup_database": {
        "title": "Backup Database",
        "tooltip": "Create a copy of all event data for safe keeping.",
        "recommendation": "Backup at least once per shift, and always before making manual corrections.",
    },
    "hardware_status": {
        "title": "Hardware Status",
        "tooltip": "System health metrics: CPU temperature, disk space, and system load.",
        "warnings": {
            "temp": "Temperature >70°C may cause throttling. Improve ventilation.",
            "disk": "Disk >80% full may cause logging failures. Clear old data.",
            "throttle": "System is throttled due to under-voltage or overheating.",
        },
    },
    "manual_events": {
        "title": "Manual Event Entry",
        "tooltip": "Add or remove tap events manually to correct mistakes.",
        "use_cases": [
            "Someone forgot to tap at a station",
            "Accidental tap at wrong station",
            "Card scanner was offline temporarily",
        ],
        "warning": "Manual changes bypass validation. Use carefully and document why.",
    },
}


# Configuration Help Text
CONFIG_HELP = {
    "device_id": {
        "field": "station.device_id",
        "tooltip": "Unique identifier for this station (e.g., 'station1', 'entry-pi', 'exit-mobile').",
        "required": True,
        "example": "station1",
    },
    "stage": {
        "field": "station.stage",
        "tooltip": "Which checkpoint this station represents in the workflow.",
        "required": True,
        "options": ["QUEUE_JOIN", "SERVICE_START", "SUBSTANCE_RETURNED", "EXIT"],
    },
    "session_id": {
        "field": "station.session_id",
        "tooltip": "Event identifier to group taps from the same event (e.g., 'festival-2026-01-25').",
        "required": True,
        "example": "festival-2026-summer",
    },
    "debounce_seconds": {
        "field": "nfc.debounce_seconds",
        "tooltip": "Minimum seconds between taps from the same card. Prevents accidental double-taps.",
        "range": "0.1-10 seconds",
        "recommended": "1.0 seconds",
    },
    "auto_init_cards": {
        "field": "nfc.auto_init_cards",
        "tooltip": "Automatically assign token IDs to uninitialized cards on first tap.",
        "benefit": "No need to pre-initialize cards - just hand them out!",
        "default": False,
    },
    "admin_password": {
        "field": "web_server.admin.password",
        "tooltip": "Password for control panel access. MUST be changed from default before deployment.",
        "security": "Use a strong password. All staff can share this password for admin access.",
        "default_warning": "Default is 'CHANGE-ME-BEFORE-DEPLOYMENT' - NOT SECURE!",
    },
    "gpio_pins": {
        "field": "feedback.gpio.*",
        "tooltip": "GPIO pin numbers for buzzer and LEDs (BCM numbering, valid range: 0-27).",
        "wiring": "See wiring_schematic.md for pin layout.",
        "validation": "Invalid pins will show error in logs.",
    },
}


# Alert Messages Help Text
ALERT_HELP = {
    "queue_critical": {
        "condition": "Queue >20 people OR wait >90 minutes",
        "message": "🚨 CRITICAL: Queue overloaded",
        "actions": [
            "Open additional service station if available",
            "Prioritize people waiting longest",
            "Consider turning away new arrivals temporarily",
            "Check if anyone forgot to tap exit (stuck cards)",
        ],
    },
    "queue_warning": {
        "condition": "Queue >10 people OR wait >45 minutes",
        "message": "⚠️ WARNING: Queue getting busy",
        "actions": [
            "Monitor closely for further increases",
            "Call additional volunteers if available",
            "Inform new arrivals of current wait time",
            "Check for any stuck cards or anomalies",
        ],
    },
    "inactivity": {
        "condition": "No taps in >10 minutes",
        "message": "⏰ INACTIVITY: No recent taps",
        "actions": [
            "Check if NFC reader is working (tap a test card)",
            "Verify service is running (control panel)",
            "May be normal during quiet periods",
            "Consider break or close if event ending",
        ],
    },
    "service_variance": {
        "condition": "Service time >3× normal variance",
        "message": "⚠️ Service time unusually variable",
        "actions": [
            "Some people taking much longer than others",
            "May indicate complex cases or issues",
            "Check for stuck cards or forgotten taps",
            "Verify process is consistent across staff",
        ],
    },
}


def get_mobile_help(field: str) -> Dict[str, str]:
    """Get help text for mobile app field."""
    return MOBILE_HELP.get(field, {})


def get_dashboard_help(metric: str) -> Dict[str, str]:
    """Get help text for dashboard metric."""
    return DASHBOARD_HELP.get(metric, {})


def get_control_help(feature: str) -> Dict[str, str]:
    """Get help text for control panel feature."""
    return CONTROL_PANEL_HELP.get(feature, {})


def get_config_help(field: str) -> Dict[str, str]:
    """Get help text for configuration field."""
    return CONFIG_HELP.get(field, {})


def get_alert_help(alert_type: str) -> Dict[str, str]:
    """Get help text for alert type."""
    return ALERT_HELP.get(alert_type, {})
