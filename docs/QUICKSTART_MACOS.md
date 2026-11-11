# Quickstart — macOS

Use a **disposable development database** for first-time setup and destructive tests. MySQL 8.0.16+ is required.

## 1. Prerequisites

- macOS, Python 3.10+ (3.11 recommended), MySQL 8.0.16+, MySQL Workbench or `mysql` CLI.
- Aiven CA certificate if using the hosted database.
- Network access and credentials with permissions on `stg`, `oltp`, and `dw`.

```bash
python3 --version
mysql --version
```

## 2. Extract and install

If you have already extracted the ZIP, `cd` into its root. Otherwise:

```bash
unzip v4c_employee_analytics_handover.zip
cd v4c_employee_analytics_handover
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Configure MySQL

```bash
cp .env.example .env
```

Edit `.env` using the exact variable names in `.env.example` and `config/database.py`.

For Aiven, download the CA certificate from the Aiven console, store it locally (for example `certificates/ca.pem`), and set the certificate path in `.env`. Verify the host, port, database, username and password against the Aiven service details. Do not commit `.env`, passwords, certificates, or production data.

## 4. Prepare the database — choose one path

Read [`../sql/README.md`](../sql/README.md) before running SQL.

### Path A — OLTP is already populated (likely for an existing project DB)

1. Back up the current `dw` schema.
2. Confirm `oltp.employee`, `department`, `job_role`, `employee_change_log`, `review`, `project`, and `assignment` exist.
3. Confirm each employee has a `Hire` event in `oltp.employee_change_log`; historical events are needed for multiple SCD2 versions.
4. Run `sql/03_olap_install.sql` in MySQL Workbench or with the MySQL CLI.
5. Inspect the SCD2 self-test and final acceptance output. Resolve failures before proceeding.

Do **not** run `02_oltp_schema.sql` over an already populated OLTP schema.

### Path B — brand-new development database

1. Create the required schemas and run `sql/01_stg_schema.sql`.
2. Run `sql/02_oltp_schema.sql` to create the normalized OLTP tables.
3. Run the provided synthesis/preprocessing pipeline with the approved base dataset; load the resulting data into staging and normalize it into OLTP.
4. Verify that the generated data exceeds 100,000 records where required, that foreign keys reconcile, and that employee history events exist.
5. Run `sql/03_olap_install.sql`.
6. Inspect the self-test and acceptance output.

The SQL scripts do not themselves generate the 100K dataset. The supplied pipeline and approved source data are required.

### Destructive rebuild warning

`sql/03_olap_destructive_rebuild.sql` drops and recreates **only `dw`**. Use it only after a backup and only when the current warehouse layout is incompatible. Never use it for routine refreshes or casually against production.

## 5. Run local checks

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
```

These are local syntax/static contract checks. They do not prove live MySQL/Aiven behaviour. Complete [`TEST_CASES.md`](TEST_CASES.md) for database and UI verification.

## 6. Launch Streamlit

```bash
streamlit run app.py
```

Open `http://localhost:8501`. Use the sidebar:
- Employees — onboarding and tracked employment changes.
- Projects — project and assignment management.
- Reviews — performance review entry.
- Analytics Dashboard — OLAP-backed metrics and charts.
- Warehouse Sync — ETL execution and warehouse checks.

## 7. Smoke-test the workflow

1. Open the app and verify database-backed pages load.
2. Create a uniquely identified test employee.
3. Change that employee's department with an effective date later than the current SCD2 `start_date`.
4. Confirm the previous dimension row closes the day before the effective date and the new row becomes current.
5. Create a test project and assignment.
6. Submit a review for the test employee.
7. Run warehouse sync.
8. Verify dashboard data where source records support the metric.
9. Run the read-only final acceptance checks and save the result grids.

Use test-only records and a documented cleanup procedure. Do not delete production source rows just to force row-count equality.

## 8. Troubleshooting

- `ModuleNotFoundError`: activate `.venv`, then rerun `pip install -r requirements.txt`.
- Connection timeout/refused: check host, port, network allowlist and server status.
- Aiven TLS error: verify CA file path and certificate; do not disable certificate verification.
- Access denied: check credentials and schema grants.
- Missing table/procedure: confirm SQL ran on the intended server and follow `sql/README.md` order.
- SCD2 effective-date error: effective date must be after the current version's `start_date`.
- Empty project/assignment insights: populate valid project and assignment rows; dashboards cannot infer absent data.
- Limited historical analytics: inspect `employee_change_log` and review dates. One hire event per employee produces only one SCD2 version.
