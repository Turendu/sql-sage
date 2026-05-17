from .base import BaseDriver
from .mysql import MySQLDriver
from .postgres import PostgreSQLDriver
from .sqlserver import SQLServerDriver
from .sqlite import SQLiteDriver

SUPPORTED_ENGINES = {
    "mysql":    MySQLDriver,
    "mariadb":   MySQLDriver,
    "postgres": PostgreSQLDriver,
    "sqlserver": SQLServerDriver,
    "sqlite":    SQLiteDriver,
}


def get_driver(engine: str, db_config: dict) -> BaseDriver:
    """
    Factory: Returns the driver corresponding to the engine specified in config.json.

    Supported engines: 'mysql', 'mariadb', 'postgres', 'sqlserver', 'sqlite'
    """
    engine = engine.lower().strip()
    driver_class = SUPPORTED_ENGINES.get(engine)

    if driver_class is None:
        supported = ", ".join(SUPPORTED_ENGINES.keys())
        raise ValueError(
            f"Engine '{engine}' not supported. Available options: {supported}"
        )

    return driver_class(db_config)
