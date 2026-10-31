"""Unit tests for the persistent carbon ledger."""
from __future__ import annotations

import tempfile
from pathlib import Path

from services.ledger import CarbonLedger


def _ledger() -> tuple[CarbonLedger, Path]:
    path = Path(tempfile.mkdtemp()) / "ledger.db"
    return CarbonLedger(path), path


def test_record_and_totals():
    ledger, _ = _ledger()
    ledger.record("r1", "Delhi", "Jaipur", "heavy_truck", 45.0)
    ledger.record("r2", "Mumbai", "Pune", "electric_van", 3.0)
    count, total = ledger.totals()
    assert count == 2
    assert abs(total - 48.0) < 1e-6
    ledger.close()


def test_empty_ledger_totals():
    ledger, _ = _ledger()
    count, total = ledger.totals()
    assert count == 0
    assert total == 0.0
    ledger.close()


def test_persistence_across_reopen():
    """The whole point: totals survive a close/reopen (restart)."""
    _, path = _ledger()
    ledger = CarbonLedger(path)
    ledger.record("r1", "A", "B", "light_truck", 10.0)
    ledger.close()

    reopened = CarbonLedger(path)
    count, total = reopened.totals()
    assert count == 1
    assert abs(total - 10.0) < 1e-6
    reopened.close()
