"""
Webhook Event Publishing System

This module provides a robust webhook system for integrating the tap station
with external services. It enables:
- Event publishing to external endpoints
- Retry logic with exponential backoff
- Payload signing for security
- Event filtering and transformation
- Delivery status tracking

Webhooks enable integration with:
- External dashboards and monitoring
- Data warehouses and analytics
- Alert systems and notifications
- Audit and compliance systems
"""

import hashlib
import hmac
import json
import logging
import queue
import threading
import time
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse

from .datetime_utils import utc_now, to_iso
from .constants import DeliveryStatus

logger = logging.getLogger(__name__)


class WebhookEventType(Enum):
    """Types of events that can trigger webhooks"""
    # Event lifecycle
    EVENT_CREATED = "event.created"
    EVENT_UPDATED = "event.updated"
    EVENT_DELETED = "event.deleted"

    # Journey events
    JOURNEY_STARTED = "journey.started"
    JOURNEY_COMPLETED = "journey.completed"
    JOURNEY_ABANDONED = "journey.abandoned"

    # Queue events
    QUEUE_UPDATED = "queue.updated"
    QUEUE_THRESHOLD_WARNING = "queue.threshold.warning"
    QUEUE_THRESHOLD_CRITICAL = "queue.threshold.critical"

    # Service events
    SERVICE_STARTED = "service.started"
    SERVICE_STOPPED = "service.stopped"

    # System events
    SYSTEM_HEALTH = "system.health"
    SYSTEM_ERROR = "system.error"

    # Anomaly events
    ANOMALY_DETECTED = "anomaly.detected"

    # Test event
    TEST = "test"


@dataclass
class WebhookEndpoint:
    """Configuration for a webhook endpoint"""
    id: str
    url: str
    secret: Optional[str] = None
    events: Set[WebhookEventType] = field(default_factory=set)
    enabled: bool = True
    headers: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 60
    description: str = ""

    def subscribes_to(self, event_type: WebhookEventType) -> bool:
        """Check if this endpoint subscribes to an event type"""
        if not self.events:
            return True  # Empty set = subscribe to all
        return event_type in self.events


@dataclass
class WebhookPayload:
    """Payload for a webhook delivery"""
    id: str
    event_type: WebhookEventType
    timestamp: datetime
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event": self.event_type.value,
            "timestamp": to_iso(self.timestamp),
            "data": self.data,
            "metadata": self.metadata
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass
class DeliveryRecord:
    """Record of a webhook delivery attempt"""
    id: str
    endpoint_id: str
    payload_id: str
    status: DeliveryStatus
    attempt: int
    created_at: datetime
    delivered_at: Optional[datetime] = None
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    error: Optional[str] = None


class WebhookSigner:
    """Signs webhook payloads for verification"""

    ALGORITHM = "sha256"

    def __init__(self, secret: str):
        self._secret = secret.encode('utf-8')

    def sign(self, payload: str) -> str:
        """Generate HMAC signature for payload"""
        return hmac.new(
            self._secret,
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def get_signature_header(self, payload: str, timestamp: int) -> str:
        """Get signature header value"""
        signed_payload = f"{timestamp}.{payload}"
        signature = self.sign(signed_payload)
        return f"t={timestamp},v1={signature}"


class WebhookDeliveryWorker(threading.Thread):
    """Background worker for webhook delivery"""

    def __init__(
        self,
        delivery_queue: queue.Queue,
        manager: 'WebhookManager'
    ):
        super().__init__(daemon=True)
        self._queue = delivery_queue
        self._manager = manager
        self._running = True

    def run(self):
        while self._running:
            try:
                # Get next delivery with timeout
                item = self._queue.get(timeout=1.0)
                if item is None:
                    continue

                endpoint, payload = item
                self._deliver(endpoint, payload)

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Delivery worker error: {e}", exc_info=True)

    def stop(self):
        self._running = False

    def _deliver(self, endpoint: WebhookEndpoint, payload: WebhookPayload):
        """Attempt to deliver a webhook"""
        for attempt in range(1, endpoint.max_retries + 1):
            try:
                success = self._send_request(endpoint, payload, attempt)
                if success:
                    return
            except Exception as e:
                logger.warning(
                    f"Webhook delivery attempt {attempt} failed: {e}"
                )

            if attempt < endpoint.max_retries:
                # Exponential backoff
                delay = endpoint.retry_delay_seconds * (2 ** (attempt - 1))
                time.sleep(delay)

        logger.error(
            f"Webhook delivery failed after {endpoint.max_retries} attempts: "
            f"{endpoint.url}"
        )

    def _send_request(
        self,
        endpoint: WebhookEndpoint,
        payload: WebhookPayload,
        attempt: int
    ) -> bool:
        """Send HTTP request to endpoint"""
        payload_json = payload.to_json()
        timestamp = int(time.time())

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "NFC-Tap-Logger-Webhook/1.0",
            "X-Webhook-ID": payload.id,
            "X-Webhook-Timestamp": str(timestamp),
        }

        # Add signature if secret configured
        if endpoint.secret:
            signer = WebhookSigner(endpoint.secret)
            headers["X-Webhook-Signature"] = signer.get_signature_header(
                payload_json, timestamp
            )

        # Add custom headers
        headers.update(endpoint.headers)

        try:
            request = Request(
                endpoint.url,
                data=payload_json.encode('utf-8'),
                headers=headers,
                method='POST'
            )

            with urlopen(request, timeout=endpoint.timeout_seconds) as response:
                status_code = response.status
                response_body = response.read().decode('utf-8', errors='replace')

                if 200 <= status_code < 300:
                    self._manager._log_delivery(
                        endpoint.id, payload.id, DeliveryStatus.DELIVERED,
                        attempt, status_code, response_body[:500]
                    )
                    return True
                else:
                    self._manager._log_delivery(
                        endpoint.id, payload.id, DeliveryStatus.FAILED,
                        attempt, status_code, response_body[:500]
                    )
                    return False

        except HTTPError as e:
            self._manager._log_delivery(
                endpoint.id, payload.id, DeliveryStatus.FAILED,
                attempt, e.code, str(e)
            )
            return False

        except URLError as e:
            self._manager._log_delivery(
                endpoint.id, payload.id, DeliveryStatus.FAILED,
                attempt, None, str(e)
            )
            return False


class WebhookManager:
    """
    Central manager for webhook operations.

    Handles:
    - Endpoint registration and management
    - Event publishing
    - Delivery tracking
    - Configuration persistence
    """

    def __init__(
        self,
        conn: Optional[sqlite3.Connection] = None,
        worker_count: int = 2
    ):
        """
        Initialize webhook manager.

        Args:
            conn: Database connection for persistence
            worker_count: Number of delivery workers
        """
        self._conn = conn
        self._endpoints: Dict[str, WebhookEndpoint] = {}
        self._delivery_queue: queue.Queue = queue.Queue()
        self._workers: List[WebhookDeliveryWorker] = []
        self._filters: Dict[str, Callable[[WebhookPayload], bool]] = {}
        self._transformers: Dict[str, Callable[[WebhookPayload], WebhookPayload]] = {}
        self._payload_counter = 0

        if conn:
            self._ensure_tables()

        # Start workers
        for _ in range(worker_count):
            worker = WebhookDeliveryWorker(self._delivery_queue, self)
            worker.start()
            self._workers.append(worker)

    def _ensure_tables(self):
        """Create webhook tables if needed"""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS webhook_endpoints (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                secret TEXT,
                events_json TEXT,
                enabled INTEGER DEFAULT 1,
                headers_json TEXT,
                timeout_seconds INTEGER DEFAULT 30,
                max_retries INTEGER DEFAULT 3,
                retry_delay_seconds INTEGER DEFAULT 60,
                description TEXT,
                created_at TEXT NOT NULL
            )
        """)

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS webhook_deliveries (
                id TEXT PRIMARY KEY,
                endpoint_id TEXT NOT NULL,
                payload_id TEXT NOT NULL,
                status TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                delivered_at TEXT,
                response_code INTEGER,
                response_body TEXT,
                error TEXT,
                FOREIGN KEY (endpoint_id) REFERENCES webhook_endpoints(id)
            )
        """)

        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_deliveries_endpoint
            ON webhook_deliveries(endpoint_id, created_at)
        """)

        self._conn.commit()

    def register_endpoint(self, endpoint: WebhookEndpoint) -> None:
        """
        Register a webhook endpoint.

        Args:
            endpoint: The endpoint configuration
        """
        # Validate URL
        parsed = urlparse(endpoint.url)
        if parsed.scheme not in ('http', 'https'):
            raise ValueError(f"Invalid URL scheme: {parsed.scheme}")

        self._endpoints[endpoint.id] = endpoint

        # Persist if database available
        if self._conn:
            self._conn.execute("""
                INSERT OR REPLACE INTO webhook_endpoints
                (id, url, secret, events_json, enabled, headers_json,
                 timeout_seconds, max_retries, retry_delay_seconds,
                 description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                endpoint.id,
                endpoint.url,
                endpoint.secret,
                json.dumps([e.value for e in endpoint.events]),
                1 if endpoint.enabled else 0,
                json.dumps(endpoint.headers),
                endpoint.timeout_seconds,
                endpoint.max_retries,
                endpoint.retry_delay_seconds,
                endpoint.description,
                to_iso(utc_now())
            ))
            self._conn.commit()

        logger.info(f"Registered webhook endpoint: {endpoint.id} -> {endpoint.url}")

    def unregister_endpoint(self, endpoint_id: str) -> bool:
        """
        Unregister a webhook endpoint.

        Args:
            endpoint_id: ID of the endpoint to remove

        Returns:
            True if removed, False if not found
        """
        if endpoint_id not in self._endpoints:
            return False

        del self._endpoints[endpoint_id]

        if self._conn:
            self._conn.execute(
                "DELETE FROM webhook_endpoints WHERE id = ?",
                (endpoint_id,)
            )
            self._conn.commit()

        return True

    def set_endpoint_enabled(self, endpoint_id: str, enabled: bool) -> bool:
        """Enable or disable an endpoint"""
        if endpoint_id not in self._endpoints:
            return False

        self._endpoints[endpoint_id].enabled = enabled

        if self._conn:
            self._conn.execute(
                "UPDATE webhook_endpoints SET enabled = ? WHERE id = ?",
                (1 if enabled else 0, endpoint_id)
            )
            self._conn.commit()

        return True

    def add_filter(
        self,
        name: str,
        filter_func: Callable[[WebhookPayload], bool]
    ) -> None:
        """
        Add a filter that can suppress webhook delivery.

        Args:
            name: Filter name
            filter_func: Function that returns True to allow delivery
        """
        self._filters[name] = filter_func

    def add_transformer(
        self,
        name: str,
        transform_func: Callable[[WebhookPayload], WebhookPayload]
    ) -> None:
        """
        Add a transformer to modify payloads before delivery.

        Args:
            name: Transformer name
            transform_func: Function that transforms the payload
        """
        self._transformers[name] = transform_func

    def publish(
        self,
        event_type: WebhookEventType,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Publish an event to all subscribed endpoints.

        Args:
            event_type: Type of event
            data: Event data
            metadata: Optional metadata

        Returns:
            Payload ID
        """
        self._payload_counter += 1
        payload_id = f"wh_{int(time.time())}_{self._payload_counter}"

        payload = WebhookPayload(
            id=payload_id,
            event_type=event_type,
            timestamp=utc_now(),
            data=data,
            metadata=metadata or {}
        )

        # Apply filters
        for filter_name, filter_func in self._filters.items():
            try:
                if not filter_func(payload):
                    logger.debug(f"Payload {payload_id} filtered by {filter_name}")
                    return payload_id
            except Exception as e:
                logger.warning(f"Filter {filter_name} error: {e}")

        # Apply transformers
        for transformer_name, transform_func in self._transformers.items():
            try:
                payload = transform_func(payload)
            except Exception as e:
                logger.warning(f"Transformer {transformer_name} error: {e}")

        # Queue for delivery to subscribed endpoints
        delivered_to = 0
        for endpoint in self._endpoints.values():
            if not endpoint.enabled:
                continue
            if not endpoint.subscribes_to(event_type):
                continue

            self._delivery_queue.put((endpoint, payload))
            delivered_to += 1

        logger.debug(
            f"Published {event_type.value} to {delivered_to} endpoints "
            f"(payload_id={payload_id})"
        )

        return payload_id

    def publish_test(self, endpoint_id: str) -> Optional[str]:
        """
        Send a test webhook to a specific endpoint.

        Args:
            endpoint_id: ID of the endpoint to test

        Returns:
            Payload ID if sent, None if endpoint not found
        """
        endpoint = self._endpoints.get(endpoint_id)
        if not endpoint:
            return None

        payload = WebhookPayload(
            id=f"test_{int(time.time())}",
            event_type=WebhookEventType.TEST,
            timestamp=utc_now(),
            data={"message": "Test webhook from NFC Tap Logger"},
            metadata={"test": True}
        )

        self._delivery_queue.put((endpoint, payload))
        return payload.id

    def _log_delivery(
        self,
        endpoint_id: str,
        payload_id: str,
        status: DeliveryStatus,
        attempt: int,
        response_code: Optional[int] = None,
        response_body: Optional[str] = None,
        error: Optional[str] = None
    ) -> None:
        """Log a delivery attempt"""
        if not self._conn:
            return

        delivery_id = f"del_{int(time.time())}_{payload_id}"
        delivered_at = to_iso(utc_now()) if status == DeliveryStatus.DELIVERED else None

        try:
            self._conn.execute("""
                INSERT INTO webhook_deliveries
                (id, endpoint_id, payload_id, status, attempt, created_at,
                 delivered_at, response_code, response_body, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                delivery_id,
                endpoint_id,
                payload_id,
                status.value,
                attempt,
                to_iso(utc_now()),
                delivered_at,
                response_code,
                response_body,
                error
            ))
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to log delivery: {e}")

    def get_endpoints(self) -> List[WebhookEndpoint]:
        """Get all registered endpoints"""
        return list(self._endpoints.values())

    def get_endpoint(self, endpoint_id: str) -> Optional[WebhookEndpoint]:
        """Get an endpoint by ID"""
        return self._endpoints.get(endpoint_id)

    def get_delivery_history(
        self,
        endpoint_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get delivery history"""
        if not self._conn:
            return []

        query = "SELECT * FROM webhook_deliveries"
        params = []

        if endpoint_id:
            query += " WHERE endpoint_id = ?"
            params.append(endpoint_id)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = self._conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_delivery_stats(
        self,
        endpoint_id: Optional[str] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get delivery statistics"""
        if not self._conn:
            return {}

        cutoff = to_iso(utc_now() - timedelta(hours=hours))

        query = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) as delivered,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                AVG(attempt) as avg_attempts
            FROM webhook_deliveries
            WHERE created_at > ?
        """
        params = [cutoff]

        if endpoint_id:
            query += " AND endpoint_id = ?"
            params.append(endpoint_id)

        cursor = self._conn.execute(query, params)
        row = cursor.fetchone()

        if row:
            total = row["total"] or 0
            delivered = row["delivered"] or 0
            return {
                "total": total,
                "delivered": delivered,
                "failed": row["failed"] or 0,
                "success_rate": (delivered / total * 100) if total > 0 else 100,
                "avg_attempts": row["avg_attempts"] or 1,
                "period_hours": hours
            }

        return {
            "total": 0, "delivered": 0, "failed": 0,
            "success_rate": 100, "avg_attempts": 1, "period_hours": hours
        }

    def shutdown(self) -> None:
        """Shutdown the webhook manager"""
        logger.info("Shutting down webhook manager...")

        # Stop workers
        for worker in self._workers:
            worker.stop()

        # Wait for queue to drain (with timeout)
        try:
            self._delivery_queue.join()
        except Exception:
            pass

        logger.info("Webhook manager shutdown complete")


# =============================================================================
# Global Instance
# =============================================================================

_webhook_manager: Optional[WebhookManager] = None


def get_webhook_manager(
    conn: Optional[sqlite3.Connection] = None
) -> WebhookManager:
    """Get or create the webhook manager"""
    global _webhook_manager
    if _webhook_manager is None:
        _webhook_manager = WebhookManager(conn)
    return _webhook_manager


def publish_event(
    event_type: WebhookEventType,
    data: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """Convenience function to publish a webhook event"""
    return get_webhook_manager().publish(event_type, data, metadata)
