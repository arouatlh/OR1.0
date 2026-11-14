from app.db.astronauts import get_astronaut
from app.db.connection import Database
from app.db.telemetry import get_recent_window, insert_telemetry_batch
from app.domain.models import Sample
from app.services.alerts import AlertService
from app.services.inference import InferenceService
from app.stream.hub import StreamHub


class IngestService:
    def __init__(
        self,
        db: Database,
        alert_service: AlertService,
        inference_service: InferenceService,
        hub: StreamHub,
    ):
        self.db = db
        self.alert_service = alert_service
        self.inference_service = inference_service
        self.hub = hub

    async def ingest(self, astronaut_id: str, samples: list[Sample]) -> dict[str, int]:
        # 1. Verify astronaut exists
        astronaut = await get_astronaut(self.db.conn, astronaut_id)

        # 2. Insert batch in write transaction
        async with self.db.write_tx() as conn:
            accepted, duplicates, accepted_samples = await insert_telemetry_batch(conn, astronaut_id, samples)

        # 3. Publish to SSE
        for smp in accepted_samples:
            await self.hub.publish_telemetry(smp)

        # 4. If any samples accepted, evaluate rules on recent window
        alerts_opened = 0
        if accepted > 0:
            window = await get_recent_window(self.db.conn, astronaut_id, 25)
            if window:
                alerts_opened = await self.alert_service.evaluate_and_act(astronaut, window)

            # 5. Trigger ML inference in-process off the event loop
            await self.inference_service.maybe_run_inference(astronaut_id, accepted)

        return {
            "accepted": accepted,
            "duplicates": duplicates,
            "alerts_opened": alerts_opened,
        }
