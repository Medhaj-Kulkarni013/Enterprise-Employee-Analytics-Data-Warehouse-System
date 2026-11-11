# Enterprise Employee Analytics & Data Warehouse

## Start here

1. Follow the **[macOS Quickstart](docs/QUICKSTART_MACOS.md)** to configure the environment, prepare MySQL and launch Streamlit.
2. Execute the **[Comprehensive Test Plan](docs/TEST_CASES.md)** to verify every phase and feature in the mini-project brief. It includes test IDs, priorities, procedures, expected results and final acceptance gates.
3. Review the [Database Deployment Guide](sql/README.md) and [Database Test Report](docs/DATABASE_TEST_REPORT.md) before running warehouse SQL.

## Run the application

Install dependencies and start the Streamlit frontend from the repository root:

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

Copy `.env.example` to `.env` and fill in the database credentials and local
CA certificate path before starting the application. The `.env` file and
certificate are intentionally ignored by Git.

The application supports
employee onboarding, tracked employment changes, project and assignment
management, performance reviews, SCD Type 2 warehouse loading, and analytics.

### Frontend structure

```text
app.py                         # Landing page and Streamlit entrypoint
ui/common.py                   # Shared database, options, and error helpers
pages/1_Employees.py           # Employee onboarding and SCD2 changes
pages/2_Projects.py            # Projects and assignments
pages/3_Reviews.py             # Performance reviews
pages/4_Analytics_Dashboard.py # OLAP dashboard
pages/5_Warehouse_Sync.py      # ETL sync and warehouse checks
```

## Warehouse integration and safe deployment

The warehouse implementation is based on the project's reference OLAP/SCD2 SQL in `sql/03_olap_install.sql`. The original Streamlit pages, managers, entity models, connection singleton, and OOP documentation are retained. Compatibility procedures keep the existing manager entry points working.

### Database setup

Follow `sql/README.md` in order. Use a dedicated development database first. If the teammate's legacy `sql/backend_etl.sql` has already been run or the existing `dw` layout differs, back up the derived warehouse and use `03_olap_destructive_rebuild.sql` once to normalize it. That script drops and recreates only `dw`; never run it as a routine sync.

### Local configuration (macOS/Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and place your downloaded Aiven CA file at certificates/ca.pem
streamlit run app.py
```

Do not commit `.env`, CA certificates, passwords, or production data. If credentials from an earlier shared archive were real, rotate them.

### Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
```

Database integration tests require a disposable MySQL 8.0.16+ database configured in `.env`; the automated local suite does not claim to have tested a live Aiven instance. See `docs/DATABASE_TEST_REPORT.md` for executed checks and remaining live-database verification.
