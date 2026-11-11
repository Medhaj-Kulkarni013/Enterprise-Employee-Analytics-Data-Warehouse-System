"""
Base manager for database operations.
All manager classes inherit from this class.
"""

from core.db_manager import DatabaseConnection


class BaseManager(DatabaseConnection):
    """Base class providing database access to all managers."""

    def __init__(self):
        """Initialize the manager and inherit database access."""
        super().__init__()

    def get_connection(self):
        """Return a database connection and cursor."""
        return self.cursor()