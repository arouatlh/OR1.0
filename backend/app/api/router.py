from fastapi import APIRouter

from app.api.routes_alerts import router as alerts_router
from app.api.routes_assessments import router as assessments_router
from app.api.routes_astronauts import router as astronauts_router
from app.api.routes_demo import router as demo_router
from app.api.routes_health import router as health_router
from app.api.routes_sim import router as sim_router
from app.api.routes_stream import router as stream_router
from app.api.routes_sync import router as sync_router
from app.api.routes_telemetry import router as telemetry_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(demo_router)
api_v1_router.include_router(astronauts_router, prefix="/astronauts")
api_v1_router.include_router(telemetry_router, prefix="/telemetry")
api_v1_router.include_router(alerts_router, prefix="/alerts")
api_v1_router.include_router(assessments_router, prefix="/assessments")
api_v1_router.include_router(stream_router, prefix="/stream")
api_v1_router.include_router(sim_router, prefix="/simulate")
api_v1_router.include_router(sync_router, prefix="/sync")


def get_root_router() -> APIRouter:
    root = APIRouter()
    root.include_router(health_router)  # /healthz, /readyz at root
    root.include_router(api_v1_router)
    return root
