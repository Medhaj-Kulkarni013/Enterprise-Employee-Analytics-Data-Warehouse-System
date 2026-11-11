"""Project and assignment management page."""

from datetime import date

import streamlit as st

from managers.assignment_manager import AssignmentManager
from managers.project_manager import ProjectManager
from models.assignment import Assignment
from models.project import Project
from ui.common import (
    department_options,
    employee_options,
    feedback_message,
    initialize_database,
    project_options,
    render_feedback,
    refresh_database_options,
    save_feedback,
    setup_page,
    show_error,
)


setup_page("Projects", "📁", "Create projects and manage employee allocations.")
initialize_database()


def render_project_form(departments):
    render_feedback("project_feedback")
    with st.form("create_project"):
        left, right = st.columns(2)
        code = left.text_input("Project code")
        name = right.text_input("Project name")
        department = left.selectbox("Department", list(departments))
        start = right.date_input("Start date", value=date.today())
        has_end = left.checkbox("Has an end date")
        end = right.date_input("End date", value=date.today()) if has_end else None
        status = left.selectbox(
            "Status", ["Planned", "Active", "Completed", "On Hold"]
        )
        submitted = st.form_submit_button("Create project", type="primary")
    if submitted:
        try:
            if end and end < start:
                raise ValueError("Project end date cannot precede start date.")
            project_id = ProjectManager().create(
                Project(None, code, name, departments[department], start, end, status)
            )
            refresh_database_options()
            save_feedback("project_feedback", "success", f"Project created with ID {project_id}.")
        except Exception as error:
            save_feedback("project_feedback", "error", f"Project creation failed: {feedback_message(error)}")
        st.rerun()


def render_assignment_form(employees, projects):
    render_feedback("assignment_feedback")
    if not employees or not projects:
        st.info("Create at least one employee and one project first.")
        return
    with st.form("create_assignment"):
        employee = st.selectbox("Employee", list(employees))
        project = st.selectbox("Project", list(projects))
        role = st.selectbox("Project role", ["Lead", "Contributor", "Support"])
        allocation = st.slider("Allocation percentage", 1, 100, 50)
        start = st.date_input("Assignment start date", value=date.today())
        has_end = st.checkbox("Has an end date")
        end = st.date_input("Assignment end date", value=date.today()) if has_end else None
        submitted = st.form_submit_button("Create assignment", type="primary")
    if submitted:
        try:
            if end and end < start:
                raise ValueError("Assignment end date cannot precede start date.")
            assignment_id = AssignmentManager().create(
                Assignment(None, employees[employee], projects[project], role, allocation, start, end)
            )
            save_feedback("assignment_feedback", "success", f"Assignment created with ID {assignment_id}.")
        except Exception as error:
            save_feedback("assignment_feedback", "error", f"Assignment failed: {feedback_message(error)}")
        st.rerun()


def main():
    departments = department_options()
    employees = employee_options()
    projects = project_options()
    create, assign = st.tabs(["Create project", "Assign employees"])
    with create:
        render_project_form(departments)
    with assign:
        render_assignment_form(employees, projects)


try:
    main()
except Exception as error:
    show_error(error)
