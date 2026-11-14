from datetime import UTC, datetime

import aiosqlite

from app.db.connection import translate_db_error
from app.domain.models import Alert, AlertOrigin, AlertStatus, Severity
from app.errors import conflict, not_found


async def create_alert(conn: aiosqlite.Connection, alert: Alert) -> None:
    op = "db.alerts.create"
    try:
        cr_ms = int(alert.created_at.timestamp() * 1000)
        up_ms = int(alert.updated_at.timestamp() * 1000)
        await conn.execute("""
            INSERT INTO alerts (
                id, astronaut_id, rule_id, severity, title, message, metric,
                value, threshold, status, origin, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alert.id,
            alert.astronaut_id,
            alert.rule_id,
            alert.severity.value,
            alert.title,
            alert.message,
            alert.metric,
            alert.value,
            alert.threshold,
            alert.status.value,
            alert.origin.value,
            cr_ms,
            up_ms,
        ))
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def update_alert(conn: aiosqlite.Connection, alert: Alert) -> None:
    op = "db.alerts.update"
    try:
        up_ms = int(alert.updated_at.timestamp() * 1000)
        cursor = await conn.execute("""
            UPDATE alerts
            SET severity = ?, title = ?, message = ?, value = ?, threshold = ?, status = ?, updated_at = ?
            WHERE id = ?
        """, (
            alert.severity.value,
            alert.title,
            alert.message,
            alert.value,
            alert.threshold,
            alert.status.value,
            up_ms,
            alert.id,
        ))
        if cursor.rowcount == 0:
            raise not_found(op, f"Alert '{alert.id}' not found.")
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def get_alert(conn: aiosqlite.Connection, alert_id: str) -> Alert:
    op = "db.alerts.get"
    try:
        async with conn.execute("""
            SELECT id, astronaut_id, rule_id, severity, title, message, metric,
                   value, threshold, status, origin, created_at, updated_at
            FROM alerts
            WHERE id = ?
        """, (alert_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                raise not_found(op, f"Alert '{alert_id}' not found.")
            return _row_to_alert(row)
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def get_open_alerts_by_astronaut(conn: aiosqlite.Connection, astronaut_id: str) -> dict[str, Alert]:
    op = "db.alerts.get_open"
    try:
        async with conn.execute("""
            SELECT id, astronaut_id, rule_id, severity, title, message, metric,
                   value, threshold, status, origin, created_at, updated_at
            FROM alerts
            WHERE astronaut_id = ? AND status IN ('open', 'acknowledged')
        """, (astronaut_id,)) as cur:
            rows = await cur.fetchall()
            return {r["rule_id"]: _row_to_alert(r) for r in rows}
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def list_alerts(
    conn: aiosqlite.Connection,
    status: str | None = None,
    severity: str | None = None,
    astronaut_id: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Alert], int]:
    op = "db.alerts.list"
    try:
        conditions = []
        params: list[object] = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if astronaut_id:
            conditions.append("astronaut_id = ?")
            params.append(astronaut_id)

        where_clause = "1=1"
        if conditions:
            where_clause = " AND ".join(conditions)

        async with conn.execute(f"SELECT COUNT(1) FROM alerts WHERE {where_clause}", tuple(params)) as cur:
            count_row = await cur.fetchone()
            total = count_row[0] if count_row else 0

        query = f"""
            SELECT id, astronaut_id, rule_id, severity, title, message, metric,
                   value, threshold, status, origin, created_at, updated_at
            FROM alerts
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        query_params = tuple(params + [limit, offset])

        async with conn.execute(query, query_params) as cur:
            rows = await cur.fetchall()
            return [_row_to_alert(r) for r in rows], total
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def acknowledge_alert(conn: aiosqlite.Connection, alert_id: str, ack_time: datetime) -> Alert:
    op = "db.alerts.ack"
    try:
        alert = await get_alert(conn, alert_id)
        if alert.status == AlertStatus.RESOLVED:
            raise conflict(op, "Cannot acknowledge a resolved alert.")

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.updated_at = ack_time
        await update_alert(conn, alert)
        return alert
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


async def count_open_alerts_by_astronaut(conn: aiosqlite.Connection) -> dict[str, int]:
    op = "db.alerts.count_open"
    try:
        async with conn.execute("""
            SELECT astronaut_id, COUNT(1) as cnt
            FROM alerts
            WHERE status IN ('open', 'acknowledged')
            GROUP BY astronaut_id
        """) as cur:
            rows = await cur.fetchall()
            return {r["astronaut_id"]: r["cnt"] for r in rows}
    except Exception as exc:
        raise translate_db_error(op, exc) from exc


def _row_to_alert(row: aiosqlite.Row) -> Alert:
    return Alert(
        id=row["id"],
        astronaut_id=row["astronaut_id"],
        rule_id=row["rule_id"],
        severity=Severity(row["severity"]),
        title=row["title"],
        message=row["message"],
        metric=row["metric"],
        value=row["value"],
        threshold=row["threshold"],
        status=AlertStatus(row["status"]),
        origin=AlertOrigin(row["origin"]),
        created_at=datetime.fromtimestamp(row["created_at"] / 1000, tz=UTC),
        updated_at=datetime.fromtimestamp(row["updated_at"] / 1000, tz=UTC),
    )
