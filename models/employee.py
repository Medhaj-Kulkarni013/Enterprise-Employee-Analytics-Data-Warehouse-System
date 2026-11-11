
"""
Employee entity representing an employee in the HR Analytics System.
"""

import re
from datetime import date
from decimal import Decimal

from models.base_entity import BaseEntity


class Employee(BaseEntity):
    """
    Employee entity with encapsulated attributes and validation.
    """

    def __init__(
        self,
        employee_id=None,
        employee_code=None,
        first_name=None,
        last_name=None,
        email=None,
        hire_date=None,
        department_id=None,
        job_role_id=None,
        job_level=None,
        monthly_income=None,
        gender=None,
        date_of_birth=None,
        marital_status=None,
        education_level=None,
        education_field=None,
        distance_from_home_km=None,
        num_companies_worked=None,
        stock_option_level=None,
        prior_experience_years=None,
        business_travel=None,
        overtime_flag=None,
        manager_id=None,
        is_active=True,
        termination_date=None
    ):
        self.employee_id = employee_id
        self.employee_code = employee_code
        self.first_name = first_name
        self.last_name = last_name

        self._email = email
        self._hire_date = self._convert_date(hire_date)
        self._job_level = job_level
        self._monthly_income = monthly_income

        self.department_id = department_id
        self.job_role_id = job_role_id
        self.gender = gender
        self.date_of_birth = self._convert_date(date_of_birth)
        self.marital_status = marital_status
        self.education_level = education_level
        self.education_field = education_field
        self.distance_from_home_km = distance_from_home_km
        self.num_companies_worked = num_companies_worked
        self.stock_option_level = stock_option_level
        self.prior_experience_years = prior_experience_years
        self.business_travel = business_travel
        self.overtime_flag = overtime_flag
        self.manager_id = manager_id
        self.is_active = is_active
        self.termination_date = self._convert_date(termination_date)

        self.validate()

    # Email property
    @property
    def email(self):
        return self._email

    @email.setter
    def email(self, value):
        if not isinstance(value, str) or not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+", value
        ):
            raise ValueError("Invalid email address.")

        self._email = value

    # Monthly income property
    @property
    def monthly_income(self):
        return self._monthly_income

    @monthly_income.setter
    def monthly_income(self, value):
        if (
            not isinstance(value, (int, float, Decimal))
            or isinstance(value, bool)
            or value <= 0
        ):
            raise ValueError("Monthly income must be greater than zero.")

        self._monthly_income = float(value)

    # Job level property
    @property
    def job_level(self):
        return self._job_level

    @job_level.setter
    def job_level(self, value):
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 5:
            raise ValueError("Job level must be between 1 and 5.")

        self._job_level = value

    # Hire date property
    @property
    def hire_date(self):
        return self._hire_date

    @hire_date.setter
    def hire_date(self, value):
        if isinstance(value, str):
            try:
                value = date.fromisoformat(value)
            except ValueError as error:
                raise ValueError("Hire date must use YYYY-MM-DD format.") from error

        if not isinstance(value, date):
            raise ValueError("Hire date must be a valid date.")

        if value > date.today():
            raise ValueError("Hire date cannot be in the future.")

        self._hire_date = value

    @staticmethod
    def _convert_date(value):
        if value is None:
            return None
        if isinstance(value, str):
            return date.fromisoformat(value)
        if not isinstance(value, date):
            raise ValueError("Date must be a valid date.")
        return value

    def validate(self):
        """Validate all employee attributes."""

        if self.employee_id is not None and (
            not isinstance(self.employee_id, int) or self.employee_id <= 0
        ):
            raise ValueError("Employee ID must be a positive integer.")

        if not self.employee_code:
            raise ValueError("Employee code is required.")

        if not self.first_name or not self.last_name:
            raise ValueError("Employee name is required.")

        if not isinstance(self.department_id, int) or self.department_id <= 0:
            raise ValueError("Invalid department ID.")

        if not isinstance(self.job_role_id, int) or self.job_role_id <= 0:
            raise ValueError("Invalid job role ID.")

        if self.date_of_birth and self.hire_date:
            if self.hire_date < self.date_of_birth:
                raise ValueError("Hire date cannot precede date of birth.")

        if self.termination_date and self.termination_date < self.hire_date:
            raise ValueError("Termination date cannot precede hire date.")

        if self.is_active not in (True, False, 0, 1):
            raise ValueError("Active status must be boolean.")

        # Validate private attributes through their setters
        self.email = self._email
        self.monthly_income = self._monthly_income
        self.job_level = self._job_level
        self.hire_date = self._hire_date

        return True

    def promote(self, new_job_level, new_monthly_income):
        """Promote employee and update job level and salary."""

        if new_job_level <= self.job_level or new_job_level > 5:
            raise ValueError("Promotion requires a higher job level.")

        self.job_level = new_job_level
        self.monthly_income = new_monthly_income

    def transfer(self, dept_id):
        """Transfer employee to another department."""

        if not isinstance(dept_id, int) or isinstance(dept_id, bool) or dept_id <= 0:
            raise ValueError("Invalid department ID.")

        self.department_id = dept_id

    def tenure_years(self, as_of=None):
        """Calculate completed years of service."""

        as_of = as_of or date.today()

        if isinstance(as_of, str):
            as_of = date.fromisoformat(as_of)

        if as_of < self.hire_date:
            raise ValueError("Calculation date cannot precede hire date.")

        years = as_of.year - self.hire_date.year

        if (as_of.month, as_of.day) < (
            self.hire_date.month, self.hire_date.day
        ):
            years -= 1

        return years

    @classmethod
    def from_row(cls, row):
        """Create an Employee object from a database row."""

        return cls(
            employee_id=row["employee_id"],
            employee_code=row["employee_code"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            email=row["email"],
            hire_date=row["hire_date"],
            department_id=row["department_id"],
            job_role_id=row["job_role_id"],
            job_level=row["job_level"],
            monthly_income=row["monthly_income"],
            gender=row.get("gender"),
            date_of_birth=row.get("date_of_birth"),
            marital_status=row.get("marital_status"),
            education_level=row.get("education_level"),
            education_field=row.get("education_field"),
            distance_from_home_km=row.get("distance_from_home_km"),
            num_companies_worked=row.get("num_companies_worked"),
            stock_option_level=row.get("stock_option_level"),
            prior_experience_years=row.get("prior_experience_years"),
            business_travel=row.get("business_travel"),
            overtime_flag=row.get("overtime_flag"),
            manager_id=row.get("manager_id"),
            is_active=row.get("is_active", True),
            termination_date=row.get("termination_date")
        )

    def to_dict(self):
        """Convert employee attributes into a dictionary."""

        return {
            "employee_id": self.employee_id,
            "employee_code": self.employee_code,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "hire_date": self.hire_date.isoformat(),
            "department_id": self.department_id,
            "job_role_id": self.job_role_id,
            "job_level": self.job_level,
            "monthly_income": self.monthly_income,
            "gender": self.gender,
            "date_of_birth": (
                self.date_of_birth.isoformat() if self.date_of_birth else None
            ),
            "marital_status": self.marital_status,
            "education_level": self.education_level,
            "education_field": self.education_field,
            "distance_from_home_km": self.distance_from_home_km,
            "num_companies_worked": self.num_companies_worked,
            "stock_option_level": self.stock_option_level,
            "prior_experience_years": self.prior_experience_years,
            "business_travel": self.business_travel,
            "overtime_flag": self.overtime_flag,
            "manager_id": self.manager_id,
            "is_active": self.is_active,
            "termination_date": (
                self.termination_date.isoformat()
                if self.termination_date else None
            )
        }
