from datetime import UTC, datetime

from app.db.alerts import get_open_alerts_by_astronaut
from app.db.assessments import get_latest_assessment
from app.db.astronauts import get_astronaut
from app.db.connection import Database
from app.db.telemetry import get_latest_telemetry, get_stats_5min


class SummaryService:
    def __init__(self, db: Database):
        self.db = db

    async def get_summary(self, astronaut_id: str) -> dict[str, object]:
        astronaut = await get_astronaut(self.db.conn, astronaut_id)
        latest_telemetry = await get_latest_telemetry(self.db.conn, astronaut_id)

        now = datetime.now(UTC)
        stats = await get_stats_5min(self.db.conn, astronaut_id, now)
        open_alerts_map = await get_open_alerts_by_astronaut(self.db.conn, astronaut_id)
        latest_assessment = await get_latest_assessment(self.db.conn, astronaut_id)

        return {
            "astronaut": {
                "id": astronaut.id,
                "display_name": astronaut.display_name,
                "mission": astronaut.mission,
                "mode": astronaut.mode.value,
                "baseline_hr": astronaut.baseline_hr,
                "created_at": astronaut.created_at.isoformat() if astronaut.created_at else None,
            },
            "latest_telemetry": {
                "id": latest_telemetry.id,
                "astronaut_id": latest_telemetry.astronaut_id,
                "client_id": latest_telemetry.client_id,
                "recorded_at": latest_telemetry.recorded_at.isoformat(),
                "source": latest_telemetry.source,
                "heart_rate": latest_telemetry.heart_rate,
                "spo2": latest_telemetry.spo2,
                "systolic": latest_telemetry.systolic,
                "diastolic": latest_telemetry.diastolic,
                "resp_rate": latest_telemetry.resp_rate,
                "ecg_summary": latest_telemetry.ecg_summary,
                "stress_index": latest_telemetry.stress_index,
            } if latest_telemetry else None,
            "stats_5min": stats,
            "open_alerts": [
                {
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
                for a in open_alerts_map.values()
            ],
            "latest_assessment": {
                "id": latest_assessment.id,
                "astronaut_id": latest_assessment.astronaut_id,
                "model_version": latest_assessment.model_version,
                "risk_score": latest_assessment.risk_score,
                "label": latest_assessment.label,
                "explanation": latest_assessment.explanation,
                "created_at": latest_assessment.created_at.isoformat() if latest_assessment.created_at else None,
            } if latest_assessment else None,
        }
