from fastapi import APIRouter, Request

from app.api.schemas import SimulateStartRequest
from app.responses import write_success_response

router = APIRouter()


@router.post("/start", response_model=None)
async def start_simulation(request: Request, body: SimulateStartRequest):
    simulator = request.app.state.simulator
    await simulator.start(body.scenario, body.astronaut_id)
    return write_success_response(200, {
        "started": True,
        "scenario": body.scenario,
        "astronaut_id": body.astronaut_id,
    })


@router.post("/stop", response_model=None)
async def stop_simulation(request: Request):
    simulator = request.app.state.simulator
    await simulator.stop()
    return write_success_response(200, {"stopped": True})
