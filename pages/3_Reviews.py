"""Performance review submission page."""

from datetime import date

import streamlit as st

from managers.review_manager import ReviewManager
from models.review import Review
from ui.common import (
    employee_options,
    feedback_message,
    initialize_database,
    project_options,
    render_feedback,
    save_feedback,
    setup_page,
    show_error,
)


setup_page("Performance reviews", "📝", "Submit reviews to the OLTP database and warehouse fact table.")
initialize_database()
render_feedback("review_feedback")

employees = employee_options()
projects = project_options()

if not employees:
    st.info("Create an employee before submitting a review.")
else:
    with st.form("create_review"):
        left, right = st.columns(2)
        employee = left.selectbox("Employee", list(employees))
        reviewer = right.selectbox("Reviewer (optional)", ["None"] + list(employees))
        project = left.selectbox("Project (optional)", ["None"] + list(projects))
        review_date = right.date_input("Review date", value=date.today())
        rating = left.slider("Performance rating", 1, 4, 3)
        job_satisfaction = right.slider("Job satisfaction", 1, 4, 3)
        environment = left.slider("Environment satisfaction", 1, 4, 3)
        relationship = right.slider("Relationship satisfaction", 1, 4, 3)
        work_life = left.slider("Work-life balance", 1, 4, 3)
        involvement = right.slider("Job involvement", 1, 4, 3)
        hike = left.slider("Salary hike percentage", 0, 100, 10)
        training = right.slider("Training sessions", 0, 20, 2)

        submitted = st.form_submit_button("Submit review", type="primary")

    if submitted:
        try:
            reviewer_id = None if reviewer == "None" else employees[reviewer]
            project_id = None if project == "None" else projects[project]
            review_id = ReviewManager().create(
                Review(
                    None, employees[employee], reviewer_id, review_date, rating,
                    job_satisfaction, environment, relationship, work_life,
                    involvement, hike, training, project_id,
                )
            )
            save_feedback("review_feedback", "success", f"Review submitted with ID {review_id}.")
        except Exception as error:
            save_feedback("review_feedback", "error", f"Review submission failed: {feedback_message(error)}")
        st.rerun()
