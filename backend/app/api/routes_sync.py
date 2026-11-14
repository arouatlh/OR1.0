from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Request

from app.db.outbox import get_last_sync_time, get_pending_count, get_pending_items, mark_synced
from app.errors import bad_request, internal, unavailable
from app.responses import write_success_response

router = APIRouter()


@router.get("/status", response_model=None)
async def sync_status(request: Request):
    db = request.app.state.db
    pending_count = await get_pending_count(db.conn)
    last_sync = await get_last_sync_time(db.conn)

    return write_success_response(200, {
        "pending_count": pending_count,
        "last_synced_at": last_sync.isoformat() if last_sync else None,
    })


@router.post("/flush", response_model=None)
async def sync_flush(request: Request):
    settings = request.app.state.settings
    if not settings.sync_remote_url:
        raise bad_request("api.sync.flush", "SYNC_REMOTE_URL is not configured.")

    db = request.app.state.db
    items = await get_pending_items(db.conn, limit=100)
    if not items:
        return write_success_response(200, {"synced_count": 0})

    payload = [
        {
            "id": it.id,
            "entity": it.entity,
            "entity_id": it.entity_id,
            "payload": it.payload,
            "created_at": it.created_at.isoformat(),
        }
        for it in items
    ]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(settings.sync_remote_url, json=payload)
            if resp.status_code >= 400:
                raise unavailable("api.sync.flush", f"Remote ground station returned HTTP {resp.status_code}")
    except httpx.RequestError as exc:
        raise unavailable("api.sync.flush", f"Remote sync network failure: {exc}") from exc
    except Exception as exc:
        raise internal("api.sync.flush") from exc

    now = datetime.now(UTC)
    ids = [it.id for it in items if it.id is not None]
    async with db.write_tx() as conn:
        await mark_synced(conn, ids, now)

    return write_success_response(200, {"synced_count": len(ids)})
