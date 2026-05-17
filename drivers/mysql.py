import aiomysql
from .base import BaseDriver


class MySQLDriver(BaseDriver):
    """Driver for MySQL using aiomysql."""

    def _build_connect_kwargs(self) -> dict:
        cfg = self.config
        kwargs = {
            "host":     cfg.get("host", "localhost"),
            "port":     int(cfg.get("port", 3306)),
            "user":     cfg["user"],
            "password": cfg["password"],
            "db":       cfg["db"],
            "charset":  cfg.get("charset", "utf8mb4"),
        }
        return kwargs

    async def execute_query(self, query: str) -> list[dict]:
        conn = None
        cursor = None
        try:
            conn = await aiomysql.connect(**self._build_connect_kwargs())
            cursor = await conn.cursor(aiomysql.DictCursor)
            await cursor.execute(query)
            results = await cursor.fetchall()
            return [dict(row) for row in results]
        finally:
            if cursor:
                await cursor.close()
            if conn:
                conn.close()

    async def list_tables(self) -> list[str]:
        conn = None
        cursor = None
        try:
            conn = await aiomysql.connect(**self._build_connect_kwargs())
            cursor = await conn.cursor(aiomysql.DictCursor)
            await cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            rows = await cursor.fetchall()
            return [row["table_name"] for row in rows]
        finally:
            if cursor:
                await cursor.close()
            if conn:
                conn.close()
