import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field

from app.analyzer import analyze
from app.api.handlers import register_exception_handlers
from app.api.middleware import ASGIMiddleware
from app.api.router import get_root_router
from app.config import get_settings
from app.db.connection import Database
from app.logging import get_logger, setup_logging
from app.services.alerts import AlertService
from app.services.inference import InferenceService
from app.services.ingest import IngestService
from app.services.summary import SummaryService
from app.sim.simulator import Simulator
from app.stream.hub import StreamHub

VERSION = "1.0.0"
GEMINI_MODEL = "gemini-3.5-flash-lite"
log = get_logger("app.main")


class DemoReading(BaseModel):
    t: int
    hr: float | None = Field(default=None, allow_inf_nan=False)
    spo2: float | None = Field(default=None, allow_inf_nan=False)
    rr: float | None = Field(default=None, allow_inf_nan=False)


class DemoAnalysisRequest(BaseModel):
    readings: list[DemoReading] = Field(min_length=1, max_length=5)


class DemoAssessment(BaseModel):
    risk_level: str
    reasons: list[str]


class DemoAnalysisResponse(BaseModel):
    analysis: str
    assessment: DemoAssessment | None


def analyze_demo_readings(body: DemoAnalysisRequest) -> DemoAnalysisResponse:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Set GEMINI_API_KEY in the backend terminal and restart the server.",
        )

    readings = sorted(body.readings, key=lambda reading: reading.t)
    latest = readings[-1]
    assessment = None

    if latest.hr is not None and latest.spo2 is not None:
        try:
            timestamp = datetime.fromtimestamp(
                latest.t / 1000,
                tz=timezone.utc,
            ).isoformat()
        except (OverflowError, OSError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail="Reading timestamps must be valid Unix timestamps in milliseconds.",
            ) from exc

        result = analyze(
            {
                "astronaut_id": "astro-a",
                "timestamp": timestamp,
                "heart_rate_bpm": latest.hr,
                "spo2_percent": latest.spo2,
            },
            recent_history=[],
        )

        if result.get("status") == "success":
            assessment = DemoAssessment(
                risk_level=result["risk_level"],
                reasons=result.get("reasons", []),
            )

    demo_data = "\n".join(reading.model_dump_json() for reading in readings)

    prompt = (
        "Summarize these simulated AstroVitals readings in at most three sentences. "
        "Rows are ordered from oldest to newest. HR is in BPM, SpO2 is a percentage, "
        "and RR is in breaths per minute. Report the latest row's values and say "
        "when a measurement is missing. With multiple rows, describe any changes "
        "shown by the supplied values. Use only the supplied data. Avoid diagnoses, "
        "treatment advice, and risk classifications.\n\n"
        f"{demo_data}"
    )

    try:
        with genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=20_000),
        ) as client:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
    except errors.APIError as exc:
        log.warning("gemini_request_failed", code=exc.code)
        raise HTTPException(
            status_code=502,
            detail=f"Gemini request failed ({exc.code}).",
        ) from exc
    except Exception as exc:
        log.warning("gemini_connection_failed", error_type=type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="Could not complete the Gemini request. Try again.",
        ) from exc

    analysis = (response.text or "").strip()
    if not analysis:
        raise HTTPException(status_code=502, detail="Gemini returned no summary.")

    return DemoAnalysisResponse(analysis=analysis, assessment=assessment)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.app_env)

    # Open SQLite and apply migrations.
    db = Database(settings.db_path)
    await db.open()

    hub = StreamHub(queue_maxsize=100)
    inference_svc = InferenceService(
        db=db,
        hub=hub,
        ml_enabled=settings.ml_enabled,
        window_samples=settings.ml_window_samples,
        every_n_samples=settings.ml_every_n_samples,
        timeout_ms=settings.ml_timeout_ms,
        alert_threshold=settings.ml_alert_threshold,
    )
    alert_svc = AlertService(
        db=db,
        hub=hub,
        sustain_count=settings.alert_sustain_samples,
        resolve_count=settings.alert_resolve_samples,
        ai_alert_threshold=settings.ml_alert_threshold,
    )
    ingest_svc = IngestService(
        db=db,
        alert_service=alert_svc,
        inference_service=inference_svc,
        hub=hub,
    )
    summary_svc = SummaryService(db=db)
    simulator = Simulator(
        ingest_service=ingest_svc,
        interval_ms=settings.sim_interval_ms,
    )

    app.state.settings = settings
    app.state.db = db
    app.state.hub = hub
    app.state.alert_service = alert_svc
    app.state.inference_service = inference_svc
    app.state.ingest_service = ingest_svc
    app.state.summary_service = summary_svc
    app.state.simulator = simulator

    log.info(
        "server_start",
        version=VERSION,
        db_path=settings.db_path,
        ml_loaded=inference_svc.ml_loaded,
    )

    yield

    await simulator.stop()
    await db.close()
    log.info("server_stop", version=VERSION)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AstroVitals Backend",
        version=VERSION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(ASGIMiddleware)

    register_exception_handlers(app)
    app.include_router(get_root_router())
    app.add_api_route(
        "/api/v1/ai/analyze",
        analyze_demo_readings,
        methods=["POST"],
    )

    return app


app = create_app()