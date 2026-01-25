"""
Error Codes and User-Friendly Messages

This module provides a centralized error code system with user-friendly messages
and actionable troubleshooting guidance for all stakeholder groups.
"""

from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class ErrorInfo:
    """Information about an error with user-friendly guidance"""
    code: str
    title: str
    message: str
    suggestion: str
    audience: str  # "staff", "admin", or "all"


# Error code catalog
ERROR_CATALOG: Dict[str, ErrorInfo] = {
    # NFC/Hardware Errors (ERR-1xx)
    "ERR-101": ErrorInfo(
        code="ERR-101",
        title="Card Not Detected",
        message="The NFC card could not be read by the scanner.",
        suggestion="Hold the card flat against the reader for 2-3 seconds. Make sure the card is within 1-2 inches of the reader.",
        audience="staff"
    ),
    "ERR-102": ErrorInfo(
        code="ERR-102",
        title="NFC Reader Not Responding",
        message="The NFC reader hardware is not responding.",
        suggestion="Check that the reader is properly connected. If using Raspberry Pi, verify I2C is enabled. Try restarting the tap-station service from the control panel.",
        audience="admin"
    ),
    "ERR-103": ErrorInfo(
        code="ERR-103",
        title="Card Read Timeout",
        message="The card read operation timed out.",
        suggestion="Try scanning the card again. If the problem persists, the card may be damaged or incompatible. Use a different card.",
        audience="staff"
    ),
    "ERR-104": ErrorInfo(
        code="ERR-104",
        title="Card Write Failed",
        message="Could not write data to the NFC card.",
        suggestion="The card may be write-protected or damaged. Try a different card. If using NTAG215 cards, verify they are not locked.",
        audience="staff"
    ),
    
    # Database Errors (ERR-2xx)
    "ERR-201": ErrorInfo(
        code="ERR-201",
        title="Database Connection Failed",
        message="Cannot connect to the event database.",
        suggestion="Check that the database file exists and is not corrupted. Path should be set in config.yaml. Try restarting the service.",
        audience="admin"
    ),
    "ERR-202": ErrorInfo(
        code="ERR-202",
        title="Duplicate Tap Detected",
        message="This card has already been tapped at this station.",
        suggestion="This is normal if someone accidentally taps twice. If they're arriving for the first time, they may have the wrong station - check if they should be at the entry or exit.",
        audience="staff"
    ),
    "ERR-203": ErrorInfo(
        code="ERR-203",
        title="Event Logging Failed",
        message="Could not save the tap event to the database.",
        suggestion="Database may be full or corrupted. Check disk space in the control panel. Contact administrator if problem persists.",
        audience="admin"
    ),
    
    # Validation Errors (ERR-3xx)
    "ERR-301": ErrorInfo(
        code="ERR-301",
        title="Out of Sequence Tap",
        message="This tap is out of order (e.g., exit before queue join).",
        suggestion="The person may have missed a previous station. Ask if they forgot to tap at entry/service start. Use manual event correction in control panel if needed.",
        audience="staff"
    ),
    "ERR-302": ErrorInfo(
        code="ERR-302",
        title="Invalid Token ID",
        message="The card's token ID is not in the expected format.",
        suggestion="Card may not be initialized. If auto-init is enabled, try scanning again. Otherwise, use the init_cards.py script to initialize cards.",
        audience="admin"
    ),
    "ERR-303": ErrorInfo(
        code="ERR-303",
        title="Invalid Stage",
        message="The stage name is not recognized by the system.",
        suggestion="Check config.yaml for valid stage names. Stage should be QUEUE_JOIN, SERVICE_START, SUBSTANCE_RETURNED, or EXIT.",
        audience="admin"
    ),
    
    # Configuration Errors (ERR-4xx)
    "ERR-401": ErrorInfo(
        code="ERR-401",
        title="Configuration File Missing",
        message="The config.yaml file could not be found.",
        suggestion="Copy config.yaml.example to config.yaml and edit with your station settings (device_id, stage, session_id).",
        audience="admin"
    ),
    "ERR-402": ErrorInfo(
        code="ERR-402",
        title="Required Configuration Missing",
        message="A required configuration field is not set.",
        suggestion="Edit config.yaml and ensure device_id, stage, and session_id are all set. See config.yaml.example for reference.",
        audience="admin"
    ),
    "ERR-403": ErrorInfo(
        code="ERR-403",
        title="Invalid GPIO Pin",
        message="A GPIO pin number is outside the valid range.",
        suggestion="GPIO pins must be 0-27 (BCM numbering). Check feedback.gpio settings in config.yaml.",
        audience="admin"
    ),
    "ERR-404": ErrorInfo(
        code="ERR-404",
        title="Invalid Configuration Value",
        message="A configuration value is not valid.",
        suggestion="Check config.yaml for typos or invalid values. See logs for specific field name. Refer to config.yaml.example for valid values.",
        audience="admin"
    ),
    
    # Network/API Errors (ERR-5xx)
    "ERR-501": ErrorInfo(
        code="ERR-501",
        title="Network Request Failed",
        message="Could not connect to the server.",
        suggestion="Check that the Pi is powered on and connected to the network. Verify the IP address is correct. Try refreshing the page.",
        audience="staff"
    ),
    "ERR-502": ErrorInfo(
        code="ERR-502",
        title="Mobile Sync Failed",
        message="Could not sync mobile app data to the server.",
        suggestion="Check network connection. Try syncing again. Data is saved locally and will sync when connection is restored.",
        audience="staff"
    ),
    "ERR-503": ErrorInfo(
        code="ERR-503",
        title="API Rate Limit Exceeded",
        message="Too many requests sent too quickly.",
        suggestion="Wait 60 seconds and try again. This protects the system from overload.",
        audience="admin"
    ),
    
    # System Errors (ERR-6xx)
    "ERR-601": ErrorInfo(
        code="ERR-601",
        title="Service Not Running",
        message="The tap-station service is not active.",
        suggestion="Start the service from the control panel or run: sudo systemctl start tap-station",
        audience="admin"
    ),
    "ERR-602": ErrorInfo(
        code="ERR-602",
        title="Disk Space Low",
        message="Storage space is running low.",
        suggestion="Free up space by removing old backups or logs. Check disk usage in control panel. Consider backing up and clearing old session data.",
        audience="admin"
    ),
    "ERR-603": ErrorInfo(
        code="ERR-603",
        title="High Temperature Warning",
        message="System temperature is above safe threshold.",
        suggestion="Ensure adequate ventilation. Move device away from heat sources. Consider adding cooling if problem persists.",
        audience="admin"
    ),
    "ERR-604": ErrorInfo(
        code="ERR-604",
        title="Authentication Required",
        message="You must be logged in to access this page.",
        suggestion="Go to the login page and enter the admin password. Check config.yaml for the password.",
        audience="admin"
    ),
    "ERR-605": ErrorInfo(
        code="ERR-605",
        title="Session Expired",
        message="Your login session has expired due to inactivity.",
        suggestion="Log in again to continue. Sessions expire after 60 minutes by default (configurable in config.yaml).",
        audience="admin"
    ),
}


def get_error_info(error_code: str) -> Optional[ErrorInfo]:
    """
    Get error information by code.
    
    Args:
        error_code: Error code (e.g., "ERR-101")
        
    Returns:
        ErrorInfo object or None if code not found
    """
    return ERROR_CATALOG.get(error_code)


def format_error_message(error_code: str, context: Optional[str] = None) -> str:
    """
    Format a user-friendly error message with code and suggestion.
    
    Args:
        error_code: Error code (e.g., "ERR-101")
        context: Optional additional context about the error
        
    Returns:
        Formatted error message
    """
    error_info = get_error_info(error_code)
    
    if not error_info:
        return f"Error {error_code}: An unexpected error occurred. Please contact support."
    
    message = f"{error_info.code}: {error_info.title}\n\n"
    message += f"{error_info.message}\n\n"
    
    if context:
        message += f"Details: {context}\n\n"
    
    message += f"💡 Suggestion: {error_info.suggestion}"
    
    return message


def get_error_dict(error_code: str, context: Optional[str] = None) -> Dict[str, str]:
    """
    Get error information as a dictionary for JSON responses.
    
    Args:
        error_code: Error code (e.g., "ERR-101")
        context: Optional additional context
        
    Returns:
        Dictionary with error information
    """
    error_info = get_error_info(error_code)
    
    if not error_info:
        return {
            "error_code": error_code,
            "title": "Unknown Error",
            "message": "An unexpected error occurred.",
            "suggestion": "Please contact support.",
            "context": context or ""
        }
    
    return {
        "error_code": error_info.code,
        "title": error_info.title,
        "message": error_info.message,
        "suggestion": error_info.suggestion,
        "audience": error_info.audience,
        "context": context or ""
    }
