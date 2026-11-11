
"""
Review entity for employee performance tracking.
"""

from datetime import date
from models.base_entity import BaseEntity


class Review(BaseEntity):
    """Represents an employee performance review."""

    def __init__(
        self,
        review_id,
        employee_id,
        reviewer_id,
        review_date,
        performance_rating,
        job_satisfaction,
        environment_satisfaction,
        relationship_satisfaction,
        work_life_balance,
        job_involvement,
        percent_salary_hike,
        training_times_last_year,
        project_id=None
    ):
        self.review_id = review_id
        self.employee_id = employee_id
        self.reviewer_id = reviewer_id
        self.project_id = project_id
        self.review_date = self._convert_date(review_date)

        self.performance_rating = performance_rating
        self.job_satisfaction = job_satisfaction
        self.environment_satisfaction = environment_satisfaction
        self.relationship_satisfaction = relationship_satisfaction
        self.work_life_balance = work_life_balance
        self.job_involvement = job_involvement
        self.percent_salary_hike = percent_salary_hike
        self.training_times_last_year = training_times_last_year

        self.validate()

    @staticmethod
    def _convert_date(value):
        """Convert ISO date strings into date objects."""
        if isinstance(value, str):
            return date.fromisoformat(value)

        if not isinstance(value, date):
            raise ValueError("Invalid review date.")

        return value

    def validate(self):
        """Validate performance review details."""

        if self.review_id is not None and (
            not isinstance(self.review_id, int) or self.review_id <= 0
        ):
            raise ValueError("Review ID must be a positive integer.")

        if not isinstance(self.employee_id, int) or self.employee_id <= 0:
            raise ValueError("Employee ID is required.")

        if self.reviewer_id is not None and self.employee_id == self.reviewer_id:
            raise ValueError("An employee cannot review themselves.")

        ratings = [
            self.performance_rating,
            self.job_satisfaction,
            self.environment_satisfaction,
            self.relationship_satisfaction,
            self.work_life_balance,
            self.job_involvement
        ]

        for rating in ratings:
            if not isinstance(rating, int) or isinstance(rating, bool) or not 1 <= rating <= 4:
                raise ValueError("All review ratings must be between 1 and 4.")

        if not isinstance(self.percent_salary_hike, int) or not 0 <= self.percent_salary_hike <= 100:
            raise ValueError("Salary hike must be between 0 and 100.")

        if not isinstance(self.training_times_last_year, int) or not 0 <= self.training_times_last_year <= 20:
            raise ValueError("Training sessions must be between 0 and 20.")

        return True

    def overall_satisfaction(self):
        """Calculate average employee satisfaction."""
        scores = [
            self.job_satisfaction,
            self.environment_satisfaction,
            self.relationship_satisfaction,
            self.work_life_balance
        ]

        return round(sum(scores) / len(scores), 2)

    def is_high_performer(self):
        """Check whether the employee is a high performer."""
        return self.performance_rating >= 3

    def to_dict(self):
        """Convert review attributes into a dictionary."""

        return {
            "review_id": self.review_id,
            "employee_id": self.employee_id,
            "reviewer_id": self.reviewer_id,
            "project_id": self.project_id,
            "review_date": self.review_date.isoformat(),
            "performance_rating": self.performance_rating,
            "job_satisfaction": self.job_satisfaction,
            "environment_satisfaction": self.environment_satisfaction,
            "relationship_satisfaction": self.relationship_satisfaction,
            "work_life_balance": self.work_life_balance,
            "job_involvement": self.job_involvement,
            "percent_salary_hike": self.percent_salary_hike,
            "training_times_last_year": self.training_times_last_year
        }

    @classmethod
    def from_row(cls, row):
        """Create a review from a dictionary database row."""
        return cls(
            review_id=row["review_id"],
            employee_id=row["employee_id"],
            reviewer_id=row.get("reviewer_id"),
            project_id=row.get("project_id"),
            review_date=row["review_date"],
            performance_rating=row["performance_rating"],
            job_satisfaction=row["job_satisfaction"],
            environment_satisfaction=row["environment_satisfaction"],
            relationship_satisfaction=row["relationship_satisfaction"],
            work_life_balance=row["work_life_balance"],
            job_involvement=row["job_involvement"],
            percent_salary_hike=row["percent_salary_hike"],
            training_times_last_year=row["training_times_last_year"]
        )
