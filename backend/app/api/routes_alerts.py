from fastapi import APIRouter, Request

from app.db.alerts import list_alerts
from app.domain.models import Alert
from app.responses import get_pagination_params, write_paginated_response, write_success_response

router = APIRouter()


@router.get("", response_model=None)
async def list_alerts_route(request: Request):
    db = request.app.state.db
    offset, limit = get_pagination_params(request)

    status = request.query_params.get("status")
    severity = request.query_params.get("severity")
    astronaut_id = request.query_params.get("astronaut_id")

    alerts, total = await list_alerts(db.conn, status=status, severity=severity, astronaut_id=astronaut_id, offset=offset, limit=limit)
    result = [_serialize_alert(a) for a in alerts]
    return write_paginated_response(200, result, count=len(result))


@router.post("/{alert_id}/ack", response_model=None)
async def acknowledge_alert_route(request: Request, alert_id: str):
    alert_svc = request.app.state.alert_service
    alert = await alert_svc.acknowledge(alert_id)
    return write_success_response(200, _serialize_alert(alert))


def _serialize_alert(a: Alert) -> dict:
    return {
        "id": a.id,
        "astronaut_id": a.astronaut_id,
        "rule_id": a.rule_id,
        "severity": a.severity.value,
        "title": a.title,
        "message": a.message,
        "metric": a.metric,
        "value": a.value,
        "threshold": a.threshold,
        "status": a.status.value,
        "origin": a.origin.value,
        "created_at": a.created_at.isoformat(),
        "updated_at": a.updated_at.isoformat(),
    }
