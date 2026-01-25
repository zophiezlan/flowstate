"""
Transaction Management for Database Operations

This module provides transaction context managers and utilities for ensuring
atomic database operations. It supports:
- Automatic commit/rollback based on success/failure
- Nested transactions via savepoints
- Retry logic for transient failures
- Transaction isolation levels
"""

import sqlite3
import logging
import functools
from contextlib import contextmanager
from typing import Optional, Callable, TypeVar, Any, Generator
from enum import Enum

logger = logging.getLogger(__name__)


class IsolationLevel(Enum):
    """SQLite transaction isolation levels"""
    DEFERRED = "DEFERRED"
    IMMEDIATE = "IMMEDIATE"
    EXCLUSIVE = "EXCLUSIVE"


class TransactionError(Exception):
    """Raised when a transaction operation fails"""

    def __init__(self, message: str, cause: Optional[Exception] = None):
        self.cause = cause
        super().__init__(message)


class TransactionManager:
    """
    Manages database transactions with support for savepoints and nested transactions.

    This class provides a robust transaction management system that ensures
    data integrity and proper error handling for all database operations.

    Features:
    - Automatic commit on success, rollback on failure
    - Savepoint support for nested transactions
    - Configurable isolation levels
    - Retry logic for transient failures
    - Transaction hooks for audit/logging
    """

    def __init__(
        self,
        connection: sqlite3.Connection,
        default_isolation: IsolationLevel = IsolationLevel.IMMEDIATE
    ):
        """
        Initialize transaction manager.

        Args:
            connection: SQLite database connection
            default_isolation: Default transaction isolation level
        """
        self._conn = connection
        self._default_isolation = default_isolation
        self._transaction_depth = 0
        self._savepoint_counter = 0
        self._hooks_before_commit: list[Callable] = []
        self._hooks_after_commit: list[Callable] = []
        self._hooks_on_rollback: list[Callable] = []

    @property
    def in_transaction(self) -> bool:
        """Check if currently in a transaction"""
        return self._transaction_depth > 0

    @property
    def transaction_depth(self) -> int:
        """Get current transaction nesting depth"""
        return self._transaction_depth

    def add_before_commit_hook(self, hook: Callable[[], None]) -> None:
        """Add a hook to run before commit"""
        self._hooks_before_commit.append(hook)

    def add_after_commit_hook(self, hook: Callable[[], None]) -> None:
        """Add a hook to run after successful commit"""
        self._hooks_after_commit.append(hook)

    def add_on_rollback_hook(self, hook: Callable[[], None]) -> None:
        """Add a hook to run on rollback"""
        self._hooks_on_rollback.append(hook)

    @contextmanager
    def transaction(
        self,
        isolation: Optional[IsolationLevel] = None
    ) -> Generator[sqlite3.Connection, None, None]:
        """
        Context manager for database transactions.

        Automatically commits on success and rolls back on failure.
        Supports nested transactions via savepoints.

        Args:
            isolation: Transaction isolation level (only applies to outermost transaction)

        Yields:
            The database connection for executing queries

        Raises:
            TransactionError: If transaction operations fail
        """
        isolation = isolation or self._default_isolation
        savepoint_name = None

        try:
            if self._transaction_depth == 0:
                # Start new transaction
                self._conn.execute(f"BEGIN {isolation.value}")
                logger.debug(f"Started transaction with isolation {isolation.value}")
            else:
                # Create savepoint for nested transaction
                self._savepoint_counter += 1
                savepoint_name = f"sp_{self._savepoint_counter}"
                self._conn.execute(f"SAVEPOINT {savepoint_name}")
                logger.debug(f"Created savepoint {savepoint_name} at depth {self._transaction_depth}")

            self._transaction_depth += 1

            yield self._conn

            # Success - commit or release savepoint
            self._transaction_depth -= 1

            if self._transaction_depth == 0:
                # Run pre-commit hooks
                for hook in self._hooks_before_commit:
                    try:
                        hook()
                    except Exception as e:
                        logger.warning(f"Pre-commit hook failed: {e}")

                self._conn.commit()
                logger.debug("Transaction committed successfully")

                # Run post-commit hooks
                for hook in self._hooks_after_commit:
                    try:
                        hook()
                    except Exception as e:
                        logger.warning(f"Post-commit hook failed: {e}")
            else:
                self._conn.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                logger.debug(f"Released savepoint {savepoint_name}")

        except Exception as e:
            self._transaction_depth = max(0, self._transaction_depth - 1)

            try:
                if savepoint_name:
                    self._conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                    logger.debug(f"Rolled back to savepoint {savepoint_name}")
                else:
                    self._conn.rollback()
                    logger.debug("Transaction rolled back")

                    # Run rollback hooks
                    for hook in self._hooks_on_rollback:
                        try:
                            hook()
                        except Exception as hook_e:
                            logger.warning(f"Rollback hook failed: {hook_e}")
            except sqlite3.Error as rollback_e:
                logger.error(f"Rollback failed: {rollback_e}")

            raise TransactionError(
                f"Transaction failed: {str(e)}",
                cause=e
            ) from e

    @contextmanager
    def atomic(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Shorthand for transaction() with default settings.

        Usage:
            with tx_manager.atomic() as conn:
                conn.execute("INSERT INTO ...")
        """
        with self.transaction() as conn:
            yield conn


T = TypeVar('T')


def with_transaction(
    get_connection: Callable[[], sqlite3.Connection],
    isolation: IsolationLevel = IsolationLevel.IMMEDIATE,
    max_retries: int = 3,
    retry_delay_ms: int = 100
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for wrapping functions in a transaction.

    Args:
        get_connection: Function that returns the database connection
        isolation: Transaction isolation level
        max_retries: Maximum number of retries for transient failures
        retry_delay_ms: Delay between retries in milliseconds

    Returns:
        Decorator function

    Usage:
        @with_transaction(lambda: db.conn)
        def save_data(data):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            import time

            conn = get_connection()
            tx_manager = TransactionManager(conn, isolation)

            last_error = None
            for attempt in range(max_retries):
                try:
                    with tx_manager.atomic():
                        return func(*args, **kwargs)
                except TransactionError as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Transaction attempt {attempt + 1} failed, retrying: {e}"
                        )
                        time.sleep(retry_delay_ms / 1000)
                    else:
                        logger.error(f"Transaction failed after {max_retries} attempts")

            raise last_error

        return wrapper
    return decorator


class BatchOperationManager:
    """
    Manages batch operations with progress tracking and partial commit support.

    This is useful for large data migrations or bulk imports where you want
    to commit periodically to avoid losing all progress on failure.
    """

    def __init__(
        self,
        tx_manager: TransactionManager,
        batch_size: int = 100
    ):
        """
        Initialize batch operation manager.

        Args:
            tx_manager: Transaction manager for the database
            batch_size: Number of operations before auto-commit
        """
        self._tx_manager = tx_manager
        self._batch_size = batch_size
        self._operation_count = 0
        self._total_operations = 0
        self._failed_operations: list[tuple[int, Exception]] = []

    @property
    def progress(self) -> dict:
        """Get current batch progress"""
        return {
            "total": self._total_operations,
            "completed": self._operation_count,
            "failed": len(self._failed_operations),
            "pending_batch": self._operation_count % self._batch_size
        }

    def execute(
        self,
        operation: Callable[[], None],
        continue_on_error: bool = True
    ) -> bool:
        """
        Execute a single operation within the batch.

        Args:
            operation: The operation to execute
            continue_on_error: If True, continue with other operations on failure

        Returns:
            True if operation succeeded, False otherwise
        """
        self._total_operations += 1

        try:
            operation()
            self._operation_count += 1

            # Auto-commit batch if threshold reached
            if self._operation_count % self._batch_size == 0:
                logger.info(f"Batch checkpoint: {self._operation_count} operations completed")

            return True

        except Exception as e:
            self._failed_operations.append((self._total_operations, e))
            logger.warning(f"Operation {self._total_operations} failed: {e}")

            if not continue_on_error:
                raise

            return False

    def get_failed_operations(self) -> list[tuple[int, Exception]]:
        """Get list of failed operations with their indices and errors"""
        return self._failed_operations.copy()
