"""
Abstract base class defining common CRUD operations.
"""

from abc import ABC, abstractmethod
from managers.base_manager import BaseManager


class CrudManager(BaseManager, ABC):
    """Abstract class defining standard CRUD operations."""

    @abstractmethod
    def create(self, entity):
        """Insert a new entity into the database."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, record_id):
        """Fetch an entity using its ID."""
        raise NotImplementedError

    @abstractmethod
    def update(self, record_id, entity):
        """Update an existing entity."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, record_id):
        """Delete an entity using its ID."""
        raise NotImplementedError