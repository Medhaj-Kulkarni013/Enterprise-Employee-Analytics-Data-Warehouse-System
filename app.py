"""Streamlit entrypoint with router-enforced RBAC for the employee analytics system."""

import streamlit as st

from ui.auth import AuthService
from ui.common import initialize_database, show_error


st.set_page_config(
    page_title="Enterprise Employee Analytics",
    page_icon="📊",
    layout="wide",
)


def render_home():
    """Render the role-aware application landing page."""
    try:
        user = AuthService.current_user()
        initialize_database()
        st.title("Enterprise Employee Analytics")
        st.caption(
            f"Welcome, {user['name']} ({user['role']}) — HR operations, SCD Type 2 history, and warehouse analytics"
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
        st.info("Use the authorized modules in the sidebar to navigate the system.")
    except Exception as error:
        show_error(error)


def build_navigation():
    """Mount only the pages authorized for the active session role."""
    user = AuthService.current_user()
    if not user:
        return st.navigation(
            [st.Page(AuthService.render_login_page, title="Sign In", icon="🔐")]
        )

    role = user["role"]
    all_pages = [
        ("Home", st.Page(render_home, title="Home", icon="🏠", default=True)),
        ("Employees", st.Page("pages/1_Employees.py", title="Employees", icon="🧑‍💼")),
        ("Projects", st.Page("pages/2_Projects.py", title="Projects", icon="📁")),
        ("Performance reviews", st.Page("pages/3_Reviews.py", title="Performance reviews", icon="📝")),
        ("Analytics dashboard", st.Page("pages/4_Analytics_Dashboard.py", title="Analytics dashboard", icon="📊")),
        ("Warehouse sync", st.Page("pages/5_Warehouse_Sync.py", title="Warehouse sync", icon="🔁")),
    ]

    authorized_pages = [
        page for title, page in all_pages if AuthService.is_authorized(role, title)
    ]
    AuthService.render_sidebar_session()
    return st.navigation(authorized_pages)


def main():
    if hasattr(st, "navigation"):
        pg = build_navigation()
        pg.run()
    else:
        AuthService.enforce("Home")
        render_home()


if __name__ == "__main__":
    main()