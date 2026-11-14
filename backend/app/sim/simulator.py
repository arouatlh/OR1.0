import asyncio
import random
from datetime import UTC, datetime

from app.domain.models import Sample
from app.errors import bad_request, conflict
from app.logging import get_logger
from app.services.ingest import IngestService

log = get_logger("sim.simulator")


class Simulator:
    def __init__(self, ingest_service: IngestService, interval_ms: int = 1000):
        self.ingest_service = ingest_service
        self.interval_s = interval_ms / 1000.0
        self._task: asyncio.Task | None = None
        self._scenario: str = "normal"
        self._astronaut_id: str = "astro-a"
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self, scenario: str, astronaut_id: str = "astro-a") -> None:
        async with self._lock:
            if self.is_running:
                raise conflict("sim.start", "Simulator is already running.")

            valid_scenarios = ("normal", "tachycardia", "hypoxia", "arrhythmia")
            if scenario not in valid_scenarios:
                raise bad_request("sim.start", f"Invalid scenario '{scenario}'. Must be one of {valid_scenarios}.")

            self._scenario = scenario
            self._astronaut_id = astronaut_id or "astro-a"
            self._task = asyncio.create_task(self._run_loop(self._scenario, self._astronaut_id))
            log.info("simulator_started", scenario=self._scenario, astronaut_id=self._astronaut_id)

    async def stop(self) -> None:
        async with self._lock:
            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                log.info("simulator_stopped", scenario=self._scenario, astronaut_id=self._astronaut_id)
            self._task = None

    async def _run_loop(self, scenario: str, astronaut_id: str) -> None:
        rng = random.Random(42)
        step = 0

        try:
            while True:
                sample = self._generate_sample(rng, scenario, step, astronaut_id)
                step += 1

                try:
                    await self.ingest_service.ingest(astronaut_id, [sample])
                except Exception as exc:
                    log.warn("sim_sample_ingest_error", error=str(exc))

                await asyncio.sleep(self.interval_s)
        except asyncio.CancelledError:
            raise

    def _generate_sample(self, rng: random.Random, scenario: str, step: int, astronaut_id: str) -> Sample:
        now = datetime.now(UTC)
        client_id = f"sim-{scenario}-{int(now.timestamp()*1000)}-{step}"

        hr = 68 + rng.randint(0, 12)
        spo2 = 97 + rng.randint(0, 2)
        sys_bp = 115 + rng.randint(0, 8)
        dia_bp = 74 + rng.randint(0, 5)
        rr = 13 + rng.randint(0, 3)
        ecg = "sinus"
        stress = round(0.15 + (rng.randint(0, 10) / 100.0), 2)

        match scenario:
            case "normal":
                pass
            case "tachycardia":
                cycle = step % 50
                if cycle < 20:
                    hr = 75 + int((cycle / 20.0) * 80.0)
                elif cycle < 35:
                    hr = 154 + rng.randint(0, 4)
                    stress = 0.85
                else:
                    hr = 155 - int(((cycle - 35) / 15.0) * 80.0)
            case "hypoxia":
                cycle = step % 40
                if cycle < 15:
                    spo2 = 98 - int((cycle / 15.0) * 10.0)
                    rr = 14 + int((cycle / 15.0) * 15.0)
                elif cycle < 25:
                    spo2 = 87 + rng.randint(0, 1)
                    rr = 28 + rng.randint(0, 2)
                    stress = 0.75
                else:
                    spo2 = 88 + int(((cycle - 25) / 15.0) * 10.0)
                    rr = 28 - int(((cycle - 25) / 15.0) * 14.0)
            case "arrhythmia":
                cycle = step % 30
                if 5 <= cycle < 18:
                    ecg = "irregular"
                    hr = 85 + rng.randint(0, 40)
                    stress = 0.72

        return Sample(
            astronaut_id=astronaut_id,
            client_id=client_id,
            recorded_at=now,
            source="simulator",
            heart_rate=hr,
            spo2=spo2,
            systolic=sys_bp,
            diastolic=dia_bp,
            resp_rate=rr,
            ecg_summary=ecg,
            stress_index=stress,
        )
