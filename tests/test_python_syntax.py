"""Compile every Python source file without importing optional runtime dependencies."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestPythonSyntax(unittest.TestCase):
    def test_all_python_files_compile(self):
        files = list(ROOT.rglob("*.py"))
        self.assertGreater(len(files), 10)
        for path in files:
            with self.subTest(path=str(path.relative_to(ROOT))):
                compile(path.read_text(encoding="utf-8"), str(path), "exec")

if __name__ == "__main__":
    unittest.main()
