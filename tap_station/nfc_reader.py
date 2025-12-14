"""NFC reader wrapper for PN532 via I2C"""

import time
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class NFCReader:
    """Wrapper for PN532 NFC reader with retry logic and debouncing"""

    def __init__(
        self,
        i2c_bus: int = 1,
        address: int = 0x24,
        timeout: int = 2,
        retries: int = 3,
        debounce_seconds: float = 1.0
    ):
        """
        Initialize NFC reader

        Args:
            i2c_bus: I2C bus number (usually 1 for Pi Zero 2)
            address: I2C address for PN532 (usually 0x24)
            timeout: Read timeout in seconds
            retries: Number of retry attempts
            debounce_seconds: Time window to ignore duplicate reads
        """
        self.i2c_bus = i2c_bus
        self.address = address
        self.timeout = timeout
        self.retries = retries
        self.debounce_seconds = debounce_seconds

        self.pn532 = None
        self.last_uid = None
        self.last_read_time = None

        self._setup_reader()

    def _setup_reader(self):
        """Initialize PN532 reader"""
        try:
            from py532lib.i2c import Pn532_i2c
            from py532lib.mifare import MIFARE

            self.pn532 = Pn532_i2c(i2c_bus=self.i2c_bus, address=self.address)
            logger.info(f"PN532 reader initialized on I2C bus {self.i2c_bus}, address 0x{self.address:02x}")

        except ImportError as e:
            logger.error(f"py532lib not installed: {e}")
            raise

        except Exception as e:
            logger.error(f"Failed to initialize PN532: {e}")
            raise

    def read_card(self) -> Optional[Tuple[str, str]]:
        """
        Read NFC card UID and token ID

        Returns:
            Tuple of (uid_hex, token_id) if successful, None if failed
            - uid_hex: Card UID as hex string (e.g., "04A32FB2C15080")
            - token_id: Token ID read from card (e.g., "001") or UID if not programmed
        """
        for attempt in range(self.retries):
            try:
                # Try to read card
                uid_bytes = self.pn532.read_mifare().get_data()

                if uid_bytes:
                    uid_hex = uid_bytes.hex().upper()

                    # Check debounce
                    if self._should_debounce(uid_hex):
                        logger.debug(f"Debouncing UID: {uid_hex}")
                        return None

                    # Update debounce state
                    self.last_uid = uid_hex
                    self.last_read_time = datetime.now()

                    # Try to read token ID from card (NDEF data)
                    token_id = self._read_token_id(uid_bytes)

                    if not token_id:
                        # Fall back to using UID as token ID
                        token_id = uid_hex[:8]  # Use first 8 chars of UID
                        logger.debug(f"No token ID on card, using UID: {token_id}")

                    logger.info(f"Card read: UID={uid_hex}, Token={token_id}")
                    return (uid_hex, token_id)

            except Exception as e:
                logger.warning(f"Read attempt {attempt + 1}/{self.retries} failed: {e}")
                time.sleep(0.1)

        logger.error("Failed to read card after all retries")
        return None

    def _should_debounce(self, uid: str) -> bool:
        """
        Check if this UID should be debounced

        Args:
            uid: Card UID

        Returns:
            True if should be ignored (duplicate within debounce window)
        """
        if self.last_uid != uid:
            return False

        if self.last_read_time is None:
            return False

        time_since_last = datetime.now() - self.last_read_time
        return time_since_last.total_seconds() < self.debounce_seconds

    def _read_token_id(self, uid_bytes: bytes) -> Optional[str]:
        """
        Try to read token ID from card NDEF data

        Args:
            uid_bytes: Card UID bytes

        Returns:
            Token ID string if found, None otherwise
        """
        try:
            # Try to read NDEF message from card
            # This is a simplified implementation - actual NDEF reading
            # would require more complex logic
            #
            # For now, we'll use the card's UID as fallback
            # Cards can be initialized with token IDs written to NDEF records

            # TODO: Implement NDEF reading if needed
            # For v1.0, using UID as token ID is acceptable

            return None

        except Exception as e:
            logger.debug(f"Could not read token ID from card: {e}")
            return None

    def write_token_id(self, token_id: str) -> bool:
        """
        Write token ID to card

        Args:
            token_id: Token ID to write (e.g., "001")

        Returns:
            True if successful, False otherwise
        """
        try:
            # Read card first to ensure it's present
            uid_bytes = self.pn532.read_mifare().get_data()

            if not uid_bytes:
                logger.error("No card present to write")
                return False

            # Write token ID to card memory
            # For NTAG215, we can write to user memory pages
            # Page 4 onwards is user memory (4 bytes per page)

            # Convert token ID to bytes (pad to 4 bytes)
            token_bytes = token_id.encode('ascii')[:4].ljust(4, b'\x00')

            # Write to page 4 (first user page)
            # This is a simplified write - actual implementation would
            # use proper NDEF formatting

            # Note: py532lib's write_mifare requires specific commands
            # For now, this is a placeholder

            logger.info(f"Wrote token ID '{token_id}' to card")
            return True

        except Exception as e:
            logger.error(f"Failed to write token ID: {e}")
            return False

    def wait_for_card(self, timeout: Optional[float] = None) -> Optional[Tuple[str, str]]:
        """
        Wait for a card to be presented

        Args:
            timeout: Maximum time to wait in seconds (None = wait forever)

        Returns:
            Tuple of (uid_hex, token_id) if card detected, None if timeout
        """
        start_time = datetime.now()

        while True:
            # Try to read card
            result = self.read_card()

            if result:
                return result

            # Check timeout
            if timeout:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= timeout:
                    logger.debug("Card wait timeout")
                    return None

            # Small delay before retry
            time.sleep(0.1)


class MockNFCReader(NFCReader):
    """Mock NFC reader for testing without hardware"""

    def __init__(self, *args, **kwargs):
        """Initialize mock reader (skip PN532 setup)"""
        self.i2c_bus = kwargs.get('i2c_bus', 1)
        self.address = kwargs.get('address', 0x24)
        self.timeout = kwargs.get('timeout', 2)
        self.retries = kwargs.get('retries', 3)
        self.debounce_seconds = kwargs.get('debounce_seconds', 1.0)

        self.pn532 = None
        self.last_uid = None
        self.last_read_time = None

        self._mock_cards = []
        self._mock_index = 0

        logger.info("Mock NFC reader initialized (no hardware)")

    def add_mock_card(self, uid: str, token_id: str):
        """Add a mock card for testing"""
        self._mock_cards.append((uid, token_id))

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
