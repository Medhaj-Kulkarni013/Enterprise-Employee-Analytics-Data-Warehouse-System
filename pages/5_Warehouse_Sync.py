"""Warehouse synchronization and data-quality page."""

import pandas as pd
import streamlit as st

from managers.warehouse_manager import WarehouseManager
from ui.common import initialize_database, query_rows, setup_page, show_error


setup_page(
    "Warehouse sync",
    "🔁",
    "Load staging data, synchronize the warehouse, and inspect current counts.",
)
initialize_database()


def main():
    st.subheader("Synchronize warehouse")
    st.write("The ETL is idempotent and can be safely rerun.")
    if st.button("Run warehouse ETL", type="primary"):
        try:
            with st.spinner("Synchronizing OLTP and OLAP data..."):
                WarehouseManager().run_warehouse_etl()
            st.success("Warehouse synchronization completed.")
        except Exception as error:
            show_error(error)

    st.subheader("Warehouse reconciliation")
    count_queries = (
        ("OLTP employees", "SELECT COUNT(*) AS count FROM oltp.employee"),
        ("Employee change events", "SELECT COUNT(*) AS count FROM oltp.employee_change_log"),
        ("Employee dimension versions", "SELECT COUNT(*) AS count FROM dw.Dim_Employee"),
        ("OLTP reviews", "SELECT COUNT(*) AS count FROM oltp.review"),
        ("Review fact rows", "SELECT COUNT(*) AS count FROM dw.Fact_PerformanceReviews"),
    )
    rows = pd.DataFrame([{"table": label, "rows": query_rows(sql)[0]["count"]}
                         for label, sql in count_queries])
    st.dataframe(rows, use_container_width=True, hide_index=True)

    st.subheader("Latest ETL activity")
    logs = pd.DataFrame(query_rows(
        """SELECT run_id, step_name, log_status, rows_affected, message, logged_at
           FROM dw.etl_run_log ORDER BY log_id DESC LIMIT 25"""
    ))
    if logs.empty:
        st.info("No ETL log entries yet.")
    else:
        st.dataframe(logs, use_container_width=True, hide_index=True)


try:
    main()
except Exception as error:
    show_error(error)
