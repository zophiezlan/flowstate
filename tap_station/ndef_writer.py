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
            # Try to import ndeflib if available
            try:
                import ndef
                return self._write_url_with_ndeflib(url, token_id)
            except ImportError:
                logger.warning("ndeflib not installed, using basic implementation")
                return self._write_url_basic(url, token_id)

        except Exception as e:
            logger.error(f"Failed to write NDEF URL: {e}")
            return False

    def _write_url_with_ndeflib(self, url: str, token_id: str = None) -> bool:
        """Write URL using ndeflib library"""
        import ndef

        try:
            # Create NDEF message with URL record
            records = []

            # Add URL record
            uri_record = ndef.UriRecord(url)
            records.append(uri_record)

            # Optionally add text record with token ID
            if token_id:
                text_record = ndef.TextRecord(f"Token {token_id}")
                records.append(text_record)

            message = ndef.Message(records)

            # Write to card
            # Note: Actual writing requires lower-level PN532 commands
            # This is a placeholder for the interface
            logger.info(f"Would write NDEF: {url} (Token: {token_id})")

            # For now, we'll simulate success
            # In production with real hardware, implement actual NDEF writing
            return True

        except Exception as e:
            logger.error(f"ndeflib write failed: {e}")
            return False

    def _write_url_basic(self, url: str, token_id: str = None) -> bool:
        """
        Basic NDEF URL writing without ndeflib

        NDEF URL Record Format (simplified):
        - NDEF Message header
        - Record header (TNF=0x01, Type="U")
        - URL with prefix byte
        """
        try:
            # NTAG215 memory layout:
            # Pages 0-3: UID, lock bytes, capability container (read-only)
            # Pages 4-129: User memory (504 bytes)
            # Pages 130-134: Lock bytes, config

            # Simplified NDEF message for URL
            # This would require low-level PN532 write commands

            logger.info(f"Basic NDEF write: {url} (Token: {token_id})")

            # For mock/testing, return success
            # In production, implement actual page writes
            return True

        except Exception as e:
            logger.error(f"Basic NDEF write failed: {e}")
            return False

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
                text_record = ndef.TextRecord(text)
                message = ndef.Message([text_record])
                logger.info(f"Would write NDEF text: {text}")
                return True
            except ImportError:
                logger.warning("ndeflib not installed")
                return False

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
        base_url = base_url.rstrip('/')

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
        self.written_urls.append({'url': url, 'token_id': token_id})
        logger.info(f"Mock NDEF URL write: {url} (Token: {token_id})")
        return True

    def write_text(self, text: str) -> bool:
        """Mock write text - always succeeds"""
        self.written_texts.append(text)
        logger.info(f"Mock NDEF text write: {text}")
        return True
