from abc import ABC, abstractmethod


class BaseDriver(ABC):
    """Abstract base class for all database drivers."""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def execute_query(self, query: str) -> list[dict]:
        """Executes a SELECT query and returns the results as a list of dicts."""
        pass

    @abstractmethod
    async def list_tables(self) -> list[str]:
        """Returns the list of available tables in the database."""
        pass
