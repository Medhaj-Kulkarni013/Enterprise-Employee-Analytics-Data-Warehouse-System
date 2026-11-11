
"""
Project entity for the Employee Analytics System.
"""

from datetime import date
from models.base_entity import BaseEntity


class Project(BaseEntity):
    """Represents a company project."""

    VALID_STATUSES = {"Planned", "Active", "Completed", "On Hold"}

    def __init__(
        self,
        project_id,
        project_code,
        project_name,
        department_id,
        start_date,
        end_date=None,
        status="Planned"
    ):
        self.project_id = project_id
        self.project_code = project_code
        self.project_name = project_name
        self.department_id = department_id
        self.start_date = self._convert_date(start_date)
        self.end_date = self._convert_date(end_date) if end_date else None
        self.status = status

        self.validate()

    @staticmethod
    def _convert_date(value):
        """Convert ISO date strings into date objects."""
        if isinstance(value, str):
            return date.fromisoformat(value)

        if not isinstance(value, date):
            raise ValueError("Invalid project date.")

        return value

    def validate(self):
        """Validate project details."""

        if self.project_id is not None and (
            not isinstance(self.project_id, int) or self.project_id <= 0
        ):
            raise ValueError("Project ID must be a positive integer.")

        if not self.project_code:
            raise ValueError("Project code is required.")

        if not self.project_name:
            raise ValueError("Project name is required.")

        if not isinstance(self.department_id, int) or self.department_id <= 0:
            raise ValueError("Invalid department ID.")

        if self.status not in self.VALID_STATUSES:
            raise ValueError("Invalid project status.")

        if self.end_date and self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date.")

        return True

    def is_active(self):
        """Check whether the project is currently active."""
        return (
            self.status == "Active"
            and (self.end_date is None or self.end_date >= date.today())
        )

    def duration_days(self):
        """Calculate project duration in days."""
        end = self.end_date or date.today()

        if end < self.start_date:
            raise ValueError("Project has not started yet.")

        return (end - self.start_date).days

    def to_dict(self):
        """Convert project attributes into a dictionary."""

        return {
            "project_id": self.project_id,
            "project_code": self.project_code,
            "project_name": self.project_name,
            "department_id": self.department_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.status
        }

    @classmethod
    def from_row(cls, row):
        """Create a project from a dictionary database row."""
        return cls(
            project_id=row["project_id"],
            project_code=row["project_code"],
            project_name=row["project_name"],
            department_id=row["department_id"],
            start_date=row["start_date"],
            end_date=row.get("end_date"),
            status=row.get("project_status", row.get("status", "Planned"))
        )
