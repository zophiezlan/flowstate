"""NDEF writing for NFC Tools app integration"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class NDEFWriter:
    """
    Write NDEF records to NTAG215 cards for NFC Tools app compatibility

    Note: This is a simplified implementation for NTAG215 cards.
    For production use with physical hardware, consider using the 'ndeflib' package.
    """

    def __init__(self, nfc_reader):
        """
        Initialize NDEF writer

        Args:
            nfc_reader: NFCReader instance
        """
        self.nfc = nfc_reader

    def write_url(self, url: str, token_id: str = None) -> bool:
        """
        Write URL NDEF record to card

        Args:
            url: URL to write (e.g., "https://example.com/check?token=001")
            token_id: Optional token ID for logging

        Returns:
            True if successful, False otherwise
        """
        try:
            try:
                import ndef
            except ImportError:
                logger.warning("ndeflib not installed; cannot write NDEF URLs")
                return False

            records = [ndef.UriRecord(url)]

            if token_id:
                records.append(ndef.TextRecord(f"Token {token_id}"))

            message = b"".join(ndef.message_encoder(records))
            tlv = self._wrap_ndef_tlv(message)

            return self.nfc.write_ndef_tlv(tlv)

        except Exception as e:
            logger.error(f"Failed to write NDEF URL: {e}")
            return False

    def _wrap_ndef_tlv(self, message: bytes) -> bytes:
        """
        Wrap an NDEF message in an NDEF TLV block

        Args:
            message: Raw NDEF message bytes

        Returns:
            TLV bytes ready to write to tag memory
        """
        length = len(message)
        if length <= 0xFE:
            tlv = bytes([0x03, length]) + message + bytes([0xFE])
        else:
            tlv = (
                bytes([0x03, 0xFF, (length >> 8) & 0xFF, length & 0xFF])
                + message
                + bytes([0xFE])
            )
        return tlv

    def write_text(self, text: str) -> bool:
        """
        Write text NDEF record to card

        Args:
            text: Text to write (e.g., "Token 001 - Checked in")

        Returns:
            True if successful, False otherwise
        """
        try:
            try:
                import ndef
            except ImportError:
                logger.warning("ndeflib not installed; cannot write NDEF text")
                return False

            records = [ndef.TextRecord(text)]
            message = b"".join(ndef.message_encoder(records))
            tlv = self._wrap_ndef_tlv(message)
            return self.nfc.write_ndef_tlv(tlv)

        except Exception as e:
            logger.error(f"Failed to write NDEF text: {e}")
            return False

    def format_status_url(self, base_url: str, token_id: str) -> str:
        """
        Format a status check URL

        Args:
            base_url: Base URL (e.g., "https://festival.example.com")
            token_id: Token ID (e.g., "001")

        Returns:
            Complete URL
        """
        # Remove trailing slash from base URL
        base_url = base_url.rstrip("/")

        # Format URL
        url = f"{base_url}/check?token={token_id}"

        return url


class MockNDEFWriter(NDEFWriter):
    """Mock NDEF writer for testing"""

    def __init__(self, nfc_reader=None):
        """Initialize mock writer"""
        self.nfc = nfc_reader
        self.written_urls = []
        self.written_texts = []

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
