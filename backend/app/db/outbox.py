from datetime import UTC, datetime

import aiosqlite

from app.db.connection import translate_db_error
from app.domain.models import OutboxItem


async def insert_outbox_item(
    conn: aiosqlite.Connection,
    entity: str,
    entity_id: str,
    payload: str,
    created_at: datetime | None = None,
) -> None:
    op = "db.outbox.insert"
    try:
        now_ms = int((created_at or datetime.now(UTC)).timestamp() * 1000)
        await conn.execute("""
            INSERT INTO outbox (entity, entity_id, payload, created_at)
            VALUES (?, ?, ?, ?)
        """, (entity, entity_id, payload, now_ms))
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def get_pending_count(conn: aiosqlite.Connection) -> int:
    op = "db.outbox.pending_count"
    try:
        async with conn.execute("SELECT COUNT(1) FROM outbox WHERE synced_at IS NULL") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def get_last_sync_time(conn: aiosqlite.Connection) -> datetime | None:
    op = "db.outbox.last_sync_time"
    try:
        async with conn.execute("SELECT MAX(synced_at) FROM outbox WHERE synced_at IS NOT NULL") as cur:
            row = await cur.fetchone()
            if not row or row[0] is None:
                return None
            return datetime.fromtimestamp(row[0] / 1000, tz=UTC)
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def get_pending_items(conn: aiosqlite.Connection, limit: int = 100) -> list[OutboxItem]:
    op = "db.outbox.get_pending"
    try:
        async with conn.execute("""
            SELECT id, entity, entity_id, payload, created_at, synced_at
            FROM outbox
            WHERE synced_at IS NULL
            ORDER BY id ASC
            LIMIT ?
        """, (limit,)) as cur:
            rows = await cur.fetchall()
            return [
                OutboxItem(
                    id=r["id"],
                    entity=r["entity"],
                    entity_id=r["entity_id"],
                    payload=r["payload"],
                    created_at=datetime.fromtimestamp(r["created_at"] / 1000, tz=UTC),
                    synced_at=None,
                )
                for r in rows
            ]
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def mark_synced(conn: aiosqlite.Connection, ids: list[int], synced_at: datetime) -> None:
    op = "db.outbox.mark_synced"
    if not ids:
        return
    try:
        sync_ms = int(synced_at.timestamp() * 1000)
        placeholders = ",".join("?" for _ in ids)
        await conn.execute(f"""
            UPDATE outbox
            SET synced_at = ?
            WHERE id IN ({placeholders})
        """, (sync_ms, *ids))
    except Exception as exc:
        raise translate_db_error(op, exc) from exc
