from datetime import UTC, datetime

import aiosqlite

from app.db.connection import translate_db_error
from app.domain.models import Astronaut, Mode
from app.errors import not_found


async def list_astronauts(conn: aiosqlite.Connection) -> list[Astronaut]:
    op = "db.astronauts.list"
    try:
        async with conn.execute("""
            SELECT id, display_name, mission, mode, baseline_hr, created_at
            FROM astronauts
            ORDER BY id ASC
        """) as cursor:
            rows = await cursor.fetchall()
            return [
                Astronaut(
                    id=row["id"],
                    display_name=row["display_name"],
                    mission=row["mission"],
                    mode=Mode(row["mode"]),
                    baseline_hr=row["baseline_hr"],
                    created_at=datetime.fromtimestamp(row["created_at"] / 1000, tz=UTC),
                )
                for row in rows
            ]
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def get_astronaut(conn: aiosqlite.Connection, astronaut_id: str) -> Astronaut:
    op = "db.astronauts.get"
    try:
        async with conn.execute("""
            SELECT id, display_name, mission, mode, baseline_hr, created_at
            FROM astronauts
            WHERE id = ?
        """, (astronaut_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise not_found(op, f"Astronaut '{astronaut_id}' not found.")
            return Astronaut(
                id=row["id"],
                display_name=row["display_name"],
                mission=row["mission"],
                mode=Mode(row["mode"]),
                baseline_hr=row["baseline_hr"],
                created_at=datetime.fromtimestamp(row["created_at"] / 1000, tz=UTC),
            )
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def update_mode(conn: aiosqlite.Connection, astronaut_id: str, mode: Mode) -> None:
    op = "db.astronauts.update_mode"
    try:
        cursor = await conn.execute("""
            UPDATE astronauts
            SET mode = ?
            WHERE id = ?
        """, (mode.value, astronaut_id))
        if cursor.rowcount == 0:
            raise not_found(op, f"Astronaut '{astronaut_id}' not found.")
    except Exception as exc:
        raise translate_db_error(op, exc) from exc
