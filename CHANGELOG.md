# Changelog

## Consolidated handover

- Preserved the teammate's Streamlit frontend, pages, OOP managers, entity models, shared database connection architecture, synthesis pipeline, docs, and diagrams.
- Replaced the teammate's incomplete batch warehouse ETL with the user's reference star schema, SCD2 procedures, full ETL, ETL logging, analytics views, SCD2 self-test, and final acceptance checks.
- Added compatibility procedures for the existing warehouse sync and top-performer manager entry points.
- Made employee tracked changes transactional across OLTP update, employee change-log insert, and incremental SCD2 update.
- Updated employment-change form defaults from the selected employee's actual current values to prevent accidental overwrites.
- Updated analytics queries to consume the reference YoY, top-performer, and attrition-risk views.
- Added fact refresh logic so corrections to existing OLTP reviews are propagated on ETL reruns.
- Split non-destructive warehouse installation from a clearly marked destructive `dw` rebuild.
- Added static/contract tests and a database test report.
- Removed `.env` and private CA certificate from the handover copy; retained `.env.example`.
