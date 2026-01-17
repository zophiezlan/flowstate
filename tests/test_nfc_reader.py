"""Tests for NFC reader"""

import time
from unittest.mock import patch
from tap_station.nfc_reader import NFCReader, MockNFCReader


def test_mock_reader_initialization():
    """Test mock reader initialization"""
    reader = MockNFCReader(i2c_bus=1, address=0x24)

    assert reader.i2c_bus == 1
    assert reader.address == 0x24
    assert reader.pn532 is None  # Mock doesn't initialize PN532


def test_mock_reader_single_card():
    """Test reading a single mock card"""
    reader = MockNFCReader()
    reader.add_mock_card("1234567890ABCDEF", "001")

    # Read card
    result = reader.read_card()

    assert result is not None
    uid, token_id = result
    assert uid == "1234567890ABCDEF"
    assert token_id == "001"


def test_mock_reader_multiple_cards():
    """Test reading multiple mock cards"""
    reader = MockNFCReader()
    reader.add_mock_card("AAA", "001")
    reader.add_mock_card("BBB", "002")
    reader.add_mock_card("CCC", "003")

    # Read cards in sequence
    result1 = reader.read_card()
    assert result1[0] == "AAA"

    result2 = reader.read_card()
    assert result2[0] == "BBB"

    result3 = reader.read_card()
    assert result3[0] == "CCC"

    # Should cycle back
    result4 = reader.read_card()
    assert result4[0] == "AAA"


def test_debounce():
    """Test debouncing prevents duplicate reads"""
    reader = MockNFCReader(debounce_seconds=1.0)
    reader.add_mock_card("ABC", "001")

    # First read should succeed
    result1 = reader.read_card()
    assert result1 is not None

    # Immediate second read should be debounced
    result2 = reader.read_card()
    assert result2 is None

    # After debounce period, should succeed
    time.sleep(1.1)
    result3 = reader.read_card()
    assert result3 is not None


def test_debounce_different_cards():
    """Test debounce only affects same card"""
    reader = MockNFCReader(debounce_seconds=1.0)
    reader.add_mock_card("AAA", "001")
    reader.add_mock_card("BBB", "002")

    # Read first card
    result1 = reader.read_card()
    assert result1[0] == "AAA"

    # Immediately read second card (different UID) - should succeed
    result2 = reader.read_card()
    assert result2[0] == "BBB"


def test_wait_for_card():
    """Test waiting for card with timeout"""
    reader = MockNFCReader()
    reader.add_mock_card("ABC", "001")

    # Should return card immediately
    result = reader.wait_for_card(timeout=5)
    assert result is not None


def test_wait_for_card_timeout():
    """Test wait timeout when no card present"""
    reader = MockNFCReader()  # No cards added

    # Should timeout after 1 second
    start = time.time()
    result = reader.wait_for_card(timeout=1)
    elapsed = time.time() - start

    assert result is None
    assert 0.9 < elapsed < 1.5  # Allow some margin


def test_mock_write():
    """Test mock card write"""
    reader = MockNFCReader()

    # Mock write always succeeds
    success = reader.write_token_id("001")
    assert success is True


def test_write_ntag_pages_accepts_data_argument():
    """Ensure write supports (page, data) signature used by pn532pi"""
    class DummyPn532:
        def __init__(self):
            self.calls = []

        def mifareultralight_WritePage(self, page, data):
            self.calls.append((page, data))
            assert isinstance(data, (bytes, bytearray))
            assert len(data) == 4
            return True

    with patch.object(NFCReader, "_setup_reader", lambda self: None):
        reader = NFCReader()
    reader.pn532 = DummyPn532()

    assert reader._write_ntag_pages(4, b"ABCD") is True
    assert reader.pn532.calls == [(4, b"ABCD")]


def test_read_token_id_handles_tuple_read_page():
    """Ensure tuple returns from ReadPage are handled."""
    class DummyPn532:
        def mifareultralight_ReadPage(self, page):
            return True, bytearray(b"001\x00")

    with patch.object(NFCReader, "_setup_reader", lambda self: None):
        reader = NFCReader()
    reader.pn532 = DummyPn532()

    assert reader._read_token_id(b"\x00") == "001"


def test_write_token_id_verifies_tuple_readback():
    """Ensure tuple readback data doesn't break verification."""
    class DummyPn532:
        def readPassiveTargetID(self, cardbaudrate=0x00):
            return True, bytearray([1, 2, 3, 4])

        def mifareultralight_ReadPage(self, page):
            return True, bytearray(b"001\x00")

    with patch.object(NFCReader, "_setup_reader", lambda self: None):
        reader = NFCReader()
    reader.pn532 = DummyPn532()

    with patch.object(reader, "_write_ntag_pages", return_value=True):
        assert reader.write_token_id("001") is True
