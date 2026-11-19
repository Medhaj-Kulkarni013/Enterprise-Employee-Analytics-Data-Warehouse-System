"""Unit tests for router-enforced RBAC in ui/auth.py."""

import unittest
from ui.auth import AuthService


class TestRBAC(unittest.TestCase):
    def test_authentication_valid_and_invalid(self):
        arch = AuthService.authenticate("architect", "arch123")
        self.assertEqual(arch["role"], "Data Architect")
        self.assertIsNone(AuthService.authenticate("architect", "wrong"))

    def test_role_page_permissions(self):
        self.assertTrue(AuthService.is_authorized("Data Architect", "Warehouse sync"))
        self.assertTrue(AuthService.is_authorized("HR Operations", "Employees"))
        self.assertFalse(AuthService.is_authorized("HR Operations", "Warehouse sync"))
        self.assertTrue(AuthService.is_authorized("Executive", "Analytics dashboard"))
        self.assertFalse(AuthService.is_authorized("Executive", "Employees"))


if __name__ == "__main__":
    unittest.main()