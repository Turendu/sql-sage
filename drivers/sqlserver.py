import aioodbc
from .base import BaseDriver


class SQLServerDriver(BaseDriver):
    """
    Driver for SQL Server using aioodbc + pyodbc.

    Requires the ODBC Driver for SQL Server to be installed:
    - Windows: https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server
    - Linux:   https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server
    """

    def _build_dsn(self) -> str:
        cfg = self.config
        driver = cfg.get("odbc_driver", "ODBC Driver 17 for SQL Server")
        host = cfg.get("host", "localhost")
        port = int(cfg.get("port", 1433))
        database = cfg["db"]
        user = cfg["user"]
        password = cfg["password"]

        # Default to validating the server certificate (secure by default).
        # Set "trust_server_certificate": true in config.json only for dev/self-signed certs.
        trust_cert = "yes" if cfg.get("trust_server_certificate", False) else "no"

        return (
            f"Driver={{{driver}}};"
            f"Server={host},{port};"
            f"Database={database};"
            f"UID={user};"
            f"PWD={password};"
            f"TrustServerCertificate={trust_cert};"
        )

    async def execute_query(self, query: str) -> list[dict]:
        async with await aioodbc.connect(dsn=self._build_dsn()) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query)
                columns = [col[0] for col in cursor.description]
                rows = await cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]

    async def list_tables(self) -> list[str]:
        async with await aioodbc.connect(dsn=self._build_dsn()) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_type = 'BASE TABLE'
                    AND table_catalog = DB_NAME()
                    ORDER BY table_name
                """)
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
