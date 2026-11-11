"""Manager responsible for employee analytics operations."""

import mysql.connector

from core.exceptions import DatabaseError, ValidationError
from managers.base_manager import BaseManager


class AnalyticsManager(BaseManager):
    """Handles analytical queries and reporting."""

    def get_employee_summary(self, department_id=None):
        """Return employee counts, income and tenure statistics."""
        params = ()
        where = ""
        if department_id is not None:
            self._validate_department_id(department_id)
            where = " WHERE e.department_id = %s"
            params = (department_id,)
        query = f"""
            SELECT COUNT(*) AS employee_count,
                   SUM(e.attrition_flag = 0) AS active_count,
                   SUM(e.attrition_flag = 1) AS attrition_count,
                   ROUND(AVG(e.monthly_income), 2) AS average_monthly_income,
                   ROUND(AVG(TIMESTAMPDIFF(YEAR, e.hire_date, CURDATE())), 2)
                       AS average_tenure_years
            FROM dw.Dim_Employee e
            WHERE e.is_current = 1{where.replace(" WHERE", " AND") if where else ""}
        """
        return self._fetch_one(query, params)

    def get_department_analytics(self):
        """Return headcount, attrition and income statistics by department."""
        query = """
            SELECT d.department_id, d.department_name,
                   COUNT(e.employee_id) AS employee_count,
                   SUM(e.attrition_flag = 0) AS active_count,
                   SUM(e.attrition_flag = 1) AS attrition_count,
                   ROUND(AVG(e.monthly_income), 2) AS average_monthly_income
            FROM dw.Dim_Department d
            LEFT JOIN dw.Dim_Employee e
              ON e.department_id = d.department_id AND e.is_current = 1
            GROUP BY d.department_id, d.department_name
            ORDER BY d.department_name
        """
        return self._fetch_all(query)

    def get_performance_analysis(self):
        """Return review and satisfaction statistics grouped by department."""
        query = """
            SELECT d.department_id, d.department_name,
                   COUNT(r.review_id) AS review_count,
                   ROUND(AVG(r.performance_rating), 2) AS average_performance_rating,
                   ROUND(AVG(
                       (r.job_satisfaction + r.environment_satisfaction +
                        r.relationship_satisfaction + r.work_life_balance) / 4
                   ), 2) AS average_satisfaction,
                   ROUND(AVG(r.percent_salary_hike), 2) AS average_salary_hike
            FROM dw.Dim_Department d
            LEFT JOIN dw.Fact_PerformanceReviews r
              ON r.department_key = d.department_key
            GROUP BY d.department_id, d.department_name
            ORDER BY d.department_name
        """
        return self._fetch_all(query)

    def get_top_performers(self, department_id=None):
        """Return top performers from the reference DENSE_RANK analytics view."""
        params = ()
        where = ""
        if department_id is not None:
            self._validate_department_id(department_id)
            where = "WHERE department_name = (SELECT department_name FROM dw.Dim_Department WHERE department_id = %s)"
            params = (department_id,)
        query = f"""
            SELECT year_number, department_name, employee_id, employee_code,
                   full_name, job_role_name, job_level, performance_rating,
                   percent_salary_hike, performance_score, rank_in_dept
            FROM dw.vw_top_performers_by_dept
            {where}
            ORDER BY year_number DESC, department_name, rank_in_dept, employee_id
        """
        return self._fetch_all(query, params)

    def get_year_over_year_performance(self):
        """Return the reference view's department-level YoY metrics."""
        return self._fetch_all(
            """SELECT year_number, department_name, avg_rating, avg_salary_hike,
                      reviews, prev_year_avg_rating, yoy_change
               FROM dw.vw_yoy_performance
               ORDER BY year_number, department_name"""
        )

    def get_attrition_analysis(self):
        """Return risk bands from the reference attrition-risk view."""
        return self._fetch_all(
            """SELECT department_name, job_level, overtime, business_travel,
                      headcount, leavers, attrition_rate_pct, risk_band, risk_rank
               FROM dw.vw_attrition_risk
               ORDER BY risk_rank, department_name, job_level"""
        )

    def get_project_bottlenecks(self):
        """Return project allocation pressure and review coverage."""
        query = """
            WITH assignment_totals AS (
                SELECT project_id, COUNT(DISTINCT employee_id) AS assigned_employees,
                       SUM(allocation_pct) AS allocated_percent
                FROM oltp.assignment
                GROUP BY project_id
            ),
            review_totals AS (
                SELECT project_key, COUNT(*) AS review_count
                FROM dw.Fact_PerformanceReviews
                GROUP BY project_key
            )
            SELECT dp.project_id, dp.project_name,
                   COALESCE(a.assigned_employees, 0) AS assigned_employees,
                   COALESCE(a.allocated_percent, 0) AS allocated_percent,
                   COALESCE(r.review_count, 0) AS review_count
            FROM dw.Dim_Project dp
            LEFT JOIN assignment_totals a ON a.project_id = dp.project_id
            LEFT JOIN review_totals r ON r.project_key = dp.project_key
            WHERE dp.project_id <> 0
            GROUP BY dp.project_id, dp.project_name
            ORDER BY allocated_percent DESC, assigned_employees DESC
        """
        return self._fetch_all(query)

    def _fetch_one(self, query, params=()):
        connection = cursor = None
        try:
            connection, cursor = self.get_connection()
            cursor.execute(query, params)
            return cursor.fetchone()
        except mysql.connector.Error as error:
            raise DatabaseError("Analytics query failed.", error) from error
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def _fetch_all(self, query, params=()):
        connection = cursor = None
        try:
            connection, cursor = self.get_connection()
            cursor.execute(query, params)
            return cursor.fetchall()
        except mysql.connector.Error as error:
            raise DatabaseError("Analytics query failed.", error) from error
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    @staticmethod
    def _validate_department_id(department_id):
        if (
            not isinstance(department_id, int)
            or isinstance(department_id, bool)
            or department_id <= 0
        ):
            raise ValidationError("Department ID must be a positive integer.")
