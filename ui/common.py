"""Shared Streamlit configuration, database access, and UI helpers."""

import streamlit as st

from config.database import get_database_config
from core.db_manager import DatabaseConnection
from core.exceptions import AppError


@st.cache_resource
def initialize_database():
    """Initialize the shared connection pool once per Streamlit process."""
    db = DatabaseConnection()
    db.initialize_pool(get_database_config())
    return db


def query_rows(query, params=()):
    """Run a dictionary query through the shared connection pool."""
    connection, cursor = initialize_database().cursor()
    try:
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def setup_page(title, icon, description):
    """Apply consistent page configuration and heading."""
    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    st.title(f"{icon} {title}")
    st.caption(description)


def show_error(error):
    """Render application errors without hiding unexpected failures."""
    if isinstance(error, AppError):
        st.error(error.message)
    else:
        st.error(f"Unexpected error: {error}")


def save_feedback(key, kind, message):
    """Persist a one-time result through the next Streamlit rerun."""
    st.session_state[key] = (kind, message)


def render_feedback(key):
    """Render and consume a persisted success or error message."""
    feedback = st.session_state.pop(key, None)
    if not feedback:
        return
    kind, message = feedback
    if kind == "success":
        st.success(message)
    else:
        st.error(message)


def feedback_message(error):
    """Return a user-facing error message for either app or Python errors."""
    return getattr(error, "message", str(error))


def option_map(rows, key, label):
    """Create readable selectbox labels mapped to database IDs."""
    return {
        f"{row[label]} (ID {row[key]})": row[key]
        for row in rows
    }


def employee_options():
    return option_map(
        query_rows(
            """SELECT employee_id, employee_code
            FROM oltp.employee ORDER BY employee_id"""
        ),
        "employee_id",
        "employee_code",
    )


def project_options():
    return option_map(
        query_rows(
            "SELECT project_id, project_code FROM oltp.project ORDER BY project_id"
        ),
        "project_id",
        "project_code",
    )


def department_options():
    return option_map(
        query_rows(
            """SELECT department_id, department_name
            FROM oltp.department ORDER BY department_name"""
        ),
        "department_id",
        "department_name",
    )


def role_options():
    return option_map(
        query_rows(
            """SELECT job_role_id, job_role_name
            FROM oltp.job_role ORDER BY job_role_name"""
        ),
        "job_role_id",
        "job_role_name",
    )


def refresh_database_options():
    """Clear cached option queries after a write."""
    st.cache_data.clear()
