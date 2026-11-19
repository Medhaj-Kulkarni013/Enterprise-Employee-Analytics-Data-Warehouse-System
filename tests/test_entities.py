"""Unit tests for Domain Entity classes, encapsulation, and validation rules."""
import unittest
from datetime import date, timedelta

from models.assignment import Assignment
from models.base_entity import BaseEntity
from models.employee import Employee
from models.project import Project
from models.review import Review


def _valid_employee(**overrides):
    data = dict(
        employee_id=1,
        employee_code="E000001",
        first_name="Aarav",
        last_name="Sharma",
        email="aarav.sharma@example.com",
        hire_date=date(2022, 1, 15),
        department_id=1,
        job_role_id=2,
        job_level=2,
        monthly_income=5500.0,
        gender="Male",
        date_of_birth=date(1992, 5, 10),
        marital_status="Single",
        education_level=3,
        education_field="Life Sciences",
        distance_from_home_km=12,
        num_companies_worked=1,
        stock_option_level=1,
        prior_experience_years=3,
        business_travel="Travel_rarely",
        overtime_flag=0,
    )
    data.update(overrides)
    return Employee(**data)


class TestEntities(unittest.TestCase):
    def test_abstract_base_entity_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            BaseEntity()

    def test_employee_encapsulation_and_validation(self):
        emp = _valid_employee()
        self.assertEqual(emp.email, "aarav.sharma@example.com")

        with self.assertRaises(ValueError):
            emp.email = "invalid-email"
        with self.assertRaises(ValueError):
            emp.monthly_income = -100
        with self.assertRaises(ValueError):
            emp.job_level = 6
        with self.assertRaises(ValueError):
            emp.hire_date = date.today() + timedelta(days=10)

    def test_employee_promote_transfer_and_tenure(self):
        emp = _valid_employee(job_level=2, monthly_income=5000.0, hire_date=date(2020, 6, 1))
        emp.promote(3, 6800.0)
        self.assertEqual(emp.job_level, 3)
        self.assertEqual(emp.monthly_income, 6800.0)

        with self.assertRaises(ValueError):
            emp.promote(3, 7000.0)  # Must be strictly higher level

        emp.transfer(3)
        self.assertEqual(emp.department_id, 3)
        self.assertEqual(emp.tenure_years(as_of=date(2025, 6, 1)), 5)
        self.assertEqual(emp.tenure_years(as_of=date(2025, 5, 31)), 4)

    def test_employee_from_row_and_to_dict_roundtrip(self):
        emp = _valid_employee()
        rebuilt = Employee.from_row(emp.to_dict())
        self.assertEqual(emp, rebuilt)

    def test_project_domain_methods_and_date_validation(self):
        proj = Project(
            project_id=10,
            project_code="PRJ010",
            project_name="Warehouse Migration",
            department_id=1,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            status="Completed",
        )
        self.assertEqual(proj.duration_days(), 30)
        self.assertFalse(proj.is_active())

        with self.assertRaises(ValueError):
            Project(11, "PRJ011", "Bad Dates", 1, date(2025, 5, 10), date(2025, 5, 1), "Planned")

    def test_review_satisfaction_high_performer_and_self_review_block(self):
        rev = Review(
            review_id=1,
            employee_id=10,
            reviewer_id=2,
            review_date=date(2025, 12, 15),
            performance_rating=4,
            job_satisfaction=4,
            environment_satisfaction=3,
            relationship_satisfaction=4,
            work_life_balance=3,
            job_involvement=4,
            percent_salary_hike=18,
            training_times_last_year=3,
        )
        self.assertEqual(rev.overall_satisfaction(), 3.5)
        self.assertTrue(rev.is_high_performer())

        with self.assertRaises(ValueError):
            Review(2, 10, 10, date(2025, 12, 15), 3, 3, 3, 3, 3, 3, 12, 2)

    def test_assignment_allocation_bounds(self):
        assign = Assignment(1, 10, 5, "Lead", 80, date(2025, 2, 1))
        self.assertEqual(assign.to_dict()["allocation_pct"], 80)
        with self.assertRaises(ValueError):
            Assignment(2, 10, 5, "Lead", 120, date(2025, 2, 1))


if __name__ == "__main__":
    unittest.main()