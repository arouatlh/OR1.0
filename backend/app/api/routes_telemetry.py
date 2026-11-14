from datetime import UTC, datetime

from fastapi import APIRouter, Request

from app.api.schemas import TelemetryBatchRequest
from app.db.telemetry import get_history
from app.domain.models import Sample
from app.errors import bad_request
from app.responses import get_pagination_params, write_paginated_response, write_success_response

router = APIRouter()


@router.post("", response_model=None)
async def ingest_telemetry(request: Request, body: TelemetryBatchRequest):
    ingest_svc = request.app.state.ingest_service

    domain_samples = [
        Sample(
            astronaut_id=body.astronaut_id,
            client_id=s.client_id,
            recorded_at=s.recorded_at,
            source=s.source,
            heart_rate=s.heart_rate,
            spo2=s.spo2,
            systolic=s.systolic,
            diastolic=s.diastolic,
            resp_rate=s.resp_rate,
            ecg_summary=s.ecg_summary,
            stress_index=s.stress_index,
        )
        for s in body.samples
    ]

    res = await ingest_svc.ingest(body.astronaut_id, domain_samples)
    return write_success_response(202, res)


@router.get("/export", response_model=None)
async def export_telemetry(request: Request):
    db = request.app.state.db
    offset, limit = get_pagination_params(request)
    astronaut_id = request.query_params.get("astronaut_id", "astro-a")

    samples, total = await get_history(db.conn, astronaut_id, offset=offset, limit=limit, order="ASC")
    result = [_serialize_sample(s) for s in samples]
    return write_paginated_response(200, result, count=len(result))


@router.get("/astronauts/{astronaut_id}/telemetry", response_model=None)
async def get_astronaut_telemetry(request: Request, astronaut_id: str):
    db = request.app.state.db
    offset, limit = get_pagination_params(request)

    from_time = None
    if from_str := request.query_params.get("from"):
        try:
            from_time = datetime.fromisoformat(from_str).astimezone(UTC)
        except ValueError as exc:
            raise bad_request("api.telemetry.history", "Invalid 'from' timestamp: must be RFC 3339 format.") from exc

    to_time = None
    if to_str := request.query_params.get("to"):
        try:
            to_time = datetime.fromisoformat(to_str).astimezone(UTC)
        except ValueError as exc:
            raise bad_request("api.telemetry.history", "Invalid 'to' timestamp: must be RFC 3339 format.") from exc

    order = request.query_params.get("order", "DESC")
    samples, total = await get_history(db.conn, astronaut_id, from_time=from_time, to_time=to_time, offset=offset, limit=limit, order=order)
    result = [_serialize_sample(s) for s in samples]
    return write_paginated_response(200, result, count=len(result))


def _serialize_sample(s: Sample) -> dict:
    return {
        "id": s.id,
        "astronaut_id": s.astronaut_id,
        "client_id": s.client_id,
        "recorded_at": s.recorded_at.isoformat(),
        "received_at": s.received_at.isoformat() if s.received_at else None,
        "source": s.source,
        "heart_rate": s.heart_rate,
        "spo2": s.spo2,
        "systolic": s.systolic,
        "diastolic": s.diastolic,
        "resp_rate": s.resp_rate,
        "ecg_summary": s.ecg_summary,
        "stress_index": s.stress_index,
    }
