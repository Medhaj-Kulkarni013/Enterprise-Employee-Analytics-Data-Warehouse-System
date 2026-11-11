# Comprehensive Test Plan — Enterprise Employee Analytics & Data Warehouse

This is the end-to-end verification checklist for the mini-project brief. It covers the five phases and the named evaluation criteria: 100K+ synthesis, normalized OLTP, star-schema OLAP, surrogate keys, SCD Type 2 history, SQL ETL with CTEs/window functions/procedures, OOP and error handling, Streamlit data entry, warehouse-backed analytics, GitHub workflow and cloud deployment.

**Test environment:** use a disposable development database with the same MySQL major/minor version as the target. Never run destructive, data-mutation, or load tests against production. Capture screenshots, SQL result grids, logs and test data IDs as evidence.

**Status convention:** `Not Run` → `Pass` / `Fail` / `Blocked`. A test is not passed merely because the page opens; verify the underlying database state and expected values.

## A. Test setup and test data

| Item | Requirement |
|---|---|
| DB engine | MySQL 8.0.16+ |
| Schemas | `stg`, `oltp`, `dw` |
| Application | Python environment from `requirements.txt`; Streamlit launched from repository root |
| Dataset | Approved IBM HR source dataset plus synthesized data |
| Scale target | At least 100,000 synthesized employee records as specified by brief |
| Test records | Dedicated employee(s), department(s), project(s), assignment(s), review(s) with unique identifiers |
| SCD2 history | At least one employee with Hire + two later tracked changes at distinct effective dates |
| Multi-year analytics | Reviews spanning at least two calendar years and more than one department |
| Cleanup | Record all test IDs; delete only test data and in FK-safe order, or reset the disposable database |

Recommended fixture employees:
- `EMP-SCD2-001`: Hire, then department change, then salary/role change.
- `EMP-SCD2-002`: no changes; control employee.
- `EMP-ATTR-001`: use a controlled attrition flag/termination state if the schema supports it.
- `EMP-CRUD-001`: employee CRUD lifecycle.
Use valid existing department and job-role IDs. Use review dates that fall inside the intended employee version intervals.

## B. Phase 1 — data sourcing, synthesis, staging and modelling

| ID | Priority | Test case / procedure | Expected result / evidence |
|---|---|---|---|
| P1-01 | P0 | Confirm the approved IBM HR source file is present and readable by the pipeline. | Source loads without malformed columns; source row count and column list recorded. |
| P1-02 | P0 | Run the synthesis pipeline with a fixed/random seed if supported. | Reproducible output for the same seed; no unexplained exceptions. |
| P1-03 | P0 | Count synthesized employees. | At least 100,000 employee records are generated, satisfying the brief's scale target. |
| P1-04 | P1 | Validate uniqueness of employee business identifiers, employee codes and emails. | No duplicate values in fields intended to be unique. |
| P1-05 | P1 | Validate generated categorical values (department, role, education, travel, overtime, attrition). | Values belong to approved domain sets; no invalid category labels. |
| P1-06 | P1 | Validate numeric/date ranges (salary, ratings, satisfaction, hire dates, termination dates). | Values are within schema/business constraints; dates are logically ordered. |
| P1-07 | P0 | Inspect generated historical events for employees selected for history. | Events include a Hire baseline and at least one tracked change; effective dates are ordered and plausible. |
| P1-08 | P0 | Load synthesized output into `stg`. | Load completes; staging count matches the source output count; rejected rows are reported. |
| P1-09 | P1 | Run staging validation / preprocessing on intentionally malformed rows in a disposable fixture. | Invalid rows are rejected or quarantined with a useful reason; valid rows continue. |
| P1-10 | P1 | Check duplicate and null handling in staging. | Required fields are not silently null; duplicate business keys are detected and handled according to the pipeline's documented rule. |
| P1-11 | P1 | Inspect editable OLTP ER diagram source (`.drawio`). | Diagram opens and represents the normalized entities and relationships. |
| P1-12 | P1 | Inspect editable dimensional model diagram if included. | Diagram opens and shows fact/dimension relationships and grain. |

## C. Phase 1/2 — OLTP schema and data integrity

| ID | Priority | Test case / procedure | Expected result / evidence |
|---|---|---|---|
| DB-01 | P0 | Inspect `stg`, `oltp`, `dw` schemas and required tables. | Schemas and expected tables exist on the intended server. |
| DB-02 | P0 | Inspect OLTP entities: employee, department, project, review, assignment, plus supporting job_role/change_log. | Required tables, primary keys and columns exist. |
| DB-03 | P0 | Inspect foreign keys for employee→department/job_role, assignment→employee/project, review→employee. | Referential constraints are present and point to the correct parent keys. |
| DB-04 | P1 | Attempt an employee insert with a nonexistent department/job role. | FK violation is raised; no orphan employee row is created. |
| DB-05 | P1 | Attempt duplicate employee code/email where uniqueness is required. | Duplicate is rejected cleanly and UI displays a useful message. |
| DB-06 | P1 | Insert a valid employee and read it back. | Stored values match submitted values; generated key is returned/usable. |
| DB-07 | P1 | Verify review and assignment rows reference existing employees/projects. | No orphan rows. |
| DB-08 | P1 | Check indexes on frequently searched/joined keys. | Primary, unique and FK-supporting indexes exist; query plan is reasonable for key lookups. |
| DB-09 | P1 | Compare staging, OLTP and warehouse business-key counts after load. | Counts reconcile under documented transformation rules; any expected filtering is explained. |
| DB-10 | P1 | Check transaction rollback on a deliberately failed multi-step OLTP operation. | Partial changes are rolled back; no half-created entity or audit record remains. |

## D. Phase 1/2 — OLAP star schema and surrogate keys

| ID | Priority | Test case / procedure | Expected result / evidence |
|---|---|---|---|
| DW-01 | P0 | Inspect fact table `dw.Fact_PerformanceReviews` and dimensions `Dim_Employee`, `Dim_Project`, `Dim_Date`, `Dim_Department`. | All five required star-schema tables exist. |
| DW-02 | P0 | Verify each dimension has a surrogate primary key. | Dimension PKs are generated surrogate keys; natural/business keys remain separately identifiable. |
| DW-03 | P0 | Verify fact grain. | Exactly one fact per source performance review; `review_id` is unique in the fact table. |
| DW-04 | P0 | Inspect fact foreign keys to employee, department, project and date dimensions. | All fact references resolve; no orphan dimension keys. |
| DW-05 | P1 | Verify unknown/not-project-related member. | A fact with no project maps to the documented Unknown project member rather than an invalid/null FK. |
| DW-06 | P1 | Check Dim_Date coverage for all review dates. | Every review date maps to one date key; no missing date dimension rows. |
| DW-07 | P1 | Compare dimension natural-key coverage with OLTP. | Every expected department/project/employee is represented, allowing for documented unknown members and SCD2 multiple versions. |
| DW-08 | P1 | Inspect indexes and query plans for fact-to-dimension joins. | Joins use keys/indexes and are viable for the expected dataset size. |

## E. Phase 2 — SQL ETL, CTEs, window functions and reconciliation

| ID | Priority | Test case / procedure | Expected result / evidence |
|---|---|---|---|
| ETL-01 | P0 | Execute `CALL dw.sp_run_full_etl();` on a populated disposable DB. | Procedure completes; ETL log records successful steps; validation succeeds. |
| ETL-02 | P0 | Execute full ETL a second time without source changes. | Idempotent result: no duplicate dimension versions or fact rows; counts remain stable. |
| ETL-03 | P0 | Compare fact row count to `oltp.review` row count. | Counts match for supported source rows. |
| ETL-04 | P0 | Compare review IDs in OLTP to fact review IDs in DW. | No missing source reviews in the fact table. |
| ETL-05 | P1 | Compare key fact measures (ratings, satisfaction, salary hike, income) between OLTP and DW. | Aggregates reconcile; any transformation/rounding is documented. |
| ETL-06 | P1 | Correct a source review measure, rerun ETL. | Existing fact row is refreshed; no duplicate fact is created. |
| ETL-07 | P1 | Add a new valid source review, rerun ETL. | One corresponding fact row is inserted. |
| ETL-08 | P1 | Test source review deletion policy in a disposable DB. | Behaviour matches documented policy: deletions are not silently cascaded; discrepancy is surfaced/governed. |
| ETL-09 | P0 | Inspect stored procedure source for CTE usage and window functions. | Required SQL techniques are genuinely used in transformation/ranking logic, not merely mentioned in comments. |
| ETL-10 | P1 | Force a controlled ETL failure in a disposable DB (e.g. invalid FK/source row). | Transaction rolls back affected ETL work; error is logged and propagated. |
| ETL-11 | P1 | Review `dw.etl_run_log` after successful and failed runs. | Run ID, step, status, row counts/message and timestamp are useful and traceable. |
| ETL-12 | P1 | Compare row counts and grouped totals across staging→OLTP→DW. | Reconciliation report explains all expected differences; no unexplained loss or multiplication. |

## F. Phase 1/2/4 — SCD Type 2 correctness (critical)

Run these on a disposable database or dedicated test employee only. Use effective dates strictly later than the current version start date.

| ID | Priority | Test case / procedure | Expected result / evidence |
|---|---|---|---|
| SCD-01 | P0 | Load initial employee history containing a Hire event. | One initial dimension version is created with correct tracked attributes and start date. |
| SCD-02 | P0 | Change department through `sp_scd2_update_employee(employee_id, effective_date)`. | Old version ends on effective date minus one day; new version starts on effective date and is current. |
| SCD-03 | P0 | Change job role/level only. | A new version is created when tracked values change; old version closes correctly. |
| SCD-04 | P0 | Change salary only. | Salary change creates a new version if salary is in the tracked hash; other attributes are preserved. |
| SCD-05 | P0 | Submit same tracked values again. | No new version is created for a no-op update. |
| SCD-06 | P0 | Run incremental SCD2 twice for the same effective event. | Second call is idempotent; no duplicate version. |
| SCD-07 | P0 | Run batch SCD2 after incremental SCD2 (and vice versa). | Both paths agree; no duplicate or conflicting current version is introduced. |
| SCD-08 | P0 | Check every employee's current version count. | Exactly one row with `is_current=1` per employee. |
| SCD-09 | P0 | Check interval continuity using `LEAD(start_date)`. | For adjacent versions, next start date equals prior end date + 1 day; no gaps/overlaps. |
| SCD-10 | P1 | Review a date before a change and a date after a change. | Fact lookup associates review with the employee version valid on the review date. |
| SCD-11 | P1 | Attempt an effective date equal to or earlier than current version start date. | Procedure rejects the invalid temporal change without leaving partial OLTP/DW state. |
| SCD-12 | P1 | Attempt update for nonexistent employee. | Clear error; no dimension or change-log mutation. |
| SCD-13 | P0 | Change department through Streamlit employee UI. | OLTP update, change-log event and SCD2 version change succeed atomically; if any step fails, all roll back. |
| SCD-14 | P1 | Change department while keeping role, level and salary unchanged. | UI prepopulates existing values; unedited tracked fields are not overwritten by defaults. |
| SCD-15 | P1 | Verify the built-in SCD2 self-test result grid. | Every required test is PASS and overall verdict is PASS; preserve output as evidence. |

## G. Phase 3 — Python OOP, Singleton, entities, DAL and error handling

| ID | Priority | Test case / procedure | Expected result / evidence |
|---|---|---|---|
| OOP-01 | P0 | Inspect `DatabaseConnection` Singleton by constructing it multiple times. | Same instance is returned; connection pool is initialized once safely. |
| OOP-02 | P1 | Test connection acquisition and release repeatedly. | Connections are returned to pool; no leaks or exhausted pool under normal use. |
| OOP-03 | P1 | Simulate unavailable DB / invalid credentials. | Controlled exception and actionable UI/log message; app does not expose secrets or raw stack trace to end users. |
| OOP-04 | P1 | Inspect Employee, Project and Review entity constructors/attributes/behaviours. | Entity classes encapsulate the relevant data and validation/behaviour as designed. |
| OOP-05 | P0 | Inspect manager inheritance/composition and responsibilities. | Employee, project, review, assignment, analytics and warehouse operations remain separated in DAL/manager classes. |
| OOP-06 | P0 | Exercise EmployeeManager create/read/update/delete in disposable DB. | CRUD methods work and return consistent results; invalid operations fail safely. |
| OOP-07 | P1 | Exercise ProjectManager create/read/update/delete. | Project CRUD works; referenced project data remains consistent. |
| OOP-08 | P1 | Exercise AssignmentManager create/read/update/delete. | Assignment operations enforce valid employee/project references and expected assignment rules. |
| OOP-09 | P1 | Exercise ReviewManager create/read/update/delete (if exposed by current manager). | Review operations work; constraints and fact-refresh expectations are respected. |
| OOP-10 | P1 | Trigger duplicate key, FK and validation exceptions through managers. | Exceptions are caught/translated consistently; transaction rollback occurs. |
| OOP-11 | P1 | Review parameterized SQL usage. | User-provided values are bound parameters; no string-concatenated SQL injection path. |
| OOP-12 | P1 | Check transaction boundaries for multi-table writes. | Related writes commit together or roll back together. |

## H. Phase 4 — Streamlit data entry and interaction

| ID | Priority | Test case / procedure | Expected result / evidence |
|---|---|---|---|
| UI-01 | P0 | Start Streamlit and navigate every sidebar page. | All pages render without import/runtime errors. |
| UI-02 | P0 | Employee onboarding with valid required fields. | Success message; employee is persisted in OLTP and appears in employee listing. |
| UI-03 | P1 | Submit employee form with missing/invalid required fields. | Validation prevents insert; user sees a clear message. |
| UI-04 | P1 | Submit duplicate employee email/code. | Duplicate rejected gracefully; no duplicate row. |
| UI-05 | P0 | Change employee department through UI with valid effective date. | SCD2 change is visible in DW and audit/change log. |
| UI-06 | P1 | Change one tracked field and leave other tracked fields unchanged. | Existing values remain intact; only intended change is applied. |
| UI-07 | P0 | Create a project through Projects page. | Project saved in OLTP and appears in project list/dropdowns. |
| UI-08 | P0 | Create assignment linking valid employee and project. | Assignment persisted and visible; invalid employee/project is rejected. |
| UI-09 | P1 | Attempt duplicate/invalid assignment if schema rules prohibit it. | Database/UI prevents invalid duplicate or reports documented rule. |
| UI-10 | P0 | Submit valid performance review. | Review saved with correct employee/date/measures and appears in OLTP. |
| UI-11 | P1 | Submit review with invalid score/date/employee. | Validation/constraint error shown; no partial review saved. |
| UI-12 | P1 | Refresh page/reopen app after writes. | Persisted data remains; UI does not rely only on session state. |
| UI-13 | P1 | Test page behaviour with empty tables and database unavailable. | Empty-state/error UX is understandable and does not crash the whole app. |
| UI-14 | P1 | Test form resubmission/rerun behaviour. | One click does not accidentally create duplicate records. |

## I. Phase 4 — warehouse sync and analytics dashboard

| ID | Priority | Test case / procedure | Expected result / evidence |
|---|---|---|---|
| ANA-01 | P0 | Open Analytics Dashboard after successful ETL. | Dashboard reads from DW star schema/views, not OLTP-only ad hoc queries. |
| ANA-02 | P0 | Verify year-over-year trend view/chart with at least two years of reviews. | Year, department, average rating, review count and previous-year/change values are correct. |
| ANA-03 | P1 | Independently calculate a small YoY fixture in SQL/Python and compare chart values. | Dashboard values match independently calculated values. |
| ANA-04 | P0 | Verify top performers by department/year. | Employees are ranked within the correct year and department using `DENSE_RANK()`. |
| ANA-05 | P1 | Create a tie in performance score. | Tied employees receive the same dense rank; next rank has no gap. |
| ANA-06 | P1 | Filter/inspect more than one department and year. | Results remain correctly partitioned; no cross-department/year rank contamination. |
| ANA-07 | P0 | Verify attrition-risk view/chart. | Headcount, leavers, attrition rate, risk band and ranking agree with the underlying current employee population. |
| ANA-08 | P1 | Check minimum group-size filtering. | Small groups are excluded as specified by the view; this is explained in dashboard UX/docs. |
| ANA-09 | P1 | Check dashboard empty/one-year data case. | No crash; previous-year fields are null/appropriately displayed when no prior year exists. |
| ANA-10 | P0 | Run Warehouse Sync page full ETL action. | Calls compatibility procedure, shows success/failure and refreshes status/counts. |
| ANA-11 | P1 | Run sync twice from UI. | No duplicate facts/versions; repeat operation is safe. |
| ANA-12 | P1 | Trigger a failed sync in disposable DB. | Error is visible and logged; partial warehouse transaction is rolled back. |
| ANA-13 | P1 | Compare dashboard aggregates to direct view queries. | Charts/tables display the same values as SQL views. |
| ANA-14 | P1 | Check project bottleneck analysis only if implemented. | If not implemented, confirm the brief's alternative attrition-risk analysis is delivered; do not claim both. |

## J. Scale, performance, reliability and security

| ID | Priority | Test case / procedure | Expected result / evidence |
|---|---|---|---|
| PERF-01 | P0 | Run synthesis to 100K+ rows and record duration/memory. | Completes without memory exhaustion; output count meets brief. |
| PERF-02 | P0 | Load 100K+ employees and associated reviews into staging/OLTP/DW. | Load completes; counts reconcile and no silent truncation occurs. |
| PERF-03 | P1 | Record full ETL duration and row counts at target scale. | ETL completes within a documented acceptable time; no table lock/deadlock failures. |
| PERF-04 | P1 | Run key dashboard queries with `EXPLAIN ANALYZE` where supported. | Plans use useful indexes; no accidental full scans beyond expected aggregation workloads. |
| PERF-05 | P1 | Repeat dashboard page refreshes. | No unbounded connection growth or repeated duplicate writes. |
| SEC-01 | P0 | Inspect repository and ZIP for `.env`, passwords, private CA file and production data. | No secrets/private certs included; `.env.example` only. |
| SEC-02 | P1 | Attempt SQL injection-like text in free-text fields. | Inputs are parameterized and treated as data. |
| SEC-03 | P1 | Verify database account privileges. | App account has only required schema/table/procedure permissions; avoid root/admin account. |
| SEC-04 | P1 | Check logs and Streamlit error messages. | Passwords, tokens, certificate contents and sensitive connection strings are not printed. |
| REL-01 | P1 | Restart Streamlit after database writes. | App reconnects and reads persisted records correctly. |
| REL-02 | P1 | Interrupt DB connection during a read/write. | Graceful error; no corrupt/partial multi-step transaction. |

## K. Phase 5 — GitHub and Streamlit Community Cloud

| ID | Priority | Test case / procedure | Expected result / evidence |
|---|---|---|---|
| DEV-01 | P0 | Inspect GitHub repository contents. | Source, SQL, tests, diagrams and documentation are committed; no secrets or generated private data. |
| DEV-02 | P0 | Confirm work was developed on feature branches and merged through Pull Requests. | PR history shows feature branches and review/merge into main as requested by brief. |
| DEV-03 | P1 | Clone repository into a clean directory and follow Quickstart. | Setup succeeds without relying on untracked local files. |
| CLOUD-01 | P0 | Deploy the Streamlit app to Streamlit Community Cloud. | Public URL loads the app successfully. |
| CLOUD-02 | P0 | Configure secrets/connection variables in deployment settings. | Cloud app connects securely without committing `.env` or CA credentials to GitHub. |
| CLOUD-03 | P1 | Open all pages on deployed app. | All pages load and DB-backed interactions work over the cloud deployment. |
| CLOUD-04 | P1 | Test a read and a controlled write from deployed app. | Cloud app persists data in intended MySQL instance; no local-only path assumptions. |
| CLOUD-05 | P1 | Restart/redeploy app. | App starts cleanly and retains database data. |

## L. Final acceptance gate

Do not mark the project fully verified until all P0 cases pass and all P1 failures are either fixed or explicitly accepted with rationale.

| Gate | Acceptance condition | Evidence to retain |
|---|---|---|
| Data synthesis | 100K+ employee-scale dataset and engineered history | Pipeline log, output counts, sample history rows |
| OLTP | Normalized tables and relationships work | DDL inspection, FK/uniqueness tests, ER diagram |
| OLAP | Required star schema and surrogate keys exist | DDL inspection, dimensional diagram |
| SCD2 | Exactly one current row per employee; no gaps/overlaps; effective-dated updates work | Self-test grid, SQL validation queries, before/after rows |
| ETL | Full load, idempotency, fact reconciliation and error rollback work | ETL logs, row-count reconciliation, repeat-run results |
| OOP | Singleton, entities, managers, CRUD and exception handling work | Unit/integration test output and code review |
| UI | Employee, project, assignment, review workflows work | Screenshots and matching OLTP rows |
| Analytics | YoY, department/year DENSE_RANK and attrition risk are correct | Independent SQL calculations and dashboard screenshots |
| Scale | 100K+ load and dashboard queries remain usable | Timings, row counts, query plans |
| GitHub/cloud | Feature-branch PR workflow and Streamlit Community Cloud deployment | PR links, repository URL, deployed URL |

## M. Test execution log

Copy this table into the project issue tracker or add columns for tester/date/build.

| Test ID range | Status | Tester | Date | Evidence / defect |
|---|---|---|---|---|
| P1-01 to P1-12 | Not Run | | | |
| DB-01 to DB-10 | Not Run | | | |
| DW-01 to DW-08 | Not Run | | | |
| ETL-01 to ETL-12 | Not Run | | | |
| SCD-01 to SCD-15 | Not Run | | | |
| OOP-01 to OOP-12 | Not Run | | | |
| UI-01 to UI-14 | Not Run | | | |
| ANA-01 to ANA-14 | Not Run | | | |
| PERF-01 to REL-02 | Not Run | | | |
| DEV-01 to CLOUD-05 | Not Run | | | |

## Scope notes and known boundaries

- The brief asks for employee attrition risk **or** project bottleneck analysis. This implementation's selected deliverable is the attrition-risk view/dashboard. Do not represent project bottleneck analysis as delivered unless separately implemented and tested.
- The brief asks for historical SCD2 data. The warehouse can only reproduce history represented in `employee_change_log`; a one-event-per-employee dataset will not magically yield multiple versions.
- The documented fact policy refreshes inserts/updates from source reviews; physical source review deletion is not cascaded because the OLTP model has no soft-delete/tombstone contract.
- Streamlit Community Cloud deployment and live Aiven/MySQL integration must be verified in the target account/environment; static local tests cannot prove those deployment paths.
