import asyncpg
from .base import BaseDriver


class PostgreSQLDriver(BaseDriver):
    """Driver for PostgreSQL using asyncpg."""

    def _build_connect_kwargs(self) -> dict:
        """Build connection kwargs instead of a DSN URL to safely handle
        passwords containing special characters (@, :, /, etc.)."""
        cfg = self.config
        return {
            "user":     cfg["user"],
            "password": cfg["password"],
            "host":     cfg.get("host", "localhost"),
            "port":     int(cfg.get("port", 5432)),
            "database": cfg.get("db", "unknown"),
        }

    async def execute_query(self, query: str) -> list[dict]:
        conn = None
        try:
            conn = await asyncpg.connect(**self._build_connect_kwargs())
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]
        finally:
            if conn:
                await conn.close()

    async def list_tables(self) -> list[str]:
        conn = None
        try:
            conn = await asyncpg.connect(**self._build_connect_kwargs())
            rows = await conn.fetch("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            return [row["table_name"] for row in rows]
        finally:
            if conn:
                await conn.close()
