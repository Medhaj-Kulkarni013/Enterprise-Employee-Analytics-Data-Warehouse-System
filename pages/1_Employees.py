"""Employee onboarding and employment-history page."""

from datetime import date

import streamlit as st

from managers.employee_manager import EmployeeManager
from models.employee import Employee
from ui.common import (
    department_options,
    employee_options,
    initialize_database,
    feedback_message,
    render_feedback,
    refresh_database_options,
    role_options,
    query_rows,
    save_feedback,
    setup_page,
    show_error,
)


setup_page(
    "Employees",
    "🧑‍💼",
    "Onboard employees and apply tracked changes to the SCD Type 2 warehouse.",
)
initialize_database()


def render_onboarding(departments, roles):
    """Render the employee onboarding form."""
    render_feedback("employee_onboarding_feedback")
    with st.expander("Onboard employee", expanded=True):
        with st.form("create_employee"):
            first, last = st.columns(2)
            employee_code = first.text_input("Employee code")
            email = last.text_input("Email")
            first_name = first.text_input("First name")
            last_name = last.text_input("Last name")
            gender = first.selectbox("Gender", ["Male", "Female"])
            date_of_birth = last.date_input(
                "Date of birth", value=date(1990, 1, 1)
            )
            hire_date = first.date_input("Hire date", value=date.today())
            department = first.selectbox("Department", list(departments))
            role = last.selectbox("Job role", list(roles))
            level = first.number_input("Job level", 1, 5, 1)
            income = last.number_input(
                "Monthly income", min_value=1.0, value=2500.0
            )

            submitted = st.form_submit_button("Create employee", type="primary")

    if submitted:
        try:
            employee_id = EmployeeManager().create(
                Employee(
                    None,
                    employee_code,
                    first_name,
                    last_name,
                    email,
                    hire_date,
                    departments[department],
                    roles[role],
                    level,
                    income,
                    gender=gender,
                    date_of_birth=date_of_birth,
                    marital_status="Single",
                    education_level=3,
                    education_field="Other",
                    distance_from_home_km=10,
                    num_companies_worked=1,
                    stock_option_level=0,
                    prior_experience_years=2,
                    business_travel="Non-Travel",
                    overtime_flag=0,
                )
            )
            refresh_database_options()
            save_feedback(
                "employee_onboarding_feedback",
                "success",
                f"Employee created with ID {employee_id}.",
            )
        except Exception as error:
            save_feedback(
                "employee_onboarding_feedback",
                "error",
                f"Employee creation failed: {feedback_message(error)}",
            )
        st.rerun()


def render_employment_change(departments, roles, employees):
    """Render tracked employment changes."""
    st.subheader("Tracked employment change")
    if not employees:
        st.info("Create an employee before recording an employment change.")
        return

    feedback = st.session_state.pop("employment_change_feedback", None)
    if feedback:
        feedback_kind, feedback_message = feedback
        if feedback_kind == "success":
            st.success(feedback_message)
        else:
            st.error(feedback_message)

    selected = st.selectbox("Employee", list(employees), key="employment_employee")
    current_rows = query_rows(
        """SELECT department_id, job_role_id, job_level, monthly_income
        FROM oltp.employee WHERE employee_id=%s""",
        (employees[selected],),
    )
    if not current_rows:
        st.warning("The selected employee could not be found.")
        return
    current = current_rows[0]
    department_labels = list(departments)
    role_labels = list(roles)
    current_department = next((i for i, label in enumerate(department_labels)
                               if departments[label] == current["department_id"]), 0)
    current_role = next((i for i, label in enumerate(role_labels)
                         if roles[label] == current["job_role_id"]), 0)
    with st.form("employment_change"):
        department = st.selectbox("New department", department_labels, index=current_department)
        role = st.selectbox("New job role", role_labels, index=current_role)
        level = st.number_input("New job level", 1, 5, int(current["job_level"]))
        income = st.number_input("New monthly income", min_value=1.0, value=float(current["monthly_income"]))
        effective = st.date_input("Effective date", value=date.today())
        change_type = st.selectbox(
            "Change type", ["Transfer", "Promotion", "SalaryHike"]
        )
        submitted = st.form_submit_button(
            "Save employment change", type="primary"
        )

    if submitted:
        try:
            EmployeeManager().update_employment(
                employees[selected],
                department_id=departments[department],
                job_role_id=roles[role],
                job_level=level,
                monthly_income=income,
                effective_date=effective,
                change_type=change_type,
            )
            st.session_state["employment_change_feedback"] = (
                "success",
                "Employment change saved; the SCD2 dimension was updated atomically.",
            )
        except Exception as error:
            message = error.message if hasattr(error, "message") else str(error)
            st.session_state["employment_change_feedback"] = (
                "error",
                f"Employment change failed: {message}",
            )
        st.rerun()




    # Display chronological employment history
    st.divider()
    st.subheader("Employment History")

    try:
        history = EmployeeManager().get_change_history(employees[selected])

        if history:
            history_display = []

            for row in history:
                history_display.append({
                    "Effective Date": row["effective_date"],
                    "Change Type": row["change_type"],
                    "Department": next(
                        (name for name, dept_id in departments.items()
                         if dept_id == row["department_id"]),
                        row["department_id"],
                    ),
                    "Job Role": next(
                        (name for name, role_id in roles.items()
                         if role_id == row["job_role_id"]),
                        row["job_role_id"],
                    ),
                    "Job Level": row["job_level"],
                    "Monthly Income": row["monthly_income"],
                })

            st.dataframe(
                history_display,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No employment history found for this employee.")

    except Exception as error:
        show_error(error)






def main():
    departments = department_options()
    roles = role_options()
    employees = employee_options()
    render_onboarding(departments, roles)
    render_employment_change(departments, roles, employees)


try:
    main()
except Exception as error:
    show_error(error)
