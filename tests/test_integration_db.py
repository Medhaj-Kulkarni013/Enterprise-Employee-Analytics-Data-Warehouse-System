"""Opt-in live MySQL integration tests (run with RUN_LIVE_DB_TESTS=1)."""
import os
import unittest
from datetime import date

from config.database import get_database_config
from core.db_manager import DatabaseConnection
from managers.employee_manager import EmployeeManager
from models.employee import Employee


@unittest.skipUnless(
    os.getenv("RUN_LIVE_DB_TESTS") == "1",
    "Set RUN_LIVE_DB_TESTS=1 with a valid .env to run live MySQL integration tests.",
)
class TestLiveDatabaseIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseConnection()
        cls.db.initialize_pool(get_database_config())
        cls.emp_mgr = EmployeeManager()

    def test_onboard_and_scd2_department_transfer_end_to_end(self):
        conn, cur = self.db.cursor()
        try:
            cur.execute("SELECT department_id FROM oltp.department ORDER BY department_id LIMIT 2")
            depts = [row["department_id"] for row in cur.fetchall()]
            cur.execute("SELECT job_role_id FROM oltp.job_role ORDER BY job_role_id LIMIT 1")
            role_id = cur.fetchone()["job_role_id"]
        finally:
            cur.close()
            conn.close()

        self.assertGreaterEqual(len(depts), 2, "Need at least 2 departments in oltp.department")
        dept_initial, dept_new = depts[0], depts[1]

        test_emp = Employee(
            employee_id=None,
            employee_code="TST99999",
            first_name="Integration",
            last_name="Tester",
            email="tst99999@example.com",
            hire_date=date(2023, 1, 10),
            department_id=dept_initial,
            job_role_id=role_id,
            job_level=2,
            monthly_income=5000.0,
            gender="Male",
            date_of_birth=date(1990, 1, 1),
            marital_status="Single",
            education_level=3,
            education_field="Other",
            distance_from_home_km=10,
            num_companies_worked=1,
            stock_option_level=0,
            prior_experience_years=2,
            business_travel="Non-Travel",
            overtime_flag=0,
        )

        emp_id = None
        try:
            # 1. Onboard employee -> inserts OLTP + Hire log + Dim_Employee v1
            emp_id = self.emp_mgr.create(test_emp)

            # 2. Transfer department -> triggers atomic SCD2 close + v2 insert
            self.emp_mgr.update_employment(
                emp_id,
                department_id=dept_new,
                effective_date=date(2025, 6, 1),
                change_type="Transfer",
            )

            # 3. Verify SCD2 state directly in dw.Dim_Employee
            conn, cur = self.db.cursor()
            try:
                cur.execute(
                    """SELECT version_no, department_id, start_date, end_date, is_current
                       FROM dw.Dim_Employee WHERE employee_id = %s ORDER BY version_no""",
                    (emp_id,),
                )
                versions = cur.fetchall()
            finally:
                cur.close()
                conn.close()

            self.assertEqual(len(versions), 2)
            self.assertEqual(versions[0]["is_current"], 0)
            self.assertEqual(versions[0]["end_date"], date(2025, 5, 31))
            self.assertEqual(versions[1]["is_current"], 1)
            self.assertEqual(versions[1]["department_id"], dept_new)
            self.assertEqual(versions[1]["end_date"], date(9999, 12, 31))
        finally:
            # Clean up test record in FK-safe order
            if emp_id is not None:
                with self.db.transaction() as cur:
                    cur.execute("DELETE FROM dw.Dim_Employee WHERE employee_id = %s", (emp_id,))
                    cur.execute("DELETE FROM oltp.employee_change_log WHERE employee_id = %s", (emp_id,))
                    cur.execute("DELETE FROM oltp.employee WHERE employee_id = %s", (emp_id,))


if __name__ == "__main__":
    unittest.main()