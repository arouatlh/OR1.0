from fastapi import APIRouter

from app.responses import write_success_response

router = APIRouter()


@router.get("/demo/alert", response_model=None)
async def get_demo_alert():
    alert_data = {
        "id": "01JD8Z3K6Q9X2V4N7M1B5C8R0T",
        "astronaut_id": "astro-a",
        "rule_id": "hr_high",
        "severity": "critical",
        "title": "Elevated heart rate",
        "message": "Heart rate 156 bpm exceeds critical threshold of 150 bpm.",
        "metric": "heart_rate",
        "value": 156,
        "threshold": 150,
        "status": "open",
        "origin": "demo",
        "created_at": "2026-11-14T10:30:00Z",
        "updated_at": "2026-11-14T10:30:00Z",
    }
    return write_success_response(200, alert_data)
