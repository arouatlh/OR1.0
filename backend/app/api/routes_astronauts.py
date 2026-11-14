from datetime import UTC, datetime

from fastapi import APIRouter, Request

from app.api.schemas import ModeUpdateRequest
from app.db.alerts import count_open_alerts_by_astronaut, get_open_alerts_by_astronaut
from app.db.assessments import get_latest_assessment, list_assessments
from app.db.astronauts import get_astronaut, list_astronauts, update_mode
from app.db.telemetry import get_history, get_latest_telemetry
from app.domain.models import Mode, Sample, Severity
from app.errors import bad_request
from app.responses import get_pagination_params, write_paginated_response, write_success_response

router = APIRouter()


@router.get("", response_model=None)
async def list_astronauts_route(request: Request):
    db = request.app.state.db
    astronauts = await list_astronauts(db.conn)
    open_counts = await count_open_alerts_by_astronaut(db.conn)

    result = []
    for a in astronauts:
        latest_tel = await get_latest_telemetry(db.conn, a.id)
        open_cnt = open_counts.get(a.id, 0)
        status = "nominal"
        if open_cnt > 0:
            open_alerts = await get_open_alerts_by_astronaut(db.conn, a.id)
            has_crit = any(al.severity == Severity.CRITICAL for al in open_alerts.values())
            status = "critical" if has_crit else "warning"

        result.append({
            "id": a.id,
            "display_name": a.display_name,
            "mission": a.mission,
            "mode": a.mode.value,
            "baseline_hr": a.baseline_hr,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "open_alerts_count": open_cnt,
            "status": status,
            "latest_telemetry": {
                "id": latest_tel.id,
                "astronaut_id": latest_tel.astronaut_id,
                "client_id": latest_tel.client_id,
                "recorded_at": latest_tel.recorded_at.isoformat(),
                "source": latest_tel.source,
                "heart_rate": latest_tel.heart_rate,
                "spo2": latest_tel.spo2,
                "systolic": latest_tel.systolic,
                "diastolic": latest_tel.diastolic,
                "resp_rate": latest_tel.resp_rate,
                "ecg_summary": latest_tel.ecg_summary,
                "stress_index": latest_tel.stress_index,
            } if latest_tel else None,
        })

    return write_success_response(200, result)


@router.get("/{astronaut_id}", response_model=None)
async def get_astronaut_route(request: Request, astronaut_id: str):
    db = request.app.state.db
    a = await get_astronaut(db.conn, astronaut_id)
    latest_tel = await get_latest_telemetry(db.conn, a.id)
    open_alerts = await get_open_alerts_by_astronaut(db.conn, a.id)
    latest_assess = await get_latest_assessment(db.conn, a.id)

    status = "nominal"
    if open_alerts:
        has_crit = any(al.severity == Severity.CRITICAL for al in open_alerts.values())
        status = "critical" if has_crit else "warning"

    detail = {
        "id": a.id,
        "display_name": a.display_name,
        "mission": a.mission,
        "mode": a.mode.value,
        "baseline_hr": a.baseline_hr,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "open_alerts_count": len(open_alerts),
        "status": status,
        "latest_telemetry": {
            "id": latest_tel.id,
            "astronaut_id": latest_tel.astronaut_id,
            "client_id": latest_tel.client_id,
            "recorded_at": latest_tel.recorded_at.isoformat(),
            "source": latest_tel.source,
            "heart_rate": latest_tel.heart_rate,
            "spo2": latest_tel.spo2,
            "systolic": latest_tel.systolic,
            "diastolic": latest_tel.diastolic,
            "resp_rate": latest_tel.resp_rate,
            "ecg_summary": latest_tel.ecg_summary,
            "stress_index": latest_tel.stress_index,
        } if latest_tel else None,
        "latest_assessment": {
            "id": latest_assess.id,
            "astronaut_id": latest_assess.astronaut_id,
            "model_version": latest_assess.model_version,
            "risk_score": latest_assess.risk_score,
            "label": latest_assess.label,
            "explanation": latest_assess.explanation,
            "created_at": latest_assess.created_at.isoformat() if latest_assess.created_at else None,
        } if latest_assess else None,
    }
    return write_success_response(200, detail)


@router.patch("/{astronaut_id}/mode", response_model=None)
async def update_astronaut_mode(request: Request, astronaut_id: str, body: ModeUpdateRequest):
    db = request.app.state.db
    new_mode = Mode(body.mode)
    async with db.write_tx() as conn:
        await update_mode(conn, astronaut_id, new_mode)

    updated = await get_astronaut(db.conn, astronaut_id)
    return write_success_response(200, {
        "id": updated.id,
        "display_name": updated.display_name,
        "mission": updated.mission,
        "mode": updated.mode.value,
        "baseline_hr": updated.baseline_hr,
        "created_at": updated.created_at.isoformat() if updated.created_at else None,
    })


@router.get("/{astronaut_id}/summary", response_model=None)
async def get_astronaut_summary(request: Request, astronaut_id: str):
    summary_svc = request.app.state.summary_service
    summary = await summary_svc.get_summary(astronaut_id)
    return write_success_response(200, summary)


@router.get("/{astronaut_id}/assessments", response_model=None)
async def get_astronaut_assessments(request: Request, astronaut_id: str):
    db = request.app.state.db
    offset, limit = get_pagination_params(request)
    assessments, total = await list_assessments(db.conn, astronaut_id, offset, limit)

    result = [
        {
            "id": ass.id,
            "astronaut_id": ass.astronaut_id,
            "model_version": ass.model_version,
            "risk_score": ass.risk_score,
            "label": ass.label,
            "explanation": ass.explanation,
            "created_at": ass.created_at.isoformat() if ass.created_at else None,
        }
        for ass in assessments
    ]
    return write_paginated_response(200, result, count=len(result))


@router.get("/{astronaut_id}/telemetry", response_model=None)
async def get_astronaut_telemetry(request: Request, astronaut_id: str):
    db = request.app.state.db
    await get_astronaut(db.conn, astronaut_id)

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

