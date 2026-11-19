"""Unit tests for Singleton DB connection, transaction rollback, and DAL Managers."""
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from core.db_manager import DatabaseConnection
from core.exceptions import AppError, DatabaseError, NotFoundError, ValidationError
from managers.analytics_manager import AnalyticsManager
from managers.crud_manager import CrudManager
from managers.employee_manager import EmployeeManager
from managers.project_manager import ProjectManager
from managers.review_manager import ReviewManager
from models.employee import Employee


class TestCoreAndManagers(unittest.TestCase):
    def test_singleton_identity_and_inheritance_hierarchy(self):
        db1 = DatabaseConnection()
        db2 = DatabaseConnection()
        self.assertIs(db1, db2)

        em1 = EmployeeManager()
        em2 = EmployeeManager()
        self.assertIs(em1, em2)
        self.assertIsInstance(em1, DatabaseConnection)
        self.assertTrue(issubclass(EmployeeManager, CrudManager))
        self.assertTrue(issubclass(DatabaseError, AppError))

    def test_abstract_crud_manager_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            CrudManager()

    def test_transaction_commits_on_success_and_rolls_back_on_error(self):
        db = DatabaseConnection()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        with patch.object(db, "cursor", return_value=(mock_conn, mock_cursor)):
            with db.transaction() as cur:
                cur.execute("SELECT 1")
            mock_conn.start_transaction.assert_called_once()
            mock_conn.commit.assert_called_once()
            mock_conn.rollback.assert_not_called()

        mock_conn.reset_mock()
        with patch.object(db, "cursor", return_value=(mock_conn, mock_cursor)):
            with self.assertRaises(ValidationError):
                with db.transaction():
                    raise ValidationError("Invalid business input")
            mock_conn.rollback.assert_called_once()
            mock_conn.commit.assert_not_called()

    def test_employee_manager_get_by_id_and_not_found(self):
        mgr = EmployeeManager()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        with patch.object(mgr, "get_connection", return_value=(mock_conn, mock_cursor)):
            with self.assertRaises(NotFoundError):
                mgr.get_by_id(99999)
            mock_cursor.close.assert_called_once()
            mock_conn.close.assert_called_once()

    def test_employee_manager_atomic_update_employment_triggers_scd2(self):
        mgr = EmployeeManager()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            {"department_id": 1, "job_role_id": 2, "job_level": 2, "monthly_income": 5000.0},
            {"latest_effective_date": date(2023, 1, 1)},
        ]
        mock_cursor.stored_results.return_value = []

        with patch.object(mgr, "cursor", return_value=(mock_conn, mock_cursor)):
            result = mgr.update_employment(
                101,
                department_id=3,
                effective_date=date(2025, 6, 1),
                change_type="Transfer",
            )

        self.assertTrue(result)
        mock_cursor.callproc.assert_called_once_with("dw.sp_sync_employee_scd2", (101,))
        mock_conn.commit.assert_called_once()

    def test_employee_manager_rejects_stale_effective_date(self):
        mgr = EmployeeManager()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [
            {"department_id": 1, "job_role_id": 2, "job_level": 2, "monthly_income": 5000.0},
            {"latest_effective_date": date(2025, 6, 1)},
        ]

        with patch.object(mgr, "cursor", return_value=(mock_conn, mock_cursor)):
            with self.assertRaises(ValidationError):
                mgr.update_employment(
                    101,
                    department_id=3,
                    effective_date=date(2025, 5, 1),
                )
        mock_conn.rollback.assert_called_once()

    def test_analytics_manager_validates_department_id(self):
        am = AnalyticsManager()
        with self.assertRaises(ValidationError):
            am.get_employee_summary(department_id=-5)
        with self.assertRaises(ValidationError):
            am.get_top_performers(department_id=0)


if __name__ == "__main__":
    unittest.main()