"""OLAP analytics dashboard."""

import pandas as pd
import plotly.express as px
import streamlit as st

from managers.analytics_manager import AnalyticsManager
from ui.common import initialize_database, setup_page, show_error


setup_page("Analytics dashboard", "📊", "Explore workforce, attrition, and performance metrics.")
initialize_database()


def main():
    manager = AnalyticsManager()
    summary = manager.get_employee_summary()
    columns = st.columns(5)
    for column, (label, value) in zip(
        columns,
        (
            ("Employees", summary["employee_count"]),
            ("Active", summary["active_count"]),
            ("Attrited", summary["attrition_count"]),
            ("Average income", summary["average_monthly_income"]),
            ("Average tenure", summary["average_tenure_years"]),
        ),
    ):
        column.metric(label, value)

    departments = pd.DataFrame(manager.get_department_analytics())
    attrition = pd.DataFrame(manager.get_attrition_analysis())
    performance = pd.DataFrame(manager.get_performance_analysis())
    yoy = pd.DataFrame(manager.get_year_over_year_performance())
    top = pd.DataFrame(manager.get_top_performers())

    left, right = st.columns(2)
    with left:
        st.subheader("Headcount by department")
        st.plotly_chart(
            px.bar(departments, x="department_name", y="employee_count"),
            use_container_width=True,
        )
    with right:
        st.subheader("Attrition rate")
        st.plotly_chart(
            px.bar(attrition, x="department_name", y="attrition_rate_pct", color="risk_band"),
            use_container_width=True,
        )

    st.subheader("Year-over-year performance")
    st.plotly_chart(
        px.line(
            yoy,
            x="year_number",
            y="avg_rating",
            color="department_name",
            markers=True,
        ),
        use_container_width=True,
    )
    st.subheader("Department performance")
    st.dataframe(performance, use_container_width=True, hide_index=True)
    st.subheader("Attrition risk segments")
    st.dataframe(attrition, use_container_width=True, hide_index=True)
    st.subheader("Top performers")
    st.dataframe(top, use_container_width=True, hide_index=True)


try:
    main()
except Exception as error:
    show_error(error)
