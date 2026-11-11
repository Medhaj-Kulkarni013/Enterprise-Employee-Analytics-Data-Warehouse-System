"""Warehouse SQL contract checks; live MySQL execution is a separate integration step."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql/03_olap_install.sql").read_text()

class TestWarehouseSQLContract(unittest.TestCase):
    def test_install_script_does_not_drop_warehouse_schema(self):
        self.assertNotRegex(SQL, r"(?im)^\s*DROP\s+SCHEMA")
        self.assertIn("CREATE SCHEMA IF NOT EXISTS dw", SQL)

    def test_reference_star_schema_and_scd2_columns_exist(self):
        for token in ("Dim_Employee", "Dim_Project", "Dim_Date", "Dim_Department", "Fact_PerformanceReviews", "start_date", "end_date", "is_current"):
            self.assertIn(token, SQL)

    def test_batch_scd2_closes_superseded_versions(self):
        self.assertIsNotNone(re.search(r"SET d\.end_date\s*=.*?d\.is_current\s*=", SQL, re.S))
        self.assertIn("LEAD(l.effective_date)", SQL)

    def test_incremental_scd2_closes_then_inserts(self):
        body = SQL[SQL.index("CREATE PROCEDURE dw.sp_scd2_update_employee"):SQL.index("CREATE PROCEDURE dw.sp_run_full_etl") ]
        self.assertIn("SET end_date = DATE_SUB(p_effective_date, INTERVAL 1 DAY), is_current = 0", body)
        self.assertIn("INSERT INTO dw.Dim_Employee", body)

    def test_fact_etl_refreshes_existing_reviews(self):
        self.assertIn("UPDATE dw.Fact_PerformanceReviews f", SQL)
        self.assertIn("WHERE NOT EXISTS (SELECT 1 FROM dw.Fact_PerformanceReviews f WHERE f.review_id = r.review_id)", SQL)

    def test_required_analytics_views_and_compatibility_procedures_exist(self):
        for name in ("vw_yoy_performance", "vw_top_performers_by_dept", "vw_attrition_risk", "sp_load_warehouse", "sp_top_performers"):
            self.assertIn(name, SQL)
        self.assertIn("DENSE_RANK()", SQL)

    def test_destructive_rebuild_is_separate(self):
        rebuild = (ROOT / "sql/03_olap_destructive_rebuild.sql").read_text()
        self.assertRegex(rebuild, r"(?im)^\s*DROP\s+SCHEMA\s+IF\s+EXISTS\s+dw")

if __name__ == "__main__":
    unittest.main()
