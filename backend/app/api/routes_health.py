from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/healthz", response_model=None)
async def healthz():
    return JSONResponse(status_code=200, content={"status": "ok"})


@router.get("/readyz", response_model=None)
async def readyz(request: Request):
    db = request.app.state.db
    await db.ping()
    inference_svc = getattr(request.app.state, "inference_service", None)
    ml_loaded = inference_svc.ml_loaded if inference_svc else False
    return JSONResponse(status_code=200, content={"status": "ok", "ml_loaded": ml_loaded})
