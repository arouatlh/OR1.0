import asyncio
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.get("", response_model=None)
async def sse_stream(request: Request):
    hub = request.app.state.hub
    client_id = str(uuid.uuid4())
    astronaut_id = request.query_params.get("astronaut_id")

    queue = await hub.subscribe(client_id, astronaut_id)

    async def event_generator():
        # Initial comment to establish stream
        yield ": connected\n\n"
        ping_interval = 15

        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    # Wait for next event or 15s heartbeat
                    msg = await asyncio.wait_for(queue.get(), timeout=ping_interval)
                    yield f"event: {msg.event}\ndata: {msg.data}\n\n"
                except TimeoutError:
                    if await request.is_disconnected():
                        break
                    yield ": ping\n\n"
        finally:
            await hub.unsubscribe(client_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
