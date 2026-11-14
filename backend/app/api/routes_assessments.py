from fastapi import APIRouter, Request

from app.api.schemas import AssessmentRequest
from app.domain.models import Assessment
from app.responses import write_success_response

router = APIRouter()


@router.post("", response_model=None)
async def create_assessment_route(request: Request, body: AssessmentRequest):
    alert_svc = request.app.state.alert_service
    assessment = Assessment(
        astronaut_id=body.astronaut_id,
        model_version=body.model_version,
        risk_score=body.risk_score,
        label=body.label,
        explanation=body.explanation,
    )

    created = await alert_svc.record_assessment(assessment)
    return write_success_response(201, {
        "id": created.id,
        "astronaut_id": created.astronaut_id,
        "model_version": created.model_version,
        "risk_score": created.risk_score,
        "label": created.label,
        "explanation": created.explanation,
        "created_at": created.created_at.isoformat() if created.created_at else None,
    })
