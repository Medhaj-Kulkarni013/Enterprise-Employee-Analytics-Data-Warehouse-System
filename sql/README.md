# Database deployment order

Use MySQL 8.0.16 or newer. Back up the target database before deployment.

1. `01_stg_schema.sql` — creates the staging schema/tables.
2. `02_oltp_schema.sql` — reference OLTP DDL. It is a fresh-schema script; do not rerun over existing tables.
3. Load/seed normalized OLTP data and ensure `employee_change_log` contains a Hire event per employee.
4. `03_olap_install.sql` — creates/updates the warehouse objects, runs the full ETL and its built-in checks. It does not drop `dw`, but it is not a general schema migration framework; review DDL changes against an existing warehouse before applying.

If the old teammate `sql/backend_etl.sql` was previously executed, or the existing `dw` schema has a different unknown-project surrogate key/schema, back up `dw` and use `03_olap_destructive_rebuild.sql` once to normalize the derived warehouse to the reference design. It drops only `dw`; OLTP and staging are retained. Never use it as a routine sync.

The application calls `dw.sp_load_warehouse()` (compatibility wrapper for `dw.sp_run_full_etl()`) and `dw.sp_top_performers()` (view-backed compatibility wrapper). The department-change workflow calls `dw.sp_scd2_update_employee()` inside the same transaction as the OLTP update and audit-log insert.

Fact policy: review facts are upsert-refreshed when source reviews are corrected; source review deletions are not cascaded into the warehouse. The project has no soft-delete field on reviews, so deleting source reviews is intentionally treated as unsupported; use a governed correction/retention process instead.
