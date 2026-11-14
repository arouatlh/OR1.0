import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import create_app


@pytest.fixture
async def client(tmp_path):
    settings = get_settings()
    settings.db_path = str(tmp_path / "api_test.db")
    settings.app_env = "dev"
    app = create_app()

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def test_first_milestone_canonical_demo_alert(client):
    """FIRST MILESTONE: GET /api/v1/demo/alert returns canonical simulated alert JSON (Part 6.1)"""
    resp = await client.get("/api/v1/demo/alert")
    assert resp.status_code == 200
    assert "x-request-id" in resp.headers

    body = resp.json()
    assert body["message"] == "Success"
    assert body["status_code"] == 200

    data = body["data"]
    assert data["id"] == "01JD8Z3K6Q9X2V4N7M1B5C8R0T"
    assert data["astronaut_id"] == "astro-a"
    assert data["rule_id"] == "hr_high"
    assert data["severity"] == "critical"
    assert data["value"] == 156
    assert data["threshold"] == 150
    assert data["status"] == "open"
    assert data["origin"] == "demo"


async def test_health_probes(client):
    # Liveness
    resp_liveness = await client.get("/healthz")
    assert resp_liveness.status_code == 200
    assert resp_liveness.json() == {"status": "ok"}

    # Readiness
    resp_readiness = await client.get("/readyz")
    assert resp_readiness.status_code == 200
    assert resp_readiness.json()["status"] == "ok"
    assert "ml_loaded" in resp_readiness.json()


async def test_telemetry_validation_and_ingest(client):
    # 1. Validation error: SpO2 > 100 -> 422
    invalid_payload = {
        "astronaut_id": "astro-a",
        "samples": [
            {
                "client_id": "watch-001",
                "recorded_at": "2026-11-14T10:30:00Z",
                "source": "watch",
                "spo2": 150,  # Invalid
            }
        ],
    }
    resp = await client.post("/api/v1/telemetry", json=invalid_payload)
    assert resp.status_code == 422
    err_body = resp.json()
    assert err_body["status_code"] == 422
    assert "validation failed" in err_body["message"]
    assert "spo2" in err_body["message"]

    # 2. Valid Ingest -> 202 Accepted
    valid_payload = {
        "astronaut_id": "astro-a",
        "samples": [
            {
                "client_id": "watch-valid-1",
                "recorded_at": "2026-11-14T10:30:00Z",
                "source": "watch",
                "heart_rate": 72,
                "spo2": 98,
                "systolic": 118,
                "diastolic": 76,
                "resp_rate": 14,
            }
        ],
    }
    resp_valid = await client.post("/api/v1/telemetry", json=valid_payload)
    assert resp_valid.status_code == 202
    succ_body = resp_valid.json()
    assert succ_body["message"] == "Success"
    assert succ_body["data"]["accepted"] == 1
    assert succ_body["data"]["duplicates"] == 0

    # 3. Duplicate Ingest -> 202 Accepted with duplicates=1
    resp_dup = await client.post("/api/v1/telemetry", json=valid_payload)
    assert resp_dup.status_code == 202
    dup_body = resp_dup.json()
    assert dup_body["data"]["accepted"] == 0
    assert dup_body["data"]["duplicates"] == 1

    # 4. Ingest without blood pressure (systolic and diastolic completely omitted) -> 202 Accepted
    no_bp_payload = {
        "astronaut_id": "astro-a",
        "samples": [
            {
                "client_id": "watch-without-bp-001",
                "recorded_at": "2026-11-14T10:35:00Z",
                "source": "watch",
                "heart_rate": 78,
                "spo2": 99,
                "resp_rate": 15,
                "ecg_summary": "sinus",
                "stress_index": 0.18,
            }
        ],
    }
    resp_no_bp = await client.post("/api/v1/telemetry", json=no_bp_payload)
    assert resp_no_bp.status_code == 202
    assert resp_no_bp.json()["data"]["accepted"] == 1


async def test_astronauts_and_mode_toggle(client):
    # List astronauts
    resp_list = await client.get("/api/v1/astronauts")
    assert resp_list.status_code == 200
    assert len(resp_list.json()["data"]) == 3

    # Toggle EVA mode
    resp_patch = await client.patch("/api/v1/astronauts/astro-a/mode", json={"mode": "eva"})
    assert resp_patch.status_code == 200
    assert resp_patch.json()["data"]["mode"] == "eva"

    # Verify summary endpoint
    resp_summary = await client.get("/api/v1/astronauts/astro-a/summary")
    assert resp_summary.status_code == 200
    summary_data = resp_summary.json()["data"]
    assert summary_data["astronaut"]["mode"] == "eva"
    assert "stats_5min" in summary_data
    assert "open_alerts" in summary_data
