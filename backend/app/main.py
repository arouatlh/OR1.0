from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
log = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.app_env)

    # 1. Open SQLite database and apply migrations
    db = Database(settings.db_path)
    await db.open()

    # 2. Initialize components
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
    simulator = Simulator(ingest_service=ingest_svc, interval_ms=settings.sim_interval_ms)

    # Store on app.state
    app.state.settings = settings
    app.state.db = db
    app.state.hub = hub
    app.state.alert_service = alert_svc
    app.state.inference_service = inference_svc
    app.state.ingest_service = ingest_svc
    app.state.summary_service = summary_svc
    app.state.simulator = simulator

    log.info("server_start", version=VERSION, db_path=settings.db_path, ml_loaded=inference_svc.ml_loaded)

    yield

    # Shutdown
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

    # Middlewares
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(ASGIMiddleware)

    # Error Handlers
    register_exception_handlers(app)

    # Routes
    app.include_router(get_root_router())

    return app


app = create_app()
