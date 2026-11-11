# Database and application test report

## Scope

This handover consolidates the teammate's Streamlit/OOP repository with the user's reference OLAP/SCD2 implementation. The original application layers and entity/manager organization are retained. The warehouse SQL is in `sql/03_olap_install.sql`; a separate explicitly destructive rebuild is in `sql/03_olap_destructive_rebuild.sql`.

## Executed in the handover build environment

| Check | Result | Notes |
|---|---|---|
| Python compile check | PASS | `python -m compileall -q .` |
| Unit/contract tests | PASS | 11 tests in `tests/`; static OOP structure, Python syntax, SQL contract and deployment safety |
| SQL install safety check | PASS | Install script contains no `DROP SCHEMA`; destructive rebuild is isolated |
| SCD2 SQL contract | PASS | Batch version closure and incremental close/insert patterns are present |
| Analytics SQL contract | PASS | YoY, DENSE_RANK top-performer and attrition-risk views plus compatibility procedures present |
| Fact refresh contract | PASS | Existing review fact rows are refreshed from corrected OLTP review values before missing facts are inserted |

## Not executed / requires user environment

- Live MySQL execution of stored procedures, views, transaction handlers, and the built-in SCD2 self-test.
- Aiven SSL connection and Streamlit end-to-end test.
- Runtime CRUD and UI tests against a populated database.

The build container does not have `mysql-connector-python`, and outbound package installation is unavailable. No live database credentials or private CA certificate were supplied as an approved test connection. Therefore this report does **not** claim live MySQL/Aiven integration has passed.

## Required final verification on a disposable MySQL 8.0.16+ database

1. Load the staging/OLTP schema and test seed data. Ensure every employee has a `Hire` row in `oltp.employee_change_log` on their hire date.
2. Run `sql/03_olap_install.sql` in MySQL Workbench or the MySQL client.
3. Confirm the built-in SCD2 self-test and final acceptance result grid both report `PASS` for required checks. Review any `INFO` rows separately.
4. Run `CALL dw.sp_run_full_etl();` twice and verify counts remain stable.
5. Change one employee's department in the app using an effective date later than their current SCD2 `start_date`. Confirm the previous row closes on effective date minus one day, the new row becomes current, and exactly one current row remains.
6. Correct one OLTP review and rerun ETL; confirm the corresponding fact row is refreshed rather than duplicated.
7. Test onboarding, projects/assignments, review creation, dashboard, and warehouse sync.

## Important data caveats

- Fact rows are updated when source reviews are corrected, and missing source reviews are inserted. Source review deletions are not cascaded because the OLTP schema has no soft-delete/tombstone contract.
- Historical SCD2 performance is only as complete as `employee_change_log`. If the source data contains only one hire event per employee, the dimension will correctly have one version per employee until history is generated/loaded.
- Project and assignment insights depend on OLTP project/assignment data being populated.


## Full project acceptance coverage

The detailed phase-by-phase manual and integration test catalogue is maintained in `docs/TEST_CASES.md`. It maps the project brief's synthesis, normalized OLTP, star schema, SCD2, SQL ETL, OOP, Streamlit, analytics, scale, GitHub and Streamlit Community Cloud requirements to test IDs and expected evidence.

The quickstart is `docs/QUICKSTART_MACOS.md`. Follow it before executing the test catalogue. The live database, Aiven TLS, full 100K load, UI end-to-end and cloud deployment cases remain environment-dependent and must be marked `Pass` only after execution in the target environment.
