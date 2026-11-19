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
    bottlenecks = pd.DataFrame(manager.get_project_bottlenecks())

    left, right = st.columns(2)
    with left:
        st.subheader("Headcount by department")
        st.plotly_chart(
            px.bar(
                departments,
                x="department_name",
                y="employee_count",
                color="department_name",
                text_auto=True,
            ),
            use_container_width=True,
        )
    with right:
        st.subheader("Top attrition risk segments")
        if not attrition.empty:
            top_risk = attrition.head(10).copy()
            top_risk["segment"] = (
                top_risk["department_name"]
                + " | L"
                + top_risk["job_level"].astype(str)
                + " | "
                + top_risk["overtime"]
            )
            st.plotly_chart(
                px.bar(
                    top_risk,
                    x="attrition_rate_pct",
                    y="segment",
                    color="risk_band",
                    orientation="h",
                    hover_data=["business_travel", "headcount", "leavers", "risk_rank"],
                    color_discrete_map={"High": "#dc2626", "Medium": "#f59e0b", "Low": "#16a34a"},
                ),
                use_container_width=True,
            )

    st.subheader("Year-over-year performance (2021–2025)")
    if not yoy.empty:
        yoy_recent = yoy[yoy["year_number"].between(2021, 2025)].copy()
        st.plotly_chart(
            px.line(
                yoy_recent,
                x="year_number",
                y="avg_rating",
                color="department_name",
                markers=True,
                hover_data=["prev_year_avg_rating", "yoy_change", "avg_salary_hike", "reviews"],
            ),
            use_container_width=True,
        )

    st.subheader("Top performers by department (DENSE_RANK)")
    selected_year = st.selectbox("Review year", [2025, 2024, 2023, 2022, 2021], index=0)
    top = pd.DataFrame(manager.get_top_performers(year_number=selected_year, top_n=5))
    st.dataframe(top, use_container_width=True, hide_index=True)

    st.subheader("Department performance summary")
    st.dataframe(performance, use_container_width=True, hide_index=True)

    if not bottlenecks.empty:
        st.subheader("Project allocation & bottleneck analysis")
        st.plotly_chart(
            px.bar(
                bottlenecks,
                x="project_name",
                y="assigned_employees",
                hover_data=["allocated_percent", "review_count"],
            ),
            use_container_width=True,
        )

    st.subheader("All attrition risk segments")
    st.dataframe(attrition, use_container_width=True, hide_index=True)


try:
    main()
except Exception as error:
    show_error(error)