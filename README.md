# MCP Database Server

> [!IMPORTANT]
> This server exposes your database to an AI model. The most important protection you can configure is using a **database user with read-only permissions** — no application-level validation is a substitute for that. See the [Security](#security) section before deploying.

An MCP server for querying relational databases from **Claude Desktop**. Supports read-only SQL queries and table listing across multiple database engines.

## Features

- Support for **MySQL**, **MariaDB**, **PostgreSQL**, **SQLite** and **SQL Server**
- Centralized configuration via `config.json`
- Editable system prompt without touching code
- Query validation: only `SELECT` statements allowed (DDL and DML are blocked)
- Extensible architecture to add new engines easily

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Claude Desktop

> **SQL Server only:** requires the [ODBC Driver for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server) to be installed at the OS level.

## Installation

```bash
# Clone the repository
git clone https://github.com/Turendu/sql-sage.git
cd sql-sage

# Reproducible install with exact pinned versions (recommended for deployment)
pip install -r requirements.lock

# Or with open ranges (development / keeping up with updates)
pip install -r requirements.txt
```

> To regenerate `requirements.lock` after updating dependencies:
> ```bash
> pip freeze > requirements.lock
> ```

## Quick Start with sample database

If you don't have a database available, you can use the included SQLite sample database to try the server immediately.

**1. Generate the sample database:**
```bash
python scripts/create_sample_db.py
```
This creates `sample.db` with four tables: `customers`, `products`, `orders` and `order_items`.

**2. Copy the example config and point it to the generated file:**
```bash
cp config.example.json config.json
```
Then edit `config.json` and set the absolute path to `sample.db` in the `file` field.

**3. Connect Claude Desktop** following the [Claude Desktop Integration](#claude-desktop-integration) section.

You can now ask Claude things like *"which customers have placed more than one order?"* or *"what are the top 3 best-selling products?"*.

---

## Configuration

Copy `config.example.json` to `config.json` and edit it with your connection details:

### Supported engines

| `db_engine`  | Engine        | Notes                                        |
|--------------|---------------|----------------------------------------------|
| `mysql`      | MySQL         |                                              |
| `mariadb`    | MariaDB       | Uses the same driver as MySQL                |
| `postgres`   | PostgreSQL    |                                              |
| `sqlite`     | SQLite        | Use `file` instead of `host/user/password`   |
| `sqlserver`  | SQL Server    | Requires ODBC Driver installed at OS level   |

### Configuration per engine (`config.json`)

**PostgreSQL**
```json
{
  "server": { "db_engine": "postgres" },
  "database": {
    "host": "localhost",
    "port": 5432,
    "user": "user",
    "password": "pass",
    "db": "dbname"
  }
}
```

**SQLite**
```json
{
  "server": { "db_engine": "sqlite" },
  "database": {
    "file": "C:\\path\\to\\database.db"
  }
}
```

**SQL Server**
```json
{
  "server": { "db_engine": "sqlserver" },
  "database": {
    "host": "localhost",
    "port": 1433,
    "user": "sa",
    "password": "pass",
    "db": "dbname",
    "odbc_driver": "ODBC Driver 17 for SQL Server"
  }
}
```

## Claude Desktop Integration

Add the following to your Claude Desktop configuration file:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`  
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "sql-sage": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\path\\to\\mcp_server",
        "run",
        "server.py"
      ]
    }
  }
}
```
> **TLS / corporate proxy / issues with uv?** Use the `.venv` Python directly instead:
> ```json
> {
>   "mcpServers": {
>     "sql-sage": {
>       "command": "C:\\path\\to\\mcp_server\\.venv\\Scripts\\python.exe",
>       "args": ["C:\\path\\to\\mcp_server\\server.py"]
>     }
>   }
> }
> ```
Restart Claude Desktop after saving the file.

## Project Structure

```
mcp_server/
├── server.py               # Entry point: loads config and registers MCP tools
├── config.json             # Your local config (gitignored — contains credentials)
├── config.example.json     # Example config to use as starting point
├── pyproject.toml          # Project metadata and dependencies (required by uv)
├── requirements.txt        # Python dependencies (alternative to pyproject.toml)
├── scripts/
│   └── create_sample_db.py # Generates sample.db with fictional data for testing
└── drivers/
    ├── __init__.py         # Factory: get_driver() based on db_engine
    ├── base.py             # Abstract BaseDriver class
    ├── mysql.py            # MySQL / MariaDB driver (aiomysql)
    ├── postgres.py         # PostgreSQL driver (asyncpg)
    ├── sqlite.py           # SQLite driver (aiosqlite)
    └── sqlserver.py        # SQL Server driver (aioodbc)
```

## Available Tools

Once connected, Claude will have access to:

- **`query_database`** — runs a `SELECT` query and returns the results
- **`list_tables`** — lists all available tables in the database

## Security

> [!IMPORTANT]
> The strongest protection is a **database user with read-only permissions** granted only to the tables the assistant needs. All application-level filters below are defense-in-depth — they reduce risk but are not a substitute for database-level access control.

The server applies three layers of validation to every query before execution:

1. **Comment stripping** — `/* */` block comments and `--` line comments are removed before any check, preventing comment-injection evasion (e.g. `DR/**/OP` collapsing into `DROP`).
2. **Allowlist (primary barrier)** — the sanitized query must start with `SELECT` or `WITH` (for CTEs). Anything else — `SHOW`, `EXPLAIN`, `DESCRIBE`, `PRAGMA`, `EXEC`, etc. — is rejected even if it does not appear in the keyword blocklist.
3. **Blocklist (secondary barrier)** — explicit dangerous keywords (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, …) and system schemas (`information_schema`, `pg_catalog`, `mysql`, `master`, …) are blocked as an additional layer.

Additional hardening recommendations:
- Use a database user with `SELECT`-only privileges scoped to the tables you want to expose.
- `config.json` is listed in `.gitignore` — it will never be committed accidentally. Use `config.example.json` as the template.
- Set `query_timeout_seconds` in `config.json` to limit the impact of expensive queries.