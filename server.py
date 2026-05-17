import json
import re
import sys
import asyncio
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from drivers import get_driver

# ---------------------------------------------------------------------------
# Load configuration
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent / "config.json"
EXAMPLE_PATH = Path(__file__).parent / "config.example.json"

try:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    sys.exit(
        f"[mcp_server] config.json not found at {CONFIG_PATH}\n"
        f"Copy {EXAMPLE_PATH} to config.json and fill in your connection details."
    )
except json.JSONDecodeError as exc:
    sys.exit(f"[mcp_server] config.json is not valid JSON: {exc}")

try:
    SERVER_NAME = CONFIG["server"]["name"]
    DB_ENGINE = CONFIG["server"]["db_engine"]
    DB_CONFIG = CONFIG["database"]
    SYSTEM_PROMPT_TEMPLATE = CONFIG["system_prompt"]
except KeyError as exc:
    sys.exit(
        f"[mcp_server] Missing required key in config.json: {exc}\n"
        f"Check config.example.json for the expected structure."
    )

_security = CONFIG.get("security", {})
QUERY_TIMEOUT = _security.get("query_timeout_seconds", 30)
MAX_ROWS = _security.get("max_rows", 500)

if not isinstance(QUERY_TIMEOUT, (int, float)) or QUERY_TIMEOUT <= 0:
    sys.exit(
        "[mcp_server] security.query_timeout_seconds must be a positive number.")
if not isinstance(MAX_ROWS, int) or MAX_ROWS <= 0:
    sys.exit("[mcp_server] security.max_rows must be a positive integer.")

# For SQLite the 'file' value is a full path; expose only the stem to the AI model.
_raw_db_name = DB_CONFIG.get("db") or DB_CONFIG.get("file") or "unknown"
db_name = Path(_raw_db_name).stem if _raw_db_name != "unknown" else "unknown"
try:
    SYSTEM_PROMPT = SYSTEM_PROMPT_TEMPLATE.format(
        db_engine=DB_ENGINE.upper(),
        db_name=db_name,
    )
except KeyError as exc:
    sys.exit(
        f"[mcp_server] system_prompt in config.json contains an unknown placeholder: {exc}\n"
        f"Valid placeholders are: {{db_engine}}, {{db_name}}"
    )
except (AttributeError, TypeError):
    sys.exit(
        "[mcp_server] system_prompt in config.json must be a string.\n"
        f"Check config.example.json for the expected structure."
    )

# ---------------------------------------------------------------------------
# Driver initialization
# ---------------------------------------------------------------------------

try:
    db = get_driver(DB_ENGINE, DB_CONFIG)
except ValueError as exc:
    sys.exit(f"[mcp_server] {exc}")

# ---------------------------------------------------------------------------
# Query validation
# ---------------------------------------------------------------------------

DANGEROUS_KEYWORDS = [
    "DROP", "TRUNCATE", "ALTER", "CREATE", "DELETE", "UPDATE",
    "INSERT", "REPLACE", "MERGE", "GRANT", "REVOKE", "COMMIT", "ROLLBACK",
    "SAVEPOINT", "LOCK", "UNLOCK", "EXEC", "EXECUTE", "CALL",
]

# Internal system catalogs that should not be accessible
BLOCKED_SCHEMAS = [
    # SQL standard: table/column names, user & table privileges (all engines)
    "information_schema",  # SQL standard metadata schema
    "pg_catalog",          # PostgreSQL internal catalog
    "pg_toast",            # PostgreSQL internal TOAST storage
    "pg_temp",             # PostgreSQL temporary schemas
    "mysql",               # MySQL system schema (contains user credentials)
    "sys",                 # MySQL 5.7+ / SQL Server system schema
    "performance_schema",  # MySQL internal metrics
    "master",              # SQL Server: server config, login hashes
    "msdb",                # SQL Server: Agent jobs, backup history, stored credentials
    "tempdb",              # SQL Server: internal temporary objects
    "model",               # SQL Server: template database
]


def strip_sql_comments(query: str) -> str:
    """Remove SQL comments before validation to prevent keyword-evasion techniques.

    Block comments are replaced with an empty string (NOT a space) so that
    split-keyword attacks like ``DR/**/OP`` collapse into ``DROP`` and are
    detected by the subsequent keyword check.
    Line comments are removed entirely.
    """
    # Remove /* ... */ block comments with empty string to collapse split keywords
    result = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
    # Remove -- line comments
    result = re.sub(r'--[^\n]*', '', result)
    return result.strip()


def check_dangerous_query(query: str) -> str | None:
    """Returns the first dangerous keyword found, or None if the query is safe."""
    query_upper = query.upper()
    for keyword in DANGEROUS_KEYWORDS:
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, query_upper):
            return keyword
    return None


def check_blocked_schema(query: str) -> str | None:
    """Returns the first blocked system schema found, or None if the query is safe."""
    query_upper = query.upper()
    for schema in BLOCKED_SCHEMAS:
        pattern = r"\b" + re.escape(schema.upper()) + r"\b"
        if re.search(pattern, query_upper):
            return schema
    return None


# Matches queries that start with SELECT or WITH (CTEs), optionally wrapped in parentheses.
# Everything else (SHOW, EXPLAIN, PRAGMA, DESCRIBE, EXEC, etc.) is rejected by default.
_ALLOWED_START_RE = re.compile(r'^[\s(]*(?:WITH|SELECT)\b', re.IGNORECASE)


def check_starts_with_select(query: str) -> bool:
    """Return True only if the query begins with SELECT or WITH (for CTEs).

    This is a positive allowlist check and acts as the primary barrier:
    even if a dangerous statement is not in DANGEROUS_KEYWORDS it will be
    rejected here (e.g. SHOW, EXPLAIN, PRAGMA, DESCRIBE, EXECUTE).
    Leading parentheses are accepted to support engines that allow
    parenthesised SELECT expressions such as ``(SELECT 1)``.
    """
    return bool(_ALLOWED_START_RE.match(query))


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

app = Server(name=SERVER_NAME, instructions=SYSTEM_PROMPT)


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="query_database",
            description="Executes a SQL SELECT query on the database",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": f"SQL SELECT query to execute on {DB_ENGINE.upper()}",
                    }
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="list_tables",
            description="Lists all available tables in the database",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    if name == "query_database":
        query = arguments.get("query", "").strip()

        if not query:
            return [TextContent(type="text", text="Error: the query is empty.")]

        sanitized_query = strip_sql_comments(query)

        # Primary barrier (allowlist): only SELECT / WITH (CTE) queries are permitted.
        # Rejects SHOW, EXPLAIN, PRAGMA, DESCRIBE and anything not in the blocklist.
        if not check_starts_with_select(sanitized_query):
            return [TextContent(
                type="text",
                text="WARNING! Operation not allowed. Only SELECT queries are permitted.",
            )]

        found_keyword = check_dangerous_query(sanitized_query)
        if found_keyword:
            return [TextContent(
                type="text",
                text=(
                    f"WARNING! Operation not allowed. "
                    f"Dangerous keyword found: '{found_keyword}'. "
                    f"Only SELECT queries are allowed."
                ),
            )]

        blocked_schema = check_blocked_schema(sanitized_query)
        if blocked_schema:
            return [TextContent(
                type="text",
                text=(
                    f"WARNING! Access to system catalog '{blocked_schema}' is not allowed."
                ),
            )]

        try:
            results = await asyncio.wait_for(
                db.execute_query(sanitized_query),
                timeout=QUERY_TIMEOUT,
            )
            if results:
                if len(results) > MAX_ROWS:
                    results = results[:MAX_ROWS]
                    footer = f"\n\n[Output limited to {MAX_ROWS} rows. Refine your query to get more specific results.]"
                else:
                    footer = ""
                formatted = "\n".join([str(row) for row in results])
                return [TextContent(type="text", text=formatted + footer)]
            else:
                return [TextContent(type="text", text="No results found.")]
        except asyncio.TimeoutError:
            return [TextContent(
                type="text",
                text=f"Error: query exceeded the maximum allowed time ({QUERY_TIMEOUT}s) and was cancelled.",
            )]
        except Exception as e:
            return [TextContent(type="text", text=f"Error executing query: {e}")]

    elif name == "list_tables":
        try:
            tables = await db.list_tables()
            if tables:
                return [TextContent(
                    type="text",
                    text="Available tables:\n" + "\n".join(tables),
                )]
            else:
                return [TextContent(type="text", text="No tables found.")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error listing tables: {e}")]

    else:
        return [TextContent(type="text", text=f"Unknown tool: '{name}'")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
