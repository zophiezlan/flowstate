"""
Mock implementations for testing

This module provides mock implementations of hardware-dependent classes,
allowing tests to run without physical hardware.
"""

import time
import logging
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class MockNFCReader:
    """Mock NFC reader for testing without hardware"""

    def __init__(self, *args, **kwargs):
        """Initialize mock reader (skip PN532 setup)"""
        self.i2c_bus = kwargs.get("i2c_bus", 1)
        self.address = kwargs.get("address", 0x24)
        self.timeout = kwargs.get("timeout", 2)
        self.retries = kwargs.get("retries", 3)
        self.debounce_seconds = kwargs.get("debounce_seconds", 1.0)

        self.pn532 = None
        self.last_uid = None
        self.last_read_time = None

        self._mock_cards: List[Tuple[str, str]] = []
        self._mock_index = 0

        logger.info("Mock NFC reader initialized (no hardware)")

    def add_mock_card(self, uid: str, token_id: str):
        """Add a mock card for testing"""
        self._mock_cards.append((uid, token_id))

    def clear_mock_cards(self):
        """Clear all mock cards"""
        self._mock_cards.clear()
        self._mock_index = 0

    def _should_debounce(self, uid: str) -> bool:
        """Check if this UID should be debounced"""
        if self.last_uid != uid:
            return False

        if self.last_read_time is None:
            return False

        time_since_last = datetime.now() - self.last_read_time
        return time_since_last.total_seconds() < self.debounce_seconds

    def read_card(self) -> Optional[Tuple[str, str]]:
        """Read next mock card"""
        if not self._mock_cards:
            return None

        # Get next card (cycle through)
        card = self._mock_cards[self._mock_index % len(self._mock_cards)]
        self._mock_index += 1

        uid, token_id = card

        # Check debounce
        if self._should_debounce(uid):
            return None

        self.last_uid = uid
        self.last_read_time = datetime.now()

        logger.info(f"Mock card read: UID={uid}, Token={token_id}")
        return (uid, token_id)

    def write_token_id(self, token_id: str) -> bool:
        """Mock write always succeeds"""
        logger.info(f"Mock write: {token_id}")
        return True

    def write_ndef_tlv(self, tlv_bytes: bytes) -> bool:
        """Mock NDEF TLV write always succeeds"""
        logger.info(f"Mock NDEF TLV write: {len(tlv_bytes)} bytes")
        return True

    def reset_reader(self):
        """Mock reset"""
        logger.debug("Mock reader reset")
        time.sleep(0.1)

    def is_card_present(self) -> bool:
        """Mock card presence check"""
        return False

    def wait_for_card_removal(self, timeout: float = 10.0) -> bool:
        """Mock card removal always succeeds"""
        logger.debug("Mock card removal")
        time.sleep(0.5)
        return True

    def wait_for_card(
        self, timeout: Optional[float] = None
    ) -> Optional[Tuple[str, str]]:
        """Wait for a card to be presented"""
        return self.read_card()


class MockNDEFWriter:
    """Mock NDEF writer for testing"""

    def __init__(self, nfc_reader=None):
        """Initialize mock writer"""
        self.nfc = nfc_reader
        self.written_urls: List[Dict[str, Any]] = []
        self.written_texts: List[str] = []

    def write_url(self, url: str, token_id: str = None) -> bool:
        """Mock write URL - always succeeds"""
        self.written_urls.append({"url": url, "token_id": token_id})
        logger.info(f"Mock NDEF URL write: {url} (Token: {token_id})")
        return True

    def write_text(self, text: str) -> bool:
        """Mock write text - always succeeds"""
        self.written_texts.append(text)
        logger.info(f"Mock NDEF text write: {text}")
        return True

    def format_status_url(self, base_url: str, token_id: str) -> str:
        """Format a status check URL"""
        base_url = base_url.rstrip("/")
        return f"{base_url}/check?token={token_id}"

    def get_written_urls(self) -> List[Dict[str, Any]]:
        """Get list of written URLs for verification"""
        return self.written_urls.copy()

    def get_written_texts(self) -> List[str]:
        """Get list of written texts for verification"""
        return self.written_texts.copy()

    def clear(self):
        """Clear written data for fresh test"""
        self.written_urls.clear()
        self.written_texts.clear()


class MockGPIOManager:
    """Mock GPIO manager for testing without hardware"""

    def __init__(self):
        self._pins: Dict[int, Dict[str, Any]] = {}
        self._available = True

    @property
    def available(self) -> bool:
        return self._available

    def set_available(self, available: bool):
        """Set GPIO availability for testing"""
        self._available = available

    def setup_output(self, pin: int, initial_state: bool = False) -> bool:
        if not self._available:
            return False
        self._pins[pin] = {"mode": "OUT", "state": initial_state}
        return True

    def setup_input(self, pin: int, pull_up: bool = False, pull_down: bool = False) -> bool:
        if not self._available:
            return False
        self._pins[pin] = {"mode": "IN", "pull_up": pull_up, "pull_down": pull_down, "state": pull_up}
        return True

    def output(self, pin: int, state: bool) -> bool:
        if not self._available or pin not in self._pins:
            return False
        self._pins[pin]["state"] = state
        return True

    def input(self, pin: int) -> Optional[bool]:
        if not self._available or pin not in self._pins:
            return None
        return self._pins[pin].get("state", False)

    def is_low(self, pin: int) -> bool:
        result = self.input(pin)
        return result is False

    def is_high(self, pin: int) -> bool:
        result = self.input(pin)
        return result is True

    def set_pin_state(self, pin: int, state: bool):
        """Set pin state for testing (simulates button press, etc.)"""
        if pin in self._pins:
            self._pins[pin]["state"] = state

    def cleanup(self, pins: Optional[List[int]] = None):
        if pins:
            for pin in pins:
                self._pins.pop(pin, None)
        else:
            self._pins.clear()

    def get_configured_pins(self) -> Dict[int, str]:
        return {pin: info["mode"] for pin, info in self._pins.items()}


class MockDatabase:
    """Mock database for testing without SQLite"""

    def __init__(self, *args, **kwargs):
        self.events: List[Dict[str, Any]] = []
        self._next_id = 1

    def log_event(
        self,
        token_id: str,
        uid: str,
        stage: str,
        device_id: str,
        session_id: str,
        timestamp=None,
        allow_out_of_order: bool = False,
    ) -> dict:
        """Log a mock event"""
        event = {
            "id": self._next_id,
            "token_id": token_id,
            "uid": uid,
            "stage": stage,
            "device_id": device_id,
            "session_id": session_id,
            "timestamp": timestamp or datetime.now().isoformat(),
        }
        self.events.append(event)
        self._next_id += 1
        return {"success": True, "duplicate": False, "out_of_order": False, "warning": None}

    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.events[-limit:][::-1]

    def get_event_count(self, session_id: Optional[str] = None) -> int:
        if session_id:
            return len([e for e in self.events if e["session_id"] == session_id])
        return len(self.events)

    def get_anomalies(self, session_id: str) -> Dict[str, Any]:
        return {
            "incomplete_journeys": [],
            "long_service_times": [],
            "stuck_in_service": [],
            "out_of_order_events": [],
            "rapid_fire_taps": [],
            "forgotten_exit_taps": [],
        }

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
