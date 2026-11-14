import asyncio
import os
import sqlite3
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

import aiosqlite

from app.errors import AppError, conflict, internal, not_found, unavailable


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None
        self._write_lock = asyncio.Lock()

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database connection not opened")
        return self._conn

    async def open(self) -> None:
        if self.db_path != ":memory:":
            db_dir = Path(self.db_path).parent
            if db_dir != Path(".") and not db_dir.exists():
                os.makedirs(db_dir, exist_ok=True)

        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row

        # Set production pragmas
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA synchronous=NORMAL;")
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        await self._conn.execute("PRAGMA busy_timeout=5000;")
        await self._conn.execute("PRAGMA temp_store=MEMORY;")

        await self._migrate()
        await self._seed_astronauts()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def ping(self) -> bool:
        try:
            cursor = await self.conn.execute("SELECT 1")
            await cursor.fetchone()
            await cursor.close()
            return True
        except Exception as exc:
            raise translate_db_error("db.ping", exc) from exc

    @asynccontextmanager
    async def write_tx(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Acquires the in-process write lock, begins an immediate transaction,
        and guarantees commit or rollback."""
        async with self._write_lock:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
                await self.conn.commit()
            except Exception as exc:
                await self.conn.rollback()
                raise translate_db_error("db.write_tx", exc) from exc

    async def _migrate(self) -> None:
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at INTEGER NOT NULL
            );
        """)
        await self.conn.commit()

        # Load migration files from app/db/migrations
        migrations_dir = resources.files("app.db.migrations")
        migration_files = sorted([f.name for f in migrations_dir.iterdir() if f.name.endswith(".sql")])

        for filename in migration_files:
            async with self.conn.execute("SELECT COUNT(1) FROM schema_migrations WHERE version = ?", (filename,)) as cur:
                row = await cur.fetchone()
                if row and row[0] > 0:
                    continue

            content = (migrations_dir / filename).read_text(encoding="utf-8")
            async with self.write_tx() as conn:
                await conn.executescript(content)
                now_ms = int(datetime.now(UTC).timestamp() * 1000)
                await conn.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (filename, now_ms))

    async def _seed_astronauts(self) -> None:
        async with self.conn.execute("SELECT COUNT(1) FROM astronauts") as cur:
            row = await cur.fetchone()
            if row and row[0] > 0:
                return

        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        seed_data = [
            ("astro-a", "Dr. Alex Rivera", "EVA-01", "normal", 70, now_ms),
            ("astro-b", "Capt. Samantha Vance", "EVA-02", "normal", 68, now_ms),
            ("astro-c", "Lt. David Chen", "EVA-03", "normal", 72, now_ms),
        ]

        async with self.write_tx() as conn:
            await conn.executemany("""
                INSERT INTO astronauts (id, display_name, mission, mode, baseline_hr, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, seed_data)


def translate_db_error(op: str, exc: Exception) -> Exception:
    if isinstance(exc, AppError):
        return exc

    msg = str(exc).lower()
    if isinstance(exc, sqlite3.OperationalError):
        if "locked" in msg or "busy" in msg:
            return unavailable(op, "Database is currently busy.")
        return internal(op)
    if isinstance(exc, sqlite3.IntegrityError):
        if "foreign key" in msg:
            return not_found(op, "Referenced entity not found.")
        return conflict(op, "Unique constraint violation.")
    return internal(op)
