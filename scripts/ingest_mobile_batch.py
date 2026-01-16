"""Ingest mobile-exported NFC events into the core SQLite database."""

import argparse
import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from tap_station.database import Database

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _coerce_timestamp(value) -> datetime:
    """Convert ms timestamps or ISO strings to timezone-aware datetimes."""
    if value is None:
        return datetime.now(timezone.utc)

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)

    if isinstance(value, str):
        try:
            # Support ms stored as strings
            if value.isdigit():
                return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
            return datetime.fromisoformat(value)
        except ValueError:
            logger.warning("Could not parse timestamp '%s', falling back to now", value)
    return datetime.now(timezone.utc)


def _normalize_event(raw: Dict) -> Tuple[str, str, str, str, str, datetime]:
    """Normalize incoming event dict into the database fields."""
    token_id = str(raw.get("token_id") or raw.get("tokenId") or "UNKNOWN")
    uid = str(raw.get("uid") or raw.get("serial") or token_id or "UNKNOWN")
    stage = str(raw.get("stage") or "").strip().upper() or "UNKNOWN"
    session_id = str(raw.get("session_id") or raw.get("sessionId") or "UNKNOWN")
    device_id = str(raw.get("device_id") or raw.get("deviceId") or "mobile")
    ts_value = raw.get("timestamp_ms") or raw.get("timestamp") or raw.get("timestampMs")
    timestamp = _coerce_timestamp(ts_value)
    return token_id, uid, stage, session_id, device_id, timestamp


def _load_jsonl(path: Path) -> List[Dict]:
    events: List[Dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def _load_csv(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _load_events(path: Path) -> List[Dict]:
    if path.suffix.lower() == ".jsonl":
        return _load_jsonl(path)
    if path.suffix.lower() == ".csv":
        return _load_csv(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def ingest_events(events: Iterable[Dict], db_path: Path) -> Dict[str, int]:
    """Ingest parsed events into the SQLite database.

    Returns a summary dict with counts for inserted, duplicates, and errors.
    """
    summary = {"inserted": 0, "duplicates": 0, "errors": 0}
    with Database(str(db_path), wal_mode=True) as db:
        for event in events:
            try:
                (
                    token_id,
                    uid,
                    stage,
                    session_id,
                    device_id,
                    timestamp,
                ) = _normalize_event(event)
                success = db.log_event(
                    token_id=token_id,
                    uid=uid,
                    stage=stage,
                    device_id=device_id,
                    session_id=session_id,
                    timestamp=timestamp,
                )
                if success:
                    summary["inserted"] += 1
                else:
                    summary["duplicates"] += 1
            except Exception as exc:  # pragma: no cover - defensive
                summary["errors"] += 1
                logger.error("Failed to ingest event %s: %s", event, exc)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", required=True, help="Path to JSONL or CSV export from the mobile app"
    )
    parser.add_argument(
        "--db",
        default="data/events.db",
        help="Path to events database (default: data/events.db)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    events = _load_events(input_path)
    logger.info("Loaded %s events from %s", len(events), input_path)

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    summary = ingest_events(events, db_path)
    logger.info(
        "Ingestion complete: %s inserted, %s duplicates, %s errors",
        summary["inserted"],
        summary["duplicates"],
        summary["errors"],
    )


if __name__ == "__main__":
    main()
