"""Execute the full test suite and generate formatted Markdown and HTML/PDF reports."""
import html
import io
import os
import sys
import time
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEST_CATALOG = {
    # 1. OOP Architecture & Static Syntax
    "test_expected_architecture_modules_exist": (
        "OOP Architecture",
        "Verifies all 4 architectural layers (Core, Entity, Manager, Pipeline) and Streamlit pages exist.",
        "Confirms strict modular separation of concerns with no monolithic scripts.",
    ),
    "test_database_connection_uses_singleton_pattern": (
        "OOP Architecture",
        "Inspects AST of DatabaseConnection to verify __new__ and initialize_pool definitions.",
        "Proves connection pooling follows the Singleton design pattern at the structural level.",
    ),
    "test_employee_manager_has_crud_and_atomic_employment_change": (
        "OOP Architecture",
        "Verifies EmployeeManager implements full CRUD and invokes _sync_employee_dimension.",
        "Ensures employment updates are structurally bound to SCD Type 2 warehouse sync.",
    ),
    "test_all_python_files_compile": (
        "Static Quality",
        "Compiles every .py source file across the repository to bytecode.",
        "Guarantees zero syntax or indentation errors anywhere in the codebase.",
    ),
    # 2. Domain Entities & Encapsulation
    "test_abstract_base_entity_cannot_be_instantiated": (
        "Domain Entities",
        "Attempts direct instantiation of abstract BaseEntity.",
        "Enforces abstraction: subclasses must implement validate() and to_dict().",
    ),
    "test_employee_encapsulation_and_validation": (
        "Domain Entities",
        "Tests @property setters on Employee for malformed emails, negative income, invalid job level, and future hire dates.",
        "Prevents corrupt domain state from entering the application before any DB query runs.",
    ),
    "test_employee_promote_transfer_and_tenure": (
        "Domain Entities",
        "Exercises promote(), transfer(), and anniversary-aware tenure_years() calculations.",
        "Validates business rules (promotions require strictly higher job levels; tenure handles leap/anniversary dates).",
    ),
    "test_employee_from_row_and_to_dict_roundtrip": (
        "Domain Entities",
        "Serializes an Employee via to_dict() and reconstructs it via Factory Method from_row().",
        "Guarantees lossless mapping between MySQL dictionary rows and Python domain objects.",
    ),
    "test_project_domain_methods_and_date_validation": (
        "Domain Entities",
        "Verifies Project duration_days(), is_active(), and rejection of end_date < start_date.",
        "Ensures project lifecycle tracking enforces chronological integrity.",
    ),
    "test_review_satisfaction_high_performer_and_self_review_block": (
        "Domain Entities",
        "Checks composite satisfaction averaging, high-performer threshold (>=3), and blocks employee_id == reviewer_id.",
        "Enforces HR review governance rules directly inside the Review entity.",
    ),
    "test_assignment_allocation_bounds": (
        "Domain Entities",
        "Validates project allocation percentages remain within 1%–100%.",
        "Prevents invalid over-allocation (>100%) or zero-allocation records.",
    ),
    # 3. Core Singleton & DAL Managers (Monkey-Patched)
    "test_singleton_identity_and_inheritance_hierarchy": (
        "Core & DAL (Mocked)",
        "Instantiates DatabaseConnection and EmployeeManager multiple times and checks inheritance.",
        "Confirms per-class Singleton reuse and proper BaseManager -> CrudManager -> AppError hierarchy.",
    ),
    "test_abstract_crud_manager_cannot_be_instantiated": (
        "Core & DAL (Mocked)",
        "Attempts direct instantiation of abstract CrudManager.",
        "Enforces uniform CRUD contract across all data access managers.",
    ),
    "test_transaction_commits_on_success_and_rolls_back_on_error": (
        "Core & DAL (Mocked)",
        "Monkey-patches DB cursor to verify commit() on clean exit and rollback() on ValidationError.",
        "Guarantees ACID atomicity across multi-statement write operations.",
    ),
    "test_employee_manager_get_by_id_and_not_found": (
        "Core & DAL (Mocked)",
        "Simulates missing DB row and verifies NotFoundError plus cursor/connection cleanup.",
        "Prevents connection pool leaks and translates missing records into clean domain exceptions.",
    ),
    "test_employee_manager_atomic_update_employment_triggers_scd2": (
        "Core & DAL (Mocked)",
        "Monkey-patches cursor during update_employment() to verify dw.sp_sync_employee_scd2 call and commit.",
        "Proves OLTP update, audit log insert, and SCD2 dimension update execute in one atomic transaction.",
    ),
    "test_employee_manager_rejects_stale_effective_date": (
        "Core & DAL (Mocked)",
        "Submits an effective_date earlier than the employee's latest change-log event.",
        "Protects SCD Type 2 timeline integrity by blocking out-of-order historical mutations and rolling back.",
    ),
    "test_analytics_manager_validates_department_id": (
        "Core & DAL (Mocked)",
        "Passes negative/zero department IDs to AnalyticsManager methods.",
        "Blocks invalid filter parameters before hitting OLAP warehouse views.",
    ),
    # 4. ETL Synthesis & History Pipeline
    "test_abstract_pipeline_step_cannot_be_instantiated": (
        "ETL Pipeline",
        "Attempts direct instantiation of abstract PipelineStep.",
        "Enforces Template Method pattern (validate_input -> execute -> validate_output).",
    ),
    "test_end_to_end_preprocess_synthesize_and_history_generation": (
        "ETL Pipeline",
        "Runs a 35-column IBM HR fixture through Preprocessor -> Synthesizer -> HistoryGenerator.",
        "Verifies schema cleaning, unique ID/email generation, Level-5 manager hierarchy, and non-duplicate SCD2 history.",
    ),
    # 5. SQL Warehouse & SCD2 Contract
    "test_install_script_does_not_drop_warehouse_schema": (
        "SQL Warehouse Contract",
        "Scans sql/03_olap_install.sql to verify absence of DROP SCHEMA statements.",
        "Ensures routine warehouse installation is non-destructive to existing DW data.",
    ),
    "test_reference_star_schema_and_scd2_columns_exist": (
        "SQL Warehouse Contract",
        "Verifies Fact_PerformanceReviews, 4 Dimensions, and SCD2 columns (start_date, end_date, is_current).",
        "Confirms full Kimball Star Schema compliance with project brief specifications.",
    ),
    "test_batch_scd2_closes_superseded_versions": (
        "SQL Warehouse Contract",
        "Checks batch ETL SQL for LEAD(l.effective_date) window function closing prior versions.",
        "Verifies gap-free, overlap-free SCD Type 2 interval closure during batch warehouse loads.",
    ),
    "test_incremental_scd2_closes_then_inserts": (
        "SQL Warehouse Contract",
        "Inspects dw.sp_scd2_update_employee for DATE_SUB(p_effective_date, INTERVAL 1 DAY) closure + insert.",
        "Confirms real-time incremental SCD Type 2 versioning works identically to batch ETL.",
    ),
    "test_fact_etl_refreshes_existing_reviews": (
        "SQL Warehouse Contract",
        "Verifies fact ETL updates modified OLTP reviews before inserting new ones.",
        "Ensures idempotent ETL reruns propagate score corrections without duplicating fact rows.",
    ),
    "test_required_analytics_views_and_compatibility_procedures_exist": (
        "SQL Warehouse Contract",
        "Checks for vw_yoy_performance, vw_top_performers_by_dept (DENSE_RANK), vw_attrition_risk, and wrappers.",
        "Confirms all OLAP analytical views required by the Streamlit dashboard are present.",
    ),
    "test_destructive_rebuild_is_separate": (
        "SQL Warehouse Contract",
        "Verifies DROP SCHEMA IF EXISTS dw is isolated inside sql/03_olap_destructive_rebuild.sql.",
        "Protects production/staging data by isolating destructive resets into a dedicated script.",
    ),
    # 6. Live Database Integration
    "test_onboard_and_scd2_department_transfer_end_to_end": (
        "Live DB Integration",
        "Creates an employee in MySQL, executes a department transfer, verifies 2 SCD2 rows in dw.Dim_Employee, and cleans up.",
        "End-to-end proof of Python -> MySQL OLTP -> Stored Procedure -> Star Schema SCD2 synchronization.",
    ),
}


class DetailedResult(unittest.TextTestResult):
    """Collect per-test timing, status, and messages."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []
        self._started_at = 0.0

    def startTest(self, test):
        self._started_at = time.perf_counter()
        super().startTest(test)

    def _record(self, test, status, detail=""):
        elapsed_ms = (time.perf_counter() - self._started_at) * 1000.0
        method_name = test.id().split(".")[-1]
        self.records.append(
            {
                "id": f"TC-{len(self.records) + 1:02d}",
                "method": method_name,
                "suite": test.__class__.__name__,
                "status": status,
                "duration_ms": elapsed_ms,
                "detail": detail,
            }
        )

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "PASS")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "SKIPPED", reason)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "FAIL", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "ERROR", self._exc_info_to_string(err, test))


def build_reports():
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"))

    raw_stream = io.StringIO()
    runner = unittest.TextTestRunner(
        stream=raw_stream,
        verbosity=2,
        resultclass=DetailedResult,
    )

    t0 = time.perf_counter()
    result = runner.run(suite)
    total_sec = time.perf_counter() - t0

    total = result.testsRun
    skipped = len(result.skipped)
    failed = len(result.failures) + len(result.errors)
    passed = total - skipped - failed
    verdict = "PASS" if failed == 0 else "FAIL"
    run_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    live_mode = "Enabled (Live MySQL)" if os.getenv("RUN_LIVE_DB_TESTS") == "1" else "Offline Unit/Mock Mode"

    enriched = []
    for rec in result.records:
        layer, purpose, inference = TEST_CATALOG.get(
            rec["method"],
            ("General", "Automated verification check.", "Confirms expected component behavior."),
        )
        if rec["status"] == "SKIPPED":
            inference = f"Skipped in offline mode ({rec['detail']}). Run with RUN_LIVE_DB_TESTS=1 against live MySQL."
        elif rec["status"] in ("FAIL", "ERROR"):
            inference = f"FAILED — requires investigation: {rec['detail'].splitlines()[-1] if rec['detail'] else ''}"

        enriched.append({**rec, "layer": layer, "purpose": purpose, "inference": inference})

    # 1. Write Markdown Report (docs/UNIT_TEST_REPORT.md)
    md_path = ROOT / "docs" / "UNIT_TEST_REPORT.md"
    md_lines = [
        "# Automated Test & Quality Assurance Report",
        "",
        "## 1. Executive Summary",
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| **Execution Timestamp** | {run_timestamp} |",
        f"| **Execution Mode** | {live_mode} |",
        f"| **Total Test Cases** | {total} |",
        f"| **Passed** | {passed} |",
        f"| **Skipped** | {skipped} |",
        f"| **Failed / Errors** | {failed} |",
        f"| **Total Duration** | {total_sec:.2f}s |",
        f"| **Overall Verdict** | **{verdict}** |",
        "",
        "### Testing Methodology",
        "- **Static & Architectural Verification:** AST inspection and bytecode compilation verify Singleton connection pooling, module boundaries, and non-destructive SQL DDL.",
        "- **Domain Encapsulation Unit Tests:** Validates `@property` setters, boundary constraints, and domain logic across `Employee`, `Project`, `Review`, and `Assignment`.",
        "- **Monkey-Patched DAL Tests (`unittest.mock`):** Intercepts `DatabaseConnection` cursors at runtime to verify transaction commit/rollback behavior and atomic `dw.sp_sync_employee_scd2` execution without requiring an active database.",
        "- **End-to-End Pipeline Tests:** Executes `Preprocessor` -> `Synthesizer` -> `HistoryGenerator` using the Template Method pattern (`PipelineStep.run()`).",
        "",
        "## 2. Detailed Test Traceability & Inference Matrix",
        "",
        "| ID | Layer | Test Case | Purpose | Result / Engineering Inference | Time | Status |",
        "| :--- | :--- | :--- | :--- | :--- | ---: | :---: |",
    ]

    for r in enriched:
        md_lines.append(
            f"| {r['id']} | {r['layer']} | `{r['method']}` | {r['purpose']} | {r['inference']} | {r['duration_ms']:.1f} ms | **{r['status']}** |"
        )

    md_lines.extend([
        "",
        "## 3. Raw Execution Log",
        "",
        "```text",
        raw_stream.getvalue().strip(),
        "```",
        "",
    ])
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    # 2. Write Print-Ready HTML Report (reports/UNIT_TEST_REPORT.html)
    html_path = ROOT / "reports" / "UNIT_TEST_REPORT.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)

    rows_html = []
    for r in enriched:
        badge_cls = "pass" if r["status"] == "PASS" else ("skip" if r["status"] == "SKIPPED" else "fail")
        rows_html.append(
            f"<tr>"
            f"<td><strong>{html.escape(r['id'])}</strong></td>"
            f"<td>{html.escape(r['layer'])}</td>"
            f"<td><code>{html.escape(r['method'])}</code></td>"
            f"<td>{html.escape(r['purpose'])}</td>"
            f"<td>{html.escape(r['inference'])}</td>"
            f"<td style='text-align:right'>{r['duration_ms']:.1f} ms</td>"
            f"<td><span class='badge {badge_cls}'>{html.escape(r['status'])}</span></td>"
            f"</tr>"
        )

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Test & QA Report — Enterprise Employee Analytics & DW</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #1e293b; margin: 32px; line-height: 1.45; }}
  h1 {{ margin-bottom: 4px; color: #0f172a; }}
  .subtitle {{ color: #64748b; margin-bottom: 24px; font-size: 14px; }}
  .cards {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 24px; }}
  .card {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; background: #f8fafc; }}
  .card .label {{ font-size: 12px; text-transform: uppercase; color: #64748b; font-weight: 600; }}
  .card .val {{ font-size: 24px; font-weight: 700; margin-top: 4px; color: #0f172a; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
  th, td {{ border: 1px solid #cbd5e1; padding: 8px 10px; text-align: left; vertical-align: top; }}
  th {{ background: #0f172a; color: #ffffff; font-weight: 600; }}
  tr:nth-child(even) {{ background: #f8fafc; }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11.5px; color: #0369a1; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-weight: 700; font-size: 11px; }}
  .badge.pass {{ background: #dcfce7; color: #166534; }}
  .badge.skip {{ background: #fef9c3; color: #854d0e; }}
  .badge.fail {{ background: #fee2e2; color: #991b1b; }}
  @media print {{ body {{ margin: 12mm; }} th {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }} }}
</style>
</head>
<body>
  <h1>Enterprise Employee Analytics &amp; Data Warehouse — QA Test Report</h1>
  <div class="subtitle">Generated on {html.escape(run_timestamp)} &bull; Mode: {html.escape(live_mode)} &bull; Duration: {total_sec:.2f}s</div>
  <div class="cards">
    <div class="card"><div class="label">Total Tests</div><div class="val">{total}</div></div>
    <div class="card"><div class="label">Passed</div><div class="val" style="color:#166534">{passed}</div></div>
    <div class="card"><div class="label">Skipped</div><div class="val" style="color:#854d0e">{skipped}</div></div>
    <div class="card"><div class="label">Failed</div><div class="val" style="color:#991b1b">{failed}</div></div>
    <div class="card"><div class="label">Verdict</div><div class="val" style="color:#166534">{verdict}</div></div>
  </div>
  <table>
    <thead>
      <tr>
        <th style="width:55px">ID</th>
        <th style="width:130px">Layer</th>
        <th style="width:230px">Test Case</th>
        <th>Purpose</th>
        <th>Result / Engineering Inference</th>
        <th style="width:65px">Time</th>
        <th style="width:70px">Status</th>
      </tr>
    </thead>
    <tbody>
      {"".join(rows_html)}
    </tbody>
  </table>
</body>
</html>
"""
    html_path.write_text(html_doc, encoding="utf-8")

    print(f"Verdict: {verdict} ({passed} passed, {skipped} skipped, {failed} failed in {total_sec:.2f}s)")
    print(f"Markdown report written to : {md_path}")
    print(f"HTML/PDF report written to : {html_path}")


if __name__ == "__main__":
    build_reports()