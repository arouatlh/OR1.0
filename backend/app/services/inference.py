import asyncio
import json
import uuid
from datetime import UTC, datetime

import anyio

from app.db.alerts import create_alert, get_open_alerts_by_astronaut, update_alert
from app.db.assessments import create_assessment
from app.db.connection import Database
from app.db.outbox import insert_outbox_item
from app.db.telemetry import get_recent_window
from app.domain.models import Alert, AlertOrigin, AlertStatus, Assessment, Severity
from app.logging import get_logger
from app.ml.model import DefaultPredictor
from app.ml.predictor import NullPredictor, Predictor
from app.stream.hub import StreamHub

log = get_logger("service.inference")


class InferenceService:
    def __init__(
        self,
        db: Database,
        hub: StreamHub,
        ml_enabled: bool = True,
        window_samples: int = 30,
        every_n_samples: int = 5,
        timeout_ms: int = 500,
        alert_threshold: float = 0.8,
    ):
        self.db = db
        self.hub = hub
        self.ml_enabled = ml_enabled
        self.window_samples = window_samples
        self.every_n_samples = every_n_samples
        self.timeout_s = timeout_ms / 1000.0
        self.alert_threshold = alert_threshold

        self._in_flight: set[str] = set()
        self._sample_counters: dict[str, int] = {}
        self.predictor: Predictor = self._init_predictor()

    def _init_predictor(self) -> Predictor:
        if not self.ml_enabled:
            return NullPredictor()

        try:
            pred = DefaultPredictor()
            log.info("ml_loaded", version=pred.version)
            return pred
        except Exception as exc:
            log.warn("ml_fallback_null_predictor", error=str(exc))
            return NullPredictor()

    @property
    def ml_loaded(self) -> bool:
        return not isinstance(self.predictor, NullPredictor)

    async def maybe_run_inference(self, astronaut_id: str, new_samples_count: int) -> None:
        """Triggered on ingest. Runs inference every ML_EVERY_N_SAMPLES with in-flight guard."""
        if not self.ml_enabled or isinstance(self.predictor, NullPredictor):
            return

        cnt = self._sample_counters.get(astronaut_id, 0) + new_samples_count
        self._sample_counters[astronaut_id] = cnt

        if cnt < self.every_n_samples:
            return

        self._sample_counters[astronaut_id] = 0

        # Guard: at most one inference in flight per astronaut
        if astronaut_id in self._in_flight:
            return

        self._in_flight.add(astronaut_id)
        try:
            window = await get_recent_window(self.db.conn, astronaut_id, self.window_samples)
            if not window:
                return

            # CPU-bound inference in worker thread off event loop with timeout
            async with asyncio.timeout(self.timeout_s):
                result = await anyio.to_thread.run_sync(self.predictor.predict, window)

            now = datetime.now(UTC)
            assessment_id = str(uuid.uuid4())
            assessment = Assessment(
                id=assessment_id,
                astronaut_id=astronaut_id,
                model_version=result.model_version,
                risk_score=result.risk_score,
                label=result.label,
                explanation=result.explanation,
                created_at=now,
            )

            # Persist assessment and outbox in write transaction
            async with self.db.write_tx() as conn:
                await create_assessment(conn, assessment)
                payload_str = json.dumps({
                    "id": assessment_id,
                    "astronaut_id": astronaut_id,
                    "model_version": assessment.model_version,
                    "risk_score": assessment.risk_score,
                    "label": assessment.label,
                    "explanation": assessment.explanation,
                    "created_at": now.isoformat(),
                })
                await insert_outbox_item(conn, "assessment", assessment_id, payload_str, now)

                # Check if risk exceeds threshold to raise or update AI alert
                if assessment.risk_score >= self.alert_threshold:
                    await self._handle_ml_alert(conn, assessment, now)

            # Broadcast SSE event
            await self.hub.publish_assessment(assessment)

        except TimeoutError:
            log.warn("ml_timeout", astronaut_id=astronaut_id, timeout_s=self.timeout_s)
        except Exception as exc:
            log.warn("ml_inference_error", astronaut_id=astronaut_id, error=str(exc))
        finally:
            self._in_flight.discard(astronaut_id)

    async def _handle_ml_alert(self, conn, assessment: Assessment, now: datetime) -> None:
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
                threshold=self.alert_threshold,
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
