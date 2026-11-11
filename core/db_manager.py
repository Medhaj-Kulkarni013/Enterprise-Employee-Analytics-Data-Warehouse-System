

"""
Database connection manager using the Singleton design pattern.

Features:
- Thread-safe Singleton pattern
- Shared MySQL connection pool
- Aiven SSL certificate verification
- Transaction management
- Safe connection and cursor handling
"""

from threading import Lock
from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling

from core.exceptions import DatabaseError


class DatabaseConnection:
    """
    Thread-safe Singleton database connection manager.

    Each subclass gets its own instance, while all managers
    share the same database connection pool.
    """

    _instances = {}
    _lock = Lock()

    _pool = None
    _pool_lock = Lock()

    def __new__(cls, *args, **kwargs):
        """Create only one instance per class."""

        with DatabaseConnection._lock:
            if cls not in DatabaseConnection._instances:
                DatabaseConnection._instances[cls] = (
                    super().__new__(cls)
                )

        return DatabaseConnection._instances[cls]

    def __init__(self):
        """Avoid duplicate initialization."""
        pass

    @classmethod
    def initialize_pool(cls, config):
        """
        Initialize the shared MySQL connection pool.

        Args:
            config (dict): MySQL connection configuration.
                           Must include host, port, user,
                           password, database and ssl_ca.
        """

        with DatabaseConnection._pool_lock:

            if DatabaseConnection._pool is None:

                try:
                    pool_config = config.copy()

                    # Configure SSL certificate verification
                    pool_config.update({
                        "ssl_ca": pool_config.pop("ssl_ca"),
                        "ssl_verify_cert": True,
                        "ssl_verify_identity": True,
                        "autocommit": False,
                    })

                    DatabaseConnection._pool = (
                        pooling.MySQLConnectionPool(
                            pool_name="employee_pool",
                            pool_size=5,
                            **pool_config
                        )
                    )

                except mysql.connector.Error as error:
                    raise DatabaseError(
                        "Failed to initialize database pool",
                        error
                    ) from error

    def cursor(self, dictionary=True):
        """
        Get a cursor from the shared connection pool.

        Returns:
            tuple: (connection, cursor)
        """

        if DatabaseConnection._pool is None:
            raise DatabaseError(
                "Database pool is not initialized."
            )

        connection = None

        try:
            connection = (
                DatabaseConnection._pool.get_connection()
            )

            cursor = connection.cursor(
                dictionary=dictionary
            )

            return connection, cursor

        except mysql.connector.Error as error:

            if connection is not None:
                connection.close()

            raise DatabaseError(
                "Failed to obtain database cursor",
                error
            ) from error

    @contextmanager
    def transaction(self):
        """
        Provide a transactional database connection.

        Commits when successful and rolls back on failure.
        """

        connection = None
        cursor = None

        try:
            connection, cursor = self.cursor()

            connection.start_transaction()

            yield cursor

            connection.commit()

        except Exception as error:

            if connection is not None:
                connection.rollback()

            if isinstance(error, (DatabaseError,)):
                raise
            # Preserve domain exceptions (ValidationError, NotFoundError, etc.)
            # while still guaranteeing rollback.
            if error.__class__.__module__.startswith(("core.", "managers.", "models.")):
                raise
            raise DatabaseError("Transaction failed", error) from error

        finally:

            if cursor is not None:
                cursor.close()

            if connection is not None:
                connection.close()

    def close(self):
        """
        Individual pooled connections are returned using close().

        The shared pool remains available for application use.
        """
        pass
