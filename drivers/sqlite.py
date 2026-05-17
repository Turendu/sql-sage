import aiosqlite
from .base import BaseDriver


class SQLiteDriver(BaseDriver):
    """Driver for SQLite using aiosqlite."""

    def _get_path(self) -> str:
        """Returns the path to the .db file. Uses 'file' instead of 'db' if defined."""
        path = self.config.get("file") or self.config.get("db")
        if not path:
            raise ValueError(
                "SQLite driver requires 'file' to be set in the database config."
            )
        return path

    async def execute_query(self, query: str) -> list[dict]:
        async with aiosqlite.connect(self._get_path()) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(query) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def list_tables(self) -> list[str]:
        async with aiosqlite.connect(self._get_path()) as conn:
            async with conn.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
