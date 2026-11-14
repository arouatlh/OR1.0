from datetime import UTC, datetime

import pytest

from app.db.alerts import acknowledge_alert, create_alert, get_alert
from app.db.astronauts import list_astronauts
from app.db.connection import Database
from app.db.outbox import get_pending_count
from app.db.telemetry import get_latest_telemetry, insert_telemetry_batch
from app.domain.models import Alert, AlertOrigin, AlertStatus, Sample, Severity


@pytest.fixture
async def temp_db(tmp_path):
    db_file = str(tmp_path / "test.db")
    db = Database(db_file)
    await db.open()
    yield db
    await db.close()


async def test_db_init_and_seed(temp_db):
    astronauts = await list_astronauts(temp_db.conn)
    assert len(astronauts) == 3
    ids = [a.id for a in astronauts]
    assert ids == ["astro-a", "astro-b", "astro-c"]


async def test_telemetry_idempotency_and_outbox(temp_db):
    now = datetime.now(UTC)
    samples = [
        Sample(astronaut_id="astro-a", client_id="c-001", recorded_at=now, heart_rate=72, spo2=98),
        Sample(astronaut_id="astro-a", client_id="c-002", recorded_at=now, heart_rate=74, spo2=97),
    ]

    # First ingest: 2 accepted, 0 duplicates
    async with temp_db.write_tx() as conn:
        accepted, duplicates, accepted_samples = await insert_telemetry_batch(conn, "astro-a", samples)

    assert accepted == 2
    assert duplicates == 0
    assert len(accepted_samples) == 2

    # Verify outbox entries were recorded in same transaction
    pending = await get_pending_count(temp_db.conn)
    assert pending == 2

    # Re-ingest exact same samples: 0 accepted, 2 duplicates
    async with temp_db.write_tx() as conn:
        accepted2, duplicates2, _ = await insert_telemetry_batch(conn, "astro-a", samples)

    assert accepted2 == 0
    assert duplicates2 == 2

    # Verify latest sample
    latest = await get_latest_telemetry(temp_db.conn, "astro-a")
    assert latest is not None
    assert latest.client_id in ("c-001", "c-002")


async def test_alert_lifecycle(temp_db):
    now = datetime.now(UTC)
    alert = Alert(
        id="alert-001",
        astronaut_id="astro-a",
        rule_id="hr_high",
        severity=Severity.CRITICAL,
        title="Elevated heart rate",
        message="HR 156 exceeds 150",
        metric="heart_rate",
        value=156.0,
        threshold=150.0,
        status=AlertStatus.OPEN,
        origin=AlertOrigin.RULES,
        created_at=now,
        updated_at=now,
    )

    # Create
    async with temp_db.write_tx() as conn:
        await create_alert(conn, alert)

    # Get
    fetched = await get_alert(temp_db.conn, "alert-001")
    assert fetched.id == "alert-001"
    assert fetched.status == AlertStatus.OPEN

    # Acknowledge
    async with temp_db.write_tx() as conn:
        acked = await acknowledge_alert(conn, "alert-001", now)
    assert acked.status == AlertStatus.ACKNOWLEDGED
