
"""
Custom exception hierarchy for the Employee Analytics System.
"""


class AppError(Exception):
    """Base exception for all application-specific errors."""

    def __init__(self, message="An application error occurred", original_error=None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


class DatabaseError(AppError):
    """Raised when a database operation fails."""
    pass


class ValidationError(AppError):
    """Raised when input data fails validation."""
    pass


class NotFoundError(AppError):
    """Raised when a requested record does not exist."""
    pass


class DuplicateError(AppError):
    """Raised when a duplicate record is encountered."""
    pass
