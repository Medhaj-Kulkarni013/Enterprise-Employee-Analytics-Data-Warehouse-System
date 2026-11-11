"""Streamlit entrypoint for the employee analytics system."""

import streamlit as st

from ui.common import initialize_database, show_error


st.set_page_config(
    page_title="Employee Analytics",
    page_icon="📊",
    layout="wide",
)


def main():
    """Render the application landing page."""
    try:
        initialize_database()
        st.title("Enterprise Employee Analytics")
        st.caption(
            "HR operations, SCD Type 2 employment history, and warehouse analytics"
        )

        operations, analytics = st.columns(2)
        with operations:
            st.subheader("Operational workflows")
            st.markdown(
                "- Onboard employees\n"
                "- Update tracked employment attributes\n"
                "- Create projects and assignments\n"
                "- Submit performance reviews"
            )
        with analytics:
            st.subheader("Warehouse insights")
            st.markdown(
                "- Department headcount and attrition\n"
                "- Year-over-year performance\n"
                "- Top performers\n"
                "- SCD Type 2 history and warehouse sync"
            )

        st.divider()
        st.info("Use the pages in the sidebar to manage data and explore analytics.")
    except Exception as error:
        show_error(error)


if __name__ == "__main__":
    main()
