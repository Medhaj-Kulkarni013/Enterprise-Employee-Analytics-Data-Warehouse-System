"""Assignment entity for employee project allocations."""

from datetime import date

from models.base_entity import BaseEntity


class Assignment(BaseEntity):
    """Represents an employee's allocation to a project."""

    VALID_ROLES = {"Lead", "Contributor", "Support"}

    def __init__(
        self,
        assignment_id=None,
        employee_id=None,
        project_id=None,
        role_on_project="Contributor",
        allocation_pct=100,
        start_date=None,
        end_date=None,
    ):
        self.assignment_id = assignment_id
        self.employee_id = employee_id
        self.project_id = project_id
        self.role_on_project = role_on_project
        self.allocation_pct = allocation_pct
        self.start_date = self._convert_date(start_date)
        self.end_date = self._convert_date(end_date) if end_date else None
        self.validate()

    @staticmethod
    def _convert_date(value):
        if isinstance(value, str):
            return date.fromisoformat(value)
        if not isinstance(value, date):
            raise ValueError("Assignment date must be a valid date.")
        return value

    def validate(self):
        if self.assignment_id is not None and (
            not isinstance(self.assignment_id, int) or self.assignment_id <= 0
        ):
            raise ValueError("Assignment ID must be a positive integer.")
        for name, value in (
            ("Employee", self.employee_id),
            ("Project", self.project_id),
        ):
            if not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} ID must be a positive integer.")
        if self.role_on_project not in self.VALID_ROLES:
            raise ValueError("Invalid project assignment role.")
        if (
            not isinstance(self.allocation_pct, int)
            or isinstance(self.allocation_pct, bool)
            or not 1 <= self.allocation_pct <= 100
        ):
            raise ValueError("Allocation must be between 1 and 100 percent.")
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("Assignment end date cannot precede start date.")
        return True

    @classmethod
    def from_row(cls, row):
        return cls(
            assignment_id=row["assignment_id"],
            employee_id=row["employee_id"],
            project_id=row["project_id"],
            role_on_project=row["role_on_project"],
            allocation_pct=row["allocation_pct"],
            start_date=row["start_date"],
            end_date=row.get("end_date"),
        )

    def to_dict(self):
        return {
            "assignment_id": self.assignment_id,
            "employee_id": self.employee_id,
            "project_id": self.project_id,
            "role_on_project": self.role_on_project,
            "allocation_pct": self.allocation_pct,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
        }
