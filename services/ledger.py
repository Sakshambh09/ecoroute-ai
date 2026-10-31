"""Persistent carbon-impact ledger (SQLite).

The in-memory metrics reset on every restart; this ledger does not. Each
optimized query appends one row, so the cumulative CO2e-saved figure is a
durable, auditable number — the "live impact" stat for the demo survives
reboots and can be exported for reporting.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS queries (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    request_id TEXT NOT NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    vehicle_type TEXT NOT NULL,
    carbon_saved_kg REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_queries_ts ON queries(ts);
"""


class CarbonLedger:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def record(
        self,
        request_id: str,
        origin: str,
        destination: str,
        vehicle_type: str,
        carbon_saved_kg: float,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO queries (ts, request_id, origin, destination, vehicle_type, carbon_saved_kg)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (ts, request_id, origin, destination, vehicle_type, carbon_saved_kg),
            )
            self._conn.commit()

    def totals(self) -> tuple[int, float]:
        """Return (query_count, total_carbon_saved_kg) since first run."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(carbon_saved_kg), 0) FROM queries"
            ).fetchone()
        return int(row[0]), float(row[1])

    def close(self) -> None:
        with self._lock:
            self._conn.close()
