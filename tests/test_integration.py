"""V1 integration tests for core service flow."""

import os
import tempfile

from tap_station.database import Database


def _temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return path


def test_v1_core_flow_and_dashboard_like_queries():
    path = _temp_db_path()
    db = Database(path, wal_mode=True)

    try:
        session = "festival-v1"
        token = "100"
        uid = "uid-100"

        # create episode at entry-capable stage
        assert db.log_event(token, uid, "ENTERED", "entry-station", session)["success"]

        # progress through valid stages
        for stage in ["FIRST_CONTACT", "SAMPLE_LOGGED", "TESTING"]:
            assert db.log_event(token, uid, stage, f"{stage}-station", session)["success"]

        # correction to another valid stage
        correction = db.set_episode_stage(
            token_id=token,
            target_stage="RESULT_READY",
            session_id=session,
            corrected_by="supervisor",
        )
        assert correction["success"] is True
        assert correction["to_stage"] == "RESULT_READY"

        # dashboard-like state query: latest stage per token
        row = db.conn.execute(
            """
            WITH latest AS (
                SELECT token_id, MAX(id) AS max_id
                FROM events
                WHERE session_id = ?
                GROUP BY token_id
            )
            SELECT e.token_id, e.stage
            FROM events e
            INNER JOIN latest l ON l.max_id = e.id
            """,
            (session,),
        ).fetchone()
        assert row["token_id"] == token
        assert row["stage"] == "RESULT_READY"

        # export contains expected fields
        export_fd, export_path = tempfile.mkstemp(suffix=".csv")
        os.close(export_fd)
        try:
            db.export_to_csv(export_path, session_id=session)
            with open(export_path, "r", encoding="utf-8") as f:
                header = f.readline().strip()
            assert "token_id" in header
            assert "stage" in header
            assert "timestamp" in header
            assert "device_id" in header
            assert "session_id" in header
        finally:
            os.unlink(export_path)

    finally:
        db.close()
        for ext in ["", "-wal", "-shm"]:
            p = path + ext
            if os.path.exists(p):
                os.unlink(p)
