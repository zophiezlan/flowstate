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
        debounce_seconds: float = 1.0,
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
            from pn532pi import Pn532, Pn532I2c

            # Initialize I2C interface
            try:
                i2c = Pn532I2c(self.i2c_bus, self.address)
            except TypeError:
                # Fallback for libraries that don't accept address argument
                i2c = Pn532I2c(self.i2c_bus)
            self.pn532 = Pn532(i2c)

            # Begin communication
            self.pn532.begin()

            # Get firmware version to verify communication
            versiondata = self.pn532.getFirmwareVersion()
            if not versiondata:
                raise RuntimeError("Failed to communicate with PN532")

            logger.info(
                f"PN532 reader initialized on I2C bus {self.i2c_bus}, address 0x{self.address:02x}"
            )
            logger.info(
                f"Firmware version: {(versiondata >> 24) & 0xFF}.{(versiondata >> 16) & 0xFF}"
            )

            # Configure for reading MiFare cards
            self.pn532.SAMConfig()

        except ImportError as e:
            logger.error(f"pn532pi not installed: {e}")
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
                # Try to read card using PN532 readPassiveTargetID
                # Returns a list [success, uid] where uid is a bytearray
                success, uid_bytes = self.pn532.readPassiveTargetID(cardbaudrate=0x00)

                if success and uid_bytes:
                    # Convert bytearray to hex string
                    uid_hex = "".join(["{:02X}".format(b) for b in uid_bytes])

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
        Try to read token ID from card (supports NDEF and legacy formats)

        Args:
            uid_bytes: Card UID bytes

        Returns:
            Token ID string if found, None otherwise
        """
        try:
            if not self.pn532:
                return None

            read_page = getattr(self.pn532, "mifareultralight_ReadPage", None)
            if not read_page:
                return None

            # Read first ~96 bytes (pages 4-27) to cover NDEF records
            # Each read_page usually returns 16 bytes (4 pages)
            raw_data = bytearray()
            for page in range(4, 28, 4):
                try:
                    chunk = read_page(page)
                    if chunk:
                        raw_data.extend(bytes(chunk))
                    else:
                        break
                except Exception:
                    break

            if not raw_data:
                return None

            # 1. Search for "Token {id}" pattern (Standard NDEF format)
            # This searches the raw dump so it works regardless of NDEF structure
            try:
                text = raw_data.decode("utf-8", errors="ignore")
                import re

                match = re.search(r"Token\s+([A-Za-z0-9]+)", text)
                if match:
                    return match.group(1)
            except Exception:
                pass

            # 2. Legacy Fallback (Plain ASCII at page 4)
            # Only if it doesn't look like NDEF (header 0x03)
            # Legacy cards start immediately with the ID (e.g. "001")
            if len(raw_data) >= 4 and raw_data[0] != 0x03:
                token = (
                    raw_data[:4].decode("ascii", errors="ignore").strip("\x00").strip()
                )
                if token and len(token) >= 1:
                    return token

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
            if not self.pn532:
                logger.error("PN532 reader not initialized")
                return False

            # Read card first to ensure it's present
            success, uid_bytes = self.pn532.readPassiveTargetID(cardbaudrate=0x00)

            if not success or not uid_bytes:
                logger.error("No card present to write")
                return False

            # Convert token ID to bytes (pad to 4 bytes)
            token_bytes = token_id.encode("ascii")[:4].ljust(4, b"\x00")

            if not self._write_ntag_pages(4, token_bytes):
                logger.error("Failed to write token ID to card")
                return False

            # Verify readback if possible
            read_page = getattr(self.pn532, "mifareultralight_ReadPage", None)
            if read_page:
                raw = read_page(4)
                if raw:
                    read_token = (
                        bytes(raw)
                        .decode("ascii", errors="ignore")
                        .strip("\x00")
                        .strip()
                    )
                    if read_token and read_token != token_id:
                        logger.error(
                            f"Token ID verification mismatch: wrote {token_id}, read {read_token}"
                        )
                        return False

            logger.info(f"Wrote token ID '{token_id}' to card")
            return True

        except Exception as e:
            logger.error(f"Failed to write token ID: {e}")
            return False

    def write_ndef_tlv(self, tlv_bytes: bytes) -> bool:
        """
        Write NDEF TLV bytes to card user memory starting at page 4

        Args:
            tlv_bytes: Full NDEF TLV payload

        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.pn532:
                logger.error("PN532 reader not initialized")
                return False

            # NTAG215 user memory is 504 bytes (pages 4-129)
            if len(tlv_bytes) > 504:
                logger.error("NDEF message too large for NTAG215")
                return False

            return self._write_ntag_pages(4, tlv_bytes)

        except Exception as e:
            logger.error(f"Failed to write NDEF TLV: {e}")
            return False

    def _write_ntag_pages(self, start_page: int, data: bytes) -> bool:
        """
        Write arbitrary bytes to NTAG user memory (4 bytes per page)

        Args:
            start_page: Page to start writing (usually 4)
            data: Raw bytes to write (will be padded to 4-byte pages)

        Returns:
            True if all pages written, False otherwise
        """
        write_page = getattr(self.pn532, "mifareultralight_WritePage", None)
        if not write_page:
            logger.error("PN532 library does not support mifareultralight_WritePage")
            return False

        padded = data
        if len(padded) % 4 != 0:
            padded = padded.ljust((len(padded) + 3) // 4 * 4, b"\x00")

        page = start_page
        for offset in range(0, len(padded), 4):
            chunk = padded[offset : offset + 4]
            result = write_page(page, chunk)
            if result is False:
                logger.error(f"Failed to write page {page}")
                return False
            page += 1

        return True

    def reset_reader(self):
        """
        Reset the PN532 reader to clear any stuck state

        This is important after reading/writing cards to ensure
        clean state for the next operation
        """
        try:
            # Reconfigure SAM to reset state
            self.pn532.SAMConfig()
            logger.debug("PN532 reader reset")

            # Small delay to let hardware settle
            time.sleep(0.1)

        except Exception as e:
            logger.warning(f"Failed to reset reader: {e}")

    def is_card_present(self) -> bool:
        """
        Check if a card is currently in the field

        Returns:
            True if card is present, False otherwise
        """
        try:
            # Quick check without retries
            success, uid_bytes = self.pn532.readPassiveTargetID(cardbaudrate=0x00)
            return success and uid_bytes is not None

        except Exception:
            return False

    def wait_for_card_removal(self, timeout: float = 10.0) -> bool:
        """
        Wait for current card to be removed from the field

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if card was removed, False if timeout
        """
        start_time = datetime.now()

        # First check if there's even a card present
        if not self.is_card_present():
            logger.debug("No card present to remove")
            return True

        logger.debug("Waiting for card removal...")

        while True:
            if not self.is_card_present():
                logger.debug("Card removed")
                # Extra delay to ensure card is fully out of field
                time.sleep(0.3)
                return True

            # Check timeout
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed >= timeout:
                logger.warning("Card removal timeout")
                return False

            time.sleep(0.2)

    def wait_for_card(
        self, timeout: Optional[float] = None
    ) -> Optional[Tuple[str, str]]:
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
            time.sleep(0.2)


class MockNFCReader(NFCReader):
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
