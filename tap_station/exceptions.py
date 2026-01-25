"""
Custom Exception Classes

This module defines custom exceptions for the tap station system,
providing better error handling and clearer error messages.
"""

from typing import Any


class TapStationError(Exception):
    """Base exception for all tap station errors"""
    pass


class ConfigurationError(TapStationError):
    """Raised when configuration is invalid or missing"""
    
    def __init__(self, message: str, config_key: str = None):
        """
        Initialize configuration error.
        
        Args:
            message: Error description
            config_key: The configuration key that caused the error
        """
        self.config_key = config_key
        if config_key:
            message = f"Configuration error for '{config_key}': {message}"
        super().__init__(message)


class DatabaseError(TapStationError):
    """Raised when database operations fail"""
    
    def __init__(self, message: str, operation: str = None):
        """
        Initialize database error.
        
        Args:
            message: Error description
            operation: The database operation that failed (e.g., 'insert', 'query')
        """
        self.operation = operation
        if operation:
            message = f"Database {operation} failed: {message}"
        super().__init__(message)


class NFCError(TapStationError):
    """Raised when NFC operations fail"""
    
    def __init__(self, message: str, card_uid: str = None):
        """
        Initialize NFC error.
        
        Args:
            message: Error description
            card_uid: The UID of the card that caused the error (if known)
        """
        self.card_uid = card_uid
        if card_uid:
            message = f"NFC error for card {card_uid}: {message}"
        super().__init__(message)


class NFCReadError(NFCError):
    """Raised when reading NFC card fails"""
    pass


class NFCWriteError(NFCError):
    """Raised when writing to NFC card fails"""
    pass


class NFCParseError(NFCError):
    """Raised when parsing NFC card data fails"""
    
    def __init__(self, message: str, card_uid: str = None, parser: str = None):
        """
        Initialize parse error.
        
        Args:
            message: Error description
            card_uid: The UID of the card that caused the error
            parser: The parser that failed (e.g., 'NDEF', 'legacy')
        """
        self.parser = parser
        if parser:
            message = f"{parser} parsing failed: {message}"
        super().__init__(message, card_uid)


class ValidationError(TapStationError):
    """Raised when validation fails"""
    
    def __init__(self, message: str, field: str = None, value: Any = None):
        """
        Initialize validation error.
        
        Args:
            message: Error description
            field: The field that failed validation
            value: The value that failed validation
        """
        self.field = field
        self.value = value
        if field:
            message = f"Validation failed for '{field}': {message}"
        super().__init__(message)


class SequenceValidationError(ValidationError):
    """Raised when event sequence is invalid (e.g., EXIT before QUEUE_JOIN)"""
    
    def __init__(
        self,
        message: str,
        token_id: str = None,
        expected_stage: str = None,
        actual_stage: str = None
    ):
        """
        Initialize sequence validation error.
        
        Args:
            message: Error description
            token_id: The token ID with the sequence error
            expected_stage: The expected stage
            actual_stage: The actual stage that was invalid
        """
        self.token_id = token_id
        self.expected_stage = expected_stage
        self.actual_stage = actual_stage
        
        if token_id:
            message = f"Sequence error for token {token_id}: {message}"
        if expected_stage and actual_stage:
            message = f"{message} (expected {expected_stage}, got {actual_stage})"
        
        super().__init__(message)


class HardwareError(TapStationError):
    """Raised when hardware operations fail"""
    
    def __init__(self, message: str, component: str = None):
        """
        Initialize hardware error.
        
        Args:
            message: Error description
            component: The hardware component that failed (e.g., 'buzzer', 'GPIO')
        """
        self.component = component
        if component:
            message = f"{component} error: {message}"
        super().__init__(message)


class GPIOError(HardwareError):
    """Raised when GPIO operations fail"""
    pass

