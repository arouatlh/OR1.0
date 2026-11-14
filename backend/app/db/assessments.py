from datetime import UTC, datetime

import aiosqlite

from app.db.connection import translate_db_error
from app.domain.models import Assessment


async def create_assessment(conn: aiosqlite.Connection, assessment: Assessment) -> None:
    op = "db.assessments.create"
    try:
        cr_ms = int((assessment.created_at or datetime.now(UTC)).timestamp() * 1000)
        await conn.execute("""
            INSERT INTO assessments (id, astronaut_id, model_version, risk_score, label, explanation, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            assessment.id,
            assessment.astronaut_id,
            assessment.model_version,
            assessment.risk_score,
            assessment.label,
            assessment.explanation,
            cr_ms,
        ))
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def get_latest_assessment(conn: aiosqlite.Connection, astronaut_id: str) -> Assessment | None:
    op = "db.assessments.get_latest"
    try:
        async with conn.execute("""
            SELECT id, astronaut_id, model_version, risk_score, label, explanation, created_at
            FROM assessments
            WHERE astronaut_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (astronaut_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return Assessment(
                id=row["id"],
                astronaut_id=row["astronaut_id"],
                model_version=row["model_version"],
                risk_score=row["risk_score"],
                label=row["label"],
                explanation=row["explanation"],
                created_at=datetime.fromtimestamp(row["created_at"] / 1000, tz=UTC),
            )
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def list_assessments(
    conn: aiosqlite.Connection,
    astronaut_id: str,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Assessment], int]:
    op = "db.assessments.list"
    try:
        async with conn.execute("SELECT COUNT(1) FROM assessments WHERE astronaut_id = ?", (astronaut_id,)) as cur:
            count_row = await cur.fetchone()
            total = count_row[0] if count_row else 0

        async with conn.execute("""
            SELECT id, astronaut_id, model_version, risk_score, label, explanation, created_at
            FROM assessments
            WHERE astronaut_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (astronaut_id, limit, offset)) as cur:
            rows = await cur.fetchall()
            items = [
                Assessment(
                    id=r["id"],
                    astronaut_id=r["astronaut_id"],
                    model_version=r["model_version"],
                    risk_score=r["risk_score"],
                    label=r["label"],
                    explanation=r["explanation"],
                    created_at=datetime.fromtimestamp(r["created_at"] / 1000, tz=UTC),
                )
                for r in rows
            ]
            return items, total
    except Exception as exc:
        raise translate_db_error(op, exc) from exc
