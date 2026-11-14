import json
from datetime import UTC, datetime

import aiosqlite

from app.db.connection import translate_db_error
from app.domain.models import Sample
from app.errors import not_found


async def insert_telemetry_batch(
    conn: aiosqlite.Connection,
    astronaut_id: str,
    samples: list[Sample],
) -> tuple[int, int, list[Sample]]:
    op = "db.telemetry.insert_batch"
    try:
        # Check astronaut exists
        async with conn.execute("SELECT COUNT(1) FROM astronauts WHERE id = ?", (astronaut_id,)) as cur:
            row = await cur.fetchone()
            if not row or row[0] == 0:
                raise not_found(op, f"Astronaut '{astronaut_id}' not found.")

        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        accepted = 0
        duplicates = 0
        accepted_samples: list[Sample] = []

        for s in samples:
            rec_ms = int(s.recorded_at.timestamp() * 1000)
            cursor = await conn.execute("""
                INSERT OR IGNORE INTO telemetry (
                    astronaut_id, client_id, recorded_at, received_at, source,
                    heart_rate, spo2, systolic, diastolic, resp_rate, ecg_summary, stress_index
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                astronaut_id,
                s.client_id,
                rec_ms,
                now_ms,
                s.source,
                s.heart_rate,
                s.spo2,
                s.systolic,
                s.diastolic,
                s.resp_rate,
                s.ecg_summary,
                s.stress_index,
            ))

            if cursor.rowcount == 0:
                duplicates += 1
            else:
                accepted += 1
                sample_id = cursor.lastrowid
                new_sample = Sample(
                    id=sample_id,
                    astronaut_id=astronaut_id,
                    client_id=s.client_id,
                    recorded_at=s.recorded_at,
                    received_at=datetime.fromtimestamp(now_ms / 1000, tz=UTC),
                    source=s.source,
                    heart_rate=s.heart_rate,
                    spo2=s.spo2,
                    systolic=s.systolic,
                    diastolic=s.diastolic,
                    resp_rate=s.resp_rate,
                    ecg_summary=s.ecg_summary,
                    stress_index=s.stress_index,
                )
                accepted_samples.append(new_sample)

                # Outbox entry in the same transaction
                payload_dict = {
                    "astronaut_id": astronaut_id,
                    "client_id": s.client_id,
                    "recorded_at": s.recorded_at.isoformat(),
                    "source": s.source,
                    "heart_rate": s.heart_rate,
                    "spo2": s.spo2,
                    "systolic": s.systolic,
                    "diastolic": s.diastolic,
                    "resp_rate": s.resp_rate,
                    "ecg_summary": s.ecg_summary,
                    "stress_index": s.stress_index,
                }
                await conn.execute("""
                    INSERT INTO outbox (entity, entity_id, payload, created_at)
                    VALUES (?, ?, ?, ?)
                """, ("telemetry", str(sample_id), json.dumps(payload_dict), now_ms))

        return accepted, duplicates, accepted_samples
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def get_latest_telemetry(conn: aiosqlite.Connection, astronaut_id: str) -> Sample | None:
    op = "db.telemetry.get_latest"
    try:
        async with conn.execute("""
            SELECT id, astronaut_id, client_id, recorded_at, received_at, source,
                   heart_rate, spo2, systolic, diastolic, resp_rate, ecg_summary, stress_index
            FROM telemetry
            WHERE astronaut_id = ?
            ORDER BY recorded_at DESC, id DESC
            LIMIT 1
        """, (astronaut_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            return _row_to_sample(row)
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def get_recent_window(conn: aiosqlite.Connection, astronaut_id: str, limit: int = 30) -> list[Sample]:
    op = "db.telemetry.get_window"
    try:
        # Retrieve recent samples, order oldest to newest for evaluation
        async with conn.execute("""
            SELECT id, astronaut_id, client_id, recorded_at, received_at, source,
                   heart_rate, spo2, systolic, diastolic, resp_rate, ecg_summary, stress_index
            FROM (
                SELECT * FROM telemetry
                WHERE astronaut_id = ?
                ORDER BY recorded_at DESC, id DESC
                LIMIT ?
            )
            ORDER BY recorded_at ASC, id ASC
        """, (astronaut_id, limit)) as cur:
            rows = await cur.fetchall()
            return [_row_to_sample(r) for r in rows]
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def get_history(
    conn: aiosqlite.Connection,
    astronaut_id: str,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    offset: int = 0,
    limit: int = 20,
    order: str = "DESC",
) -> tuple[list[Sample], int]:
    op = "db.telemetry.get_history"
    try:
        conditions = ["astronaut_id = ?"]
        params: list[object] = [astronaut_id]

        if from_time:
            conditions.append("recorded_at >= ?")
            params.append(int(from_time.timestamp() * 1000))
        if to_time:
            conditions.append("recorded_at <= ?")
            params.append(int(to_time.timestamp() * 1000))

        where_clause = " AND ".join(conditions)

        # Count total
        async with conn.execute(f"SELECT COUNT(1) FROM telemetry WHERE {where_clause}", tuple(params)) as cur:
            count_row = await cur.fetchone()
            total = count_row[0] if count_row else 0

        sort_dir = "ASC" if order.upper() == "ASC" else "DESC"
        query = f"""
            SELECT id, astronaut_id, client_id, recorded_at, received_at, source,
                   heart_rate, spo2, systolic, diastolic, resp_rate, ecg_summary, stress_index
            FROM telemetry
            WHERE {where_clause}
            ORDER BY recorded_at {sort_dir}, id {sort_dir}
            LIMIT ? OFFSET ?
        """
        query_params = tuple(params + [limit, offset])

        async with conn.execute(query, query_params) as cur:
            rows = await cur.fetchall()
            return [_row_to_sample(r) for r in rows], total
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def get_stats_5min(conn: aiosqlite.Connection, astronaut_id: str, now: datetime) -> dict[str, object]:
    op = "db.telemetry.get_stats_5min"
    try:
        five_min_ago_ms = int((now.timestamp() - 300) * 1000)
        async with conn.execute("""
            SELECT COUNT(1) as count,
                   COALESCE(AVG(heart_rate), 0) as mean_hr,
                   COALESCE(MIN(heart_rate), 0) as min_hr,
                   COALESCE(MAX(heart_rate), 0) as max_hr,
                   COALESCE(AVG(spo2), 0) as mean_spo2,
                   COALESCE(MIN(spo2), 0) as min_spo2,
                   COALESCE(MAX(spo2), 0) as max_spo2,
                   COALESCE(AVG(systolic), 0) as mean_systolic,
                   COALESCE(AVG(resp_rate), 0) as mean_resp_rate
            FROM telemetry
            WHERE astronaut_id = ? AND recorded_at >= ?
        """, (astronaut_id, five_min_ago_ms)) as cur:
            row = await cur.fetchone()
            if not row:
                return {}
            return {
                "count": row["count"],
                "mean_hr": round(row["mean_hr"], 1),
                "min_hr": row["min_hr"],
                "max_hr": row["max_hr"],
                "mean_spo2": round(row["mean_spo2"], 1),
                "min_spo2": row["min_spo2"],
                "max_spo2": row["max_spo2"],
                "mean_systolic": round(row["mean_systolic"], 1),
                "mean_resp_rate": round(row["mean_resp_rate"], 1),
            }
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


def _row_to_sample(row: aiosqlite.Row) -> Sample:
    return Sample(
        id=row["id"],
        astronaut_id=row["astronaut_id"],
        client_id=row["client_id"],
        recorded_at=datetime.fromtimestamp(row["recorded_at"] / 1000, tz=UTC),
        received_at=datetime.fromtimestamp(row["received_at"] / 1000, tz=UTC),
        source=row["source"],
        heart_rate=row["heart_rate"],
        spo2=row["spo2"],
        systolic=row["systolic"],
        diastolic=row["diastolic"],
        resp_rate=row["resp_rate"],
        ecg_summary=row["ecg_summary"],
        stress_index=row["stress_index"],
    )
