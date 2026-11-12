"""Static OOP architecture checks that do not require a database driver."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestOOPBlueprint(unittest.TestCase):
    def test_expected_architecture_modules_exist(self):
        expected = [
            "core/db_manager.py", "config/database.py",
            "managers/employee_manager.py", "managers/project_manager.py",
            "managers/review_manager.py", "managers/analytics_manager.py",
            "managers/warehouse_manager.py", "models/employee.py",
            "models/project.py", "models/review.py", "models/assignment.py",
            "pages/1_Employees.py", "pages/2_Projects.py",
            "pages/3_Reviews.py", "pages/4_Analytics_Dashboard.py",
        ]
        for relative in expected:
            with self.subTest(module=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_database_connection_uses_singleton_pattern(self):
        tree = ast.parse((ROOT / "core/db_manager.py").read_text())
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        self.assertIn("DatabaseConnection", classes)
        methods = {n.name for n in classes["DatabaseConnection"].body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertIn("__new__", methods)
        self.assertIn("initialize_pool", methods)

    def test_employee_manager_has_crud_and_atomic_employment_change(self):
        tree = ast.parse((ROOT / "managers/employee_manager.py").read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "EmployeeManager")
        methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
        for name in ("create", "get_by_id", "get_all", "update", "delete", "update_employment"):
            self.assertIn(name, methods)
        source = ast.get_source_segment((ROOT / "managers/employee_manager.py").read_text(), methods["update_employment"])
        self.assertIn("_sync_employee_dimension", source)

if __name__ == "__main__":
    unittest.main()
