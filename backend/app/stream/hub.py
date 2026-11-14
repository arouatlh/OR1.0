import asyncio
import json
from dataclasses import dataclass
from datetime import datetime

from app.domain.models import Alert, Assessment, Sample
from app.logging import get_logger

log = get_logger("stream.hub")


@dataclass
class SSEMessage:
    event: str
    data: str
    astronaut_id: str | None = None


class StreamHub:
    def __init__(self, queue_maxsize: int = 100):
        self.queue_maxsize = queue_maxsize
        self._subscribers: dict[str, tuple[asyncio.Queue[SSEMessage], str | None]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, client_id: str, astronaut_id: str | None = None) -> asyncio.Queue[SSEMessage]:
        queue: asyncio.Queue[SSEMessage] = asyncio.Queue(maxsize=self.queue_maxsize)
        async with self._lock:
            self._subscribers[client_id] = (queue, astronaut_id)
        return queue

    async def unsubscribe(self, client_id: str) -> None:
        async with self._lock:
            self._subscribers.pop(client_id, None)

    async def publish(self, event: str, data: dict, astronaut_id: str | None = None) -> None:
        message = SSEMessage(
            event=event,
            data=json.dumps(data),
            astronaut_id=astronaut_id,
        )

        dropped_clients: list[str] = []
        async with self._lock:
            for client_id, (queue, filter_astro) in list(self._subscribers.items()):
                if filter_astro and astronaut_id and filter_astro != astronaut_id:
                    continue

                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    dropped_clients.append(client_id)

            for client_id in dropped_clients:
                self._subscribers.pop(client_id, None)
                log.warn("sse_client_dropped", client_id=client_id, reason="buffer_full")

    async def publish_telemetry(self, sample: Sample) -> None:
        payload: dict[str, object] = {
            "astronaut_id": sample.astronaut_id,
            "recorded_at": sample.recorded_at.isoformat(),
        }
        if sample.heart_rate is not None:
            payload["heart_rate"] = sample.heart_rate
        if sample.spo2 is not None:
            payload["spo2"] = sample.spo2
        if sample.systolic is not None:
            payload["systolic"] = sample.systolic
        if sample.diastolic is not None:
            payload["diastolic"] = sample.diastolic
        if sample.resp_rate is not None:
            payload["resp_rate"] = sample.resp_rate
        if sample.ecg_summary is not None:
            payload["ecg_summary"] = sample.ecg_summary
        if sample.stress_index is not None:
            payload["stress_index"] = sample.stress_index

        await self.publish("telemetry", payload, astronaut_id=sample.astronaut_id)

    async def publish_alert(self, alert: Alert) -> None:
        payload = {
            "id": alert.id,
            "astronaut_id": alert.astronaut_id,
            "rule_id": alert.rule_id,
            "severity": alert.severity.value,
            "title": alert.title,
            "message": alert.message,
            "metric": alert.metric,
            "value": alert.value,
            "threshold": alert.threshold,
            "status": alert.status.value,
            "origin": alert.origin.value,
            "created_at": alert.created_at.isoformat(),
            "updated_at": alert.updated_at.isoformat(),
        }
        await self.publish("alert", payload, astronaut_id=alert.astronaut_id)

    async def publish_alert_update(self, alert_id: str, status: str, updated_at: datetime, astronaut_id: str) -> None:
        payload = {
            "id": alert_id,
            "status": status,
            "updated_at": updated_at.isoformat(),
        }
        await self.publish("alert_update", payload, astronaut_id=astronaut_id)

    async def publish_assessment(self, assessment: Assessment) -> None:
        payload = {
            "astronaut_id": assessment.astronaut_id,
            "risk_score": assessment.risk_score,
            "label": assessment.label,
            "model_version": assessment.model_version,
            "created_at": (assessment.created_at or datetime.now()).isoformat(),
        }
        await self.publish("assessment", payload, astronaut_id=assessment.astronaut_id)
