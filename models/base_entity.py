
"""
Abstract base class for all application entities.
"""

from abc import ABC, abstractmethod


class BaseEntity(ABC):
    """
    Common abstract parent class for Employee, Project and Review.
    """

    @abstractmethod
    def validate(self):
        """Validate the entity's attributes."""
        pass

    @abstractmethod
    def to_dict(self):
        """Convert entity attributes into a dictionary."""
        pass

    def __eq__(self, other):
        """Compare two entities of the same class."""
        if not isinstance(other, self.__class__):
            return False

        return self.to_dict() == other.to_dict()

    def __repr__(self):
        """Return a readable representation of the entity."""
        return f"{self.__class__.__name__}({self.to_dict()})"
