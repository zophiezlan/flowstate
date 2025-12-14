#!/usr/bin/env python3
"""
Data Export Script

Export event data from SQLite to CSV with timestamp in filename.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from datetime import datetime
from pathlib import Path
from tap_station.config import Config
from tap_station.database import Database


def export_data(
    config_path: str = "config.yaml",
    output_dir: str = ".",
    session_id: str = None,
    filename: str = None
):
    """
    Export event data to CSV

    Args:
        config_path: Path to configuration file
        output_dir: Output directory for CSV file
        session_id: Optional session ID filter
        filename: Optional custom filename

    Returns:
        Path to exported CSV file
    """
    # Load config
    config = Config(config_path)

    # Use session from config if not specified
    if session_id is None:
        session_id = config.session_id

    # Generate filename with timestamp if not provided
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"export_{timestamp}.csv"

    # Ensure .csv extension
    if not filename.endswith('.csv'):
        filename += '.csv'

    # Build output path
    output_path = Path(output_dir) / filename

    # Open database and export
    print(f"Exporting data from: {config.database_path}")
    print(f"Session ID filter: {session_id}")
    print(f"Output file: {output_path}")

    db = Database(config.database_path, wal_mode=False)

    try:
        # Export to CSV
        row_count = db.export_to_csv(str(output_path), session_id=session_id)

        print(f"\n✓ Exported {row_count} events to {output_path}")

        # Show summary stats
        if row_count > 0:
            print_summary(db, session_id)

        return output_path

    finally:
        db.close()


def print_summary(db: Database, session_id: str):
    """Print summary statistics"""
    # Get event count by stage
    cursor = db.conn.execute("""
        SELECT stage, COUNT(*) as count
        FROM events
        WHERE session_id = ?
        GROUP BY stage
        ORDER BY stage
    """, (session_id,))

    stages = cursor.fetchall()

    print("\nEvent Summary:")
    print("-" * 40)
    for row in stages:
        print(f"  {row['stage']}: {row['count']} events")

    # Get unique tokens
    cursor = db.conn.execute("""
        SELECT COUNT(DISTINCT token_id) as count
        FROM events
        WHERE session_id = ?
    """, (session_id,))

    unique_tokens = cursor.fetchone()['count']
    print(f"\nUnique tokens: {unique_tokens}")

    # Get time range
    cursor = db.conn.execute("""
        SELECT MIN(timestamp) as first, MAX(timestamp) as last
        FROM events
        WHERE session_id = ?
    """, (session_id,))

    time_range = cursor.fetchone()
    if time_range['first']:
        print(f"Time range: {time_range['first']} to {time_range['last']}")

    print("-" * 40)


def main():
    """Entry point for data export"""
    parser = argparse.ArgumentParser(description='Export event data to CSV')
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    parser.add_argument(
        '--output-dir',
        default='.',
        help='Output directory (default: current directory)'
    )
    parser.add_argument(
        '--session',
        help='Session ID filter (default: from config)'
    )
    parser.add_argument(
        '--filename',
        help='Custom output filename (default: export_TIMESTAMP.csv)'
    )
    parser.add_argument(
        '--all-sessions',
        action='store_true',
        help='Export all sessions (ignore session filter)'
    )

    args = parser.parse_args()

    try:
        # Determine session filter
        session_id = None if args.all_sessions else args.session

        # Export data
        output_path = export_data(
            config_path=args.config,
            output_dir=args.output_dir,
            session_id=session_id,
            filename=args.filename
        )

        print(f"\nExport complete!")
        print(f"\nTo analyze in R:")
        print(f"  library(tidyverse)")
        print(f"  events <- read_csv('{output_path}')")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
