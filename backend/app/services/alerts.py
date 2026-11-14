import json
import uuid
from datetime import UTC, datetime

from app.db.alerts import (
    acknowledge_alert as db_ack_alert,
)
from app.db.alerts import (
    create_alert,
    get_open_alerts_by_astronaut,
    update_alert,
)
from app.db.assessments import create_assessment
from app.db.connection import Database
from app.db.outbox import insert_outbox_item
from app.domain.models import (
    ActionType,
    Alert,
    AlertOrigin,
    AlertStatus,
    Assessment,
    Astronaut,
    Sample,
    Severity,
)
from app.domain.rules import evaluate
from app.logging import get_logger
from app.stream.hub import StreamHub

log = get_logger("service.alerts")


class AlertService:
    def __init__(
        self,
        db: Database,
        hub: StreamHub,
        sustain_count: int = 3,
        resolve_count: int = 5,
        ai_alert_threshold: float = 0.8,
    ):
        self.db = db
        self.hub = hub
        self.sustain_count = sustain_count
        self.resolve_count = resolve_count
        self.ai_alert_threshold = ai_alert_threshold

    async def evaluate_and_act(self, astronaut: Astronaut, window: list[Sample]) -> int:
        if not window:
            return 0

        async with self.db.conn.cursor():
            open_alerts = await get_open_alerts_by_astronaut(self.db.conn, astronaut.id)

        now = datetime.now(UTC)
        actions = evaluate(
            astronaut_id=astronaut.id,
            window=window,
            mode=astronaut.mode,
            open_alerts=open_alerts,
            sustain_count=self.sustain_count,
            resolve_count=self.resolve_count,
            eval_time=now,
        )

        opened_count = 0

        for action in actions:
            if action.type == ActionType.OPEN:
                async with self.db.write_tx() as conn:
                    await create_alert(conn, action.alert)
                    payload_str = json.dumps({
                        "id": action.alert.id,
                        "astronaut_id": action.alert.astronaut_id,
                        "rule_id": action.alert.rule_id,
                        "severity": action.alert.severity.value,
                        "title": action.alert.title,
                        "message": action.alert.message,
                        "metric": action.alert.metric,
                        "value": action.alert.value,
                        "threshold": action.alert.threshold,
                        "status": action.alert.status.value,
                        "origin": action.alert.origin.value,
                        "created_at": action.alert.created_at.isoformat(),
                        "updated_at": action.alert.updated_at.isoformat(),
                    })
                    await insert_outbox_item(conn, "alert", action.alert.id, payload_str, now)

                log.info(
                    "alert_opened",
                    alert_id=action.alert.id,
                    astronaut_id=action.alert.astronaut_id,
                    rule_id=action.alert.rule_id,
                    severity=action.alert.severity.value,
                )
                await self.hub.publish_alert(action.alert)
                opened_count += 1

            elif action.type == ActionType.ESCALATE:
                async with self.db.write_tx() as conn:
                    await update_alert(conn, action.alert)

                log.info(
                    "alert_escalated",
                    alert_id=action.alert.id,
                    astronaut_id=action.alert.astronaut_id,
                    rule_id=action.alert.rule_id,
                    severity=action.alert.severity.value,
                )
                await self.hub.publish_alert(action.alert)

            elif action.type == ActionType.RESOLVE:
                async with self.db.write_tx() as conn:
                    await update_alert(conn, action.alert)

                log.info(
                    "alert_resolved",
                    alert_id=action.alert.id,
                    astronaut_id=action.alert.astronaut_id,
                    rule_id=action.alert.rule_id,
                    severity=action.alert.severity.value,
                )
                await self.hub.publish_alert_update(
                    alert_id=action.alert.id,
                    status=action.alert.status.value,
                    updated_at=action.alert.updated_at,
                    astronaut_id=action.alert.astronaut_id,
                )

        return opened_count

    async def acknowledge(self, alert_id: str) -> Alert:
        now = datetime.now(UTC)
        async with self.db.write_tx() as conn:
            alert = await db_ack_alert(conn, alert_id, now)

        await self.hub.publish_alert_update(
            alert_id=alert.id,
            status=alert.status.value,
            updated_at=alert.updated_at,
            astronaut_id=alert.astronaut_id,
        )
        return alert

    async def record_assessment(self, assessment: Assessment) -> Assessment:
        now = datetime.now(UTC)
        assessment.id = str(uuid.uuid4())
        assessment.created_at = now

        async with self.db.write_tx() as conn:
            await create_assessment(conn, assessment)
            payload_str = json.dumps({
                "id": assessment.id,
                "astronaut_id": assessment.astronaut_id,
                "model_version": assessment.model_version,
                "risk_score": assessment.risk_score,
                "label": assessment.label,
                "explanation": assessment.explanation,
                "created_at": now.isoformat(),
            })
            await insert_outbox_item(conn, "assessment", assessment.id, payload_str, now)

            # Check AI alert threshold
            if assessment.risk_score >= self.ai_alert_threshold:
                open_alerts = await get_open_alerts_by_astronaut(conn, assessment.astronaut_id)
                rule_id = "ml_anomaly"
                existing = open_alerts.get(rule_id)
                sev = Severity.CRITICAL if assessment.risk_score >= 0.95 else Severity.WARNING

                if not existing or existing.status not in (AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED):
                    alert = Alert(
                        id=str(uuid.uuid4()),
                        astronaut_id=assessment.astronaut_id,
                        rule_id=rule_id,
                        severity=sev,
                        title="ML Anomaly Detected",
                        message=f"Model risk score {assessment.risk_score:.2f}: {assessment.explanation}",
                        metric="risk_score",
                        value=assessment.risk_score,
                        threshold=self.ai_alert_threshold,
                        status=AlertStatus.OPEN,
                        origin=AlertOrigin.AI,
                        created_at=now,
                        updated_at=now,
                    )
                    await create_alert(conn, alert)
                    log.info("alert_opened", alert_id=alert.id, astronaut_id=alert.astronaut_id, rule_id=alert.rule_id, severity=alert.severity.value)
                    await self.hub.publish_alert(alert)
                elif existing.severity.rank < sev.rank or existing.value != assessment.risk_score:
                    existing.severity = sev
                    existing.value = assessment.risk_score
                    existing.message = f"Model risk score {assessment.risk_score:.2f}: {assessment.explanation}"
                    existing.updated_at = now
                    await update_alert(conn, existing)
                    log.info("alert_opened", alert_id=existing.id, astronaut_id=existing.astronaut_id, rule_id=existing.rule_id, severity=existing.severity.value)
                    await self.hub.publish_alert(existing)

        await self.hub.publish_assessment(assessment)
        return assessment
